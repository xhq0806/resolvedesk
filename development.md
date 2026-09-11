# ResolveDesk 开发指南

## 本地开发

本地开发时，使用 Docker Compose 运行 PostgreSQL 和 Mailpit，同时在本机运行 ResolveDesk 的 FastAPI API 和 Vite 前端。

先启动依赖服务：

```bash
docker compose up -d db mailpit
```

然后进入 `backend` 目录，安装依赖并准备数据库：

```bash
uv sync
uv run bash scripts/prestart.sh
```

启动 ResolveDesk API：

```bash
uv run fastapi dev
```

在另一个终端中，从项目根目录安装前端依赖并启动 Vite 开发服务器：

```bash
bun install
bun run dev
```

现在可以打开这些地址：

前端开发服务器：<http://localhost:5173>

后端 API：<http://localhost:8000>

Swagger UI 自动交互式 API 文档：<http://localhost:8000/docs>

Mailpit: <http://localhost:8025>

前端开发服务器会按照 `frontend/.env` 配置使用 `http://localhost:8000` 作为后端地址。

### 由 API 托管前端

在 `frontend` 目录中构建前端：

```bash
bun run build
```

构建产物会写入 `backend/app/frontend`，并由 ResolveDesk API 在 <http://localhost:8000> 提供访问。修改前端后需要重新构建。

## 使用 Docker Compose 运行全栈

使用 Docker Compose 运行后端和已构建前端：

```bash
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

现在可以打开这些地址：

ResolveDesk（前端和 API 均由 FastAPI 托管）：<http://localhost:8000>

Swagger UI 自动交互式 API 文档：<http://localhost:8000/docs>

Adminer 数据库 Web 管理界面：<http://localhost:8080>

Traefik UI，用于查看代理如何处理路由：<http://localhost:8090>

Mailpit: <http://localhost:8025>

启动 Compose 后端前，请先停止本机正在运行的 API 服务，因为两者都会占用 `8000` 端口。

**注意**：首次启动整套服务时，所有服务完全就绪可能需要一分钟左右。可以使用 `docker compose logs` 查看整体日志，或使用 `docker compose logs backend` 查看后端服务日志。

## Mailpit

[Mailpit](https://mailpit.axllent.org) 会拦截本地开发期间发送的邮件，而不会真正投递。 本机后端通过 `localhost:1025` 连接 Mailpit，Compose 后端通过 `mailpit` 服务名连接。捕获的邮件可在 <http://localhost:8025> 查看。

## Docker Compose 文件和环境变量

主文件 `compose.yml` 包含整套服务共享的配置，Docker Compose 会自动加载它。

`compose.override.yml` 添加本地开发设置，例如把源代码挂载为 volume。Docker Compose 也会自动加载它，并覆盖到 `compose.yml` 之上。

`compose.deploy.yml` 包含部署专用设置，包括 HTTPS 和证书自动处理。部署应用时需要显式地把它和 `compose.yml` 一起使用。

后端会从 `.env` 文件读取本地配置。Docker Compose 也会使用它做变量插值，并把各容器需要的配置传入容器。

修改变量后，请重启服务：

```bash
docker compose watch
```

## `.env` 文件

仓库中跟踪的 `.env` 文件包含本地开发默认值，包括占位密码和其他配置。它的主机名使用 `localhost`，适用于本机直接运行的进程。Docker Compose 会把数据库、SMTP 服务器等主机名覆盖为对应的 Compose 服务名。

不要把部署密钥保存在 `.env` 中。请按照 [FastAPI Cloud 部署指南](./deployment.md) 或 [Docker Compose 部署指南](./deployment-docker-compose.md) 配置部署环境。

## Pre-commit Hook 和代码检查

项目使用 [prek](https://prek.j178.dev/) 做代码检查和格式化。它是 [pre-commit](https://pre-commit.com/) 的现代替代方案。

项目根目录下的 `.pre-commit-config.yaml` 包含相关配置。

### 安装 `prek` 以自动运行

`prek` 已经包含在项目依赖中。

在项目根目录安装 Git hook，让 `prek` 在每次提交前自动运行：

```bash
uv run prek install -f
```

`-f` 参数会强制安装，用于覆盖之前可能已经存在的 `pre-commit` hook。

之后每次尝试提交，例如运行：

```bash
git commit
```

`prek` 都会检查并格式化即将提交的代码。如果它修改了文件，请重新把这些文件加入 Git 后再提交。

### 手动运行 `prek`

也可以在项目根目录手动对所有文件运行 `prek`：

```bash
uv run prek run --all-files
```
