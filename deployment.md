# ResolveDesk 部署

可以使用仓库内置的 GitHub Actions 工作流，将 ResolveDesk 部署到 [FastAPI Cloud](https://fastapicloud.com)。

## 创建 FastAPI Cloud 应用

在 FastAPI Cloud 中创建应用，并将 [Application Directory](https://fastapicloud.com/docs/builds-and-deployments/application-directory/) 设置为 `backend`。

使用 [Neon](https://fastapicloud.com/docs/integrations/neon-integration/) 或 [Supabase](https://fastapicloud.com/docs/integrations/supabase-integration/) 集成连接 PostgreSQL 数据库。这两个集成都可以自动配置 `DATABASE_URL` secret。也可以为其他 PostgreSQL 服务商手动配置 `DATABASE_URL`。

## 配置应用

### 环境变量

在 FastAPI Cloud 应用中添加以下必需的 [环境变量](https://fastapicloud.com/docs/builds-and-deployments/environment-variables/)：

* `PROJECT_NAME`：项目名称，用于 API 文档和邮件。
* `FIRST_SUPERUSER`：初始管理员邮箱。环境变量名为了兼容现有初始化脚本而保留。
* `FRONTEND_HOST`：应用的公网 URL，例如生成的 `https://your-app.fastapicloud.dev` 地址或自定义域名。

如需启用邮件，请根据邮件服务商提供的值添加以下可选环境变量：

* `SMTP_HOST`
* `SMTP_USER`
* `EMAILS_FROM_EMAIL`

如需启用 Sentry，请配置 `SENTRY_DSN`。

### Secret

添加以下必需值，并标记为 secret：

* `SECRET_KEY`：用于签发安全令牌的密钥。
* `FIRST_SUPERUSER_PASSWORD`：初始管理员密码。
* `DATABASE_URL`：PostgreSQL 连接 URL；使用数据库集成时会自动配置。

如需使用带认证的邮件服务商，请把 `SMTP_PASSWORD` 添加为 secret。

可以用以下命令为 `SECRET_KEY` 和 `FIRST_SUPERUSER_PASSWORD` 生成安全值：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 配置持续部署

仓库内置的 `.github/workflows/deploy.yml` 会在变更推送到 `master` 时构建前端、准备数据库并部署应用。也可以在 **Actions** 页面手动运行。

登录 FastAPI Cloud，并将 [deploy token](https://fastapicloud.com/docs/advanced-features/deploy-tokens/) 和应用 ID 配置为 GitHub 仓库 secret：

```bash
uv run fastapi login
uv run fastapi cloud setup-ci --secrets-only --app-id <your-app-id>
```

如果已经安装并登录 GitHub CLI，该命令会自动配置 `FASTAPI_CLOUD_TOKEN` 和 `FASTAPI_CLOUD_APP_ID`。否则，它会打印这些值，你可以在仓库的 **Settings** > **Secrets and variables** > **Actions** 中手动添加。

部署前，工作流会运行数据库迁移并创建初始管理员。请在仓库 **Settings** > **Secrets and variables** > **Actions** 页面添加以下 repository variables：

* `PROJECT_NAME`
* `FIRST_SUPERUSER`

添加以下 repository secrets：

* `DATABASE_URL`
* `SECRET_KEY`
* `FIRST_SUPERUSER_PASSWORD`

请使用与 FastAPI Cloud 中一致的配置值。`DATABASE_URL` 使用数据库服务商提供的连接 URL。数据库必须能被 GitHub 托管 runner 访问，这样准备步骤才能连接数据库。

部署工作流会执行以下步骤：

1. 安装前端依赖，并将前端构建到 `backend/app/frontend`。
2. 运行 `backend/scripts/prestart.sh`，应用数据库迁移并创建初始管理员。
3. 使用 `uv run fastapi deploy` 部署项目。

## URL

请将 `your-app.fastapicloud.dev` 替换为你的 FastAPI Cloud 应用 URL。

应用（前端和 API）：`https://your-app.fastapicloud.dev`

交互式 API 文档：`https://your-app.fastapicloud.dev/docs`

## Docker Compose

如果要部署到自己的服务器，请参阅 [Docker Compose 部署指南](./deployment-docker-compose.md)。

## 仓库自动化

仓库包含用于后端测试、Docker Compose 冒烟测试、前端检查、部署、发布准备和 pre-commit 校验的 GitHub Actions。修改 CI 或部署行为前，请先查看 `.github/workflows/` 下的工作流文件。
