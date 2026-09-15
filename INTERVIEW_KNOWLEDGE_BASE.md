# ResolveDesk 个人面试知识库

> 用途：将本文档作为其他 AI 的项目上下文，使其能够基于真实代码回答面试官关于项目背景、个人贡献、全栈实现、AI 应用和 RAG 的问题。
>
> 事实范围：本文档根据 `README.md`、`.understand-anything/knowledge-graph.json`、产品规格、验收报告和当前代码整理。项目事实优先于面试表达模板；涉及个人职责的内容应按本人真实参与情况调整。

## 0. 给回答型 AI 的使用说明

回答时遵循以下原则：

1. 先给结论，再解释实现；使用第一人称“我负责/我设计/我实现”。
2. 不把规划能力说成已上线能力。当前已实现的是 Workspace 隔离客服平台、AI 在线咨询、知识库 RAG、SSE、转人工和自动分派。
3. 没有真实线上指标时，不编造 QPS、准确率、成本或客户数量。可使用已验证工程指标：后端 Pytest 170 passed、Playwright 56 passed、OpenAPI/迁移/Docker 检查通过、分析产物覆盖 414 个文件。
4. 被追问 AI 时，完整描述“文档上传 → 解析 → 切块 → Embedding → pgvector 检索 → 来源裁剪 → Prompt → Chat Provider → SSE → 持久化”的链路。
5. 被追问安全时，优先提 WorkspaceContext、`X-Workspace-ID`、成员/角色校验、跨租户统一 404、API Key Fernet 加密、SSRF URL 校验、工具白名单和数据库约束。
6. 被追问不足时，诚实说明当前没有复杂技能组路由、排班心跳、SLA 自动升级、邮件转工单、生产合规认证和跨 Workspace 知识共享。

## 1. 一分钟项目介绍

ResolveDesk 是一个以 Workspace 为隔离边界的 AI 客服支持平台。客户可以在当前页面右下角打开在线咨询，AI Agent 先检索当前 Workspace 的知识库并流式回答；如果客户需要人工服务，系统把 AI 会话幂等转换为工单，并按当前 Workspace 内人工客服的未关闭工单数自动分派。人工客服可以在公共队列或自己的工单上回复、添加内部备注、推进状态；管理员负责成员、工单、知识库、AI Provider、工具权限和审计。

我把它做成了一个完整的全栈闭环：React/TypeScript 前端负责角色化路由、工单和 AI 浮窗；FastAPI 负责认证、Workspace 上下文、业务服务、SSE 和 Provider 适配；SQLModel/Alembic + PostgreSQL/pgvector 负责数据和向量；Docker Compose、Mailpit、Traefik 和 CI 测试负责本地开发与交付。

## 2. 背景、痛点与目标

传统客服系统通常把“FAQ 机器人”和“人工工单”割裂：客户在机器人中重复描述问题，转人工后客服没有上下文；多租户数据隔离容易依赖前端传参；模型供应商切换会侵入业务代码；长回答还会让用户等待整段 HTTP 响应。

ResolveDesk 的目标是：

- 让每个 Workspace 拥有独立的客户、客服、知识库、AI 配置和审计边界。
- 用 RAG 让 AI 优先依据企业自己的文档回答，而不是只依赖模型参数记忆。
- 通过来源摘要让客户和客服知道回答依据，降低幻觉风险。
- 在 AI 无法解决时保留最近会话上下文，幂等创建工单并自动分派。
- 让同一套前后端契约覆盖 Customer、Agent、Admin/Owner 三类角色。

## 3. 用户角色与权限边界

