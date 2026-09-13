"""新增 AI 会话、消息、运行和 SSE 事件表。by AI.Coding

Revision ID: d9f5a2b8c3e1
Revises: c8e4f1a7d2b9
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d9f5a2b8c3e1"
down_revision = "c8e4f1a7d2b9"
branch_labels = None
depends_on = None


def _enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    """构造可重复创建的 PostgreSQL 枚举。by AI.Coding"""
    return postgresql.ENUM(*values, name=name, create_type=False)


CONVERSATION_MODE = _enum("conversation_mode", ("WORKSPACE", "TICKET"))
CONVERSATION_STATUS = _enum(
    "conversation_status", ("ACTIVE", "HANDED_OFF", "PAUSED")
)
MESSAGE_ROLE = _enum("ai_message_role", ("USER", "ASSISTANT", "TOOL", "SYSTEM"))
MESSAGE_STATUS = _enum(
    "ai_message_status", ("CONFIRMED", "DRAFT", "FAILED", "CANCELLED")
)
RUN_STATUS = _enum("ai_run_status", ("RUNNING", "COMPLETED", "CANCELLED", "FAILED"))
EVENT_TYPE = _enum(
    "ai_run_event_type",
    (
        "run.started",
        "message.delta",
        "source.found",
        "tool.started",
        "tool.result",
        "message.completed",
        "run.completed",
        "run.cancelled",
        "run.failed",
    ),
)


def upgrade() -> None:
    """创建 AI 会话、消息、运行和事件持久化结构。by AI.Coding"""
    bind = op.get_bind()
    for enum_type in (
        CONVERSATION_MODE,
        CONVERSATION_STATUS,
        MESSAGE_ROLE,
        MESSAGE_STATUS,
        RUN_STATUS,
        EVENT_TYPE,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "ai_conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mode", CONVERSATION_MODE, nullable=False),
        sa.Column("status", CONVERSATION_STATUS, nullable=False),
        sa.Column("handed_off", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_conversation_workspace_updated",
        "ai_conversation",
        ["workspace_id", "updated_at"],
    )
    op.create_index(
        "ix_ai_conversation_ticket",
        "ai_conversation",
        ["workspace_id", "ticket_id"],
    )

    op.create_table(
        "ai_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", MESSAGE_ROLE, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", MESSAGE_STATUS, nullable=False),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("client_message_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "client_message_id",
            name="ux_ai_message_client_id",
        ),
    )
    op.create_index(
        "ix_ai_message_conversation_created",
        "ai_message",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "ai_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("status", RUN_STATUS, nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_run_request_id", "ai_run", ["request_id"])
    op.create_index(
        "ix_ai_run_conversation_status",
        "ai_run",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_ai_run_workspace_started",
        "ai_run",
        ["workspace_id", "started_at"],
    )
    op.create_index(
        "ux_ai_run_running_conversation",
        "ai_run",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )

    op.create_table(
        "ai_run_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", EVENT_TYPE, nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ai_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="ux_ai_run_event_sequence"),
    )
    op.create_index(
        "ix_ai_run_event_workspace_created",
        "ai_run_event",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    """删除 AI 会话与运行事件表及其枚举。by AI.Coding"""
    op.drop_index(
        "ix_ai_run_event_workspace_created", table_name="ai_run_event"
    )
    op.drop_table("ai_run_event")
    op.drop_index("ix_ai_run_workspace_started", table_name="ai_run")
    op.drop_index("ix_ai_run_conversation_status", table_name="ai_run")
    op.drop_index("ux_ai_run_running_conversation", table_name="ai_run")
    op.drop_index("ix_ai_run_request_id", table_name="ai_run")
    op.drop_table("ai_run")
    op.drop_index("ix_ai_message_conversation_created", table_name="ai_message")
    op.drop_table("ai_message")
    op.drop_index("ix_ai_conversation_ticket", table_name="ai_conversation")
    op.drop_index("ix_ai_conversation_workspace_updated", table_name="ai_conversation")
    op.drop_table("ai_conversation")
    bind = op.get_bind()
    for enum_type in (
        EVENT_TYPE,
        RUN_STATUS,
        MESSAGE_STATUS,
        MESSAGE_ROLE,
        CONVERSATION_STATUS,
        CONVERSATION_MODE,
    ):
        enum_type.drop(bind, checkfirst=True)
