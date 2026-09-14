# AI Agent 支持型客服协同系统

> 归档日期: 2026-09-14
> 原始 spec: `changes/archive/2026-09-14-ai-agent-support-copilot/spec.md`

## 功能描述

ResolveDesk 提供 Workspace 级客服工单与 AI Agent 协同能力。Admin/Owner 管理知识库、AI Provider 和用户；Customer 通过右下角“在线咨询”与 AI Agent 对话；AI Agent 在服务端内部检索当前 Workspace 的 READY 知识文档并给出带来源摘要的回答；客户需要人工服务时，系统将 AI conversation 幂等转换为工单，并优先分派给当前 Workspace 中负载最低的活跃 Agent。

## 核心流程

1. 用户进入受保护页面后，前端根据当前 Workspace 成员角色生成导航；Customer/Agent 不显示知识库入口，Admin/Owner 显示知识库入口。
2. Admin/Owner 进入知识库页面后，可上传、查看、删除和重试知识文档；非 manager 直接访问 `/knowledge` 时不会挂载知识库管理面板，后端接口也拒绝非 manager 请求。
3. Customer 登录后在右下角看到“在线咨询”悬浮按钮；点击后打开咨询面板，面板提供推荐问题、输入框、消息流、来源摘要、失败提示和转人工入口。
4. Customer 首次发送消息时，后端在当前 Workspace 创建或复用该 Customer 的 Workspace 级 AI conversation；消息流复用 SSE run 事件。
5. AI Agent 在服务端内部检索当前 Workspace 的 READY 知识文档，向前端发送 `source.found` 来源摘要和 `message.delta` 文本增量；Customer 不获得知识库管理权限。
6. Customer 点击转人工后，后端校验 conversation 属于当前 Workspace 和当前 Customer；若 conversation 已关联 ticket，则返回原 ticket，避免重复创建。
7. 对未转人工 conversation，后端基于最近客户消息、AI 回复和转人工原因生成工单标题与描述，创建 Customer 工单并写入转人工审计。
8. 自动分派策略只选择当前 Workspace 内 ACTIVE 成员、用户 active、成员角色为 AGENT 的候选人，按未关闭负责工单数升序和稳定顺序选取。
9. 有候选 Agent 时，新工单分派给该 Agent 并进入 `IN_PROGRESS`；无候选 Agent 时，工单保持未分派 `OPEN` 并进入公共队列。
10. Agent 查看被分派或公共队列工单时，可在工单描述中看到转人工上下文，并继续使用公开回复、内部备注、状态、优先级和分类能力。

## 边界约束

- Workspace 是所有工单、知识文档、AI 会话、附件和审计的隔离边界，跨 Workspace 访问不得泄露资源存在性。
- 知识库是后台运营资产，只有 Workspace OWNER/ADMIN 可直接管理；Customer/Agent 不显示入口，也不能调用管理接口。
- Customer 只能通过 AI 回答间接消费知识库来源摘要，不能进入知识库管理页或下载完整后台文档。
- AI Agent 使用的知识来源仅限当前 Workspace 的 READY 文档；文档内容视为不可信资料，不改变系统权限。
- 同一 AI conversation 同时只允许一个 RUNNING run；断流或取消不得保存半条完整 AI 回复。
- 转人工必须幂等；同一 conversation 只能关联一个 handoff ticket。
- 自动分派不得选择 Customer、停用用户、非当前 Workspace 成员或非 ACTIVE 成员。
- Agent 只能处理公共队列和分派给自己的工单，不能管理知识库、Provider、工具权限、用户或其他 Agent 工单。
- AI Agent 不得删除工单、管理成员、修改 Provider 或绕过工具授权。

## 代码索引

### 关键文件

| 文件路径 | 职责 |
|----------|------|
| `backend/app/api/routes/ai.py` | 暴露 Customer conversation、SSE 消息流和 handoff-ticket API |
| `backend/app/services/agent_service.py` | 编排 Customer 会话、RAG 上下文、SSE run 和 conversation 转工单 |
| `backend/app/services/ticket_service.py` | 创建 AI handoff 工单、写转人工与自动分派审计 |
| `backend/app/services/assignment_service.py` | 按当前 Workspace Agent 负载选择自动分派对象 |
| `backend/app/api/routes/knowledge.py` | 知识库文档和检索接口的 manager-only 权限边界 |
| `frontend/src/components/AI/CustomerSupportWidget.tsx` | Customer 右下角在线咨询浮窗、消息流、来源摘要和转人工入口 |
| `frontend/src/components/Sidebar/AppSidebar.tsx` | 基于 Workspace 角色生成侧边栏，知识库仅 Admin/Owner 可见 |
| `frontend/src/lib/routeGuards.ts` | 受保护路由和 Workspace manager 路由守卫 |
| `frontend/src/lib/aiApi.ts` | Customer conversation、SSE 和 handoff-ticket 前端 API 封装 |
| `frontend/src/components/Knowledge/KnowledgePanel.tsx` | 知识库管理面板，使用当前 Workspace 且不允许手输租户 ID |

### 接口定义

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/workspaces/{workspace_id}/customer/conversation` | GET/POST | 获取或创建当前 Customer 的在线咨询会话 |
| `/api/v1/workspaces/{workspace_id}/customer/conversation/messages/stream` | POST | Customer 在线咨询 SSE 消息流，服务端内部执行 RAG |
| `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/handoff-ticket` | POST | 将在线咨询 conversation 幂等转换为工单并尝试自动分派 |
| `/api/v1/workspaces/{workspace_id}/knowledge/documents` | GET/POST | Admin/Owner 知识库文档列表和上传 |
| `/api/v1/workspaces/{workspace_id}/knowledge/search` | POST | Admin/Owner 知识库后台检索；Customer RAG 走服务端内部调用 |

### 涉及项目

| 项目 | 角色 | 说明 |
|------|------|------|
| `backend` | 后端服务 | FastAPI、SQLModel、Workspace 权限、AI/RAG、Ticket、Alembic |
| `frontend` | 前端应用 | React、TanStack Router/Query、侧栏、知识库、在线咨询浮窗 |
