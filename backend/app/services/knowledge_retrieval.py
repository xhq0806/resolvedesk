"""Workspace 隔离的 RAG 检索与来源裁剪服务。by AI.Coding"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Protocol

from sqlmodel import Session

from app.core.config import settings
from app.core.errors import ConflictError, ErrorCode
from app.core.workspace import WorkspaceContext
from app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    RagRetrievalPolicy,
    RagRetrievalTrace,
)
from app.providers.embedding import EmbeddingProvider
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """用于 Prompt 和前端引用的最小来源信息。by AI.Coding"""

    chunk_id: str
    document_id: str
    display_name: str
    locator: dict[str, object]
    content: str
    distance: float


@dataclass(frozen=True)
class RetrievalTraceContext:
    """将检索追踪关联到请求和可选会话的内部上下文。by AI.Coding"""

    request_id: str
    conversation_id: uuid.UUID | None = None


class RetrievalRepository(Protocol):
    """检索服务依赖的最小仓储协议。by AI.Coding"""

    def search_ready_chunks(
        self,
        context: WorkspaceContext,
        embedding: Sequence[float],
        *,
        limit: int = 8,
    ) -> list[tuple[KnowledgeChunk, float]]: ...

    def get_document(
        self, context: WorkspaceContext, document_id: uuid.UUID
    ) -> KnowledgeDocument | None: ...

    def get_retrieval_policy(
        self, context: WorkspaceContext
    ) -> RagRetrievalPolicy | None: ...

    def create_retrieval_trace(self, trace: RagRetrievalTrace) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


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
        repository: RetrievalRepository,
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
        trace_context: RetrievalTraceContext | None = None,
    ) -> list[RetrievedChunk]:
        """只检索当前租户 READY 文档并返回最多五个去重来源。by AI.Coding"""
        started_at = perf_counter()
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
        sources = trim_sources(hydrated)
        # 追踪只记录已完成的检索元数据，避免失败路径泄露原始 query。by AI.Coding
        self._record_trace(
            context,
            normalized_query,
            sources,
            elapsed_ms=round((perf_counter() - started_at) * 1000),
            trace_context=trace_context,
        )
        return sources

    def _record_trace(
        self,
        context: WorkspaceContext,
        normalized_query: str,
        sources: Sequence[RetrievedChunk],
        *,
        elapsed_ms: int,
        trace_context: RetrievalTraceContext | None,
    ) -> None:
        """按 Workspace 策略尽力写入无正文检索追踪。by AI.Coding"""
        try:
            policy = self.repository.get_retrieval_policy(context)
            if policy is None or not policy.trace_enabled:
                return
            # HMAC 允许关联重复查询，同时避免普通哈希暴露短问题。by AI.Coding
            fingerprint = hmac.new(
                settings.SECRET_KEY.encode("utf-8"),
                normalized_query.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            candidates = [
                {
                    "chunk_id": source.chunk_id,
                    "document_id": source.document_id,
                    "rank": rank,
                    "distance": source.distance,
                    "locator": source.locator,
                }
                for rank, source in enumerate(sources, start=1)
            ]
            trace = RagRetrievalTrace(
                workspace_id=context.workspace_id,
                conversation_id=(
                    trace_context.conversation_id if trace_context is not None else None
                ),
                request_id=(trace_context.request_id if trace_context is not None else ""),
                query_fingerprint=fingerprint,
                query_length=len(normalized_query),
                strategy_version=policy.strategy_version,
                result_count=len(sources),
                elapsed_ms=max(0, elapsed_ms),
                candidates=candidates,
            )
            self.repository.create_retrieval_trace(trace)
            self.repository.commit()
        except Exception:
            # 观测故障不得影响客户获得既有 RAG 回答。by AI.Coding
            try:
                self.repository.rollback()
            except Exception:
                # 回滚自身失败时同样不能改变已完成的检索结果。by AI.Coding
                pass
            logger.warning(
                "rag_retrieval_trace_write_failed",
                extra={"workspace_id": str(context.workspace_id)},
            )


class RagRetrievalPolicyService:
    """管理 Workspace RAG 观测策略与检索追踪查询。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求会话并复用知识库仓储。by AI.Coding"""
        self.session = session
        self.repository = KnowledgeRepository(session)

    def get_policy(self, context: WorkspaceContext) -> RagRetrievalPolicy:
        """返回已保存策略或不落库的安全默认策略。by AI.Coding"""
        return self.repository.get_retrieval_policy(context) or RagRetrievalPolicy(
            workspace_id=context.workspace_id
        )

    def update_policy(
        self,
        context: WorkspaceContext,
        *,
        trace_enabled: bool | None,
        strategy_version: str | None,
    ) -> RagRetrievalPolicy:
        """只更新显式提供的 Workspace 检索策略字段。by AI.Coding"""
        policy = self.repository.get_retrieval_policy(context)
        if policy is None:
            policy = RagRetrievalPolicy(workspace_id=context.workspace_id)
        # 未提供字段保留原值，确保 PATCH 不会意外关闭观测。by AI.Coding
        if trace_enabled is not None:
            policy.trace_enabled = trace_enabled
        if strategy_version is not None:
            policy.strategy_version = strategy_version
        self.repository.add_retrieval_policy(policy)
        self.repository.commit()
        self.session.refresh(policy)
        return policy

    def list_traces(
        self,
        context: WorkspaceContext,
        *,
        limit: int,
        before: datetime | None,
    ) -> list[RagRetrievalTrace]:
        """读取当前 Workspace 的无正文检索追踪。by AI.Coding"""
        return self.repository.list_retrieval_traces(context, limit=limit, before=before)
