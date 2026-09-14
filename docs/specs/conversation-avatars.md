# Conversation Avatars

> 归档日期: 2026-09-14
> 原始 spec: `changes/archive/2026-09-14-conversation-avatars/spec.md`

## 功能描述

ResolveDesk 支持所有登录角色在个人资料中设置头像并在会话、工单和侧边栏展示。当前头像来源已由本地上传规格接管，详见 [local-avatar-upload.md](local-avatar-upload.md)。AI Agent 在在线咨询中使用固定系统头像，并以可见 `AI` 文本作为兜底。

## 核心流程

1. 用户进入设置页，在个人资料中查看头像并通过本地上传规格管理头像图片。
2. 后端将系统生成的 `avatar_url` 写入用户表，并在 `UserPublic` 和工单 `UserSummary` 中返回。
3. `avatar_url` 作为展示契约保留，不再作为用户手填外链输入。
4. 前端侧边栏用户菜单使用当前用户头像；缺失或加载失败时显示姓名/邮箱首字母。
5. 工单列表的客户/负责人列、工单时间线的消息与审计节点使用用户摘要中的头像。
6. Customer 在线咨询中，用户消息显示当前用户头像，AI 回复显示固定 AI 头像。
7. AI 头像兜底可见显示 `AI`，不依赖外部图片资源。

## 边界约束

- `avatar_url` 是可选用户公开资料字段。
- 当前版本不接受用户手填外链 URL。
- 本能力不提供图片裁剪、对象存储、CDN 或 Workspace 级独立头像。
- 头像加载失败不得阻断工单、时间线或在线咨询渲染。
- 本能力不改变角色权限、工单可见范围或 AI Agent 工具权限。

## 代码索引

### 关键文件

| 文件路径 | 职责 |
|----------|------|
| `backend/app/models/user.py` | 用户模型新增 `avatar_url` 字段 |
| `backend/app/schemas/user.py` | 当前用户资料更新不接受头像外链，公开用户响应包含头像读取地址 |
| `backend/app/schemas/ticket.py` | 工单 `UserSummary` 返回用户头像 URL |
| `backend/app/alembic/versions/b1c2d3e4f5a6_add_user_avatar_url.py` | 用户表头像 URL 迁移 |
| `frontend/src/components/Common/UserAvatar.tsx` | 通用用户头像和 AI 头像组件 |
| `frontend/src/components/UserSettings/UserInformation.tsx` | 个人资料页头像上传、清除和预览 |
| `frontend/src/components/Sidebar/User.tsx` | 侧边栏用户菜单头像展示 |
| `frontend/src/components/Tickets/TicketColumns.tsx` | 工单列表客户/负责人头像展示 |
| `frontend/src/components/Tickets/TicketTimeline.tsx` | 工单时间线消息/审计头像展示 |
| `frontend/src/components/AI/CustomerSupportWidget.tsx` | 在线咨询用户和 AI 消息头像展示 |

### 接口定义

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/users/me/avatar` | POST/DELETE | 上传或清除当前用户头像 |
| `/api/v1/users/{user_id}/avatar` | GET | 公开读取用户头像图片 |
| `/api/v1/users/me` | GET | 返回当前用户的 `avatar_url` |
| `/api/v1/tickets` / `/api/v1/tickets/{ticket_id}` | GET | 工单用户摘要携带 `avatar_url` |

### 涉及项目

| 项目 | 角色 | 说明 |
|------|------|------|
| `backend` | 后端服务 | 用户模型、schema、迁移、工单摘要 |
| `frontend` | 前端应用 | 头像设置、通用头像组件、工单和在线咨询展示 |
