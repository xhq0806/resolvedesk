# Design: Conversation Avatars

## 背景与现状

- `User` 模型仅包含 `email/full_name/role/is_active` 等基础字段。
- 前端已有 `Avatar/AvatarImage/AvatarFallback` UI 组件，但当前大多只用 fallback。
- 在线咨询消息是前端本地 `ChatMessage` 状态，不依赖后端消息作者摘要。
- 工单响应通过 `UserSummary` 嵌入 requester、assignee、message author 和 audit actor。

## 设计目标

- 用最小数据模型变更支持所有登录角色设置头像。
- 复用现有 Avatar 组件，不引入上传链路。
- 让头像随现有用户/工单 API 自然返回，避免新增专用头像接口。

## 非目标

- 不实现文件上传、图片处理、访问签名或 Workspace 级头像。
- 不新增 AI Agent 后台头像配置。

## 技术方案

### 数据模型

- `backend/app/models/user.py`
  - `User.avatar_url: str | None = Field(default=None, max_length=2048)`
- Alembic 新增迁移：
  - 给 `"user"` 表增加可空 `avatar_url` 字段。

### API Schema

- `UserUpdateMe` 增加 `avatar_url`。
- `UserPublic` 增加 `avatar_url`。
- `UserSummary` 增加 `avatar_url`，使工单列表和时间线自然获得头像。
- 增加 URL 规范化：空字符串转 `None`；非 `http://` / `https://` 拒绝。

### 前端

- 新增 `UserAvatar` 组件统一处理图片、首字母和加载失败 fallback。
- `UserInformation` 增加头像 URL 输入和预览。
- `Sidebar/User` 使用 `UserAvatar`。
- `TicketColumns` 和 `TicketTimeline` 使用 `UserAvatar`。
- `CustomerSupportWidget` 消息布局改为头像 + 气泡；用户消息靠右，AI 消息靠左；AI 使用固定品牌头像样式。

## 关键决策

- 选择 URL 字段而非上传：当前系统没有附件头像域、对象存储或图片处理链路，URL 字段能快速满足头像设置与展示。
- 选择嵌入 `UserSummary`：工单视图已经依赖摘要对象，扩展字段比新增查询更简单。
- AI 头像前端固定：当前 AI Agent 没有独立后台配置实体面向 UI，固定头像可先满足区分度。

## 风险与权衡

- 外链图片可能失效或加载慢，因此所有头像展示必须保留 fallback。
- URL 未做代理，浏览器会直接请求外链图片；第一版只做展示，不做隐私代理。

## 任务拆分

- [ ] 后端模型、schema、迁移增加 `avatar_url`。
- [ ] 前端 client 类型同步 `avatar_url`。
- [ ] 设置页支持头像 URL 编辑与预览。
- [ ] 侧边栏、工单列表、工单时间线、在线咨询展示头像。
- [ ] 构建、类型检查、数据库迁移、容器健康检查和归档。
