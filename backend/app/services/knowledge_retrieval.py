"""Workspace 隔离的 RAG 检索与来源裁剪服务。by AI.Coding"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.errors import ConflictError, ErrorCode
from app.core.workspace import WorkspaceContext
from app.models.knowledge import KnowledgeChunk
from app.providers.embedding import EmbeddingProvider
from app.repositories.knowledge_repository import KnowledgeRepository


@dataclass(frozen=True)
class RetrievedChunk:
    """用于 Prompt 和前端引用的最小来源信息。by AI.Coding"""

    chunk_id: str
    document_id: str
    display_name: str
    locator: dict[str, object]
    content: str
    distance: float


def trim_sources(
    rows: Sequence[tuple[KnowledgeChunk, str, float]],
    *,
    max_sources: int = 5,
) -> list[RetrievedChunk]:
    """按文档去重并裁剪来源数量，保留最相近片段。by AI.Coding"""
    seen_documents: set[str] = set()
    result: list[RetrievedChunk] = []
    for chunk, display_name, distance in rows:
        document_id = str(chunk.document_id)
        if document_id in seen_documents:
            continue
        seen_documents.add(document_id)
        result.append(
            RetrievedChunk(
                chunk_id=str(chunk.id),
                document_id=document_id,
                display_name=display_name,
                locator=dict(chunk.source_meta),
                content=chunk.content,
                distance=distance,
            )
        )
        if len(result) >= max(1, max_sources):
            break
    return result


class KnowledgeRetrievalService:
    """执行当前 Workspace 的 Embedding 检索并生成可定位来源。by AI.Coding"""

    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        """保存向量查询仓储和 Embedding provider。by AI.Coding"""
        self.repository = repository
        self.embedding_provider = embedding_provider

    async def search(
        self,
        context: WorkspaceContext,
        query: str,
        *,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        """只检索当前租户 READY 文档并返回最多五个去重来源。by AI.Coding"""
        normalized_query = query.strip()
        if not normalized_query:
            raise ConflictError(ErrorCode.VALIDATION_ERROR)
        vectors = await self.embedding_provider.embed([normalized_query])
        if len(vectors) != 1:
            raise ConflictError(ErrorCode.PROVIDER_UNAVAILABLE)
        rows = self.repository.search_ready_chunks(
            context,
            vectors[0],
            limit=limit,
        )
        hydrated: list[tuple[KnowledgeChunk, str, float]] = []
        for chunk, distance in rows:
            document = self.repository.get_document(context, chunk.document_id)
            if document is not None:
                hydrated.append((chunk, document.display_name, distance))
        return trim_sources(hydrated)
