"""知识库文档与向量切块查询仓储。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlmodel import Session, select

from app.core.workspace import WorkspaceContext
from app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)


class KnowledgeRepository:
    """封装带 Workspace 隔离条件的知识库查询。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求级数据库会话。by AI.Coding"""
        self.session = session

    def search_ready_chunks(
        self,
        context: WorkspaceContext,
        embedding: Sequence[float],
        *,
        limit: int = 8,
    ) -> list[tuple[KnowledgeChunk, float]]:
        """按余弦距离检索当前 Workspace 的 READY 文档切块。by AI.Coding"""
        # pgvector SQLAlchemy 扩展提供 cosine_distance；cast 仅用于兼容 SQLModel 的静态类型。by AI.Coding
        embedding_column = cast(Any, KnowledgeChunk.embedding)
        document_id_column = cast(Any, KnowledgeDocument.id)
        chunk_document_id_column = cast(Any, KnowledgeChunk.document_id)
        embedding_value_column = cast(Any, KnowledgeChunk.embedding)
        distance_column = embedding_column.cosine_distance(list(embedding))
        statement = (
            select(KnowledgeChunk, distance_column)
            .join(
                KnowledgeDocument,
                document_id_column == chunk_document_id_column,
            )
            .where(
                KnowledgeChunk.workspace_id == context.workspace_id,
                KnowledgeDocument.workspace_id == context.workspace_id,
                KnowledgeDocument.status == KnowledgeDocumentStatus.READY,
                embedding_value_column.is_not(None),
            )
            .order_by(distance_column)
            .limit(max(1, min(limit, 32)))
        )
        rows = self.session.exec(statement).all()
        return [(chunk, float(distance)) for chunk, distance in rows]

    def get_document(
        self,
        context: WorkspaceContext,
        document_id: uuid.UUID,
    ) -> KnowledgeDocument | None:
        """按 Workspace 查询文档元数据，避免来源跨租户泄漏。by AI.Coding"""
        return self.session.exec(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.workspace_id == context.workspace_id,
                KnowledgeDocument.status == KnowledgeDocumentStatus.READY,
            )
        ).first()
