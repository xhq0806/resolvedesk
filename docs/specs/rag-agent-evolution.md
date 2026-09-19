# RAG 与 Agent 演进方案

> 状态：规划中
>
> 记录日期：2026-09-19
>
> 目的：在不破坏 Workspace 隔离、人工接管和现有 SSE 协议的前提下，逐步提升知识检索质量、回答可验证性和 Agent 协同能力。

## 1. 当前基线

当前 Customer 在线咨询链路为：

```text
用户原始问题
  -> Embedding
  -> 当前 Workspace 的 READY 文档 pgvector 余弦检索（top-8）
  -> 按文档去重，最多 5 个来源
  -> 来源正文写入 system prompt
  -> Chat Provider SSE 输出
```

当前能力边界：

- 仅使用单路 Dense Retrieval；没有关键词/BM25 检索、结果融合或 Cross-Encoder 重排。
- 用户问题直接用于 Embedding；没有条件式 query rewrite、指代消解或多问题拆分。
- `AiToolPermission` 和 `ToolExecutor` 已实现工具白名单、Workspace 重验、工单绑定和幂等边界，但 Customer 对话主链路尚未形成模型选择工具并执行的循环。
- 无系统化评测集、线上检索轨迹或用户反馈闭环，无法量化改进是否有效。

关键代码：

| 文件 | 当前职责 | 演进方向 |
| --- | --- | --- |
| `backend/app/services/knowledge_retrieval.py` | Query Embedding、向量召回与来源裁剪 | 拆分为检索编排入口，接入 query 分析、混合召回、重排和上下文构建 |
| `backend/app/repositories/knowledge_repository.py` | Workspace 隔离的 pgvector 查询 | 保留 Dense 查询，新增词法检索端口和批量文档水合能力 |
| `backend/app/services/agent_service.py` | Customer RAG、SSE、转人工 | 接入证据包、置信度门控和受控 Agent Runner |
| `backend/app/services/tool_executor.py` | 工单工具白名单与服务端重验 | 作为 Agent Runner 的唯一工具执行出口 |
| `backend/app/models/knowledge.py` | 文档、chunk、摄取任务 | 增加检索元数据、版本和评测/追踪关联 |

## 2. 目标与非目标

### 目标

- 让关键词精确匹配、语义相似匹配和多轮追问都能得到可解释的证据。
- 让最终回答只引用经过重排、阈值筛选和上下文预算控制的片段。
- 让低置信度回答稳定地转为澄清问题或转人工，而不是编造答案。
- 让 Agent 可在人工可控的范围内辅助工单处理，所有权限和写操作仍由服务端重新校验。
- 用离线评测和线上反馈驱动版本迭代，而不是只凭主观体验调参。

### 非目标

- 不允许 Customer Agent 直接执行工单写操作、成员管理、Provider 配置或删除操作。
- 不放宽 `workspace_id`、文档状态、角色和工具权限的服务端过滤。
- 不将完整 Prompt、敏感原文或 API Key 写入检索追踪日志。
- 不在首版引入无限工具循环、自治工单关闭或跨 Workspace 知识共享。

## 3. 目标检索链路

```text
用户问题 + 可见会话历史
  -> QueryAnalyzer（意图、语言、是否需要改写）
  -> 原 query + 最多两个受控变体
  -> DenseRetriever（pgvector） + LexicalRetriever（中文 BM25）
  -> RankFusion（RRF）
  -> RerankerProvider（Cross-Encoder）
  -> ContextBuilder（邻近 chunk、去重、token 预算、引用编号）
  -> EvidenceGate（相关性、覆盖度、注入风险）
  -> 回答 / 澄清 / 转人工 / Agent 工具计划
```

每个候选在整个链路中携带 `chunk_id`、`document_id`、`workspace_id`、召回通道、原始排名、融合分数、重排分数和引用编号。文档去重应在重排之后执行；同一文档可保留至多两个互补片段作为证据。

## 4. 分阶段实施

### 阶段 0：评测、追踪与功能开关

先建立基线，再调整召回策略。

