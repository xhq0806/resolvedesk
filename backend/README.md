# ResolveDesk 后端

后端是一个同步 FastAPI 应用，负责提供 ResolveDesk API；在生产构建中，也会从同一域名提供编译后的前端资源。

## 环境要求

- [Docker](https://www.docker.com/)，用于运行 PostgreSQL 和 Mailpit。
- [uv](https://docs.astral.sh/uv/)，用于 Python 依赖和虚拟环境管理。
- Python 3.14 或更高版本。

## 本地开发

在项目根目录启动配套服务：

```bash
docker compose up -d db mailpit
```

进入 `backend/`，安装依赖、执行数据库迁移并启动 API：

```bash
uv sync
uv run bash scripts/prestart.sh
uv run fastapi dev
```

API 地址为 <http://localhost:8000>。OpenAPI JSON 地址为 <http://localhost:8000/api/v1/openapi.json>，Swagger UI 地址为 <http://localhost:8000/docs>。

## 后端职责

- `app/api/routes/`：声明 HTTP 接口，并将领域错误映射为 API 响应。
- `app/models/`：保存 SQLModel 实体和数据库枚举。
- `app/schemas/`：保存请求、响应、筛选和错误模型。
- `app/repositories/`：负责数据库查询、按角色过滤、分页、条件更新和聚合查询。
- `app/services/`：负责工单状态流转、权限、用户生命周期、统计、事务和审计记录。
- `app/core/`：保存配置、认证、数据库初始化、请求 ID 和错误处理逻辑。
- `tests/`：保存单元、API、迁移、OpenAPI 和集成测试。

当前主要业务资源包括用户、工单、工单消息和工单审计记录。`Item` 已不再属于产品或 API。

## 使用 Docker Compose 运行全栈

在 Docker Compose 中运行后端和构建后的前端：

```bash
docker compose build
docker compose run --rm backend bash scripts/prestart.sh
docker compose up -d --wait backend adminer
```

应用地址为 <http://localhost:8000>。如需进入后端容器，可以执行 `docker compose exec backend bash`。

## 后端测试

在 `backend/` 目录运行后端检查：

```bash
uv run bash scripts/test.sh
```

如果 Docker Compose 环境已经运行，可以直接执行：

```bash
docker compose exec backend bash scripts/tests-start.sh
```

额外的 Pytest 参数会继续传递：

```bash
docker compose exec backend bash scripts/tests-start.sh -x
```

覆盖率报告写入 `backend/htmlcov/`。

## 数据库迁移

修改模型后，在 `backend/` 目录创建并执行 Alembic 迁移：

```bash
uv run alembic revision --autogenerate -m "描述数据库结构变更"
uv run alembic upgrade head
```

请提交 `app/alembic/versions/` 下生成的文件。当前迁移历史包含从模板 `Item` 模型到 ResolveDesk 工单平台的迁移，并会将已有超级管理员映射为 `ADMIN` 角色。

## 邮件模板

邮件源组件位于 `packages/react-email/`。后端实际使用的渲染模板位于 `app/email-templates/`，不应直接手动修改。

在项目根目录预览和导出邮件模板：

```bash
bun run email:dev
bun run email:export
```

密码找回和新账号邮件功能依赖的 SMTP 配置，请参阅[开发指南](../development.md)。
