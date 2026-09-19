"""Workspace 知识库文档管理 HTTP 接口。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, File, Query, UploadFile, status

from app.api.deps import CurrentUser, SessionDep, WorkspaceContextDep
from app.core.errors import ErrorCode, NotFoundError
from app.core.request_context import get_request_id
from app.core.workspace import WorkspacePolicy
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    DocumentIngestionJobPublic,
    KnowledgeDocumentPublic,
    KnowledgeSearchRequest,
    RagRetrievalPolicyPatch,
    RagRetrievalPolicyPublic,
    RagRetrievalTracePublic,
    RetrievedChunkPublic,
)
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalService,
    RagRetrievalPolicyService,
    RetrievalTraceContext,
)
from app.services.knowledge_service import KnowledgeService
from app.services.provider_service import ProviderService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/knowledge",
    tags=["knowledge"],
)


def _ensure_same_workspace(
    workspace_id: uuid.UUID,
    context: WorkspaceContextDep,
) -> None:
    """校验路径与请求头租户一致，避免跨租户文档探测。by AI.Coding"""
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)


@router.get("/documents", response_model=list[KnowledgeDocumentPublic])
def list_documents(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> list[KnowledgeDocumentPublic]:
    """返回当前 Workspace 的知识文档状态列表。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return [
        KnowledgeDocumentPublic.model_validate(document)
        for document in KnowledgeService(session).list_documents(context)
    ]


@router.post(
    "/documents",
    response_model=KnowledgeDocumentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
) -> KnowledgeDocumentPublic:
    """上传文档并创建异步摄取任务，不在 HTTP 请求内调用模型。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    document, _ = await KnowledgeService(session).create_document(context, current_user, file)
    return KnowledgeDocumentPublic.model_validate(document)


@router.post("/search", response_model=list[RetrievedChunkPublic])
async def search_knowledge(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: KnowledgeSearchRequest,
) -> list[RetrievedChunkPublic]:
    """检索当前 Workspace READY 文档并返回可定位来源预览。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    WorkspacePolicy.require_manager(context)
    provider = ProviderService(session).build_embedding_provider(context)
    rows = await KnowledgeRetrievalService(
        KnowledgeRepository(session),
        provider,
    ).search(
        context,
        payload.query,
        limit=payload.limit,
        trace_context=RetrievalTraceContext(
            request_id=get_request_id() or str(uuid.uuid4())
        ),
    )
    return [
        RetrievedChunkPublic(
            chunk_id=uuid.UUID(row.chunk_id),
            document_id=uuid.UUID(row.document_id),
            display_name=row.display_name,
            locator=row.locator,
            preview=row.content[:500],
            distance=row.distance,
        )
        for row in rows
    ]


@router.get("/retrieval-policy", response_model=RagRetrievalPolicyPublic)
def get_retrieval_policy(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> RagRetrievalPolicyPublic:
    """返回当前 Workspace 的 RAG 观测策略。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    WorkspacePolicy.require_manager(context)
    return RagRetrievalPolicyPublic.model_validate(
        RagRetrievalPolicyService(session).get_policy(context)
    )


@router.patch("/retrieval-policy", response_model=RagRetrievalPolicyPublic)
def update_retrieval_policy(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: RagRetrievalPolicyPatch,
) -> RagRetrievalPolicyPublic:
    """更新当前 Workspace 的 RAG 观测策略。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    WorkspacePolicy.require_manager(context)
    policy = RagRetrievalPolicyService(session).update_policy(
        context,
        trace_enabled=payload.trace_enabled,
        strategy_version=payload.strategy_version,
    )
    return RagRetrievalPolicyPublic.model_validate(policy)


@router.get("/retrieval-traces", response_model=list[RagRetrievalTracePublic])
def list_retrieval_traces(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    before: datetime | None = None,
) -> list[RagRetrievalTracePublic]:
    """按时间倒序返回当前 Workspace 的无正文检索追踪。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    WorkspacePolicy.require_manager(context)
    return [
        RagRetrievalTracePublic.model_validate(trace)
        for trace in RagRetrievalPolicyService(session).list_traces(
            context,
            limit=limit,
            before=before,
        )
    ]


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentPublic)
def get_document(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> KnowledgeDocumentPublic:
    """返回当前 Workspace 的单个文档状态。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    document = KnowledgeService(session).get_document(context, document_id)
    return KnowledgeDocumentPublic.model_validate(document)


@router.post(
    "/documents/{document_id}/retry",
    response_model=DocumentIngestionJobPublic,
)
def retry_document(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentIngestionJobPublic:
    """重试当前 Workspace 的失败摄取任务。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    job = KnowledgeService(session).retry_document(context, document_id)
    return DocumentIngestionJobPublic.model_validate(job)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """软删除当前 Workspace 文档并清理向量切块。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    KnowledgeService(session).delete_document(context, document_id)
