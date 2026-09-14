# Debug Log: Restrict AI Settings Tabs to Workspace Managers

## Context

- User observed that Customer and Agent settings still displayed `AI Provider`, `知识库`, and `AI 工作台`.
- Product decision: those entries are workspace administration capabilities and should only be visible to `OWNER` / `ADMIN`.

## Root Cause

- The settings page used a static tab list for every authenticated workspace role.
- The sidebar already had role-based navigation, but Agent still inherited `AI 工作台` through the shared staff menu.
- The `/ai` route and one AI tool permission read endpoint did not fully enforce the same manager-only boundary, so hiding UI alone would not be enough.

## Fix

- Settings tabs now derive from the current workspace role:
  - Customer / Agent: `我的资料`, `密码`
  - Owner / Admin: `我的资料`, `密码`, `AI Provider`, `知识库`, `AI 工作台`
- Agent sidebar no longer includes `AI 工作台`.
- `/ai` route now requires workspace manager access.
- AI tool permission listing now requires workspace manager access on the backend.

## Verification

- `bun run build` passed.
- `uv run mypy backend/app --config-file backend/pyproject.toml` passed.
- `git -C D:\resolvedesk diff --check` passed.
- Rebuilt and restarted backend container with the updated frontend bundle.
- Health check returned HTTP 200.
