"""新增 Workspace 级 AI Provider 配置。by AI.Coding

Revision ID: b7f2d9c1e4a3
Revises: a2c4e6f8b0d1
Create Date: 2026-09-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7f2d9c1e4a3"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 Provider 配置表并为已有 Workspace 补默认配置。by AI.Coding"""
    op.create_table(
        "ai_provider_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "chat_provider",
            sa.String(length=50),
            nullable=False,
            server_default="openai-compatible",
        ),
        sa.Column("chat_base_url", sa.String(length=500), nullable=True),
        sa.Column(
            "chat_model",
            sa.String(length=120),
            nullable=False,
            server_default="gpt-4o-mini",
        ),
        sa.Column(
            "embedding_provider",
            sa.String(length=50),
            nullable=False,
            server_default="openai-compatible",
        ),
        sa.Column("embedding_base_url", sa.String(length=500), nullable=True),
        sa.Column(
            "embedding_model",
            sa.String(length=120),
            nullable=False,
            server_default="text-embedding-3-small",
        ),
        sa.Column(
            "embedding_dimension",
            sa.Integer(),
            nullable=False,
            server_default="1536",
        ),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="ux_ai_provider_config_workspace"),
    )
    bind = op.get_bind()
    for workspace_id in bind.execute(sa.text("SELECT id FROM workspace")).scalars():
        bind.execute(
            sa.text(
                "INSERT INTO ai_provider_config "
                "(id, workspace_id, created_at, updated_at) "
                "VALUES (:id, :workspace_id, now(), now())"
            ),
            {"id": uuid.uuid4(), "workspace_id": workspace_id},
        )


def downgrade() -> None:
    """移除 Workspace 级 AI Provider 配置。by AI.Coding"""
    op.drop_table("ai_provider_config")
