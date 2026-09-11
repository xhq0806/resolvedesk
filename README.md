# ResolveDesk

ResolveDesk 是一个单工作空间客服支持平台，用于管理从问题提交到解决关闭的完整工单流程。

当前版本提供三类角色的完整协作流程：

- `CUSTOMER` 创建工单、跟踪处理进度并发送公开回复。
- `AGENT` 使用客服队列，接手工单、回复客户并添加内部备注。
- `ADMIN` 管理用户和角色，查看全部工单，分派工作，关闭已解决工单并保留操作审计记录。

当前全栈版本聚焦于稳定的人工客服流程。AI Copilot、知识库、实时聊天、文件附件、SLA 自动化和多租户工作空间暂不属于当前范围。

## 功能特性

- 工单创建、筛选、搜索、服务端分页和详情查看。
- 工单状态流转：待处理、处理中、等待客户、已解决、已关闭。
- 公开回复和按角色隔离的内部备注。
- 客服队列、原子接手，以及 Admin 分派、转派和取消分派。
- 按角色展示的 Dashboard 和工单统计。
- Admin 用户管理，包括角色修改、启用/停用和最后一个活跃 Admin 保护。
- 工单软删除，同时保留删除审计记录。
- 基于邮件的密码找回和本地 Mailpit 邮件调试。
- 基于后端 OpenAPI 契约生成并由前端使用的 TypeScript 客户端。
- PostgreSQL、Alembic 迁移、Docker Compose、Pytest、Playwright 和 GitHub Actions。

## 技术栈

- 后端：FastAPI、SQLModel、PostgreSQL、Alembic、Pydantic、JWT 鉴权。
- 前端：React、TypeScript、Vite、TanStack Router、TanStack Query、TanStack Table、Tailwind CSS 和 shadcn/ui。
- 本地服务：Docker Compose、PostgreSQL、Mailpit、Adminer 和 Traefik。
- 部署方式：FastAPI Cloud 或自托管 Docker Compose。

## 快速开始

### 环境要求

- Python 3.14 或更高版本
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- [Docker](https://www.docker.com/)

### 启动开发环境

仓库中的 `.env` 文件包含本地开发默认配置。在本地环境之外使用前，请修改其中的密码和密钥。

在项目根目录启动 PostgreSQL 和 Mailpit：

```bash
docker compose up -d db mailpit
```

在一个终端中准备并启动后端：

```bash
cd backend
uv sync
uv run bash scripts/prestart.sh
uv run fastapi dev
```

在另一个终端中安装依赖并启动前端：

```bash
bun install
bun run dev
```

打开 <http://localhost:5173> 访问应用。后端 API 地址为 <http://localhost:8000>，Swagger UI 地址为 <http://localhost:8000/docs>，Mailpit 地址为 <http://localhost:8025>。

本地初始 Admin 账号由 `.env` 中的 `FIRST_SUPERUSER` 和 `FIRST_SUPERUSER_PASSWORD` 配置。环境变量名称为了兼容现有初始化脚本而保留，但创建出的账号角色为 `ADMIN`。

### 使用 Docker Compose 启动

构建镜像、准备数据库并启动应用：

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend adminer
```

应用和 API 地址为 <http://localhost:8000>。Adminer 地址为 <http://localhost:8080>，Traefik 地址为 <http://localhost:8090>，Mailpit 地址为 <http://localhost:8025>。

## 测试与质量检查

运行后端测试和覆盖率检查：

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

Playwright 测试要求 Docker Compose 环境已经启动。完整浏览器测试流程请参阅 [frontend/README.md](./frontend/README.md)。

## 项目结构

```text
backend/
  app/api/          HTTP 路由和依赖
  app/models/       SQLModel 实体和领域枚举
  app/schemas/      API 请求和响应模型
  app/repositories/ 数据库查询和按角色过滤
  app/services/     工单、用户、统计和审计流程
  tests/            后端单元、集成、迁移和 API 测试
frontend/
  src/routes/       TanStack Router 页面和角色守卫
  src/components/   通用 UI、工单、队列和 Admin 组件
  src/client/       自动生成的 OpenAPI 客户端
  tests/             Playwright 端到端测试
packages/react-email/
  邮件源组件和导出工具
```

## 相关文档

- [开发指南](./development.md)
- [后端指南](./backend/README.md)
- [前端指南](./frontend/README.md)
- [FastAPI Cloud 部署](./deployment.md)
- [Docker Compose 部署](./deployment-docker-compose.md)
- [系统行为规格](./SYSTEM-SPEC.md)
- [贡献指南](./CONTRIBUTING.md)

## 许可证

ResolveDesk 使用 MIT 许可证。
