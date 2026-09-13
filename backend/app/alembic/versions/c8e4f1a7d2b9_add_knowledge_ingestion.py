"""新增 Workspace 知识库、向量切块与摄取任务。by AI.Coding

Revision ID: c8e4f1a7d2b9
Revises: b7f2d9c1e4a3
Create Date: 2026-09-13
"""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c8e4f1a7d2b9"
down_revision = "b7f2d9c1e4a3"
branch_labels = None
depends_on = None

DOCUMENT_STATUS = postgresql.ENUM(
    "PROCESSING",
    "READY",
    "FAILED",
    "DELETED",
    name="knowledge_document_status",
    create_type=False,
)
JOB_STATUS = postgresql.ENUM(
    "PENDING",
    "RUNNING",
    "READY",
    "FAILED",
    "CANCELLED",
    name="ingestion_job_status",
    create_type=False,
)


def upgrade() -> None:
    """创建 pgvector 扩展、知识文档、切块和任务表。by AI.Coding"""
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    DOCUMENT_STATUS.create(bind, checkfirst=True)
    JOB_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "knowledge_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", DOCUMENT_STATUS, nullable=False, server_default="PROCESSING"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_knowledge_document_workspace_status",
        "knowledge_document",
        ["workspace_id", "status"],
    )
    op.create_index("ix_knowledge_document_sha256", "knowledge_document", ["sha256"])

    op.create_table(
        "knowledge_chunk",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_meta", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_document.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="ux_knowledge_chunk_document_index",
        ),
    )
    op.create_index(
        "ix_knowledge_chunk_workspace_document",
        "knowledge_chunk",
        ["workspace_id", "document_id"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunk_embedding_cosine "
        "ON knowledge_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "document_ingestion_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", JOB_STATUS, nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_document.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_job_workspace_status",
        "document_ingestion_job",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_ingestion_job_document",
        "document_ingestion_job",
        ["document_id", "created_at"],
    )


def downgrade() -> None:
    """删除知识库表、索引和状态枚举，保留 pgvector 扩展供其它应用使用。by AI.Coding"""
    op.drop_index("ix_ingestion_job_document", table_name="document_ingestion_job")
    op.drop_index(
        "ix_ingestion_job_workspace_status", table_name="document_ingestion_job"
    )
    op.drop_table("document_ingestion_job")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_embedding_cosine")
    op.drop_index(
        "ix_knowledge_chunk_workspace_document", table_name="knowledge_chunk"
    )
    op.drop_table("knowledge_chunk")
    op.drop_index("ix_knowledge_document_sha256", table_name="knowledge_document")
    op.drop_index(
        "ix_knowledge_document_workspace_status", table_name="knowledge_document"
    )
    op.drop_table("knowledge_document")
    bind = op.get_bind()
    JOB_STATUS.drop(bind, checkfirst=True)
    DOCUMENT_STATUS.drop(bind, checkfirst=True)