| 角色 | 主要能力 | 明确不能做的事 |
|---|---|---|
| CUSTOMER | 在线咨询；创建/查看/回复自己的工单；请求转人工；设置和头像 | 不能看内部备注、知识库管理、Provider、工具权限或其他客户工单 |
| AGENT | 查看公共队列和分派给自己的工单；接手、公开回复、内部备注、状态/优先级/分类更新 | 不能管理用户、知识库、Provider、工具权限或其他 Agent 的工单 |
| ADMIN | 管理当前 Workspace 成员、全部工单、知识库、AI Provider、工具白名单和审计 | 不能绕过 Workspace 边界；不能删除 Owner 或破坏最后管理员约束 |
| OWNER | 拥有 Admin 全部能力，并承担 Workspace 所有者职责 | 仍受服务端策略、审计和数据约束控制 |
| AI Agent | Workspace 内独立执行主体，使用配置的 Chat/Embedding Provider 和获授权工具 | 不能删除工单、管理成员、修改 Provider 或绕过工具白名单 |

所有资源都带 `workspace_id`。请求通过 JWT 认证，再从 `X-Workspace-ID` 解析 Workspace，查询成员关系并构造不可变 `WorkspaceContext`。路径中的 Workspace ID 必须和请求上下文一致；不一致时统一返回资源不存在，避免跨租户探测。

## 4. 系统架构与技术选型

```text
浏览器 React/Vite
  ├─ TanStack Router：页面与角色路由守卫
  ├─ TanStack Query：服务端状态、缓存和刷新
  ├─ OpenAPI 生成客户端 + aiApi：类型安全 API 调用
  └─ CustomerSupportWidget：SSE 消费、来源展示、转人工
          │ JWT + X-Workspace-ID
          ▼
FastAPI API 层
  ├─ deps.py：JWT、当前用户、WorkspaceContext
  ├─ routes：login/users/workspaces/tickets/knowledge/ai/attachments
  └─ services：工单状态机、权限、AI Agent、RAG、Provider、分派、审计
          │ SQLModel / Repository
          ▼
PostgreSQL 17 + pgvector
  ├─ Workspace、User、Ticket、TicketMessage、Audit
  ├─ AiAgent、AiProviderConfig、AiConversation、AiMessage、AiRun、AiRunEvent
  └─ KnowledgeDocument、KnowledgeChunk、DocumentIngestionJob

异步摄取 Worker ──解析 PDF/DOCX/MD/TXT──> Embedding Provider ──> Vector(1024)
Chat Provider ──> SSE run.started/source.found/message.delta/completed/failed
Docker Compose：db、backend、proxy(Traefik)、Mailpit、Adminer、Playwright
```

### 4.1 后端

- FastAPI + Pydantic：REST/OpenAPI、请求校验和稳定错误码。
- SQLModel/SQLAlchemy：ORM 模型、事务和 PostgreSQL 查询。
- Alembic：数据库迁移、枚举和 pgvector 结构演进。
- `app/api/routes` 只做 HTTP 编排；核心规则放在 `app/services`；仓储放在 `app/repositories`，降低路由和数据库耦合。
- JWT Bearer + Argon2/Bcrypt 密码哈希；Sentry 可选接入错误监控。

### 4.2 前端

- React 19 + TypeScript + Vite。
- TanStack Router 组织受保护路由；`routeGuards.ts` 根据角色和 Workspace 决定是否挂载页面。
- TanStack Query 管理 Workspace、用户、工单数据；TanStack Table 展示列表。
- Tailwind CSS + shadcn/ui 统一组件风格。
- OpenAPI 生成 `frontend/src/client`，避免手写第二套接口契约；AI 流式接口在 `frontend/src/lib/aiApi.ts` 用 Fetch reader 解析 SSE。

### 4.3 数据与部署

- PostgreSQL 17 使用 `pgvector/pgvector:pg17` 镜像；知识向量为 1024 维。
- Compose 本地提供数据库、Mailpit、Adminer、Traefik 和 Playwright。
- 生产通过 Docker Compose + Traefik 路由，GitHub Actions 可触发部署。
- 后端镜像负责构建前端，因此生产服务器不需要预装 Bun。

## 5. 核心业务闭环

### 5.1 人工工单

标准状态流转：

```text
OPEN ──接手/分派──> IN_PROGRESS
IN_PROGRESS ──等待客户──> WAITING_FOR_CUSTOMER
IN_PROGRESS ──解决──> RESOLVED
WAITING_FOR_CUSTOMER ──客服继续处理──> IN_PROGRESS
WAITING_FOR_CUSTOMER/RESOLVED ──客户公开回复──> IN_PROGRESS
RESOLVED ──Admin 关闭──> CLOSED
```

