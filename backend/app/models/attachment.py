"""工单与会话附件持久化模型。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel

from app.models.user import get_datetime_utc


class Attachment(SQLModel, table=True):
    """Workspace 隔离的附件元数据，不把本地路径暴露给客户端。by AI.Coding"""

    __tablename__ = "attachment"
    __table_args__ = (
        Index("ix_attachment_workspace_created", "workspace_id", "created_at"),
        Index("ix_attachment_ticket", "workspace_id", "ticket_id"),
        Index("ix_attachment_conversation", "workspace_id", "conversation_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="ticket.id", nullable=True
    )
    conversation_id: uuid.UUID | None = Field(
        default=None, foreign_key="ai_conversation.id", nullable=True
    )
    storage_key: str = Field(max_length=500, unique=True)
    display_name: str = Field(max_length=255)
    mime_type: str = Field(max_length=120)
    size_bytes: int
    sha256: str = Field(max_length=64)
    uploaded_by_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )
