"""RAG 检索追踪与脱敏记录测试。by AI.Coding"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.core.workspace import WorkspaceContext
from app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    RagRetrievalPolicy,
    RagRetrievalTrace,
)
from app.models.workspace import Workspace, WorkspaceMember
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalService,
    RetrievalTraceContext,
)


@dataclass
class _FakeEmbeddingProvider:
    """为检索服务提供稳定向量的测试替身。by AI.Coding"""

    vectors: list[list[float]] = field(default_factory=lambda: [[0.1] * 1024])

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """返回与输入数量对应的固定向量。by AI.Coding"""
        assert texts == ["如何重置密码"]
        return self.vectors


class _FakeKnowledgeRepository:
    """记录检索追踪写入而不依赖真实向量数据库。by AI.Coding"""

    def __init__(self, policy: RagRetrievalPolicy | None) -> None:
        """保存策略并准备一份可水合的文档切块。by AI.Coding"""
        self.policy = policy
        self.trace: RagRetrievalTrace | None = None
        self.fail_commit = False
        self.chunk = KnowledgeChunk(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(int=2),
            document_id=uuid.UUID(int=1),
            chunk_index=0,
            content="请在登录页选择重置密码。",
            source_meta={"kind": "document"},
        )
        self.document = KnowledgeDocument(
            id=self.chunk.document_id,
            workspace_id=self.chunk.workspace_id,
            display_name="密码 FAQ.md",
            storage_key="test/password-faq.md",
            mime_type="text/markdown",
            size_bytes=10,
            sha256="a" * 64,
            status=KnowledgeDocumentStatus.READY,
            created_by_id=uuid.UUID(int=3),
        )

    def search_ready_chunks(
        self,
        context: WorkspaceContext,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[tuple[KnowledgeChunk, float]]:
        """返回当前 Workspace 的固定 Dense 检索结果。by AI.Coding"""
        assert context.workspace_id == self.chunk.workspace_id
        assert len(embedding) == 1024
        assert limit == 8
        return [(self.chunk, 0.12)]

    def get_document(
        self, context: WorkspaceContext, document_id: uuid.UUID
    ) -> KnowledgeDocument | None:
        """按当前 Workspace 返回测试文档。by AI.Coding"""
        assert context.workspace_id == self.chunk.workspace_id
        return self.document if document_id == self.document.id else None

    def get_retrieval_policy(
        self, context: WorkspaceContext
    ) -> RagRetrievalPolicy | None:
        """返回为当前 Workspace 配置的策略。by AI.Coding"""
        assert context.workspace_id == self.chunk.workspace_id
        return self.policy

    def create_retrieval_trace(self, trace: RagRetrievalTrace) -> None:
        """捕获服务待持久化的 trace。by AI.Coding"""
        self.trace = trace

    def commit(self) -> None:
        """模拟 trace 写入成功的事务提交。by AI.Coding"""
        if self.fail_commit:
            raise RuntimeError("trace storage unavailable")

    def rollback(self) -> None:
        """模拟 best-effort trace 写入失败后的回滚。by AI.Coding"""


def _context() -> WorkspaceContext:
    """构造仅供检索追踪测试使用的 Workspace 上下文。by AI.Coding"""
    workspace = Workspace(id=uuid.UUID(int=2), name="Trace Workspace", slug="trace")
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=uuid.UUID(int=4),
    )
    return WorkspaceContext(workspace=workspace, member=member)


def test_search_records_hmac_trace_without_query_or_chunk_content() -> None:
    """开启 trace 后应保存 HMAC 指纹和候选元数据，不保存正文。by AI.Coding"""
    context = _context()
    repository = _FakeKnowledgeRepository(
        RagRetrievalPolicy(
            workspace_id=context.workspace_id,
            trace_enabled=True,
            strategy_version="dense-v1",
        )
    )
    service = KnowledgeRetrievalService(repository, _FakeEmbeddingProvider())  # type: ignore[arg-type]

    result = asyncio.run(
        service.search(
            context,
            "如何重置密码",
            trace_context=RetrievalTraceContext(
                request_id="request-123",
                conversation_id=uuid.UUID(int=5),
            ),
        ),
    )

    assert result[0].content == "请在登录页选择重置密码。"
    assert repository.trace is not None
    assert repository.trace.request_id == "request-123"
    assert repository.trace.conversation_id == uuid.UUID(int=5)
    assert repository.trace.query_fingerprint != "如何重置密码"
    assert len(repository.trace.query_fingerprint) == 64
    assert repository.trace.query_length == len("如何重置密码")
    assert repository.trace.candidates == [
        {
            "chunk_id": str(repository.chunk.id),
            "document_id": str(repository.document.id),
            "rank": 1,
            "distance": 0.12,
            "locator": {"kind": "document"},
        }
    ]
    assert "请在登录页选择重置密码。" not in str(repository.trace.candidates)


def test_search_skips_trace_when_policy_is_missing_or_disabled() -> None:
    """缺失或关闭策略时，Dense Retrieval 仍正常返回且不写 trace。by AI.Coding"""
    context = _context()
    repository = _FakeKnowledgeRepository(None)
    service = KnowledgeRetrievalService(repository, _FakeEmbeddingProvider())  # type: ignore[arg-type]

    result = asyncio.run(service.search(context, "如何重置密码"))

    assert len(result) == 1
    assert repository.trace is None


def test_search_keeps_result_when_trace_persistence_fails() -> None:
    """追踪存储失败不得中断已经完成的 Dense Retrieval。by AI.Coding"""
    context = _context()
    repository = _FakeKnowledgeRepository(
        RagRetrievalPolicy(workspace_id=context.workspace_id, trace_enabled=True)
    )
    repository.fail_commit = True
    service = KnowledgeRetrievalService(repository, _FakeEmbeddingProvider())  # type: ignore[arg-type]

    result = asyncio.run(service.search(context, "如何重置密码"))

    assert len(result) == 1
    assert result[0].display_name == "密码 FAQ.md"
