# Local Avatar Upload

> 归档日期: 2026-09-14
> 原始 spec: `changes/archive/2026-09-14-local-avatar-upload/spec.md`

## 功能描述

ResolveDesk 支持所有登录角色在个人资料中上传本地头像图片。头像文件由后端保存到本地隔离目录，`avatar_url` 仍作为公开资料读取地址返回，用于侧边栏、工单列表、工单时间线和在线咨询消息展示。

## 核心流程

1. 用户进入设置页，在个人资料中选择本地 PNG、JPG/JPEG 或 WebP 图片。
2. 前端通过 `POST /api/v1/users/me/avatar` 以 multipart/form-data 上传图片。
3. 后端校验文件名、大小、MIME 和图片 magic number，通过后保存到头像存储目录。
4. 后端删除同一用户旧头像文件，更新用户 `avatar_url` 为系统生成的公开读取地址。
5. 用户可通过 `DELETE /api/v1/users/me/avatar` 清除头像，前端回退姓名或邮箱首字母。
6. 浏览器通过公开 `GET /api/v1/users/{user_id}/avatar` 读取头像图片；该读取地址不要求 Bearer token。

## 边界约束

- 头像上传和清除必须要求登录。
- 头像读取作为用户公开资料图片开放给浏览器直接加载。
- 第一版不支持手填外链 URL、裁剪、对象存储、CDN 或 Workspace 级独立头像。
- `avatar_url` 是展示契约，来源必须是后端生成的本地读取地址。
- 本能力不改变角色权限、Workspace 边界、工单可见范围或 AI Agent 工具权限。

## 代码索引

### 关键文件

| 文件路径 | 职责 |
|----------|------|
| `backend/app/core/config.py` | 头像存储目录和大小限制配置 |
| `backend/app/api/routes/users.py` | 当前用户头像上传、删除和公开读取路由 |
| `backend/app/services/user_service.py` | 头像文件校验、存储、删除和读取服务 |
| `backend/app/schemas/user.py` | 个人资料 PATCH 不再接受头像外链，公开响应保留 `avatar_url` |
| `frontend/src/lib/userAvatarApi.ts` | 头像上传、清除和相对读取地址解析 |
| `frontend/src/components/UserSettings/UserInformation.tsx` | 个人资料页本地头像选择、预览、上传和清除 |
| `frontend/src/components/Common/UserAvatar.tsx` | 统一解析头像读取地址并展示图片/首字母兜底 |

### 接口定义

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/users/me/avatar` | POST | 上传当前登录用户头像 |
| `/api/v1/users/me/avatar` | DELETE | 清除当前登录用户头像 |
| `/api/v1/users/{user_id}/avatar` | GET | 公开读取用户头像图片 |
| `/api/v1/users/me` | PATCH | 更新姓名和邮箱，不接受 `avatar_url` |

### 涉及项目

| 项目 | 角色 | 说明 |
|------|------|------|
| `backend` | 后端服务 | 头像安全校验、本地存储、公开读取 |
| `frontend` | 前端应用 | 本地上传 UI、预览、头像展示地址兼容 |
