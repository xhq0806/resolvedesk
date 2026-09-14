> 来源: spec.md
> 生成时间: 2026-09-11
> 阶段: design

# ResolveDesk 二期技术设计

## Why

一期后端为 FastAPI + SQLModel + PostgreSQL，按 `User` 全局角色和 Ticket service/repository 组织业务；前端为 React、TanStack Router/Query 和 OpenAPI 生成客户端。当前没有 Workspace、向量检索、模型 Provider、持久任务、文件存储或流式业务模块。

本设计以求职展示为目标，优先保证一条可验证的多租户 AI 客服链路：Workspace 隔离 → 文档入库 → RAG 引用 → SSE 对话 → 白名单工具 → 工单回复/变更 → 审计/人工接管。外部模型失败、断流和越权都必须成为可观察的业务状态。

### 设计目标 / 非目标

| 类型 | 说明 |
|---|---|
| ✅ 目标 | 将用户、工单、知识、会话、附件和 AI 配置统一纳入 Workspace 隔离 |
| ✅ 目标 | 提供可替换的 OpenAI-compatible Chat/Embedding provider、RAG 和 SSE Agent 编排 |
| ✅ 目标 | 通过服务端白名单、独立 AI Agent 权限和一期状态机约束 Tool Calling |
| ✅ 目标 | 用持久化处理任务、幂等键、审计和可重复 E2E 支撑演示链路 |
| ❌ 非目标 | 邮件工单、SLA、复杂团队路由、计费、生产级合规和跨 Workspace 知识共享 |
| ❌ 非目标 | 引入通用 Agent 平台、分布式消息系统或多活对象存储 |

## What

### 技术方案

#### 架构决策

| 模块 | 职责 | 依赖 |
|---|---|---|
| `workspace` domain | Workspace、成员、邀请、Owner 保护和当前租户上下文 | User、现有错误处理 |
| `workspace_scope` dependency | 从 `X-Workspace-ID` 解析成员关系并返回 `WorkspaceContext` | JWT、Workspace repository |
| `ticket` extension | 为一期 Ticket/Message/Audit 增加 `workspace_id`，所有查询先套租户条件 | WorkspaceContext、现有 service/repository |
| `provider` | Chat/Embedding provider 配置、连接测试、密钥加密和 OpenAI-compatible HTTP adapter | `httpx`、Settings、Workspace |
| `knowledge` | 文档上传、解析、切块、Embedding、pgvector 检索、来源定位和任务重试 | pgvector、worker、provider |
| `agent` | 会话上下文、Prompt 组装、检索编排、流式事件、取消、幂等和人工接管 | provider、knowledge、tool executor |
| `agent_tools` | 工具注册、参数 schema、AI Agent 权限、绑定工单校验和一期状态机复用 | ai_agent、ticket service、workspace、audit |
| `attachments` | 文件类型/大小/magic number 校验、隔离路径、授权下载和删除审计 | Workspace、ticket/conversation |
| `audit` | 统一记录 provider、检索、工具、回复、接管和附件事件，默认脱敏 | request_id、WorkspaceContext |
| `workers` | 独立进程领取文档处理任务，支持重试、取消和启动恢复 | PostgreSQL、knowledge、provider |

模块关系：

```text
HTTP route -> WorkspaceContext -> service -> repository
                                      |
                                      +-> provider adapter (HTTP, no DB transaction)
                                      +-> knowledge retriever (pgvector)
                                      +-> tool executor -> TicketService/state machine
                                      +-> audit repository

document upload -> ingestion_job -> worker -> parse/chunk/embed -> pgvector
conversation message -> AgentOrchestrator -> SSE events -> persisted run/message
```

#### RAG 流程

1. 文档上传后创建 `KnowledgeDocument` 和 `DocumentIngestionJob`，HTTP 请求只完成安全校验与元数据提交。
2. worker 使用独立 session 读取文件，按格式解析为带页码/段落元数据的纯文本；解析失败标记 `FAILED`。
3. 文本按约 700 token、约 100 token overlap 切块；空块、超长块和不可读字符被丢弃并记录数量。
4. worker 调用 Workspace 的 Embedding provider，写入 1536 维向量和来源元数据；所有 chunk 与 document 同属一个 Workspace。
5. 检索先按 `workspace_id` 和 `document.status = READY` 过滤，再用 cosine distance 取 top 8；去重后最多返回 5 个来源。
6. Agent Prompt 明确“资料是无权限的参考内容”，只允许基于检索片段回答；无足够分数或无来源时返回安全拒答，不生成公开工单回复。
7. 回答来源包含 document id、显示名、页码/段落、chunk id 和短预览；Customer 只能看到当前会话被授权的来源，不能浏览完整内部文档。

选择 pgvector 的理由：与现有 PostgreSQL、迁移和 Docker 体系一致，单库即可展示租户过滤、向量索引和事务边界；不选择独立 Pinecone/Qdrant 是因为本项目目标是可运行的求职作品，独立服务会增加部署和数据同步面。选择 1536 维固定约束是为了让 pgvector 索引稳定；更换维度必须显式停用 AI、重建全部 chunk 后再启用。

#### Agent 与 Tool Calling 流程

1. `AgentOrchestrator` 读取会话最近消息、当前工单可见信息、RAG top-k 来源和 Workspace Agent tool permissions。
2. Provider 返回普通文本或结构化 tool call；服务端只接受注册工具名和 Pydantic 参数 schema，不执行模型返回的任意函数名或 URL。
3. `ToolExecutor` 重新校验 Workspace、会话绑定工单、AI Agent 权限、操作者成员状态和一期状态机；模型上下文不能绕过这些校验。
4. 读工具返回最小字段；写工具在独立短事务中完成并写一期 TicketAuditLog 扩展审计。外部模型调用不持有数据库写事务。
5. 工具结果作为事件发送给前端，随后继续模型循环；最多 4 轮工具调用，超过上限进入失败状态并转人工。
6. 公开回复只在生成内容非空、来源策略通过且会话未被接管时写入 TicketMessage；AI 作者使用独立 `AI_AGENT` 标识，不冒充用户。

#### 流式与任务边界

