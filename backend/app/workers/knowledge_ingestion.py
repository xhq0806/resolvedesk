"""知识文档摄取 worker 的租约领取与执行入口。by AI.Coding"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlmodel import Session, col, select

from app.core.workspace import WorkspaceContext
from app.models.knowledge import (
    DocumentIngestionJob,
    IngestionJobStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.models.workspace import Workspace, WorkspaceMember
from app.providers.embedding import EmbeddingProvider
from app.services.knowledge_service import KnowledgeService

LEASE_SECONDS = 300


def claim_next_job(
    session: Session,
    *,
    workspace_id: UUID | None = None,
) -> tuple[DocumentIngestionJob, KnowledgeDocument] | None:
    """领取一个待处理或租约过期的任务，避免多 worker 重复执行。by AI.Coding"""
    now = datetime.now(UTC)
    statement = (
        select(DocumentIngestionJob, KnowledgeDocument)
        .join(
            KnowledgeDocument,
            col(KnowledgeDocument.id) == col(DocumentIngestionJob.document_id),
        )
        .where(
            col(DocumentIngestionJob.status) == IngestionJobStatus.PENDING,
            col(KnowledgeDocument.status) != KnowledgeDocumentStatus.DELETED,
        )
        .order_by(col(DocumentIngestionJob.created_at))
        .limit(1)
    )
    if workspace_id is not None:
        statement = statement.where(
            col(DocumentIngestionJob.workspace_id) == workspace_id,
            col(KnowledgeDocument.workspace_id) == workspace_id,
        )
    row = session.exec(statement).first()
    if row is None:
        return None
    job, document = row
    job.status = IngestionJobStatus.RUNNING
    job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    job.updated_at = now
    session.add(job)
    session.commit()
    session.refresh(job)
    return job, document


def recover_expired_jobs(session: Session) -> int:
    """将 worker 崩溃后超时的 RUNNING 任务恢复为 PENDING。by AI.Coding"""
    now = datetime.now(UTC)
    jobs = session.exec(
        select(DocumentIngestionJob).where(
            col(DocumentIngestionJob.status) == IngestionJobStatus.RUNNING,
            col(DocumentIngestionJob.lease_until).is_not(None),
            col(DocumentIngestionJob.lease_until) < now,
        )
    ).all()
    for job in jobs:
        job.status = IngestionJobStatus.PENDING
        job.lease_until = None
        job.updated_at = now
        session.add(job)
    session.commit()
    return len(jobs)


def process_claimed_job(
    session: Session,
    job: DocumentIngestionJob,
    document: KnowledgeDocument,
    *,
    embedding_provider: EmbeddingProvider,
) -> KnowledgeDocument:
    """在独立数据库会话中执行已领取的文档摄取任务。by AI.Coding"""
    if job.document_id != document.id or job.workspace_id != document.workspace_id:
        raise ValueError("摄取任务与文档租户不匹配")
    context = WorkspaceContext(
        workspace=_workspace_for_document(session, document),
        member=_owner_member_for_workspace(session, document.workspace_id),
    )
    return KnowledgeService(session).ingest_document(
        context,
        document.id,
        embedding_provider,
    )


def _workspace_for_document(session: Session, document: KnowledgeDocument) -> Workspace:
    """读取文档所属 Workspace，保持 worker 的租户边界。by AI.Coding"""
    workspace = session.get(Workspace, document.workspace_id)
    if workspace is None:
        raise RuntimeError("文档所属 Workspace 不存在")
    return workspace


def _owner_member_for_workspace(
    session: Session, workspace_id: UUID
) -> WorkspaceMember:
    """为内部 worker 构造最小管理上下文，不暴露给 HTTP 用户。by AI.Coding"""
    from app.models.workspace import WorkspaceRole

    member = session.exec(
        select(WorkspaceMember).where(
            col(WorkspaceMember.workspace_id) == workspace_id,
            col(WorkspaceMember.role) == WorkspaceRole.OWNER,
        )
    ).first()
    if member is None:
        raise RuntimeError("Workspace 没有可用 Owner")
    return member