- 建立 200 至 300 条脱敏客服评测样本，标注问题、期望证据 chunk、答案类型、是否应澄清或转人工。
- 新增 `rag_eval_case`、`rag_retrieval_trace`、`rag_feedback` 数据模型；原始问题仅保存脱敏摘要或哈希，正文设置短保留期。
- 记录 query 版本、候选来源、各阶段排序、阈值结果、耗时、成本、最终引用和 run/request ID。
- 新增 Workspace 级功能开关：`rag_trace_enabled`、`hybrid_retrieval_enabled`、`reranker_enabled`、`query_rewrite_enabled`、`agent_runner_enabled`。
- 建立回归测试夹具：跨 Workspace、失效文档、空召回、Prompt Injection 文档、重排服务故障和转人工。

验收：可以对每个评测问题复现最终引用和排名路径；线上关闭全部新开关时，行为与当前实现一致。

### 阶段 1：混合检索与融合

- 抽象 `DenseRetriever`、`LexicalRetriever` 和 `RankFusion` 协议；现有 pgvector 查询继续作为 Dense 实现。
- 词法检索推荐采用 OpenSearch + IK 分词的 BM25 索引，索引字段至少包含 `workspace_id`、`document_id`、`chunk_id`、`status`、`content` 和文档版本。
- 若部署阶段暂不能新增 OpenSearch，先保持 `LexicalRetriever` 接口，使用 PostgreSQL `pg_trgm` 作为过渡实现；不要把 PostgreSQL 原生 FTS 作为中文客服检索的长期方案。
- Dense 与词法检索各召回 top-40 候选；过滤条件在两个通道中一致。
- 使用 RRF 融合，初始参数为 `k=60`，Dense/词法权重为 `0.55/0.45`，后续由评测集调参。
- 为文档摄取增加词法索引投递、版本刷新和删除补偿任务，保证向量索引与关键词索引最终一致。

验收：离线 `Recall@10` 相比阶段 0 基线提升；候选集不出现跨 Workspace、删除或非 READY 文档；词法服务异常时可降级为 Dense 检索并记录原因。

### 阶段 2：Cross-Encoder 重排与证据门控

- 新增 `RerankerProvider` 协议，初始接入多语言 Cross-Encoder，例如 `bge-reranker-v2-m3`，以内部推理服务或受控 API 部署；不使用生成式模型模拟重排。
- RRF 的前 30 个候选提交重排，保留前 6 个，再按 token 预算形成 4 至 6 个上下文块。
- `ContextBuilder` 应支持相邻 chunk 扩展、重复内容消除、标题/定位保留和来源编号；上下文中的文档内容必须标为不可信资料。
- `EvidenceGate` 根据最优重排分数、前后分差、证据覆盖度和风险意图决定回答、追问或转人工。
- Reranker 超时或失败时降级为 RRF，Embedding 服务失败时返回明确 Provider 不可用状态，不能伪装成“无知识”。

验收：引用正确率达到 95% 以上；有依据回答的忠实度达到 90% 以上；检索加重排 p95 目标不超过 1.5 秒。

### 阶段 3：条件式 Query Rewrite

- 仅对短问题、代词指代、多轮追问、多实体歧义和多子问题启用改写；普通明确问题只使用原 query。
- 永远保留原 query，并将其与改写 query 并行检索；不得只检索 LLM 改写结果。
- 改写模型输出结构化 JSON：`intent`、`entities`、`time_range`、`retrieval_terms`、`standalone_query`、`sub_questions`。
- 最多生成两个变体：独立问题改写和子问题拆分。实体、订单号、产品名等字段必须经过格式和会话上下文校验，禁止虚构新实体。
- 每个变体最多返回 top-40 候选，再进入统一融合和重排；记录改写版本与命中贡献。

验收：多轮追问和复合问题的 `Recall@10` 提升，不显著降低明确问题的精确率；改写异常时只检索原 query。

### 阶段 4：受控 Agent Runner 与工单 Copilot

将 Customer Agent 与 Agent Copilot 分离：

| 类型 | 允许行为 | 禁止行为 |
| --- | --- | --- |
| Customer Agent | 知识问答、澄清、建议转人工 | 直接执行任何工单写操作 |
| Agent Copilot | 读取当前工单、检索知识、生成草稿、建议分类/状态 | 未确认即发送公开回复、修改状态、跨工单或跨 Workspace 操作 |

