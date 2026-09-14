# Customer 在线咨询 404 排查记录

> 时间：2026-09-14
> 类型：运行态后端未加载新路由

## 排查步骤

- [x] 根据截图确认前端请求路径：`GET /api/v1/workspaces/{workspace_id}/customer/conversation`
- [x] 检查本地源码，确认 `backend/app/api/routes/ai.py` 已定义 `customer_router`
- [x] 检查 `backend/app/api/main.py`，确认源码已 include `ai.customer_router`
- [x] 查询运行中后端的 `/api/v1/openapi.json`，发现只包含旧 `/conversations` 路由，不包含 `/customer/conversation`
- [x] 进入 Docker 后端容器检查 Python 模块，发现容器内 `app.api.routes.ai` 没有 `customer_router`
- [x] 重建并重启 backend 容器
- [x] 再次查询 OpenAPI，确认 `/customer/conversation` 和 `/handoff-ticket` 已出现

## 假设与验证

| 假设 | 置信度 | 验证结果 |
|---|---:|---|
| 前端 URL 写错 | 低 | 源码和设计路径一致，且新 OpenAPI 已包含相同路径 |
| 后端源码未注册路由 | 中 | 本地源码已注册 `api_router.include_router(ai.customer_router)` |
| 运行中的后端容器仍是旧代码 | 高 | 容器内 `hasattr(ai, "customer_router") == False`，运行中 OpenAPI 没有 customer 路由 |

## 根因链路

1. 用户点击右下角“在线咨询”。
2. 前端正确请求 `/api/v1/workspaces/{workspace_id}/customer/conversation`。
3. 运行中的后端容器仍使用旧镜像代码，旧代码没有 `customer_router`。
4. FastAPI 路由表无法匹配该路径，因此返回 404。

## 修复方案

执行：

```bash
docker compose -f compose.yml -f compose.override.yml up -d --build backend
```

理由：当前 compose 配置没有把源码直接挂载到 `/app/backend`，`develop.watch` 只有在使用 `docker compose watch` 时才会同步源码。普通运行模式下，后端代码变更必须重建 backend 镜像并重启容器。

## 验证结果

- `/api/v1/openapi.json` 已包含：
  - `/api/v1/workspaces/{workspace_id}/customer/conversation`
  - `/api/v1/workspaces/{workspace_id}/customer/conversation/messages/stream`
  - `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/handoff-ticket`
- 健康检查 `GET /api/v1/utils/health-check/` 返回 200。
- 使用 Admin 账号直接请求 Customer 接口返回 403，说明路由已存在且角色权限生效，不再是 404。