- SSE `POST` 入口先持久化用户消息和 `AiRun(status=RUNNING)`，提交后才开始外部模型调用；SSE 连接不持有写事务。
- 事件类型固定为 `run.started`、`message.delta`、`source.found`、`tool.started`、`tool.result`、`message.completed`、`run.completed`、`run.cancelled`、`run.failed`。
- `Idempotency-Key` 与 `(conversation_id, client_message_id)` 唯一约束防止重试产生重复消息。
- 客户端断开时取消 provider 请求并将 run 标记为 `CANCELLED`；已写入的 delta 只作为草稿事件，不生成完整 AI 回复。
- 文档处理使用 `DocumentIngestionJob` 状态机 `PENDING -> RUNNING -> READY/FAILED/CANCELLED`；worker 领取使用锁和 lease，启动时恢复超时任务。

### 数据模型变更

| 操作 | 表/实体 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|---|
| 新增 | `workspace` | `id,name,slug,status,owner_user_id,created_at` | UUID/string/enum/UUID/datetime | slug 唯一；Owner 必须存在 | 租户根实体 |
| 新增 | `workspace_member` | `workspace_id,user_id,role,status,joined_at` | UUID/UUID/enum/enum/datetime | `(workspace_id,user_id)` 唯一；至少一 Owner | User 的 Workspace 级角色 |
| 新增 | `workspace_invitation` | `id,workspace_id,email,role,token_hash,expires_at,accepted_at,revoked_at` | UUID/UUID/email/enum/hash/datetime | token 只存 hash；未接受邀请唯一 | 邀请生命周期 |
| 修改 | `user` | `role` | nullable/兼容字段 | 迁移后业务权限不再读取该字段 | 保留一期兼容，成员关系为真源 |
| 修改 | `ticket` | `workspace_id` | UUID | NOT NULL、索引、历史回填默认 Workspace | 租户过滤第一条件 |
| 修改 | `ticket_message,ticket_audit_log` | `workspace_id` | UUID | NOT NULL、联合时间索引 | 降低错误 join 风险并便于审计查询 |
| 新增 | `ai_provider_config` | `workspace_id,chat_provider,chat_base_url,chat_model,embedding_provider,embedding_base_url,embedding_model,embedding_dimension,encrypted_api_key,enabled,updated_at` | UUID/string/URL/string/integer/blob/bool/datetime | Workspace 唯一；dimension=1536；密钥不可回显 | OpenAI-compatible 配置 |
| 新增 | `ai_agent` | `id,workspace_id,name,status,created_at,updated_at` | UUID/UUID/string/enum/datetime/datetime | Workspace 一对一；默认 `ACTIVE` | Workspace 独立 AI 执行主体 |
| 新增 | `ai_tool_permission` | `ai_agent_id,workspace_id,tool_name,enabled,updated_by_id,updated_at` | UUID/UUID/string/bool/UUID/datetime | `(ai_agent_id,tool_name)` 唯一；工具名枚举 | AI Agent 白名单 |
| 新增 | `knowledge_document` | `id,workspace_id,display_name,storage_key,mime_type,size_bytes,sha256,status,version,error_code,created_by_id,created_at,deleted_at` | UUID/UUID/string/string/string/int/hash/enum/int/string/UUID/datetime/datetime | 20 MB；软删除；Workspace 索引 | 文档元数据和状态 |
| 新增 | `knowledge_chunk` | `id,workspace_id,document_id,chunk_index,content,source_meta,embedding,created_at` | UUID/UUID/UUID/int/text/JSON/vector(1536)/datetime | `(document_id,chunk_index)` 唯一；向量索引 | RAG 检索单元 |
| 新增 | `document_ingestion_job` | `id,workspace_id,document_id,status,attempts,lease_until,error_code,created_at,updated_at` | UUID/UUID/UUID/enum/int/datetime/string/datetime/datetime | lease 和重试上限 | 持久化 worker 任务 |
| 新增 | `ai_conversation` | `id,workspace_id,ticket_id,mode,status,handed_off,created_by_id,created_at,updated_at` | UUID/UUID/UUID/enum/enum/bool/UUID/datetime/datetime | ticket 可空；Workspace 索引 | Workspace 或工单会话 |
| 新增 | `ai_message` | `id,conversation_id,workspace_id,role,content,status,ai_generated,client_message_id,created_at` | UUID/UUID/UUID/enum/text/enum/bool/string/datetime | client id 唯一；10k 字符 | 用户/AI/工具消息 |
| 新增 | `ai_run` | `id,conversation_id,workspace_id,request_id,status,model,started_at,finished_at,error_code` | UUID/UUID/UUID/string/enum/string/datetime/datetime/string | request_id 可查；不存 prompt 原文 | 一次生成生命周期 |
| 新增 | `ai_run_event` | `id,run_id,workspace_id,sequence,event_type,payload_json,created_at` | UUID/UUID/UUID/int/enum/JSON/datetime | `(run_id,sequence)` 唯一；payload 脱敏 | SSE 重放和审计摘要 |
| 新增 | `attachment` | `id,workspace_id,ticket_id,conversation_id,storage_key,display_name,mime_type,size_bytes,sha256,uploaded_by_id,created_at,deleted_at` | UUID/UUID/UUID/UUID/string/string/string/int/hash/UUID/datetime/datetime | ticket/conversation 至少一个；10 MB | 受授权资源附件 |
| 修改 | `ticket_audit_log` | `actor_type,ai_agent_id,ai_run_id,workspace_id` | enum/UUID/UUID/UUID | AI 操作必须关联 agent/run | 区分用户与 AI 操作 |

实体关系：`Workspace 1:N WorkspaceMember/Invitation/Document/Provider/Conversation/Attachment`，`Workspace 1:1 AiAgent`；`AiAgent 1:N ToolPermission/Run/Audit`；`Document 1:N Chunk/IngestionJob`；`Conversation 1:N Message/Run`；`Run 1:N RunEvent`；`Ticket 1:N Message/Audit/Attachment`。所有关系查询必须带 Workspace 条件。

### 接口定义

#### HTTP API