`OPEN → IN_PROGRESS` 不能被普通状态接口绕过，只能通过接手或分派流程完成。Agent 只有负责人可以主动处理；Customer 不能直接改状态，只能通过公开回复触发等待或已解决工单重开。`CLOSED` 只读。删除为软删除：业务查询隐藏工单和消息，但审计记录保留。

### 5.2 自动分派

`AgentAssignmentPolicy.pick_agent` 只选择：当前 Workspace 的 ACTIVE 成员、全局账号 `is_active=true`、Workspace 角色为 `AGENT` 的用户。使用 SQL 聚合计算每个 Agent 的未关闭工单数，按数量升序，再按用户创建时间和 UUID 稳定排序，取一人。有人可用时工单进入 `IN_PROGRESS`；无人可用时保持 `OPEN` 并进入公共队列。

### 5.3 AI 转人工

1. Customer 首次发消息时复用或创建当前 Workspace 的 ACTIVE 会话。
2. AI 生成期间持久化用户消息和 `AiRun`，完成后才写入完整 Assistant 消息。
3. Customer 点击“转人工”或表达明确意图后，服务端校验会话属于本人和当前 Workspace。
4. 取最近客户问题、AI 回复和转人工原因，生成工单标题/描述。
5. 通过唯一关联和已有 `conversation.ticket_id` 检查保证幂等；重复请求返回同一工单。
6. 尝试自动分派并写入 `AI_HANDOFF_CREATED`、`AUTO_ASSIGNED` 等审计。

## 6. AI 与 RAG 详解

### 6.1 Provider 抽象

业务服务依赖 `ChatProvider` 和 `EmbeddingProvider` Protocol，而不是直接依赖某一家厂商。当前适配：

- OpenAI-compatible Chat：`/chat/completions`，支持普通 completion 和流式 chunk。
- OpenAI-compatible Embedding：`/embeddings`。
- 火山方舟 Chat：Responses 风格适配器。
- 火山方舟 Embedding：`/embeddings/multimodal`。

Workspace 的 Provider 配置包括 Chat/Embedding provider、Base URL、模型、API Key、1024 维度和 enabled 状态。API Key 由服务端用 `SECRET_KEY` 派生 Fernet 密钥加密落库，公开响应只返回 `has_api_key` 和掩码，不回显原文。Base URL 校验阻止 localhost、`.local`、私网、回环、链路本地、保留和组播地址，降低 SSRF 风险。启用前必须同时具备 Chat/Embedding URL、模型、API Key 和 1024 维配置；设置页可以分别执行连通性测试并把超时、鉴权、网络和响应格式错误映射为稳定错误码。

### 6.2 文档摄取流程

后台上传只负责保存文件和创建任务，不在 HTTP 请求中调用模型：

1. Admin/Owner 上传 PDF、DOCX、Markdown 或 TXT。
2. 校验安全文件名、扩展名、MIME 和大小；文件按 `workspace_id/document_id.extension` 存储，并记录 SHA-256。
3. 创建 `KnowledgeDocument(PROCESSING)` 和 `DocumentIngestionJob(PENDING)`。
4. Worker 领取任务时设置 300 秒 lease；任务状态变为 RUNNING。超时任务可恢复为 PENDING，避免 Worker 崩溃后永久卡死。
5. PDF 使用 `pypdf` 按页解析，DOCX 使用 `python-docx` 按段落解析，MD/TXT 按 UTF-8 文本解析，并保留 page/paragraph/document 定位元数据。
6. 清洗行首尾空白后按约 2800 字符切块，重叠 400 字符，减少跨块语义断裂。
7. 批量调用 Embedding Provider，严格校验返回向量数量和 1024 维度。
8. 将文本、`source_meta`、chunk_index 和向量写入 PostgreSQL `knowledge_chunk`；成功后文档变为 READY，失败后变为 FAILED 并记录 error_code，可重试。
9. 删除文档采用软删除，同时删除其可检索 chunk、删除本地原文件，但保留任务历史。

