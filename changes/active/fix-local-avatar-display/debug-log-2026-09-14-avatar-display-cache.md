# Debug Log: Avatar Display Cache

## 问题

用户上传本地头像后，资料页、侧边栏和在线咨询消息仍显示首字母兜底。

## 排查步骤

- [x] 查看截图症状：资料页显示“未设置”，侧边栏和在线咨询仍显示首字母。
- [x] 搜索头像展示链路：`UserInformation`、`UserAvatar`、`userAvatarApi`、`useAuth`。
- [x] 查询数据库 `user.avatar_url`，确认当前截图状态下用户头像地址为空。
- [x] 复测接口：上传后 `POST /users/me/avatar` 返回 `avatar_url`，`GET /users/me` 能读取同一地址，公开图片读取返回 `image/png`。
- [x] 检查前端状态同步：上传成功后只 `invalidateQueries()`，没有立即写回 `currentUser` 缓存。

## 假设与验证

| 假设 | 置信度 | 验证结果 |
|---|---:|---|
| 后端没有保存头像地址 | 中 | 接口复测显示上传后 `/users/me` 返回同一 `avatar_url`，排除 |
| 图片公开读取失败 | 中 | 公开读取返回 200 和 `image/png`，排除 |
| 前端 currentUser 缓存未及时更新 | 高 | 三处展示均依赖 `useAuth()` 的 `currentUser.avatar_url`，上传成功后未写缓存，符合症状 |

## 根因

头像上传成功后，前端只调用 `queryClient.invalidateQueries()`，依赖异步 refetch 更新当前用户资料；但侧边栏、资料页和在线咨询都立即读取旧的 `currentUser` 缓存，因此继续显示首字母兜底。

## 修复

在 `UserInformation` 的头像上传和清除 mutation 成功回调中，使用接口返回的 `UserPublic` 直接写入 `queryClient.setQueryData(userKeys.current, updatedUser)`。

## 验证

- `bun run build` 通过。
- `git diff --check` 通过。
- `docker compose -f compose.yml -f compose.override.yml up -d --build backend` 通过。
- 上传、读取 `/users/me`、公开读取头像、清除头像接口验证通过。