| 接口 | 方法 | 路径/签名 | 入参 | 出参 | 说明 |
|---|---|---|---|---|---|
| Workspace 列表 | GET | `/workspaces` | JWT | `WorkspaceSummary[]` | 返回当前用户成员 Workspace |
| 创建 Workspace | POST | `/workspaces` | `WorkspaceCreate(name,slug)` | `WorkspaceDetail` | 创建者成为 Owner |
| 成员列表 | GET | `/workspaces/{workspace_id}/members` | Workspace header + JWT | `MemberPage` | Owner/Admin 或成员只读 |
| 邀请成员 | POST | `/workspaces/{workspace_id}/invitations` | `InvitationCreate(email,role)` | `InvitationPublic` | Owner/Admin；token 不返回 |
| 接受/撤销/移除/改角色 | POST/DELETE/PATCH | `/workspaces/{id}/invitations/{invitation_id}`、`/members/{user_id}` | 关系资源参数 | `MemberPublic`/204 | 全部写操作审计 |
| Provider 配置 | GET/PATCH | `/workspaces/{id}/ai/provider` | `ProviderConfigPatch` | `ProviderConfigPublic` | Public 只返回 masked key、dimension、enabled |
| Provider 测试 | POST | `/workspaces/{id}/ai/provider/test` | `ProviderTestRequest(kind)` | `ProviderTestResult` | 外部调用在事务外 |
| 工具权限 | GET/PATCH | `/workspaces/{id}/ai/tools` | `ToolPermissionPatch[]` | `ToolPermission[]` | Owner/Admin 逐项启停 |
| 文档列表/上传 | GET/POST | `/workspaces/{id}/knowledge/documents` | `DocumentFilters` / multipart | `DocumentPage` / `DocumentPublic` | 上传只创建处理任务 |
| 文档重试/删除 | POST/DELETE | `/knowledge/documents/{document_id}/retry`、`/{document_id}` | Workspace header | `DocumentPublic`/204 | 软删除，重试幂等 |
| 会话列表/创建 | GET/POST | `/workspaces/{id}/conversations` | `ConversationCreate(ticket_id?)` | `ConversationPage`/`ConversationPublic` | 检查工单归属和角色 |
| 会话消息流 | POST | `/conversations/{conversation_id}/messages/stream` | `MessageCreate(content,client_message_id)`, `Idempotency-Key` | `text/event-stream<AgentEvent>` | SSE；最多一条 RUNNING |
| 取消/接管/恢复 | POST | `/conversations/{id}/cancel`、`/handoff`、`/resume` | `run_id?` | `ConversationPublic` | 接管先取消运行中生成 |
| 会话审计 | GET | `/conversations/{id}/runs`、`/runs/{run_id}/events` | cursor/page | `AiRunPage`/`AiRunEvent[]` | 按当前成员权限裁剪 |
| 附件上传/下载/删除 | POST/GET/DELETE | `/tickets/{ticket_id}/attachments`、`/attachments/{id}/content` | multipart / attachment id | `AttachmentPublic` / 文件流 / 204 | 服务端授权和安全下载 |

#### 关键内部签名

```text
WorkspaceService.create(actor: User, payload: WorkspaceCreate) -> Workspace
WorkspaceService.invite(actor: User, workspace_id: UUID, payload: InvitationCreate) -> WorkspaceInvitation
WorkspaceScope.resolve(actor: User, workspace_id: UUID | None) -> WorkspaceContext
WorkspacePolicy.require_member(ctx: WorkspaceContext, minimum_role: WorkspaceRole) -> None

ProviderRegistry.chat(config: ProviderConfig) -> ChatProvider
ProviderRegistry.embedding(config: ProviderConfig) -> EmbeddingProvider
ChatProvider.stream(messages: list[ChatMessage], tools: list[ToolDefinition], signal: CancelSignal) -> AsyncIterator[ProviderEvent]
EmbeddingProvider.embed(texts: list[str]) -> list[EmbeddingVector]

KnowledgeService.create_document(ctx: WorkspaceContext, actor: User, upload: UploadPayload) -> KnowledgeDocument
KnowledgeService.retry_document(ctx: WorkspaceContext, actor: User, document_id: UUID) -> DocumentIngestionJob
KnowledgeRetriever.search(ctx: WorkspaceContext, query: str, limit: int = 8) -> list[RetrievedChunk]

AgentService.create_conversation(ctx: WorkspaceContext, actor: User, ticket_id: UUID | None) -> AiConversation
AgentOrchestrator.stream_run(ctx: WorkspaceContext, actor: User, conversation_id: UUID, message: MessageCreate, idempotency_key: str) -> AsyncIterator[AgentEvent]
AgentService.cancel_run(ctx: WorkspaceContext, actor: User, run_id: UUID) -> AiRun
AgentService.handoff(ctx: WorkspaceContext, actor: User, conversation_id: UUID) -> AiConversation

ToolRegistry.list_enabled(ctx: WorkspaceContext, agent_id: UUID) -> list[ToolDefinition]
ToolExecutor.execute(ctx: WorkspaceContext, run: AiRun, tool_name: str, arguments: ToolArguments) -> ToolResult
AuditService.record(ctx: WorkspaceContext, event: AuditEvent) -> None
AttachmentService.upload(ctx: WorkspaceContext, actor: User, parent: AttachmentParent, upload: UploadPayload) -> Attachment
```

主要工具定义：`get_current_ticket`、`search_knowledge`、`update_ticket_attributes`、`update_ticket_status`、`send_public_reply`、`add_internal_note`。不注册删除工单、成员管理、Provider 修改和未绑定工单读取工具。每个 Workspace 初始创建一个 `ACTIVE` AiAgent，Owner/Admin 只修改其工具权限，不直接修改 Agent 身份。

#### OpenAPI/SSE 事件契约

```text
AgentEvent =
  RunStarted { run_id, conversation_id }
  | MessageDelta { run_id, text }
  | SourceFound { run_id, source_id, document_id, display_name, locator }
  | ToolStarted { run_id, tool_call_id, tool_name }
  | ToolResult { run_id, tool_call_id, status, redacted_result }
  | MessageCompleted { message_id, ai_generated, sources[] }
  | RunCompleted { run_id }
  | RunCancelled { run_id }
  | RunFailed { run_id, error_code, request_id }
```

### 错误处理策略

