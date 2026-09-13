"""Workspace、成员和邀请 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.workspace import MembershipStatus, WorkspaceRole, WorkspaceStatus


class WorkspaceCreate(BaseModel):
    """创建 Workspace 请求。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")


class WorkspaceSummary(BaseModel):
    """Workspace 列表摘要。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: WorkspaceStatus
    role: WorkspaceRole


class WorkspaceDetail(WorkspaceSummary):
    """Workspace 详情响应。by AI.Coding"""

    owner_user_id: uuid.UUID
    created_at: datetime


class MemberPublic(BaseModel):
    """Workspace 成员公开响应。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: WorkspaceRole
    status: MembershipStatus
    joined_at: datetime


class InvitationCreate(BaseModel):
    """邀请成员请求。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.CUSTOMER


class InvitationPublic(BaseModel):
    """不返回原始 token 的邀请响应。by AI.Coding"""

    id: uuid.UUID
    workspace_id: uuid.UUID
    email: EmailStr
    role: WorkspaceRole
    expires_at: datetime
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    """修改成员角色请求。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")

    role: WorkspaceRole
