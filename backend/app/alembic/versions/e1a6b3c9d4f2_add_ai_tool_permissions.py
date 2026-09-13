"""新增 AI Agent 工具白名单授权表。by AI.Coding

Revision ID: e1a6b3c9d4f2
Revises: d9f5a2b8c3e1
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1a6b3c9d4f2"
down_revision = "d9f5a2b8c3e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 Workspace AI Agent 工具授权表。by AI.Coding"""
    op.create_table(
        "ai_tool_permission",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ai_agent_id"], ["ai_agent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ai_agent_id",
            "tool_name",
            name="ux_ai_tool_permission_agent_tool",
        ),
    )
    op.create_index(
        "ix_ai_tool_permission_workspace",
        "ai_tool_permission",
        ["workspace_id", "enabled"],
    )


def downgrade() -> None:
    """删除 AI Agent 工具授权表。by AI.Coding"""
    op.drop_index("ix_ai_tool_permission_workspace", table_name="ai_tool_permission")
    op.drop_table("ai_tool_permission")