| 错误类型 | 处理方式 | HTTP状态码/异常类 |
|---|---|---|
| 缺少/无效 Workspace header | 不推断默认租户，要求选择 Workspace | 400 `WORKSPACE_REQUIRED` / `WorkspaceError` |
| 非成员或跨 Workspace 资源 | 统一伪装为不存在，禁止泄露资源存在性 | 404 `WORKSPACE_RESOURCE_NOT_FOUND` / `NotFoundError` |
| 成员/Owner 约束冲突 | 不提交部分变更 | 409 `WORKSPACE_MEMBER_CONFLICT` / `ConflictError` |
| Provider 未配置或鉴权失败 | 生成失败 run，返回 request_id 和稳定错误码 | 409/502 `PROVIDER_UNAVAILABLE` / `ProviderError` |
| 文档解析/Embedding 失败 | 文档为 FAILED，任务可重试，原有文档不受影响 | 200 状态查询；操作错误 409 `DOCUMENT_PROCESSING_FAILED` |
| 工具未授权/参数非法/状态机冲突 | 工具不执行，写拒绝审计，模型收到结构化错误 | 409 `TOOL_NOT_ALLOWED` / `ToolExecutionError` |
| AI 会话并发生成 | 保持现有 RUNNING，拒绝第二次生成 | 409 `AI_RUN_IN_PROGRESS` / `ConflictError` |
| SSE 断开/取消/超时 | 保存取消或失败状态，不提交半条 AI 回复 | 流事件 `run.cancelled`/`run.failed` |
| 文件类型、magic number、大小或路径非法 | 上传前拒绝，不写入可访问存储 | 422 `ATTACHMENT_INVALID` / `ValidationError` |
| API Key 出现在日志/响应 | 视为安全缺陷；统一脱敏并拒绝输出 | 内部 `SecretLeakError`，触发发布阻断 |

### 关键决策与理由

| 决策 | 可选方案 | 选择 | 理由 |
|---|---|---|---|
| 租户识别 | A: 把 workspace_id 放进 JWT / B: `X-Workspace-ID` 请求头 | B | 用户可加入多个 Workspace；切换无需刷新 token，服务端每次按成员关系重验 |
| 向量数据库 | A: pgvector / B: 独立 Qdrant/Pinecone | A | 复用已有 PostgreSQL 和 Docker，部署面小且足以展示隔离和向量检索 |
| Embedding | A: 本地模型 / B: 用户配置 OpenAI-compatible API | B | 用户可配置 APIKey/baseUrl，服务端 adapter 可切换 provider，不增加本地模型运行成本 |
| Embedding 维度 | A: 动态多维 / B: Workspace 固定 1536 维 | B | pgvector 索引和验收数据稳定；变更通过明确重建流程完成 |
| Agent 框架 | A: LangChain/LangGraph / B: 项目内 orchestrator | B | 工具、审计、权限和 SSE 行为可直接追踪，减少框架黑盒和依赖 |
| 实时协议 | A: WebSocket / B: SSE POST | B | 对单向模型输出更简单；现有生成客户端已有 SSE 解析器，保留 HTTP 鉴权和取消信号 |
| 文档任务 | A: BackgroundTasks / B: 持久任务表 + worker | B | 解析和 Embedding 超过短任务边界，需要重试、恢复和审计 |
| 文件存储 | A: 本地隔离目录 / B: S3 兼容对象存储 | A（本期） | 求职演示部署简单；通过 `storage_key` 抽象，后续可替换而不改权限模型 |
| API Key 保护 | A: 明文数据库 / B: 应用密钥加密 | B | 满足不回显、不入日志和配置轮换；加密根密钥只来自服务端环境变量 |

### 风险与权衡

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| 租户条件遗漏造成数据泄漏 | 中 | 高 | 所有 repository 接受 `WorkspaceContext`；跨租户 ticket/document/conversation/tool/source/cache 测试；必要时数据库 RLS 作为后续加固 |
| Prompt 注入诱导工具越权 | 中 | 高 | 文档标记为不可信；工具固定注册；每次执行服务端重新授权并校验绑定工单；写操作审计 |
| Provider 超时、流中断和重复写入 | 高 | 中 | `httpx` timeout、取消信号、run 状态机、幂等唯一键、最大 4 轮工具调用和断流测试 |
| API Key 或 PII 进入 prompt/log | 中 | 高 | provider adapter 只传必要内容；日志白名单；审计存 hash/摘要；Sentry 继续脱敏 |
| 文件解析和上传绕过安全边界 | 中 | 高 | magic number、MIME、大小、文件名、路径隔离、压缩包限制和下载授权测试 |
| pgvector 维度/扩展在环境中不一致 | 中 | 中 | Compose 使用带 pgvector 的 PostgreSQL 镜像；启动检查 extension 和 1536 维；迁移失败即阻止启用 RAG |
| worker 任务重复或卡死 | 中 | 中 | lease、attempts、状态机、启动恢复和幂等 document hash；外部调用不持有 DB 锁 |

### 发布策略

- **发布方式**：先发布数据库迁移、Workspace 隔离和一期回归；再关闭 AI 开关部署 Provider/RAG；最后按 Workspace 启用 SSE、Tool Calling 和附件。
- **回滚条件**：任何跨租户读取、密钥泄漏、AI 越权写入、历史 Ticket 不可访问、迁移回填失败或一期测试回归失败，立即关闭二期开关并回滚应用版本。
- **数据迁移**：新增默认 Workspace；现有 User 以一期角色生成成员关系，现有 Ticket/Message/Audit 回填 `workspace_id`；迁移可重复执行，必须存在活跃 Owner/Admin；创建 pgvector extension 和向量索引。
- **版本策略**：Workspace header、Provider、Knowledge、Conversation 和 SSE 先以新增 API 发布；旧 Ticket API 在兼容窗口内要求 header。OpenAPI 稳定后重新生成前端客户端，前端再启用新路由。

