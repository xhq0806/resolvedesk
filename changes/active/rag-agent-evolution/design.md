# RAG 检索追踪基础设计

> 来源：`spec.md`
>
> 生成时间：2026-09-19
>
> 阶段：design

## Why

### 背景与现状

`KnowledgeRetrievalService` 使用 `KnowledgeRepository.search_ready_chunks()` 对当前 Workspace 的 READY 文档做 pgvector 余弦检索，再以 `trim_sources()` 去重。`AgentService.stream_customer_message()` 在创建 SSE run 前执行检索；管理端 `/knowledge/search` 也复用同一服务。当前代码没有策略实体或检索轨迹。

系统已具备 WorkspaceContext、管理者权限、请求 ID、Conversation/Run、SQLModel/Alembic 与统一的 SSE 运行边界。本期应复用这些边界，不能将 trace 写入路由层或让追踪失败影响用户回答。

### 设计目标 / 非目标

| 类型 | 说明 |
|---|---|
| ✅ 目标 | 为每个 Workspace 保存 trace 开关与策略版本，并提供管理端读取/更新接口。 |
| ✅ 目标 | 在现有检索服务内记录脱敏、可关联、可分页的检索 trace。 |
| ✅ 目标 | 为后续 HybridRetriever、Reranker、Query Rewrite 和 Agent Runner 提供策略版本与候选审计边界。 |
| ❌ 非目标 | 本期不改变召回、排序、Prompt 或 SSE 事件。 |
| ❌ 非目标 | 本期不接入 OpenSearch、Cross-Encoder、LLM rewrite、用户反馈 UI 或自动工具循环。 |

## What

### 技术方案

#### 架构决策

| 模块 | 职责 | 依赖 |
|---|---|---|
| `RagRetrievalPolicy` | Workspace 级 trace 开关、策略版本 | Workspace |
| `RagRetrievalTrace` | 脱敏检索审计记录 | Workspace、Conversation |
| `KnowledgeRepository` | 策略读取/保存、trace 写入/分页查询 | SQLModel Session |
| `KnowledgeRetrievalService` | 在 Dense Retrieval 成功后按策略尽力写入 trace | Repository、EmbeddingProvider、Settings |
| `knowledge.py` route | 管理端策略/trace HTTP 契约与 Workspace 管理权限 | Service、Schema |

```text
Customer 或管理端搜索
  -> KnowledgeRetrievalService.search(..., trace_context)
  -> Dense Retrieval + 现有来源裁剪
  -> 查询 Workspace RagRetrievalPolicy
  -> 开启时构造 HMAC query 指纹和无正文候选快照
  -> KnowledgeRepository 记录 RagRetrievalTrace
  -> 返回既有 RetrievedChunk 列表
```

追踪写入采用 best-effort：只捕获追踪持久化异常，记录不含正文的 warning，不吞掉检索/Embedding 异常。策略读取、候选来源和 trace 写入都必须携带 `workspace_id`。

#### 数据模型变更

| 操作 | 表/实体 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|---|
| 新增 | `rag_retrieval_policy` | `id, workspace_id, trace_enabled, strategy_version, created_at, updated_at` | UUID/UUID/bool/varchar/datetime | workspace 唯一；默认关闭 | Workspace 级策略 |
| 新增 | `rag_retrieval_trace` | `id, workspace_id, conversation_id, request_id, query_fingerprint, query_length, strategy_version, result_count, elapsed_ms, candidates, created_at` | UUID/UUID/UUID?/varchar/varchar/int/varchar/int/int/json/datetime | workspace/created_at、conversation 索引 | 不含 query 或正文的追踪 |

`candidates` 是无正文 JSON 数组，每项仅包含 `chunk_id`、`document_id`、`rank`、`distance`、`locator`。`query_fingerprint` 使用 `HMAC-SHA256(SECRET_KEY, normalized_query)`，不能使用无密钥的普通 SHA-256。

#### 接口定义

| 接口 | 方法 | 路径/签名 | 入参 | 出参 | 说明 |
|---|---|---|---|---|---|
| 获取策略 | GET | `/workspaces/{workspace_id}/knowledge/retrieval-policy` | Workspace header/path | `RagRetrievalPolicyPublic` | 管理者获取已保存或默认策略 |
| 更新策略 | PATCH | `/workspaces/{workspace_id}/knowledge/retrieval-policy` | `RagRetrievalPolicyPatch` | `RagRetrievalPolicyPublic` | 管理者启停 trace |
| 查询追踪 | GET | `/workspaces/{workspace_id}/knowledge/retrieval-traces?limit&before` | limit 1..100，时间游标 | `list[RagRetrievalTracePublic]` | 管理者按时间倒序查询 |
| 检索 | `KnowledgeRetrievalService.search` | `search(context, query, *, limit, trace_context)` | `RetrievalTraceContext | None` | `list[RetrievedChunk]` | 维持当前调用兼容 |

`RagRetrievalPolicyPatch` 仅接受 `trace_enabled` 和 `strategy_version`，并设置 `extra="forbid"`。`before` 为 timezone-aware UTC 时间游标。路线层负责 manager 校验，service/repository 不依赖 HTTP 对象。

#### 错误处理策略

