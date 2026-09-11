# ResolveDesk 前端

前端是 ResolveDesk 的 React 单页应用，承载客户、客服和管理员三类角色的工作流程。它使用 Vite、TypeScript、TanStack Router、TanStack Query、TanStack Table、Tailwind CSS、shadcn/ui，以及由后端 OpenAPI 契约生成的客户端。

## 环境要求

- [Bun](https://bun.sh/)
- 一个正在运行的 ResolveDesk 后端，用于处理 API 请求

## 本地开发

在项目根目录执行：

```bash
bun install
bun run dev
```

打开 <http://localhost:5173> 访问前端。Vite 开发服务器会读取 `frontend/.env` 中的 `VITE_API_URL`，默认指向 `http://localhost:8000`。

请在另一个终端中启动 PostgreSQL 和 Mailpit，并准备、运行后端。完整流程见 [../development.md](../development.md)。

## 按角色划分的应用区域

- 客户使用 `/tickets` 创建、筛选、搜索和回复自己的工单。
- 客服使用 `/queue` 查看未分派工单、接手工单、回复客户、添加内部备注，并更新自己负责的工单。
- 管理员使用 `/admin/tickets` 进行全局工单管理，使用 `/admin` 管理用户、角色和账号状态。
- 所有已登录用户共用 Dashboard 和账号设置页面。

前端路由守卫用于改善导航体验。权限判定和资源级访问控制仍以后端为准。

## 构建并由 FastAPI 托管

在 `frontend/` 目录中构建前端：

```bash
bun run build
```

构建产物会写入 `backend/app/frontend`，并由 FastAPI 在 <http://localhost:8000> 提供访问。

## 生成 API 客户端

客户端由后端 OpenAPI 契约生成。只要后端 API 变更影响 schema，就需要重新生成：

```bash
bash ./scripts/generate-client.sh
```

当本地工作流产生 `frontend/src/client/` 和 `frontend/.generated-client/` 下的变更时，请一起提交。不要再维护第二套手写 API 客户端。

如果需要手动生成，请先启动后端，将 `/api/v1/openapi.json` 下载到 `frontend/openapi.json`，然后运行：

```bash
bun run generate-client
```

## 代码结构

- `src/routes/` 包含基于文件的路由、URL 筛选状态和角色守卫。
- `src/components/Tickets/` 包含工单列表、详情、时间线、回复、操作和统计组件。
- `src/components/Admin/` 包含用户管理视图。
- `src/components/Common/` 包含共享布局和表格基础组件。
- `src/lib/` 包含查询配置、缓存键和共享工具函数。
- `src/client/` 包含生成的 OpenAPI 客户端。
- `tests/` 包含认证、角色导航、工单、队列和用户管理的 Playwright 端到端测试。

## Lint、构建和端到端测试

在项目根目录运行前端检查：

```bash
bun run --filter frontend lint
bun run --filter frontend build
```

运行 Playwright 测试前，请先启动 Compose 服务：

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend
```

然后运行浏览器测试：

```bash
bun run --filter frontend test
bun run --filter frontend test:ui
```

停止测试服务并删除测试数据：

```bash
docker compose down -v
```
