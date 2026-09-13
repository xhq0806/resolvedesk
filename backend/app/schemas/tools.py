"""AI Agent 工具白名单 Schema。by AI.Coding"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.user import StrictInput


class ToolPermissionPatch(StrictInput):
    """更新单个工具启用状态。by AI.Coding"""

    tool_name: str = Field(min_length=1, max_length=80)
    enabled: bool


class ToolPermissionPublic(BaseModel):
    """工具权限公开状态，不包含内部凭据。by AI.Coding"""

    tool_name: str
    enabled: bool