| 错误类型 | 处理方式 | HTTP 状态码/异常类 |
|---|---|---|
| 非管理者读取/更新 | 复用 WorkspacePolicy 拒绝 | 403 `ForbiddenError` |
| 路径 Workspace 与上下文不一致 | 复用统一资源隐藏 | 404 `NotFoundError` |
| 空 query/Embedding 异常 | 保持既有检索错误 | 409 `ConflictError` |
| trace 写入异常 | 安全 warning 后继续主检索 | 不改变客户响应 |
| 非法 patch/分页参数 | Pydantic 校验 | 422 |

### 关键决策与理由

| 决策 | 可选方案 | 选择 | 理由 |
|---|---|---|---|
| 策略存储 | 全局配置 / Workspace 独立策略 | Workspace 独立策略 | 与 Provider、知识库和会话的租户边界一致，支持安全灰度。 |
| query 标识 | 保存明文 / SHA-256 / HMAC-SHA256 | HMAC-SHA256 | 可关联同一查询而不暴露低熵客服问题给离线字典攻击。 |
| trace 写入 | 影响主路径的强事务 / best-effort | best-effort | 可观测性故障不应导致客服回答失败。 |
| trace 候选 | 保存正文 / 保存无正文元数据 | 无正文元数据 | 满足评测定位需要，同时避免扩大 PII 与知识库泄露面。 |
| API 范围 | 本期加前端 / 先提供后端契约 | 后端契约 | 先使灰度与测试可用，避免未定义运营界面阻塞后续检索质量工作。 |

### 风险与权衡

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| trace 表持续增长 | 中 | 中 | 按 Workspace/时间索引，后续设置保留任务；本期只记录开启灰度的 Workspace。 |
| 追踪泄露敏感信息 | 低 | 高 | HMAC query、无正文 candidates、仅管理者访问、禁止日志输出正文。 |
| SSE 前检索尚无 run ID | 高 | 低 | 关联 conversation 与 request ID；后续可在 AgentService 创建 run 后补 run ID。 |
| 迁移或写入故障影响咨询 | 低 | 高 | 策略默认关闭；写入 best-effort；可立即关闭 Workspace 开关。 |

**发布策略**

- **发布方式**：先执行数据库迁移，默认所有 Workspace 关闭 trace；只对测试或指定 Workspace 开启。
- **回滚条件**：数据库错误、RAG p95 增长超过 5%、trace 表写入导致 SSE 失败；关闭开关后停止新增记录。
- **数据迁移**：仅新增表与索引，无历史回填、无破坏性 API 变更；代码和迁移兼容“策略记录不存在”的窗口。

### 变更文件清单

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `backend/app/models/knowledge.py` | 修改 | 增加策略与 trace SQLModel |
| `backend/app/models/__init__.py` | 修改 | 注册新 ORM |
| `backend/app/alembic/versions/*_add_rag_retrieval_traces.py` | 新增 | 新表和索引迁移 |
| `backend/app/repositories/knowledge_repository.py` | 修改 | 策略与 trace 查询/写入 |
| `backend/app/services/knowledge_retrieval.py` | 修改 | trace context、HMAC 和 best-effort 记录 |
| `backend/app/schemas/knowledge.py` | 修改 | 策略/trace API schemas |
| `backend/app/api/routes/knowledge.py` | 修改 | 管理端策略与 trace API |
| `backend/tests/services/test_knowledge_retrieval.py` | 新增 | 检索追踪单元/数据库测试 |
| `backend/tests/api/routes/test_knowledge.py` | 修改 | API 权限与隔离测试 |

## How

### 任务拆分

| 任务名称 | 详细描述 | 关联设计章节 | 计划工作量(人天) |
|---|---|---:|---:|
| 【策略与追踪模型】(后端) 新增持久化模型和迁移 | 1. Workspace 唯一策略<br>2. 无正文 trace 与索引<br>3. 注册 ORM | 数据模型变更 | 1 |
| 【检索追踪】(后端) 在现有检索服务中记录 trace | 1. trace context<br>2. HMAC 指纹<br>3. best-effort 写入 | 架构决策、错误处理 | 1 |
| 【管理契约】(后端) 提供策略和 trace API | 1. Pydantic schema<br>2. manager 权限<br>3. 分页查询 | 接口定义 | 0.5 |
| 【检索回归】(后端) 覆盖追踪、权限和隔离 | 1. 单元测试<br>2. API 测试<br>3. OpenAPI 检查 | Verify | 1 |
| **合计** | | | **3.5** |

任务依赖：

```text
- 【策略与追踪模型】
- 【检索追踪】 <- depends: 【策略与追踪模型】
- 【管理契约】 <- depends: 【策略与追踪模型】
- 【检索回归】 <- depends: 【检索追踪】, 【管理契约】
```

## Verify

设计自检：

- [x] 所有 spec 功能需求都有对应的技术方案。
- [x] 所有技术决策都有理由。
- [x] 接口定义包含入参、出参和异常。
- [x] 数据模型变更明确为新增，未删除既有数据。
- [x] 任务拆分覆盖全部设计内容。
- [x] 任务粒度均在 0.5 至 2 人天内。
- [x] 无实现代码，只有方法签名和结构。
- [x] 已按 Python/FastAPI 约束完成 Risks 与 Rollout。

## Impact

- 涉及模块：知识检索、知识库管理 API、ORM/Alembic、后端测试。
- 数据库变更：是，新增两个 Workspace 隔离表和索引。
- 外部依赖变更：否。
- 后续阶段：通过 `strategy_version`、`trace_context` 与候选快照扩展到混合检索、重排与改写，不在本期实现。