### 变更文件清单

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `backend/app/models/workspace.py` | 新增 | Workspace、Member、Invitation ORM |
| `backend/app/models/ai.py` | 新增 | Provider、Agent tool、Conversation、Run、Event ORM |
| `backend/app/models/knowledge.py` | 新增 | Document、Chunk、IngestionJob ORM |
| `backend/app/models/attachment.py` | 新增 | 附件 ORM |
| `backend/app/models/ticket.py` | 修改 | 增加 workspace_id、AI 作者和审计字段 |
| `backend/app/core/config.py` | 修改 | 存储目录、加密根密钥、provider timeout、worker 参数 |
| `backend/app/core/workspace.py` | 新增 | Workspace header/context dependency |
| `backend/app/repositories/workspace_repository.py` | 新增 | 成员、邀请、租户查询 |
| `backend/app/repositories/knowledge_repository.py` | 新增 | 文档、chunk、任务和 pgvector 查询 |
| `backend/app/repositories/ai_repository.py` | 新增 | 会话、run、event 和幂等查询 |
| `backend/app/services/workspace_service.py` | 新增 | Workspace 与成员策略 |
| `backend/app/services/provider_service.py` | 新增 | 配置、加密和连接测试 |
| `backend/app/services/knowledge_service.py` | 新增 | 文档生命周期和来源裁剪 |
| `backend/app/services/agent_service.py` | 新增 | 会话、接管、取消和 run 编排 |
| `backend/app/services/tool_executor.py` | 新增 | 白名单工具和服务端授权 |
| `backend/app/services/attachment_service.py` | 新增 | 文件安全和资源授权 |
| `backend/app/providers/` | 新增 | Chat/Embedding adapter 与 HTTP client |
| `backend/app/workers/knowledge_ingestion.py` | 新增 | 持久化文档处理 worker |
| `backend/app/api/routes/workspaces.py` | 新增 | Workspace/member API |
| `backend/app/api/routes/ai.py` | 新增 | Provider/tool/conversation/SSE API |
| `backend/app/api/routes/knowledge.py` | 新增 | 文档和检索来源 API |
| `backend/app/api/routes/attachments.py` | 新增 | 附件 API |
| `backend/app/schemas/workspace.py`、`ai.py`、`knowledge.py`、`attachment.py` | 新增 | 请求/响应与 SSE schema |
| `backend/app/alembic/versions/<revision>_add_workspace_ai_rag.py` | 新增 | 扩展、表、索引、历史回填 |
| `backend/tests/` | 新增/修改 | 租户、迁移、provider、RAG、工具、SSE、附件安全测试 |
| `compose.yml`、`compose.override.yml` | 修改 | pgvector 镜像、worker 服务、存储卷和 AI 配置环境 |
| `frontend/src/lib/workspaceQueries.ts` | 新增 | Workspace 查询键、header 和切换清理 |
| `frontend/src/components/Workspace/` | 新增 | 切换器、成员管理 |
| `frontend/src/components/AI/`、`Knowledge/`、`Attachments/` | 新增 | 配置、聊天、来源和附件 UI |
| `frontend/src/routes/_layout/ai.tsx`、`knowledge.tsx` | 新增 | AI 工作台和知识库路由 |
| `frontend/src/client/` | 生成 | OpenAPI 请求/响应/SSE 类型同步 |
| `frontend/tests/` | 新增 | 多 Workspace、RAG、工具越权、接管和附件 E2E |

## How

### 任务拆分

| 任务名称 | 详细描述 | 关联设计章节 | 计划工作量(人天) |
|---|---|---|---:|
| 【迁移基础】(后端) 建立 pgvector 与 Workspace 数据迁移 | 1. 添加扩展、Workspace/member/invitation 表<br>2. 回填默认 Workspace 与一期业务数据<br>3. 增加可重复迁移和活跃 Owner 校验 | 数据模型变更、发布策略 | 2 |
| 【租户上下文】(后端) 实现 header 解析与成员策略 | 1. WorkspaceContext dependency<br>2. 成员/邀请/Owner 保护 service<br>3. 统一错误与跨租户伪装 | 架构决策、接口定义 | 2 |
| 【工单隔离】(后端) 迁移 Ticket 查询和一期 API | 1. 所有 ticket/message/audit repository 增加 workspace 条件<br>2. 更新统计、状态机和审计<br>3. 回归一期接口 | 数据模型变更、风险 | 2 |
| 【租户客户端】(前端) 实现 Workspace 切换和成员管理 | 1. header 注入与 Query cache 清理<br>2. 切换器、邀请和角色管理<br>3. 越权/空状态反馈 | 接口定义、架构决策 | 1.5 |
| 【Provider】(后端) 实现配置加密与 OpenAI-compatible adapter | 1. Chat/Embedding adapter<br>2. API Key 加密脱敏<br>3. 连接测试、timeout 和错误映射 | Provider、风险 | 2 |
| 【Provider UI】(前端) 实现模型和工具权限配置 | 1. Provider 表单与测试<br>2. 工具逐项启停<br>3. 权限和密钥不回显 | 接口定义 | 1 |
| 【知识入库】(后端) 实现文档任务、解析、切块和向量写入 | 1. 上传安全与文档状态<br>2. 持久任务 worker、重试和恢复<br>3. 1536 维 Embedding 与 pgvector 索引 | RAG 流程、数据模型 | 2 |
| 【知识检索】(后端) 实现 Workspace 检索和来源裁剪 | 1. cosine top-k 检索<br>2. READY/软删除/权限过滤<br>3. 来源定位和无依据拒答 | RAG 流程、接口定义 | 1.5 |
| 【知识库 UI】(前端) 实现文档管理和引用 | 1. 上传、处理状态、重试、删除<br>2. 文档来源定位<br>3. 错误和空状态 | 接口定义 | 1.5 |
| 【Agent 编排】(后端) 实现会话、SSE run 和取消接管 | 1. Conversation/Message/Run/Event 生命周期<br>2. SSE 事件、幂等、断流和超时<br>3. AI 回复标记和人工接管 | 流式与任务边界、接口定义 | 2 |
| 【工具执行】(后端) 实现 AI Agent 实体、白名单与工单动作 | 1. Agent 生命周期、工具 schema/注册/授权<br>2. 绑定工单和一期状态机重验<br>3. 工具结果脱敏和审计 | Agent 与 Tool Calling、数据模型、错误策略 | 2 |
| 【AI 工作台】(前端) 实现流式聊天和工具状态 | 1. 消息 delta、来源和工具事件<br>2. 取消、重试、接管/恢复<br>3. 工单上下文与 AI 身份展示 | SSE 契约、接口定义 | 2 |
| 【附件】(全栈) 实现文件安全和资源关联 | 1. magic/MIME/大小校验<br>2. 隔离存储、下载授权、删除审计<br>3. 工单和会话 UI | 数据模型、风险 | 1.5 |
| 【测试验收】(全栈) 完成安全、RAG、Agent 和演示回归 | 1. 多 Workspace 和迁移测试<br>2. Provider/RAG/Tool/SSE/附件失败路径<br>3. Playwright 主链路和演示脚本 | 风险、发布策略 | 2 |
| **合计** |  |  | **25.5** |

