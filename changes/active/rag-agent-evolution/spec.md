# RAG 检索追踪基础规格

> 来源：用户要求“依次完成 design，coding”及 `docs/specs/rag-agent-evolution.md`
>
> 状态：已确认，直接进入设计与编码
>
> 日期：2026-09-19

## Why

现有 RAG 只有单路向量检索，系统无法回答一次检索采用了什么策略、召回了哪些证据、耗时多少，也没有 Workspace 级灰度开关。混合检索、Cross-Encoder 重排、条件式 Query Rewrite 和受控 Agent Runner 都依赖这套观测与发布基础。

本期实现演进方案的阶段 0。阶段 1 及以后功能在设计中预留边界，但不在本期接入 OpenSearch、reranker 服务、LLM rewrite 或自动工具循环。

## What

### 功能需求

| 编号 | 功能 | 说明 | 优先级 |
|---|---|---|---|
| FR-1 | Workspace 检索策略 | 每个 Workspace 有独立的 RAG 策略配置，当前只允许启停检索 trace；未配置时按安全默认值关闭。 | P0 |
| FR-2 | 脱敏检索追踪 | 开启 trace 后，每次 RAG 搜索记录租户、请求、会话、策略版本、query 指纹、候选元数据、命中数和耗时，不保存 query 或 chunk 正文。 | P0 |
| FR-3 | 管理端策略与追踪 API | 仅 Owner/Admin 能读取/更新本 Workspace 策略，并分页查看本 Workspace trace。 | P0 |
| FR-4 | Customer 链路关联 | Customer SSE 检索 trace 关联当前 conversation 与 request ID；管理端知识库搜索关联 request ID。 | P0 |
| FR-5 | 回归与隔离 | trace 不改变现有来源排序、SSE 事件、回答内容或无依据转人工策略；跨 Workspace 与非管理者均不能读取或更新策略/trace。 | P0 |

### 验收场景

1. Given Workspace A 开启 trace，When Customer 发送咨询，Then 写入一条 Workspace A 的 trace，含 conversation/request ID、HMAC query 指纹、来源 ID/距离和毫秒耗时，但无问题正文或 chunk 正文。
2. Given Workspace A 未开启 trace，When 发生搜索，Then 不写入 trace，且原有 RAG 回答行为不变。
3. Given Owner/Admin，When 查询或更新本 Workspace 策略与 trace，Then 请求成功；Given Customer/Agent 或其他 Workspace，Then 请求被拒绝或返回资源不存在。
4. Given 追踪写入意外失败，When 主检索和 Provider 均成功，Then RAG 主链路继续完成，并记录安全的诊断日志，不泄露正文。
5. Given 升级后尚未创建策略记录，When 执行现有请求，Then 安全默认值关闭 trace，API 可返回默认策略并允许管理者保存。

## Boundaries

- 不修改 `KnowledgeRetrievalService` 的当前 Dense Retrieval 排序与来源裁剪算法。
- 不新增外部检索、模型或队列依赖；OpenSearch、Cross-Encoder、Query Rewrite 和 Agent Runner 仍由后续阶段实现。
- 不保存客户问题正文、知识片段正文、Prompt、API Key 或工具参数。
- 不变更现有 Customer SSE 的事件契约；追踪仅写数据库。
- 不创建前端管理界面；本期以后端 API 和 OpenAPI 契约作为配置入口。

## Verify

- 新增检索策略和 trace 的 repository/service/API 测试。
- 新增 Customer trace 关联、关闭策略、管理权限与跨 Workspace 隔离测试。
- 运行相关 pytest、ruff、mypy 与 OpenAPI 路由检查。
