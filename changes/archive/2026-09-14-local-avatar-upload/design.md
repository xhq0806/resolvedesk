# Design: Local Avatar Upload

## 背景与现状

- 用户模型已有 `avatar_url` 字段，前端各展示点均基于该字段显示头像。
- 当前资料页使用手填 URL，不符合最终产品口径。
- 现有工单附件服务已有本地文件校验和隔离存储思路，可复用其安全模式。

## 设计目标

- 保留 `avatar_url` 展示契约，仅改变来源为后端生成的本地头像读取地址。
- 上传链路只允许当前登录用户修改自己的头像。
- 头像读取作为公开资料图片开放给浏览器 `<img>` 直接访问。

## 技术方案

### 后端

- `Settings` 增加：
  - `AVATAR_STORAGE_DIR = ./.data/avatars`
  - `AVATAR_MAX_FILE_BYTES = 2 * 1024 * 1024`
- `UserService` 增加：
  - `upload_avatar(actor, upload) -> UserPublic`
  - `delete_avatar(actor) -> UserPublic`
  - `get_avatar_content(user_id) -> tuple[Path, str]`
- 校验：
  - 扩展名：`.png`, `.jpg`, `.jpeg`, `.webp`
  - MIME：`image/png`, `image/jpeg`, `image/webp`
  - Magic number：PNG/JPEG/WebP
- API：
  - `POST /api/v1/users/me/avatar`
  - `DELETE /api/v1/users/me/avatar`
  - `GET /api/v1/users/{user_id}/avatar`

### 前端

- `frontend/src/lib/userAvatarApi.ts` 封装上传与删除。
- `UserInformation` 移除头像 URL 输入，改为文件选择、上传、清除和预览。
- `UserAvatar` 解析 `/api/v1/...` 相对 API 地址，兼容前后端不同域开发模式。

## 风险与权衡

- 第一版不裁剪图片，用户需上传合适比例图片。
- 公开头像读取不鉴权，这是头像作为公开资料字段的产品选择。

## 任务拆分

- [ ] 后端头像本地存储、上传、删除和公开读取接口。
- [ ] 前端上传/删除 API 与资料页 UI。
- [ ] 文档、验证、归档。