- 新增有限状态 `AgentRunner`：`理解意图 -> 检索 -> 计划 -> 工具执行 -> 结果验证 -> 最终回复`。
- 模型计划采用 JSON Schema；每轮最多 3 次工具调用，限制总时长、总 token 和重复调用次数。
- 所有工具仍通过 `ToolExecutor` 执行，并带 `request_id`/幂等键、当前 ticket 绑定、Workspace 复验和审计。
- `send_public_reply`、`update_ticket_status` 和 `update_ticket_attributes` 默认进入人工确认队列；读取类工具可自动执行。
- 文档、用户消息和工具返回均是不可信输入；系统 Prompt 与策略层明确禁止其中的指令改变权限、工具或输出策略。
- 新增 `agent_run_trace` 与 `agent_pending_action`，保存脱敏计划、执行结果、确认人和拒绝原因。

验收：工具越权、跨租户、重复提交、模型伪造参数、Prompt Injection 和工具超时全部有自动化回归；Agent 失败时可恢复为人工工单处理流程。

## 5. 数据、接口与前端契约

### 后端数据

- `KnowledgeChunk`：补充文档版本、可检索状态和词法索引同步状态；不修改既有 embedding 维度契约。
- `RagRetrievalTrace`：关联 Workspace、Conversation、Run 与请求；保存脱敏 query、各阶段候选和时延。
- `RagFeedback`：记录赞/踩、原因、人工纠正的来源或答案标签。
- `RagEvaluationCase`：保存离线金标与版本化评测结果。
- `AgentPendingAction`：保存需人工确认的工单变更建议，确认后才调用写工具。

### API 与 SSE

- 保持当前 Customer SSE 事件兼容；可附加 `retrieval.completed`、`agent.plan_ready`、`action.confirmation_required` 等新事件。
- 管理端新增检索追踪、评测报告、反馈聚合和 Workspace 级检索策略读取接口；敏感 trace 仅 Admin/Owner 可访问。
- 前端来源卡片展示引用编号、文档名、定位和简短预览；不展示完整 Prompt、内部策略或其他候选文档。
- Agent Copilot 的写操作必须展示变更前后差异、证据与确认/拒绝入口。

## 6. 指标与发布策略

初始质量目标：

| 指标 | 目标 |
| --- | --- |
| `Recall@10` | 不低于 85%，并优于阶段 0 基线 |
| 引用正确率 | 不低于 95% |
| 有依据回答忠实度 | 不低于 90% |
| 检索与重排 p95 | 不高于 1.5 秒 |
| 首 token p95 | 不高于 3.5 秒 |
| 跨 Workspace 泄漏 | 0 |

发布顺序：离线评测 -> 影子流量记录 -> 单 Workspace 灰度 -> 反馈复盘 -> 扩大范围。所有新能力必须由 Workspace 功能开关控制，并支持一键降级到现有 Dense Retrieval 链路。

## 7. 实施任务清单

- [ ] 建立评测样本、评测脚本和 RAG trace 数据模型。
- [ ] 引入检索策略配置与 Workspace 功能开关。
- [ ] 抽象 Dense、Lexical、Fusion、Reranker 与 ContextBuilder 接口。
- [ ] 实现 OpenSearch/IK BM25 索引及摄取同步、删除补偿与故障降级。
- [ ] 实现 RRF 融合、Cross-Encoder 重排、证据门控和引用校验。
- [ ] 实现条件式 query rewrite 与结构化输出校验。
- [ ] 实现 Agent Runner、确认队列和工具调用审计。
- [ ] 补充单元、API、迁移、并发和 Playwright 端到端测试。
- [ ] 完成影子流量、灰度发布和指标复盘。

## 8. 决策记录

1. 评测优先于模型与检索调参；没有可重复的金标和追踪，不上线质量复杂度。
2. 采用 Dense + 中文 BM25 + RRF + Cross-Encoder 的分层检索，而不是直接用更大的生成模型替代检索。
3. Query Rewrite 是受控的候选扩展，不替代原 query。
4. Customer Agent 保持只读和转人工能力；工单写操作只在 Agent Copilot 中、经人工确认后执行。
5. 所有优化沿用现有 Workspace 隔离、Provider 适配器、SSE Run、审计和 `ToolExecutor` 边界，避免在路由层分散实现权限策略。
