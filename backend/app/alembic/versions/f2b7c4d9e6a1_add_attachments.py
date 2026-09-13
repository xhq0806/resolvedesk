"""新增 Workspace 工单与会话附件表。by AI.Coding

Revision ID: f2b7c4d9e6a1
Revises: e1a6b3c9d4f2
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f2b7c4d9e6a1"
down_revision = "e1a6b3c9d4f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建附件元数据表并约束至少关联工单或会话。by AI.Coding"""
    op.create_table(
        "attachment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(ticket_id IS NOT NULL) OR (conversation_id IS NOT NULL)",
            name="ck_attachment_parent_required",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_attachment_workspace_created",
        "attachment",
        ["workspace_id", "created_at"],
    )
    op.create_index("ix_attachment_ticket", "attachment", ["workspace_id", "ticket_id"])
    op.create_index(
        "ix_attachment_conversation",
        "attachment",
        ["workspace_id", "conversation_id"],
    )


def downgrade() -> None:
    """删除附件元数据表。by AI.Coding"""
    op.drop_index("ix_attachment_conversation", table_name="attachment")
    op.drop_index("ix_attachment_ticket", table_name="attachment")
    op.drop_index("ix_attachment_workspace_created", table_name="attachment")
    op.drop_table("attachment")
