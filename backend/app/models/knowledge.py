"""Workspace 知识库文档、切块与摄取任务模型。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Index, Integer, Text, text
from sqlmodel import Field, SQLModel

from app.models.user import get_datetime_utc


class KnowledgeDocumentStatus(StrEnum):
    """知识文档生命周期状态。by AI.Coding"""

    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    DELETED = "DELETED"


class IngestionJobStatus(StrEnum):
    """文档摄取任务状态。by AI.Coding"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class KnowledgeDocument(SQLModel, table=True):
    """Workspace 级知识文档元数据与处理状态。by AI.Coding"""

    __tablename__ = "knowledge_document"
    __table_args__ = (
        Index("ix_knowledge_document_workspace_status", "workspace_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    display_name: str = Field(max_length=255)
    storage_key: str = Field(max_length=500, unique=True)
    mime_type: str = Field(max_length=120)
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    sha256: str = Field(max_length=64, index=True)
    status: KnowledgeDocumentStatus = Field(
        default=KnowledgeDocumentStatus.PROCESSING,
        sa_column=Column(
            Enum(
                KnowledgeDocumentStatus,
                name="knowledge_document_status",
                native_enum=True,
            ),
            nullable=False,
            server_default=text("'PROCESSING'"),
        ),
    )
    version: int = Field(default=1, nullable=False)
    error_code: str | None = Field(default=None, max_length=80)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )


class KnowledgeChunk(SQLModel, table=True):
    """知识文档的可检索文本片段与向量。by AI.Coding"""

    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        Index("ix_knowledge_chunk_workspace_document", "workspace_id", "document_id"),
        Index("ux_knowledge_chunk_document_index", "document_id", "chunk_index", unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    document_id: uuid.UUID = Field(foreign_key="knowledge_document.id", nullable=False)
    chunk_index: int = Field(sa_column=Column(Integer, nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    source_meta: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1024), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RagRetrievalPolicy(SQLModel, table=True):
    """Workspace 级 RAG 检索观测策略。by AI.Coding"""

    __tablename__ = "rag_retrieval_policy"
    __table_args__ = (
        Index("ux_rag_retrieval_policy_workspace", "workspace_id", unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    trace_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    strategy_version: str = Field(default="dense-v1", max_length=80)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RagRetrievalTrace(SQLModel, table=True):
    """不保存问题正文的 Workspace 检索审计记录。by AI.Coding"""

    __tablename__ = "rag_retrieval_trace"
    __table_args__ = (
        Index("ix_rag_retrieval_trace_workspace_created", "workspace_id", "created_at"),
        Index("ix_rag_retrieval_trace_conversation", "conversation_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    conversation_id: uuid.UUID | None = Field(
        default=None, foreign_key="ai_conversation.id", nullable=True
    )
    request_id: str = Field(max_length=120, index=True)
    query_fingerprint: str = Field(max_length=64)
    query_length: int = Field(sa_column=Column(Integer, nullable=False))
    strategy_version: str = Field(max_length=80)
    result_count: int = Field(sa_column=Column(Integer, nullable=False))
    elapsed_ms: int = Field(sa_column=Column(Integer, nullable=False))
    candidates: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DocumentIngestionJob(SQLModel, table=True):
    """持久化文档解析、切块和向量写入任务。by AI.Coding"""

    __tablename__ = "document_ingestion_job"
    __table_args__ = (
        Index("ix_ingestion_job_workspace_status", "workspace_id", "status"),
        Index("ix_ingestion_job_document", "document_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id", nullable=False)
    document_id: uuid.UUID = Field(foreign_key="knowledge_document.id", nullable=False)
    status: IngestionJobStatus = Field(
        default=IngestionJobStatus.PENDING,
        sa_column=Column(
            Enum(IngestionJobStatus, name="ingestion_job_status", native_enum=True),
            nullable=False,
            server_default=text("'PENDING'"),
        ),
    )
    attempts: int = Field(default=0, nullable=False)
    lease_until: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,  # type: ignore
    )
    error_code: str | None = Field(default=None, max_length=80)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
