# Verification: Local Avatar Upload

## 已通过

- `bun run build`
- `uv run mypy backend/app --config-file backend/pyproject.toml`
- `uv run pytest tests/services/test_user_service.py`（在 `backend/` 目录运行）
- `docker compose -f compose.yml -f compose.override.yml up -d --build backend`
- `git diff --check`

## 接口验证

在 `http://localhost:8000` 上完成真实接口验证：

- 健康检查 `GET /api/v1/utils/health-check/` 返回 200。
- 使用 `admin@example.com/changethis` 登录成功。
- `POST /api/v1/users/me/avatar` 上传本地 PNG 成功，返回 `/api/v1/users/{user_id}/avatar?version=...`。
- `GET /api/v1/users/{user_id}/avatar?...` 公开读取成功，`Content-Type` 为 `image/png`。
- `PATCH /api/v1/users/me` 携带 `avatar_url` 返回 422，确认旧外链入口关闭。
- `DELETE /api/v1/users/me/avatar` 清除成功，响应中的 `avatar_url` 为 `null`。

## 说明

- 首次接口验证前数据库 `user` 表为空，`admin@example.com/changethis` 登录失败。运行项目自带 `python app/initial_data.py` 后创建了 `.env` 中配置的首个 Admin，随后验证通过。
- 直接在仓库根目录运行 `uv run pytest backend/tests/services/test_user_service.py` 会因为 `.env` 相对路径拿不到后端环境变量而失败；正确方式是在 `backend/` 目录运行 `uv run pytest tests/services/test_user_service.py`。
