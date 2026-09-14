# Provider 配置按钮无反馈排查记录

## 现象

在 AI Provider 页面填写 Workspace UUID、Chat/Embedding 配置和 API Key 后，点击“保存配置”“测试 Chat”“测试 Embedding”，页面没有可见反馈。

## 排查步骤

- 检查 `frontend/src/components/AI/ProviderSettings.tsx`：保存和测试 mutation 只有成功后的缓存更新，没有 `onError`，页面只在测试成功返回后渲染结果。
- 检查 `frontend/src/lib/aiApi.ts`：非 2xx 响应只抛出状态码错误，未解析后端 `message/detail`。
- 检查运行中 backend 的 OpenAPI：旧容器不包含 `/api/v1/workspaces/{workspace_id}/ai/provider` 和 `/provider/test` 路由。
- 重建 backend 镜像并重启容器：AI Provider 路由已出现在 OpenAPI，GET 配置接口返回 200。
- 使用未配置 API Key 的 Workspace 调用测试接口：后端返回结构化结果 `PROVIDER_UNAVAILABLE / Provider 配置不完整。`，证明接口并非静默。

## 根因链

1. 旧 backend 容器运行的是未包含二期 AI 路由的镜像，前端请求会收到 404。
2. 前端请求封装和 Provider 页面没有展示失败 mutation，因此 404/409/网络错误都表现为“没有反应”。
3. 这是部署镜像未更新与前端错误反馈缺失的组合问题，不是 Workspace UUID 本身的格式问题。

## 修复方案

- `frontend/src/lib/aiApi.ts`
  - 解析后端 JSON 错误中的 `message` 或 `detail`。
  - 无结构化响应时保留 HTTP 状态码。
- `frontend/src/components/AI/ProviderSettings.tsx`
  - 增加保存/测试的成功和失败回调。
  - 增加按钮 loading 文案和页面反馈。
  - 通过现有 Toast 展示错误，避免失败时静默。
- 重建并重启 `backend` 容器，使 API 路由和最新前端静态资源生效。

## 验证结果

- 前端 `tsc -p tsconfig.build.json --noEmit`：通过。
- 前端 `bun run build`：通过。
- backend OpenAPI：包含 Provider 配置和测试路由。
- 未配置 API Key 的测试请求：返回预期 `PROVIDER_UNAVAILABLE` 结构化结果。