### 6.3 检索与回答流程

```text
客户问题
  -> trim/校验非空
  -> Embedding(query)
  -> knowledge_chunk.embedding cosine_distance
  -> 仅当前 Workspace + READY 文档 + 非空向量
  -> limit 最多 32 的候选
  -> 按文档去重并裁剪最多 5 个来源
  -> 拼接来源名称/正文片段到 system prompt
  -> ChatProvider.stream
  -> source.found + message.delta SSE
  -> 完成后持久化 Assistant 消息和 Run 终态
```

`KnowledgeRepository.search_ready_chunks` 在 SQL 层同时约束 chunk 和 document 的 Workspace，按余弦距离升序。`KnowledgeRetrievalService.trim_sources` 按文档去重，最终最多 5 个来源，避免同一文档占满上下文。Customer 只看到来源名称、定位和最多 500 字符预览，不获得后台文档下载或管理权限。

客户 Prompt 的关键约束是：优先依据提供的知识库来源；不能声称客户可以管理知识库；证据不足时明确说明并建议转人工。当前实现没有独立 Cross-Encoder 重排和复杂 query rewrite，排序依据是 pgvector 余弦距离，后续可在检索层增加 reranker、混合关键词检索和评估集。

### 6.4 SSE 与可靠性

一次运行由 `AiRun` 表示，事件记录在 `AiRunEvent`，事件类型包括：`run.started`、`source.found`、`message.delta`、`message.completed`、`run.completed`、`run.cancelled`、`run.failed`，并预留工具事件。前端通过 Fetch `ReadableStream` 按空行切帧，实时追加 `message.delta`，把 `source.found` 渲染为来源卡片。

可靠性设计：

- `AiRun` 上有 PostgreSQL 部分唯一索引，保证同一会话最多一个 RUNNING；应用层检查只是快速失败，数据库约束是最终防线。
- 客户端每条消息带 UUID `client_message_id`，数据库唯一索引防重复提交。
- 只有完整内容生成成功才写入 CONFIRMED Assistant 消息；取消或异常只结束 Run，不伪造半条完整答案。
- 浏览器断开或请求取消时，路由调用 `cancel_run`，服务端写入 CANCELLED。
- Provider 异常统一映射为稳定失败事件，前端显示可理解提示。

## 7. 关键数据模型

| 模型 | 作用 | 关键约束 |
|---|---|---|
| Workspace / WorkspaceMember | 租户和成员角色 | `(workspace_id,user_id)` 唯一；ACTIVE 成员才能访问 |
| Ticket / TicketMessage / TicketAuditLog | 工单、消息和审计 | 工单软删除；状态和权限由服务层状态机控制 |
| AiAgent | 每个 Workspace 的 AI 执行主体 | Workspace 唯一一个 Agent |
| AiProviderConfig | Chat/Embedding 配置 | Workspace 唯一；密钥只存密文 |
| AiConversation | AI 会话、模式和人工接管状态 | workspace/ticket 索引；转人工关联 ticket |
| AiMessage | 用户、AI、工具、系统消息 | conversation + client_message_id 唯一 |
| AiRun / AiRunEvent | 运行终态和可重放事件 | 同一 conversation 只允许一个 RUNNING |
| KnowledgeDocument | 原文件元数据和摄取状态 | PROCESSING/READY/FAILED/DELETED；SHA-256 |
| KnowledgeChunk | 文本片段和向量 | `Vector(1024)`；document + chunk_index 唯一 |
| DocumentIngestionJob | 异步摄取任务 | PENDING/RUNNING/READY/FAILED/CANCELLED；lease 恢复 |

## 8. 个人贡献的面试表达模板

可以按真实情况组合以下表述：

