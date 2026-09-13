"""AI Agent 执行主体基础模型。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Index,
    LargeBinary,
    Text,
    text,
)
from sqlmodel import Field, SQLModel

from app.models.user import get_datetime_utc


def enum_values[EnumType: StrEnum](
    enum_type: type[EnumType],
) -> Callable[[type[EnumType]], list[str]]:
    """返回 SQLAlchemy Enum 应持久化的字符串值，避免事件类型名称漂移。by AI.Coding"""
    return lambda _: [member.value for member in enum_type]


class AiAgentStatus(StrEnum):
    """AI Agent 生命周期状态。by AI.Coding"""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AiAgent(SQLModel, table=True):
    """每个 Workspace 的独立 AI 执行主体。by AI.Coding"""

    __tablename__ = "ai_agent"
    __table_args__ = (Index("ux_ai_agent_workspace", "workspace_id", unique=True),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    name: str = Field(default="ResolveDesk AI", max_length=120)
    status: AiAgentStatus = Field(
        default=AiAgentStatus.ACTIVE,
        sa_column=Column(
            Enum(
                AiAgentStatus,
                name="ai_agent_status",
                native_enum=True,
                values_callable=enum_values(AiAgentStatus),
            ),
            nullable=False,
            server_default=text("'ACTIVE'"),
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AiProviderConfig(SQLModel, table=True):
    """每个 Workspace 独立保存的模型 Provider 配置。by AI.Coding"""

    __tablename__ = "ai_provider_config"
    __table_args__ = (
        Index("ux_ai_provider_config_workspace", "workspace_id", unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    chat_provider: str = Field(default="openai-compatible", max_length=50)
    chat_base_url: str | None = Field(default=None, max_length=500)
    chat_model: str = Field(default="gpt-4o-mini", max_length=120)
    embedding_provider: str = Field(default="openai-compatible", max_length=50)
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_model: str = Field(default="text-embedding-3-small", max_length=120)
    embedding_dimension: int = Field(default=1536)
    encrypted_api_key: bytes | None = Field(
        default=None,
        sa_column=Column(LargeBinary, nullable=True),
    )
    enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ConversationMode(StrEnum):
    """AI 会话所属范围。by AI.Coding"""

    WORKSPACE = "WORKSPACE"
    TICKET = "TICKET"


class ConversationStatus(StrEnum):
    """AI 会话生命周期状态。by AI.Coding"""

    ACTIVE = "ACTIVE"
    HANDED_OFF = "HANDED_OFF"
    PAUSED = "PAUSED"


class AiMessageRole(StrEnum):
    """AI 会话消息角色。by AI.Coding"""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"


class AiMessageStatus(StrEnum):
    """AI 消息确认状态。by AI.Coding"""

    CONFIRMED = "CONFIRMED"
    DRAFT = "DRAFT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AiRunStatus(StrEnum):
    """一次 AI 生成运行状态。by AI.Coding"""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class AiRunEventType(StrEnum):
    """SSE 与审计共用的运行事件类型。by AI.Coding"""

    RUN_STARTED = "run.started"
    MESSAGE_DELTA = "message.delta"
    SOURCE_FOUND = "source.found"
    TOOL_STARTED = "tool.started"
    TOOL_RESULT = "tool.result"
    MESSAGE_COMPLETED = "message.completed"
    RUN_COMPLETED = "run.completed"
    RUN_CANCELLED = "run.cancelled"
    RUN_FAILED = "run.failed"


class AiConversation(SQLModel, table=True):
    """Workspace 级 AI 会话及人工接管状态。by AI.Coding"""

    __tablename__ = "ai_conversation"
    __table_args__ = (
        Index("ix_ai_conversation_workspace_updated", "workspace_id", "updated_at"),
        Index("ix_ai_conversation_ticket", "workspace_id", "ticket_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    ticket_id: uuid.UUID | None = Field(
        default=None, foreign_key="ticket.id", nullable=True
    )
    mode: ConversationMode = Field(
        default=ConversationMode.WORKSPACE,
        sa_column=Column(
            Enum(
                ConversationMode,
                name="conversation_mode",
                native_enum=True,
                values_callable=enum_values(ConversationMode),
            ),
            nullable=False,
        ),
    )
    status: ConversationStatus = Field(
        default=ConversationStatus.ACTIVE,
        sa_column=Column(
            Enum(
                ConversationStatus,
                name="conversation_status",
                native_enum=True,
                values_callable=enum_values(ConversationStatus),
            ),
            nullable=False,
        ),
    )
    handed_off: bool = Field(default=False, nullable=False)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AiMessage(SQLModel, table=True):
    """AI 会话消息，保留失败和取消状态但不伪造完整回复。by AI.Coding"""

    __tablename__ = "ai_message"
    __table_args__ = (
        Index("ix_ai_message_conversation_created", "conversation_id", "created_at"),
        Index(
            "ux_ai_message_client_id",
            "conversation_id",
            "client_message_id",
            unique=True,
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="ai_conversation.id", nullable=False
    )
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    role: AiMessageRole = Field(
        sa_column=Column(
            Enum(
                AiMessageRole,
                name="ai_message_role",
                native_enum=True,
                values_callable=enum_values(AiMessageRole),
            ),
            nullable=False,
        )
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    status: AiMessageStatus = Field(
        default=AiMessageStatus.CONFIRMED,
        sa_column=Column(
            Enum(
                AiMessageStatus,
                name="ai_message_status",
                native_enum=True,
                values_callable=enum_values(AiMessageStatus),
            ),
            nullable=False,
        ),
    )
    ai_generated: bool = Field(default=False, nullable=False)
    client_message_id: str | None = Field(default=None, max_length=120)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AiRun(SQLModel, table=True):
    """AI 一次生成运行的状态与请求关联信息。by AI.Coding"""

    __tablename__ = "ai_run"
    __table_args__ = (
        Index("ix_ai_run_conversation_status", "conversation_id", "status"),
        Index("ix_ai_run_workspace_started", "workspace_id", "started_at"),
        # 数据库层保证同一会话最多一个 RUNNING，避免并发请求绕过应用层检查。by AI.Coding
        Index(
            "ux_ai_run_running_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(
        foreign_key="ai_conversation.id", nullable=False
    )
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    request_id: str = Field(max_length=120, index=True)
    status: AiRunStatus = Field(
        default=AiRunStatus.RUNNING,
        sa_column=Column(
            Enum(
                AiRunStatus,
                name="ai_run_status",
                native_enum=True,
                values_callable=enum_values(AiRunStatus),
            ),
            nullable=False,
        ),
    )
    model: str = Field(max_length=120)
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )
    error_code: str | None = Field(default=None, max_length=80)


class AiRunEvent(SQLModel, table=True):
    """可重放的 SSE 运行事件，payload 不包含密钥和完整敏感正文。by AI.Coding"""

    __tablename__ = "ai_run_event"
    __table_args__ = (
        Index("ux_ai_run_event_sequence", "run_id", "sequence", unique=True),
        Index("ix_ai_run_event_workspace_created", "workspace_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(foreign_key="ai_run.id", nullable=False)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    sequence: int = Field(nullable=False)
    event_type: AiRunEventType = Field(
        sa_column=Column(
            Enum(
                AiRunEventType,
                name="ai_run_event_type",
                native_enum=True,
                values_callable=enum_values(AiRunEventType),
            ),
            nullable=False,
        )
    )
    payload_json: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AiToolPermission(SQLModel, table=True):
    """Workspace AI Agent 的工具白名单授权。by AI.Coding"""

    __tablename__ = "ai_tool_permission"
    __table_args__ = (
        Index("ux_ai_tool_permission_agent_tool", "ai_agent_id", "tool_name", unique=True),
        Index("ix_ai_tool_permission_workspace", "workspace_id", "enabled"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ai_agent_id: uuid.UUID = Field(foreign_key="ai_agent.id", nullable=False)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    tool_name: str = Field(max_length=80)
    enabled: bool = Field(default=False, nullable=False)
    updated_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