### 任务依赖

```text
【迁移基础】
  ├─> 【租户上下文】 ─> 【工单隔离】 ─> 【租户客户端】
  ├─> 【Provider】 ─> 【Provider UI】
  ├─> 【知识入库】 ─> 【知识检索】 ─> 【知识库 UI】
  └─> 【Agent 编排】 ─> 【工具执行】 ─> 【AI 工作台】
【附件】依赖【租户上下文】
【测试验收】依赖以上全部任务
```

## Verify

设计自检：

- [x] 所有 spec 功能需求均有对应架构、模型、接口或任务设计。
- [x] 所有技术选择均记录了替代方案和理由。
- [x] HTTP/SSE 和关键内部方法已定义到签名级，未写实现代码。
- [x] Workspace、Provider、RAG、Agent、工具、附件和审计数据模型明确。
- [x] 任务粒度为 1~2 人天，包含前端、后端、worker、迁移和联调验收。
- [x] 已覆盖权限变更、迁移、外部调用、文件、prompt 和流式并发风险。
- [x] 已定义发布顺序、回滚条件、迁移回填和客户端版本策略。
- [x] 设计未加入 spec 明确排除的邮件、SLA、复杂团队和计费功能。

## Impact

- 后端：新增 Workspace/AI/RAG/附件领域、worker 和 provider adapter；一期 Ticket/Message/Audit 全部增加 Workspace 条件。
- 前端：新增 Workspace、AI 配置、知识库、流式会话和附件 UI；OpenAPI 契约稳定后重新生成客户端。
- 数据库：新增 pgvector 扩展、约 14 张新增表/扩展字段、迁移回填和向量索引。
- 部署：Compose 增加 pgvector 数据库镜像、knowledge worker 和本地存储卷；AI provider 只通过服务端环境/数据库加密配置访问。
- 外部依赖：新增 OpenAI-compatible Chat/Embedding HTTP 调用；不在本地运行模型，不增加独立向量数据库服务。

---

# Delta Design

> 基于: design.md
> 变更时间: 2026-09-14
> 变更依据: spec.md Delta Spec - Admin-only 知识库、Customer 在线咨询、转人工工单。

## Why

当前实现已经具备 Workspace、RAG、AI 会话、知识库管理和人工接管基础，但产品入口仍偏后台：知识库作为基础侧栏项对三角色可见，Customer 的 AI 入口也不像真实客服前台。新的设计把知识库后台收敛到 Admin/Owner，把 Customer 体验改成右下角“在线咨询”浮窗，并让转人工成为创建和分派工单的正式业务链路。

### 设计目标 / 非目标

| 类型 | 说明 |
|---|---|
| ✅ 目标 | 让知识库导航、路由和接口均只允许 Admin/Owner 管理 |
| ✅ 目标 | 为 Customer 增加全局悬浮在线咨询入口和独立聊天面板 |
| ✅ 目标 | 让 Customer 咨询可通过 AI Agent 内部 RAG 回答，且不暴露知识库管理能力 |
| ✅ 目标 | 将转人工实现为幂等的 conversation -> ticket 创建、自动分派和审计流程 |
| ❌ 非目标 | 不做客服排班、在线状态心跳、技能组路由、SLA 或多轮人工即时 IM |
| ❌ 非目标 | 不开放 Agent 浏览知识库后台，不让 Customer 直接查看完整知识文档 |

## What

### 技术方案

#### 架构决策

| 模块 | 职责 | 依赖 |
|---|---|---|
| `roleNavigation` | 根据当前 Workspace 成员角色生成侧栏项和受保护路由 | auth、workspaceQueries |
| `CustomerSupportWidget` | Customer 全局悬浮按钮、咨询面板、推荐问题、输入和转人工入口 | aiApi、workspaceQueries、queryClient |
| `customer_conversation` API | 创建/读取 Customer 自己的 Workspace 级 AI conversation，复用现有 run/SSE 事件 | AgentService、WorkspaceContext |
| `handoff_to_ticket` service | 将 conversation 幂等转换为 ticket，生成摘要、关联 ticket、写审计 | AgentService、TicketService、UserRepository |
| `AgentAssignmentPolicy` | 按当前 Workspace 选择可接待 Agent，第一版用活跃 Agent 的未关闭负责工单数排序 | TicketRepository、WorkspaceMember |
| `agent_ticket_context` UI | Agent 工单详情展示转人工来源、AI 会话摘要和公开来源摘要 | TicketDetailPage、AI message API |

模块关系：

```text
Customer UI
  -> CustomerSupportWidget
  -> conversation stream API
  -> AgentOrchestrator -> KnowledgeRetriever (internal only)
  -> handoff API -> TicketService.create_from_conversation
                 -> AgentAssignmentPolicy
                 -> TicketAuditLog

Sidebar/Route guard
  -> current workspace role
  -> Admin/Owner: knowledge route visible
  -> Agent/Customer: knowledge route hidden + direct route denied
```

#### 权限与导航设计

- `baseItems` 不再包含“知识库”。
- Admin/Owner 菜单增加“知识库”；Agent 和 Customer 菜单不渲染该项。
- `/knowledge` 路由增加 Workspace manager guard；非 manager 直接访问时显示无权/重定向，不挂载 `KnowledgePanel`，避免先发文档列表请求。
- 后端知识库 list/upload/retry/delete 继续调用 `WorkspacePolicy.require_manager(context)`；如果存在 search 管理接口，也不得对 Customer/Agent 暴露为文档浏览能力。
- Product 文案统一：界面显示“管理员”或“Admin”，内部仍兼容 `OWNER` 作为管理权限。

#### Customer 在线咨询流程

1. `_layout` 读取当前用户和 Workspace 成员角色；仅 Customer 渲染 `CustomerSupportWidget`。
2. 悬浮按钮使用竖向胶囊布局，文案为“在线咨询”，点击后打开右侧/右下浮层。
3. 面板首次打开时请求或创建当前 Customer 的 open conversation；如果本地没有 Workspace，先触发 `ensureCurrentWorkspace()`。
4. 用户发送消息时复用现有 SSE run：显示 `message.delta`、`source.found`、`run.failed` 等事件。
5. 推荐问题由前端静态配置或后端 Workspace 配置返回；第一版使用前端静态配置，避免新增配置表。
6. 来源只展示文档名、定位和短预览，不跳转知识库管理页。
7. 无依据、失败或用户主动点击时显示“转人工”动作。

#### 转人工与自动分派流程

1. `POST /workspaces/{workspace_id}/conversations/{conversation_id}/handoff-ticket` 接收 Customer 请求。
2. 服务端校验 conversation 属于当前 Customer、当前 Workspace，且尚未关联 handoff ticket。
3. 服务端基于最近用户消息、AI 回复、来源摘要生成工单标题和描述；标题最长 200 字，描述最长 10,000 字，超长内容裁剪并保留“完整会话见 AI conversation”引用。
4. `TicketService.create_from_ai_handoff(ctx, actor, conversation)` 创建 Customer 工单。
5. `AgentAssignmentPolicy.pick_agent(ctx)` 选择候选 Agent：当前 Workspace ACTIVE 成员、全局用户 active、成员角色 `AGENT`，按未关闭负责工单数升序，再按最早加入时间/用户 id 稳定排序。
6. 若选中 Agent，工单负责人设为该 Agent，状态为 `IN_PROGRESS`，写入分派审计；否则保持 `OPEN` 未分派。
7. conversation 标记 `handed_off=true` 并保存 `ticket_id`；重复请求返回同一个 ticket，不创建重复工单。
8. Customer 面板显示工单编号和当前状态；Agent 队列或我的工单中可看到该工单。

### 数据模型变更

| 操作 | 表/实体 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|---|
| 修改 | `ai_conversation` | `ticket_id` | UUID nullable | 已存在；转人工后写入 | 关联创建出的工单 |
| 修改 | `ai_conversation` | `handed_off` | bool | 已存在；默认 false | 幂等阻止重复创建工单 |
| 新增/修改 | `ticket_audit_log` | `action` 枚举 | string/enum | 增加 AI_HANDOFF_CREATED、AUTO_ASSIGNED | 记录转人工与自动分派 |
| 无新增 | `ticket` | — | — | 复用现有字段 | 转人工创建普通 Customer 工单 |

本次优先复用现有 `ai_conversation.ticket_id/handed_off` 和 ticket 状态机，不新增在线客服 IM 表。后续如要做真正人工实时聊天，再单独扩展会话参与者和在线状态。

### 接口定义

#### HTTP API

| 接口 | 方法 | 路径/签名 | 入参 | 出参 | 说明 |
|---|---|---|---|---|---|
| Customer 当前咨询会话 | GET/POST | `/workspaces/{workspace_id}/customer/conversation` | Workspace header | `ConversationPublic` | 仅 Customer；获取或创建未转人工的 Workspace 级会话 |
| Customer 消息流 | POST | `/workspaces/{workspace_id}/customer/conversation/messages/stream` | `MessageCreate(content,client_message_id)`, `Idempotency-Key` | `text/event-stream<AgentEvent>` | 仅 Customer；服务端内部 RAG |
| Customer 转人工 | POST | `/workspaces/{workspace_id}/conversations/{conversation_id}/handoff-ticket` | `HandoffTicketRequest(reason?)` | `HandoffTicketResult(ticket, assigned_agent?)` | 幂等创建/返回工单 |
| 工单 AI 上下文 | GET | `/workspaces/{workspace_id}/tickets/{ticket_id}/ai-context` | Workspace header | `TicketAiContextPublic` | Agent/Admin 或工单 Customer 可读裁剪后的对话摘要 |

#### 关键内部签名

```text
NavigationPolicy.items_for(role: WorkspaceRole, user_role: UserRole) -> list[NavigationItem]

AgentService.get_or_create_customer_conversation(ctx: WorkspaceContext, actor: User) -> AiConversation
AgentService.stream_customer_message(ctx: WorkspaceContext, actor: User, payload: MessageCreate, idempotency_key: str) -> AsyncIterator[AgentEvent]
AgentService.handoff_to_ticket(ctx: WorkspaceContext, actor: User, conversation_id: UUID, reason: str | None) -> HandoffTicketResult

TicketService.create_from_ai_handoff(ctx: WorkspaceContext, actor: User, conversation: AiConversation, summary: HandoffSummary) -> Ticket
AgentAssignmentPolicy.pick_agent(ctx: WorkspaceContext) -> User | None
AgentAssignmentPolicy.count_open_assigned(ctx: WorkspaceContext, agent_id: UUID) -> int
```

### 错误处理策略

| 错误类型 | 处理方式 | HTTP状态码/异常类 |
|---|---|---|
| Agent/Customer 访问知识库管理路由 | 前端不展示入口；后端返回 manager forbidden，不返回文档数据 | 403 `WORKSPACE_ROLE_FORBIDDEN` |
| 非 Customer 调用 Customer 咨询接口 | 拒绝请求，不创建 conversation | 403 `WORKSPACE_ROLE_FORBIDDEN` |
| 转人工重复请求 | 返回已创建 ticket 和当前分派状态 | 200 `HandoffTicketResult` |
| conversation 不属于当前用户或 Workspace | 伪装为资源不存在 | 404 `WORKSPACE_RESOURCE_NOT_FOUND` |
| 创建工单失败 | conversation 不标记 handed_off；用户可重试 | 409/500 稳定错误码 |
| 自动分派无候选 Agent | 不视为失败；创建未分派 `OPEN` 工单 | 201 `HandoffTicketResult.assigned_agent=null` |

### 关键决策与理由

| 决策 | 可选方案 | 选择 | 理由 |
|---|---|---|---|
| 知识库可见性 | A: Agent 可只读 / B: 仅 Admin/Owner 管理 | B | 用户已明确要求 Agent/Customer 侧栏完全不可见；知识库作为后台资产更安全 |
| Customer 入口 | A: 复用 `/ai` 工作台 / B: 全局悬浮咨询面板 | B | 更符合客户前台咨询习惯，不要求客户理解后台 AI 工作台 |
| 推荐问题来源 | A: 新增后端配置 / B: 前端静态默认 | B（本期） | 降低实现范围；后续可扩展 Workspace 配置 |
| 转人工承载 | A: 新建实时人工会话表 / B: 创建普通工单 | B | 复用现有工单状态机、权限、队列和审计，符合“转人工后创建工单”要求 |
| 分派策略 | A: 在线状态/排班 / B: 活跃 Agent 负载最低 | B | 当前系统没有在线状态和排班；负载最低可测试、确定性强 |
| 重复转人工 | A: 每次点击新建工单 / B: conversation 幂等关联一个 ticket | B | 避免重复工单和客服重复处理 |

