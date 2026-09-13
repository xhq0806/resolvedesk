"""Workspace、成员和邀请持久化模型。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum, Index, text
from sqlmodel import Field, SQLModel

from app.models.user import get_datetime_utc


class WorkspaceStatus(StrEnum):
    """Workspace 生命周期状态。by AI.Coding"""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class WorkspaceRole(StrEnum):
    """Workspace 成员角色，Owner 由成员关系表达。by AI.Coding"""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
    CUSTOMER = "CUSTOMER"


class MembershipStatus(StrEnum):
    """Workspace 成员状态。by AI.Coding"""

    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class Workspace(SQLModel, table=True):
    """多租户 Workspace 根实体。by AI.Coding"""

    __tablename__ = "workspace"
    __table_args__ = (Index("ix_workspace_owner_status", "owner_user_id", "status"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=120)
    slug: str = Field(max_length=80, unique=True, index=True)
    status: WorkspaceStatus = Field(
        default=WorkspaceStatus.ACTIVE,
        sa_column=Column(
            Enum(WorkspaceStatus, name="workspace_status", native_enum=True),
            nullable=False,
            server_default=text("'ACTIVE'"),
        ),
    )
    owner_user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class WorkspaceMember(SQLModel, table=True):
    """用户与 Workspace 的成员关系。by AI.Coding"""

    __tablename__ = "workspace_member"
    __table_args__ = (
        Index("ux_workspace_member_pair", "workspace_id", "user_id", unique=True),
        Index("ix_workspace_member_lookup", "user_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    role: WorkspaceRole = Field(
        sa_column=Column(
            Enum(WorkspaceRole, name="workspace_role", native_enum=True),
            nullable=False,
        )
    )
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        sa_column=Column(
            Enum(MembershipStatus, name="membership_status", native_enum=True),
            nullable=False,
            server_default=text("'ACTIVE'"),
        ),
    )
    joined_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class WorkspaceInvitation(SQLModel, table=True):
    """Workspace 邀请生命周期模型。by AI.Coding"""

    __tablename__ = "workspace_invitation"
    __table_args__ = (
        Index("ix_workspace_invitation_workspace", "workspace_id", "expires_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    email: str = Field(max_length=255, nullable=False, index=True)
    role: WorkspaceRole = Field(
        sa_column=Column(
            Enum(WorkspaceRole, name="workspace_role", native_enum=True),
            nullable=False,
        )
    )
    token_hash: str = Field(max_length=128, nullable=False, unique=True)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)  # type: ignore
    accepted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
