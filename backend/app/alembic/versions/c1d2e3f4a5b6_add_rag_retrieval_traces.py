"""add rag retrieval trace policy

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增 Workspace RAG 追踪策略与无正文检索审计表。by AI.Coding"""
    op.create_table(
        "rag_retrieval_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "trace_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("strategy_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_rag_retrieval_policy_workspace",
        "rag_retrieval_policy",
        ["workspace_id"],
        unique=True,
    )

    op.create_table(
        "rag_retrieval_trace",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("query_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("query_length", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=80), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rag_retrieval_trace_workspace_created",
        "rag_retrieval_trace",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_rag_retrieval_trace_conversation",
        "rag_retrieval_trace",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_rag_retrieval_trace_request_id",
        "rag_retrieval_trace",
        ["request_id"],
    )


def downgrade() -> None:
    """移除仅用于观测的策略和检索追踪表。by AI.Coding"""
    op.drop_index("ix_rag_retrieval_trace_request_id", table_name="rag_retrieval_trace")
    op.drop_index("ix_rag_retrieval_trace_conversation", table_name="rag_retrieval_trace")
    op.drop_index(
        "ix_rag_retrieval_trace_workspace_created", table_name="rag_retrieval_trace"
    )
    op.drop_table("rag_retrieval_trace")
    op.drop_index(
        "ux_rag_retrieval_policy_workspace", table_name="rag_retrieval_policy"
    )
    op.drop_table("rag_retrieval_policy")
