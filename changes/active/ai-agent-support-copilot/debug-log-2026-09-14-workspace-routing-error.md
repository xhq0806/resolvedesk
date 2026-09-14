# 工作台与全部工单错误页排查记录

日期：2026-09-14  
范围：工作台 `/`、全部工单 `/admin/tickets`

## 排查步骤

- 查看截图：两个受保护页面都进入统一 ErrorComponent，而不是业务空状态。
- 检查 `_layout`、Dashboard、管理员工单页面：确认页面查询依赖当前用户和工单 API。
- 检查生成的 Axios 客户端：发现 `main.tsx` 只配置 Bearer Token，没有配置 `X-Workspace-ID`。
- 用真实管理员账号调用后端：工单统计和工单列表在携带 `X-Workspace-ID` 时均返回 200；缺少租户上下文时会失败。
- 复核数据库恢复过程：Workspace UUID 曾短暂变化，浏览器 `localStorage` 可能残留旧 UUID，进一步放大问题。

## 根因定位链

受保护页面加载 → 自动生成客户端发送工单请求 → 只有 Authorization，没有 `X-Workspace-ID`（或携带已失效的旧 UUID）→ 后端无法构造 WorkspaceContext → 查询异常被路由 ErrorComponent 渲染为整页“错误”。

## 修复方案

- 在 Axios 请求拦截器中动态读取 `resolvedesk.workspace_id`，为所有生成客户端请求补充 `X-Workspace-ID`。
- 在受保护路由守卫中请求 Workspace 列表，发现 localStorage 中的租户不存在或已停用时自动选择第一个 ACTIVE Workspace，确保子页面查询开始前租户已校正。
- 保留 Workspace 切换器现有的清缓存和刷新行为。
- 新增工作台/全部工单端到端回归测试。

## 验证

- 前端 `bun run build`：通过。
- 新增 Playwright 回归测试：`2 passed`（包含 setup 和目标测试）。
- 真实后端 API：
  - `/api/v1/tickets/statistics`：200
  - `/api/v1/tickets?page=1&page_size=20`：200
- Docker backend 已重新构建并重启。
- 验证期间测试 fixture 会清理连接到本地开发库的测试数据；已重新初始化管理员和默认 Workspace，并确认当前数据库汇总为 1 个管理员、1 个 Workspace、0 个工单。
- 后续核对发现客户 `888@163.com` 和客服 `999@163.com` 没有任何 `workspace_member` 记录；已按其全局角色补回默认 Workspace 的 `CUSTOMER`/`AGENT` 成员关系。
- 使用客户和客服短期测试令牌进行真实浏览器访问：工作台、我的工单、客服队列均正常加载，无错误页。