- 我负责从业务规格落地 Workspace 隔离、角色权限、工单状态机和 AI 客服闭环，而不是只实现一个聊天页面。
- 我把 Provider、RAG、会话运行和工单转人工拆成独立服务，路由只负责协议转换，便于测试和替换模型供应商。
- 我重点处理了长连接场景的工程问题：SSE 增量事件、断流取消、Run 终态、消息幂等和数据库唯一约束。
- 我实现了知识库异步摄取，使用 lease 机制应对 Worker 崩溃，使用文档状态和错误码支持失败重试。
- 我把安全边界放到后端和数据库：每次查询带 Workspace 条件，跨租户统一隐藏资源；API Key 加密；Provider URL 做 SSRF 防护；AI 工具采用白名单。
- 我通过 Pytest、Playwright、OpenAPI、迁移和 Docker 检查验证端到端闭环，而不是只验证单个函数。

建议不要说“我一个人完成了所有代码”，除非事实确实如此；可明确区分架构设计、核心实现、联调、测试和文档贡献。

## 8.1 项目成果与可验证结果

- 形成从 Customer 在线咨询到 AI 回答、转人工、自动分派、Agent 处理、状态关闭的完整业务闭环。
- 完成 Workspace 级数据隔离和角色权限，覆盖越权访问、内部备注裁剪、停用用户和并发接手等安全回归场景。
- AI 能力从“调用模型”扩展为可配置 Provider、异步知识摄取、向量检索、来源展示、流式事件、运行终态和人工兜底。
- 验收报告记录后端 Pytest `170 passed`、Playwright `56 passed`；Ruff、Mypy、Ty、前端生产构建、Biome、OpenAPI 契约、Docker Compose 和数据库迁移检查通过。
- 当前仓库的 `.understand-anything` 分析产物覆盖 414 个文件，便于后续维护和向其他 AI 解释代码关系。

这些是工程验收结果，不等同于线上业务 KPI。若面试官追问用户数、准确率、成本或 QPS，应说明当前没有可靠线上统计，并给出后续埋点方案。

## 9. 面试高概率问题与参考答案

### Q1：请介绍一下这个项目。

**答：** ResolveDesk 是 Workspace 隔离的 AI 客服支持平台。Customer 先通过 AI 在线咨询，服务端用当前 Workspace 的 READY 知识库做 RAG 并通过 SSE 流式返回；需要人工时，AI 会话带上下文幂等转换为工单，按 Agent 未关闭工单数自动分派。Agent 处理队列和自己的工单，Admin/Owner 管理成员、知识库、Provider、工具权限和审计。技术上是 React/TypeScript + FastAPI + SQLModel/PostgreSQL/pgvector + Docker Compose，重点解决了多租户隔离、流式 AI、异步摄取和人机协同。

### Q2：为什么用 Workspace 作为隔离边界？

**答：** 客服企业的知识、工单和模型配置天然属于组织或项目。把 Workspace 作为所有业务表的 `workspace_id`，请求入口统一构造 `WorkspaceContext`，仓储查询强制带租户条件，可以避免依赖前端隐藏按钮。路径 ID 和请求头不一致时返回统一 404，不泄露另一个租户资源是否存在。

### Q3：RAG 的完整链路是什么？

**答：** Admin 上传文档后先校验并创建摄取任务，Worker 解析 PDF/DOCX/MD/TXT，按 2800 字符、400 重叠切块，调用 Embedding 生成 1024 维向量写入 pgvector。用户提问时生成 query embedding，在当前 Workspace 的 READY 文档中按余弦距离召回，跨文档去重并保留最多 5 个来源，把来源正文注入 system prompt，再调用 Chat Provider 流式生成。前端同时收到来源摘要和文本增量，服务端在成功后持久化消息和运行事件。

### Q4：为什么选择 pgvector，而不是单独的向量数据库？

**答：** 当前规模和部署目标更适合复用 PostgreSQL：文档元数据、Workspace 过滤、状态和向量查询在同一事务和权限边界内完成，Docker 运维成本低。通过 `Vector(1024)` 和索引/余弦距离支持检索。规模明显扩大时，可以把检索仓储替换为专用向量库，同时保留 `KnowledgeRetrievalService` 接口和 Workspace 过滤逻辑。

### Q5：为什么文档摄取要异步？