### 风险与权衡

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| 前端隐藏知识库但直接 URL 仍能访问 | 中 | 高 | 路由 guard 和后端 manager 校验双重覆盖，增加 E2E 直接访问测试 |
| Customer 通过 AI 来源推断内部文档结构 | 中 | 中 | 来源只给短预览和定位，不暴露下载/管理链接 |
| 自动分派把工单给停用或非成员 Agent | 低 | 高 | 分派查询同时校验 WorkspaceMember ACTIVE、User.is_active 和 role=AGENT |
| 转人工重复点击创建多个工单 | 中 | 中 | conversation `handed_off/ticket_id` 幂等约束和事务内重查 |
| Customer 浮窗与页面布局重叠 | 中 | 低 | 使用固定 z-index、移动端底部抽屉和 Playwright 视口截图检查 |

### 变更文件清单

| 文件路径 | 操作 | 变更说明 |
|---|---|---|
| `frontend/src/components/Sidebar/AppSidebar.tsx` | 修改 | 知识库从 baseItems 移到 Admin/Owner 专属导航 |
| `frontend/src/routes/_layout/knowledge.tsx` | 修改 | 增加 manager route guard |
| `frontend/src/components/Knowledge/KnowledgePanel.tsx` | 修改 | 移除手输 Workspace UUID，依赖当前 Workspace 和权限 |
| `frontend/src/components/AI/CustomerSupportWidget.tsx` | 新增 | Customer 悬浮在线咨询入口和面板 |
| `frontend/src/components/AI/CustomerConversationPanel.tsx` | 新增 | 推荐问题、消息流、来源、转人工 UI |
| `frontend/src/lib/aiApi.ts` | 修改 | 增加 Customer conversation 和 handoff-ticket 请求 |
| `frontend/src/routes/_layout.tsx` | 修改 | 注入 CustomerSupportWidget |
| `backend/app/api/routes/ai.py` | 修改 | 增加 Customer conversation 和 handoff-ticket API |
| `backend/app/services/agent_service.py` | 修改 | 增加 Customer conversation 和转人工编排 |
| `backend/app/services/ticket_service.py` | 修改 | 增加从 AI handoff 创建工单的方法 |
| `backend/app/services/assignment_service.py` | 新增 | Agent 自动分派策略 |
| `backend/app/repositories/ticket_repository.py` | 修改 | 增加 Agent 未关闭负责工单计数查询 |
| `backend/app/schemas/ai.py` | 修改 | 增加 handoff 请求/响应、ticket AI context schema |
| `backend/tests/` | 新增/修改 | 权限、转人工、分派和幂等测试 |
| `frontend/tests/` | 新增/修改 | Customer 浮窗、知识库隐藏、转人工 E2E |

## How

### 任务拆分

| 任务名称 | 详细描述 | 关联设计章节 | 计划工作量(人天) |
|---|---|---|---:|
| 【权限收敛】(全栈) Admin-only 知识库导航和路由 | 1. 调整侧边栏角色菜单<br>2. `/knowledge` 增加 manager guard<br>3. 补充后端/前端直接访问拒绝测试 | 权限与导航设计 | 1 |
| 【在线咨询】(前端) Customer 悬浮入口和咨询面板 | 1. 新增悬浮按钮和聊天面板<br>2. 实现推荐问题、输入、来源和失败状态<br>3. 移动端/桌面布局验收 | Customer 在线咨询流程 | 1.5 |
| 【咨询会话】(后端) Customer conversation 与 RAG 流 | 1. 增加 Customer 会话获取/创建接口<br>2. 复用 SSE run 和内部 RAG<br>3. 禁止非 Customer 调用 | 接口定义、Customer 在线咨询流程 | 1 |
| 【转人工】(后端) Conversation 转工单和自动分派 | 1. 增加 handoff-ticket 接口<br>2. 生成工单摘要并幂等关联 conversation<br>3. 实现负载最低 Agent 分派策略 | 转人工与自动分派流程 | 2 |
| 【人工处理】(全栈) Agent 查看转人工上下文 | 1. 工单详情展示 AI 会话摘要<br>2. Agent 继续使用现有公开回复/内部备注/状态能力<br>3. Customer 显示工单编号和处理状态 | Agent 人工处理、接口定义 | 1 |
| 【回归验收】(全栈) 权限、咨询和转人工测试 | 1. 三角色导航和直达路由测试<br>2. Customer RAG 咨询和来源裁剪测试<br>3. 有/无可用 Agent 转人工和重复点击测试 | 风险与权衡 | 1.5 |
| **合计** |  |  | **8** |

### 任务依赖

```text
【权限收敛】
【在线咨询】 -> 【咨询会话】 -> 【转人工】 -> 【人工处理】 -> 【回归验收】
【权限收敛】 ----------------------------------------------^
```

## Verify

设计自检：

- [x] Delta Spec 的 Admin-only 知识库、Customer 在线咨询、AI RAG、转人工和 Agent 处理均有技术方案。
- [x] 接口定义到路径、入参和出参级，内部方法到签名级，未写实现代码。
- [x] 未新增排班、复杂团队、SLA 或人工即时 IM。
- [x] 分派策略、幂等策略、来源裁剪和路由权限均有明确测试点。
- [x] 任务拆分覆盖前端、后端和回归验收，单项不超过 2 人天。

## Impact

- 前端：侧边栏和路由权限变化；Customer 新增全局浮窗；知识库页面仅管理者可见。
- 后端：AI conversation 增加 Customer 专用入口和 handoff-ticket；Ticket service 增加从会话创建工单与自动分派路径。
- 数据库：优先复用现有 conversation 和 ticket 字段；只需补充审计枚举/动作，不新增核心表。
- 测试：新增权限收敛、Customer 在线咨询、RAG 来源、转人工分派和幂等测试。
