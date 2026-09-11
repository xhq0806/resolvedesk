# ResolveDesk Docker Compose 部署

可以使用 Docker Compose 将项目部署到自己的远程服务器。部署配置包含 Traefik，用于处理 HTTPS，并将外部流量路由到应用。

## 准备工作

* 准备一台可用的远程服务器。
* 配置 DNS 记录，将应用域名以及需要暴露的辅助服务子域名指向该服务器，例如 `resolvedesk.example.com` 和 `adminer.resolvedesk.example.com`。
* 在远程服务器上安装并配置 [Docker](https://docs.docker.com/engine/install/)（Docker Engine，不是 Docker Desktop）。

## 复制代码

```bash
rsync -av --exclude=".git/" --filter=":- .gitignore" ./ root@your-server.example.com:/root/code/app/
```

`--filter=":- .gitignore"` 参数会让 `rsync` 使用与 Git 相同的忽略规则，从而排除 Python 虚拟环境等文件。

## 配置应用

### 环境变量

设置应用域名、项目名称和初始管理员邮箱：

```bash
export DOMAIN=resolvedesk.example.com
export PROJECT_NAME="ResolveDesk"
export FIRST_SUPERUSER=admin@example.com
```

也可以按需配置以下环境变量：

* `SMTP_HOST`：邮件服务商提供的 SMTP 服务器地址。
* `SMTP_USER`：SMTP 服务器用户。
* `EMAILS_FROM_EMAIL`：用于发送邮件的邮箱账号。
* `SENTRY_DSN`：Sentry 的 DSN。

### Secret

为数据库密码、令牌签名密钥和初始管理员密码生成并设置安全值：

```bash
export POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export FIRST_SUPERUSER_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

如需使用带认证的邮件服务商，还需要设置 `SMTP_PASSWORD`。

## 部署

```bash
cd /root/code/app/
docker compose -f compose.yml -f compose.deploy.yml build
docker compose -f compose.yml -f compose.deploy.yml run --rm backend bash scripts/prestart.sh
docker compose -f compose.yml -f compose.deploy.yml up -d
```

`compose.deploy.yml` 会在共享的 `compose.yml` 配置上添加 HTTPS 和证书自动处理。显式列出这两个文件可以避免加载 `compose.override.yml` 中的本地开发配置。

后端 Docker 镜像会构建前端，因此服务器不需要安装 Bun，也不需要提前准备前端构建产物。

## 使用 GitHub Actions 部署

仓库内置的 `.github/workflows/deploy-docker-compose.yml` 工作流会在你从 GitHub Actions 手动触发后，于服务器上运行部署命令。

只有在信任仓库贡献者和工作流代码时，才应使用 self-hosted runner。GitHub 建议在私有仓库中使用 self-hosted runner，因为工作流会直接在 runner 机器上执行。

### 配置仓库变量和 Secret

在仓库中进入 **Settings** > **Secrets and variables** > **Actions**，添加以下 repository variables：

* `DOMAIN`
* `PROJECT_NAME`
* `FIRST_SUPERUSER`

如需启用邮件，添加以下可选 repository variables：

* `SMTP_HOST`
* `SMTP_USER`
* `EMAILS_FROM_EMAIL`

如需启用 Sentry，添加可选的 `SENTRY_DSN` repository variable。

添加以下 repository secrets：

* `POSTGRES_PASSWORD`
* `SECRET_KEY`
* `FIRST_SUPERUSER_PASSWORD`

如需使用带认证的邮件服务商，添加可选的 `SMTP_PASSWORD` repository secret。

### 安装 Self-hosted Runner

在服务器上创建专用用户，并授予其访问 Docker 的权限：

```bash
sudo adduser github
sudo usermod -aG docker github
sudo su - github
```

在 GitHub 仓库中进入 **Settings** > **Actions** > **Runners**，选择 **New self-hosted runner**，选择 Linux，并按照 GitHub 提供的命令下载、配置和注册 runner。建议安装到 `/home/github/actions-runner`。

注册 runner 后，退出 `github` 用户会话，并将 runner 安装为系统服务：

```bash
exit
cd /home/github/actions-runner
sudo ./svc.sh install github
sudo ./svc.sh start
sudo ./svc.sh status
```

更多细节可参考 GitHub 的文档：[添加 self-hosted runner](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) 和 [将 runner 配置为服务](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application?platform=linux)。

### 运行部署

runner 在线后，打开仓库的 **Actions** 页面，选择 **Deploy with Docker Compose**，然后点击 **Run workflow**。

## URL

请将 `resolvedesk.example.com` 替换为你的域名。

应用（前端和 API）：`https://resolvedesk.example.com`

交互式 API 文档：`https://resolvedesk.example.com/docs`

Adminer: `https://adminer.resolvedesk.example.com`