**答：** 解析和 Embedding 可能耗时且容易受外部 Provider 影响，如果放在上传请求中会造成超时和重复提交。当前上传只落盘、写文档元数据和 PENDING job；Worker 通过 300 秒 lease 领取任务，失败标记 FAILED，超时可恢复 PENDING，管理端可重试。这样 HTTP 延迟稳定，任务状态也可观测。

### Q6：如何减少 RAG 幻觉？

**答：** 第一，检索只允许当前 Workspace 的 READY 文档；第二，按文档去重并限制来源数量和预览长度；第三，Prompt 明确要求优先依据来源，证据不足时说明信息不足并转人工；第四，向客户展示来源摘要；第五，记录 Run 和事件便于排查。当前还可以增加 reranker、置信度阈值、离线问答评估集和人工反馈闭环。

### Q7：SSE 为什么适合这个场景？

**答：** AI 输出是服务端到客户端的单向增量流，SSE 比轮询更及时、比 WebSocket 更简单。事件协议区分来源发现、文本增量、完成、取消和失败，前端可以在首 token 到达时就展示内容。必须处理断流、重复运行和终态持久化，所以我用 AiRun、AiRunEvent、取消逻辑和数据库唯一索引保证一致性。

### Q8：并发发送两条消息会怎样？

**答：** 应用层先查 RUNNING，数据库层还有 `conversation_id + status=RUNNING` 的部分唯一索引；第二个请求即使穿过应用检查，也会在提交时触发 IntegrityError 并转换为稳定冲突错误。客户端消息还带 `client_message_id` 唯一键，重试不会插入重复用户消息。

### Q9：为什么不把流式生成中的文本实时写成完整消息？

**答：** 网络断开或 Provider 失败时，实时写入可能留下看似完整但实际截断的回答。当前把增量只作为 SSE 和事件流发送，在收集到非空完整内容并成功结束 Provider 后，才写 CONFIRMED Assistant 消息；取消/失败只记录 Run 终态。

### Q10：AI 转人工如何保证幂等？

**答：** 服务端先读取 conversation。如果已经有 `ticket_id`，直接返回原工单；否则在同一业务流程中创建带会话上下文的工单、写审计、尝试分派，再回写 conversation 关联。重复点击不会创建第二张工单，且转人工时会取消正在运行的 AI Run。

### Q11：自动分派为什么按负载数？

**答：** 当前版本没有排班和在线心跳，所以用可解释的最小负载策略：只统计未关闭负责工单，按数量升序并用创建时间/UUID 稳定打破平局。候选必须是当前 Workspace ACTIVE 成员、全局账号 active 且角色 AGENT。未来接入技能组、SLA 和在线状态时，可以把策略抽象成可替换的 AssignmentPolicy。

### Q12：前后端如何保证接口契约一致？

**答：** FastAPI 生成 OpenAPI，前端通过 `openapi-ts` 生成 TypeScript client；业务查询用 TanStack Query 封装。AI SSE 是非标准 JSON 响应，因此在 `aiApi.ts` 单独实现 Fetch reader 和事件解析，但请求路径、错误结构仍遵循后端契约。

### Q13：如何做权限控制？

**答：** JWT 只解决身份；WorkspaceContext 再解决租户和成员。服务层集中使用 `WorkspacePolicy.require_member/require_manager/require_owner`，TicketPermission 决定查看、公开回复和内部备注，路由层也校验路径 Workspace。前端做角色化导航是体验优化，后端权限才是安全边界。

### Q14：Customer 为什么看不到内部备注和完整知识文档？

**答：** 工单详情构建时按角色裁剪消息；内部备注只有有权限的 Agent/Admin/Owner 可见。知识库 API 需要 manager 角色，Customer 只能从 AI 的 `source.found` 看到名称、定位和有限预览，不返回原文文件和后台管理能力。

### Q15：Provider API Key 如何保护？

**答：** 前端永远不接触密钥原文。后端使用基于 `SECRET_KEY` 派生的 Fernet 对称加密落库，调用 Provider 时服务端解密，公开配置只返回是否存在和掩码。日志和错误响应不包含密钥；Base URL 还阻止明显内网地址，避免把服务变成 SSRF 代理。

