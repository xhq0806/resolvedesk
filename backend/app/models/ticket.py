"""客服工单、消息与审计日志持久化模型。by AI.Coding"""

import uuid
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Enum, Index, Text, asc, desc, text
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import (
    TicketAuditAction,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from app.models.user import User, get_datetime_utc


def get_ticket_number() -> str:
    """生成带固定前缀且全局唯一的工单编号。by AI.Coding"""
    return f"TKT-{uuid.uuid4().hex}"


def get_enum_values[EnumType: StrEnum](
    enum_type: type[EnumType],
) -> Callable[[type[EnumType]], list[str]]:
    """返回 SQLAlchemy Enum 使用的稳定字符串值提取器。by AI.Coding"""

    def values_callable(_: type[EnumType]) -> list[str]:
        """按声明顺序提取字符串枚举值。by AI.Coding"""
        return [member.value for member in enum_type]

    return values_callable


class Ticket(SQLModel, table=True):
    """客服工单数据库模型。by AI.Coding"""

    __table_args__ = (
        Index("ux_ticket_ticket_number", "ticket_number", unique=True),
        Index(
            "ix_ticket_requester_updated",
            "requester_id",
            "deleted_at",
            desc("updated_at"),
        ),
        Index(
            "ix_ticket_assignee_updated",
            "assignee_id",
            "deleted_at",
            desc("updated_at"),
        ),
        Index(
            "ix_ticket_queue_updated",
            "assignee_id",
            "status",
            "deleted_at",
            desc("updated_at"),
        ),
        Index("ix_ticket_filter", "status", "priority", "category", "deleted_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_number: str = Field(default_factory=get_ticket_number, max_length=40)
    title: str = Field(max_length=200)
    description: str = Field(sa_column=Column(Text, nullable=False))
    status: TicketStatus = Field(
        default=TicketStatus.OPEN,
        sa_column=Column(
            Enum(
                TicketStatus,
                name="ticket_status",
                native_enum=True,
                values_callable=get_enum_values(TicketStatus),
            ),
            nullable=False,
            index=True,
            server_default=text("'OPEN'::ticket_status"),
        ),
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        sa_column=Column(
            Enum(
                TicketPriority,
                name="ticket_priority",
                native_enum=True,
                values_callable=get_enum_values(TicketPriority),
            ),
            nullable=False,
            index=True,
            server_default=text("'MEDIUM'::ticket_priority"),
        ),
    )
    category: TicketCategory = Field(
        sa_column=Column(
            Enum(
                TicketCategory,
                name="ticket_category",
                native_enum=True,
                values_callable=get_enum_values(TicketCategory),
            ),
            nullable=False,
            index=True,
        )
    )
    requester_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="RESTRICT", index=True
    )
    assignee_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        ondelete="RESTRICT",
        index=True,
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    deleted_by_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        ondelete="RESTRICT",
    )

    # 三条 User 外键必须显式绑定，避免 SQLAlchemy 推断出歧义关系。
    requester: User = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Ticket.requester_id]"}
    )
    assignee: User | None = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assignee_id]"}
    )
    deleted_by: User | None = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Ticket.deleted_by_id]"}
    )
    messages: list[TicketMessage] = Relationship(back_populates="ticket")
    audit_logs: list[TicketAuditLog] = Relationship(back_populates="ticket")


class TicketMessage(SQLModel, table=True):
    """工单公开回复或内部备注数据库模型。by AI.Coding"""

    __tablename__ = "ticket_message"
    __table_args__ = (
        Index("ix_ticket_message_timeline", "ticket_id", asc("created_at")),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(
        foreign_key="ticket.id", nullable=False, ondelete="RESTRICT", index=True
    )
    author_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="RESTRICT"
    )
    message_type: TicketMessageType = Field(
        sa_column=Column(
            Enum(
                TicketMessageType,
                name="ticket_message_type",
                native_enum=True,
                values_callable=get_enum_values(TicketMessageType),
            ),
            nullable=False,
            index=True,
        )
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

    ticket: Ticket = Relationship(back_populates="messages")
    author: User = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[TicketMessage.author_id]"}
    )


class TicketAuditLog(SQLModel, table=True):
    """工单结构化操作审计数据库模型。by AI.Coding"""

    __tablename__ = "ticket_audit_log"
    __table_args__ = (
        Index("ix_ticket_audit_timeline", "ticket_id", asc("created_at")),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(
        foreign_key="ticket.id", nullable=False, ondelete="RESTRICT", index=True
    )
    actor_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="RESTRICT"
    )
    action: TicketAuditAction = Field(
        sa_column=Column(
            Enum(
                TicketAuditAction,
                name="ticket_audit_action",
                native_enum=True,
                values_callable=get_enum_values(TicketAuditAction),
            ),
            nullable=False,
            index=True,
        )
    )
    old_value: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    new_value: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

    ticket: Ticket = Relationship(back_populates="audit_logs")
    actor: User = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[TicketAuditLog.actor_id]"}
    )
