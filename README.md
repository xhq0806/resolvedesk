# ResolveDesk

ResolveDesk 是一个以 **Workspace 为隔离边界** 的客服支持平台。客户可以先通过 AI Agent 在线咨询；AI Agent 使用当前 Workspace 的知识库回答问题。当客户需要人工服务时，系统会将 AI 会话幂等转换为工单，并优先分派给当前 Workspace 中负载最低的可用人工客服。

平台同时覆盖人工客服工单的创建、接手、分派、回复、状态流转、审计和关闭，并提供 Workspace 管理、知识库摄取、RAG 检索、SSE 流式输出、AI 工具白名单和本地头像/附件能力。

## 核心能力

### Workspace 与权限

- 用户可以在自己所属的 ACTIVE Workspace 之间切换。
- 所有工单、消息、审计、知识文档、AI Provider、AI 会话、附件和工具授权都归属于 Workspace。
- API 请求通过 `X-Workspace-ID` 绑定当前 Workspace，并校验成员关系；跨 Workspace 访问统一返回资源不存在错误，不泄露资源存在性。
- 角色包括 `CUSTOMER`、`AGENT`、`ADMIN` 和 `OWNER`。`AGENT` 是人工客服，AI Agent 是 Workspace 内独立的执行主体。

### 客服工单

- Customer 创建、筛选、搜索和回复自己的工单。
- Agent 处理公共队列或分派给自己的工单，可以接手、回复、添加内部备注并更新状态、优先级和分类。
- Admin/Owner 查看当前 Workspace 全部工单，负责分派、转派、取消分派、关闭、删除和审计。
- 状态流转为 `OPEN` → `IN_PROGRESS` → `WAITING_FOR_CUSTOMER` → `RESOLVED` → `CLOSED`；`CLOSED` 工单只读。
- 内部备注按角色裁剪；工单删除采用软删除，历史审计仍保留。

### AI 客服与 RAG

- Customer 登录后可从右下角“在线咨询”打开 AI 会话，不离开当前页面。
- Admin/Owner 在 AI 工作台配置 Chat/Embedding Provider、模型、Base URL、API Key 和 AI 工具白名单，并可执行连接测试。
- 支持 OpenAI-compatible Provider 和火山方舟 Provider。API Key 只在服务端加密保存，公开配置不会回显密钥原文。
- Admin/Owner 可上传 `PDF`、`DOCX`、`Markdown` 和 `TXT` 文档。系统创建摄取任务，解析文本、切块并写入 PostgreSQL `pgvector`；文档状态包括 `PROCESSING`、`READY`、`FAILED` 和 `DELETED`，失败任务可以重试。
- AI 回答只检索当前 Workspace 的 `READY` 文档。Customer 看到的是回答和来源摘要，不会获得知识库管理权限或完整后台文档。
- AI 消息通过 Server-Sent Events（SSE）流式返回，事件包含来源发现、文本增量、完成和失败状态；服务端持久化 Conversation、Run 和消息终态，支持取消和断线清理。

### 转人工与自动分派

- Customer 可以点击“转人工”，或在对话中表达明确的人工服务意图。
- 系统把最近问题、AI 回复摘要和转人工原因写入工单，并把 Conversation 与工单关联。
- 同一 Conversation 重复转人工始终返回同一个工单，不创建重复工单。
- 自动分派只选择当前 Workspace 中 ACTIVE 成员、全局账号 active 且角色为 `AGENT` 的用户，按未关闭负责工单数最少的顺序选择。
- 有可用 Agent 时，工单进入 `IN_PROGRESS`；没有可用 Agent 时，工单保持 `OPEN` 并进入公共队列。创建、分派和未分派都会写入审计。

### 个人资料与文件

- 所有登录角色都可以上传、替换或清除自己的本地头像；支持 PNG、JPG/JPEG 和 WebP，最大 2 MB。
- 头像读取地址可由浏览器直接访问，缺失或加载失败时显示姓名/邮箱首字母；AI 头像使用可见的 `AI` 兜底。
- 工单附件按 Workspace 隔离保存，上传和读取受工单权限控制。

## 角色入口

| 角色 | 主要入口 | 能力边界 |
| --- | --- | --- |
| `CUSTOMER` | 工作台、我的工单、设置、在线咨询 | 只能查看自己的工单和公开消息；不能访问知识库、AI Provider 或内部备注 |
| `AGENT` | 工作台、客服队列、设置 | 只能处理公共队列和自己负责的工单；不能管理用户、知识库或 AI 配置 |
| `ADMIN` / `OWNER` | 工作台、AI 工作台、知识库、全部工单、用户管理、设置 | 管理当前 Workspace 的成员、工单、知识库、Provider、工具权限和审计 |

## 技术架构

- **后端**：FastAPI、SQLModel、Pydantic、Alembic、JWT Bearer 鉴权。
- **数据层**：PostgreSQL 17 + `pgvector`，Workspace 级索引和隔离查询。
- **AI 层**：Chat/Embedding Provider 适配器、知识解析与切块、向量检索、AI Conversation/Run、SSE 流、工具执行白名单。
- **前端**：React、TypeScript、Vite、TanStack Router、TanStack Query、TanStack Table、Tailwind CSS、shadcn/ui。
- **本地服务**：Docker Compose、PostgreSQL、Mailpit、Adminer、Traefik。
- **契约**：后端 OpenAPI 生成 `frontend/src/client/` TypeScript 客户端；不要维护第二套手写业务 API。

典型请求链路：

```text
Customer 在线咨询
  -> Workspace 鉴权
  -> 当前 Workspace READY 文档向量检索
  -> Chat Provider
  -> SSE source.found / message.delta / completed
  -> 需要人工时创建工单并自动分派
```

## 快速开始

### 环境要求

- Python 3.14 或更高版本
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- [Docker](https://www.docker.com/)

### 启动开发环境

仓库根目录的 `.env` 提供本地开发默认值。离开本地环境前，请修改密码、`SECRET_KEY` 和初始管理员密码。

先启动 PostgreSQL 和 Mailpit：

```bash
docker compose up -d db mailpit
```

在一个终端准备并启动后端：

```bash
cd backend
uv sync
uv run bash scripts/prestart.sh
uv run fastapi dev
```

在另一个终端安装依赖并启动前端：

```bash
bun install
bun run dev
```

访问以下地址：

- 前端：<http://localhost:5173>
- API：<http://localhost:8000>
- Swagger UI：<http://localhost:8000/docs>
- Mailpit：<http://localhost:8025>

初始 Admin 账号由 `.env` 中的 `FIRST_SUPERUSER` 和 `FIRST_SUPERUSER_PASSWORD` 配置。登录后，Admin/Owner 可在设置页配置 AI Provider；AI 能力不依赖额外的根级环境变量。

### 使用 Docker Compose 启动全栈

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend adminer
```

访问应用 <http://localhost:8000>，以及 Adminer <http://localhost:8080>、Traefik <http://localhost:8090> 和 Mailpit <http://localhost:8025>。

## AI 配置与 API

AI Provider 配置在当前 Workspace 内保存。启用前必须同时提供 Chat 和 Embedding 的 Base URL、模型、1024 维 Embedding 配置以及 API Key；设置页可分别测试 Chat 和 Embedding 连通性。

主要接口如下（完整契约以 <http://localhost:8000/api/v1/openapi.json> 为准）：

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/workspaces` | 列出当前用户可切换的 Workspace |
| `GET/PATCH /api/v1/workspaces/{workspace_id}/ai/provider` | 读取或更新脱敏 Provider 配置 |
| `POST /api/v1/workspaces/{workspace_id}/ai/provider/test` | 测试 Chat 或 Embedding Provider |
| `GET/PATCH /api/v1/workspaces/{workspace_id}/ai/tools` | 查看或更新 AI 工具白名单 |
| `GET/POST /api/v1/workspaces/{workspace_id}/knowledge/documents` | 列出或上传知识文档 |
| `POST /api/v1/workspaces/{workspace_id}/knowledge/search` | 检索当前 Workspace 的 READY 文档 |
| `POST /api/v1/workspaces/{workspace_id}/customer/conversation/messages/stream` | Customer 专用 RAG + SSE 在线咨询 |
| `POST /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/handoff-ticket` | 将 AI 会话幂等转为人工工单并尝试自动分派 |

## 测试与质量检查

运行后端测试、lint、类型检查和格式检查：

```bash
cd backend
uv run bash scripts/test.sh
```

运行前端检查：

```bash
bun run --filter frontend lint
bun run --filter frontend build
bun run --filter frontend test
```

Playwright 测试需要先启动 Docker Compose。完整浏览器测试说明见 [frontend/README.md](./frontend/README.md)。当前验收基线包括后端 `170 passed`、Playwright `56 passed`，以及 OpenAPI、Docker Compose 和数据库迁移检查通过；具体结果以当前 CI 和本地运行结果为准。

## 项目结构

```text
backend/
  app/api/routes/       HTTP 路由：Workspace、Ticket、AI、知识库、附件和用户
  app/models/           SQLModel 实体、Workspace/AI/知识库/工单枚举
  app/schemas/          API 请求和响应模型
  app/repositories/     Workspace 隔离查询、分页、检索和聚合
  app/services/         工单状态机、AI 会话、Provider、RAG、分派和审计
  app/providers/        Chat 与 Embedding Provider 适配器
  app/workers/          知识文档摄取任务领取与执行
  tests/                单元、API、迁移、并发、OpenAPI 和集成测试
frontend/
  src/routes/            TanStack Router 页面和角色守卫
  src/components/        AI、知识库、Workspace、工单、队列和 Admin UI
  src/lib/                Workspace、AI、工单查询和 API 封装
  src/client/             由 OpenAPI 生成的 TypeScript 客户端
  tests/                  Playwright 端到端测试
packages/react-email/     邮件源组件和导出工具
```

## 相关文档

- [开发指南](./development.md)
- [后端指南](./backend/README.md)
- [前端指南](./frontend/README.md)
- [FastAPI Cloud 部署](./deployment.md)
- [Docker Compose 部署](./deployment-docker-compose.md)
- [系统行为规格](./SYSTEM-SPEC.md)
- [AI Agent 支持型客服协同系统规格](./docs/specs/ai-agent-support-copilot.md)
- [最终验收报告](./changes/active/ai-customer-support-platform/acceptance.md)
- [贡献指南](./CONTRIBUTING.md)

## 当前未覆盖范围

复杂客服组/技能组路由、Agent 排班与在线心跳、SLA 自动升级、满意度评价、邮件收件转工单、计费、生产级合规认证、跨 Workspace 知识共享，以及 AI 删除工单、管理成员或修改 Provider 配置，均不属于当前版本。

## 许可证

ResolveDesk 使用 MIT 许可证。