### Q16：工具调用如何防止 AI 越权？

**答：** 工具不是模型说调用就调用，而是先从固定 `ALLOWED_TOOLS` 集合校验，再检查 Workspace 的 `AiToolPermission` 是否 enabled。AI Agent 明确不能管理成员、Provider、删除工单等高风险能力。后续新增工具必须同时增加 schema、执行器、权限和审计测试。

### Q17：遇到 Provider 超时怎么处理？

**答：** Provider 层把超时、401/403、HTTP 错误、网络错误和无效响应转换为稳定代码；连接测试返回耗时和可展示消息。流式运行捕获异常，写 RUN_FAILED 和 error_code，前端显示可恢复提示。已有消息历史保留，用户可重试或转人工。

### Q18：数据库迁移如何保证安全？

**答：** 使用 Alembic 管理版本；Workspace 基础迁移会给既有数据回填 Workspace 并建立外键/唯一约束，AI 和知识库迁移创建枚举、索引和 pgvector 字段。发布前执行升级/降级检查，避免只在 ORM 模型里改字段而忘记数据库。

### Q19：你如何测试这个项目？

**答：** 后端有 service、repository、API、Provider、迁移、并发和错误处理测试；前端有 Playwright 的登录、角色导航、工单流转、权限回归和 AI/Workspace 路由测试。验收基线是后端 Pytest 170 passed、Playwright 56 passed，Ruff/Mypy/Ty、前端构建和 Biome、OpenAPI、Compose、迁移均通过。

### Q20：如果流式回答已经显示了一半，用户刷新页面怎么办？

**答：** 当前设计把运行状态和事件持久化，断开会取消 Run，不把半成品标成完整 Assistant 消息。进一步增强可以增加事件重放 API：前端带上 run_id/最后 sequence 恢复，或在完成后从消息表重新拉取终态。关键是把“可展示增量”和“已确认消息”分开。

### Q21：如何评估 RAG 效果？

**答：** 当前代码具备来源和距离记录，但还没有完整离线评估平台。我会建立带标准答案和文档引用的测试集，衡量 Recall@k、MRR、引用准确率、答案忠实度、无答案时的拒答率和端到端延迟，并按 Workspace/文档版本回归。线上还应记录用户转人工率、答案采纳/纠正反馈和 token 成本，但不能在没有数据时声称具体数值。

### Q22：项目当前最大的技术债是什么？

**答：** RAG 目前以余弦召回为主，没有混合检索、重排和自动评估；Worker 还是数据库轮询/租约模型，规模大时需要队列和并发治理；自动分派没有技能组、在线心跳和 SLA；生产合规、审计脱敏和跨 Workspace 知识共享也未覆盖。这些都可以在不改变 API 领域边界的前提下演进。

### Q23：如果数据量扩大十倍，你会怎么优化？

**答：** 先用指标定位：检索延迟、Embedding 吞吐、SSE 首 token、数据库连接池和 Worker 积压。然后为 pgvector 选择合适索引并限制候选范围，批量 Embedding 和分片摄取；把 Job 迁移到 Redis/Celery 或消息队列；对文档和 chunk 做分区/归档；为 SSE 增加网关超时和并发上限；Provider 增加重试、熔断和成本限额。所有优化都必须保留 Workspace 过滤和幂等。

### Q24：前端 AI 浮窗有哪些细节？

**答：** 只有 Customer 且有当前 Workspace 时显示；打开时获取或创建会话；发送时生成临时 Assistant 草稿，按 `message.delta` 追加文本，按 `source.found` 更新来源卡片；Enter 发送、Shift+Enter 换行；异常显示提示；点击转人工调用幂等接口并告知“已分派”或“已进入队列”。

### Q25：为什么要把 AI Agent 建模成独立实体？

**答：** AI Agent 不是某个用户角色，而是 Workspace 内的执行主体，未来可以有名称、状态、工具授权、运行统计和多个 Agent。当前用 `AiAgent` 一 Workspace 唯一约束，把 Provider 配置、工具权限和会话运行关联起来，避免把系统行为错误地归因给某个管理员用户。

## 10. 代码导航速查

| 主题 | 关键文件 |
|---|---|
| FastAPI 入口 | `backend/app/main.py`, `backend/app/api/main.py` |
| JWT/Workspace | `backend/app/api/deps.py`, `backend/app/core/security.py`, `backend/app/core/workspace.py` |
| AI API/SSE | `backend/app/api/routes/ai.py`, `backend/app/services/agent_service.py` |
| Provider | `backend/app/services/provider_service.py`, `backend/app/providers/chat.py`, `backend/app/providers/embedding.py` |
| RAG 摄取 | `backend/app/services/knowledge_service.py`, `backend/app/workers/knowledge_ingestion.py` |
| RAG 检索 | `backend/app/services/knowledge_retrieval.py`, `backend/app/repositories/knowledge_repository.py` |
| 工单规则 | `backend/app/services/ticket_service.py`, `ticket_permissions.py`, `ticket_state_machine.py`, `assignment_service.py` |
| AI/知识模型 | `backend/app/models/ai.py`, `backend/app/models/knowledge.py` |
| 客户 AI 浮窗 | `frontend/src/components/AI/CustomerSupportWidget.tsx`, `frontend/src/lib/aiApi.ts` |
| 角色路由/导航 | `frontend/src/lib/routeGuards.ts`, `frontend/src/components/Sidebar/AppSidebar.tsx` |
| 知识库 UI | `frontend/src/components/Knowledge/KnowledgePanel.tsx` |
| 部署 | `compose.yml`, `compose.override.yml`, `compose.deploy.yml`, `deployment-docker-compose.md` |

## 10.1 关键 API 速查

| API | 用途 |
|---|---|
| `GET /api/v1/workspaces` | 当前用户可切换的 Workspace |
| `GET/PATCH /api/v1/workspaces/{id}/ai/provider` | 读取/更新脱敏 Provider 配置 |
| `POST /api/v1/workspaces/{id}/ai/provider/test` | Chat 或 Embedding 连通性测试 |
| `GET/PATCH /api/v1/workspaces/{id}/ai/tools` | AI 工具白名单 |
| `GET/POST /api/v1/workspaces/{id}/knowledge/documents` | 知识文档列表/上传 |
| `POST /api/v1/workspaces/{id}/knowledge/search` | 后台知识检索 |
| `POST /api/v1/workspaces/{id}/customer/conversation/messages/stream` | Customer 专用 RAG + SSE |
| `POST /api/v1/workspaces/{id}/conversations/{conversation_id}/handoff-ticket` | AI 会话幂等转工单 |

## 11. 已实现、部分实现与未覆盖范围

### 已实现

Workspace 隔离、JWT 鉴权、Customer/Agent/Admin/Owner 角色、工单状态机、审计、软删除、附件和头像、AI Provider 配置与测试、API Key 加密、PDF/DOCX/MD/TXT 摄取、1024 维 pgvector RAG、来源摘要、SSE、运行取消、消息/转人工幂等、自动分派、OpenAPI 生成客户端、Pytest/Playwright/迁移/Compose 验收。

### 部分实现或可增强

工具白名单和事件类型已建模，可继续扩展实际工具编排；RunEvent 已持久化，可增加断线重放；RAG 已有来源和距离，可增加重排、混合检索、评估集和反馈闭环。

### 当前未覆盖

复杂客服组/技能组路由、Agent 排班与在线心跳、SLA 自动升级、满意度评价、邮件收件转工单、计费、生产级合规认证、跨 Workspace 知识共享，以及 AI 删除工单、管理成员或修改 Provider。

## 12. 结束时的简短总结

这个项目对我最大的价值，不只是把 LLM 接进客服页面，而是把 AI 能力放进一个有租户边界、权限、数据模型、异步任务、流式协议、审计和人工兜底的真实业务系统。面试时我会围绕三个关键词展开：**可落地的全栈闭环、可控的 RAG、可靠的人机协同**。
