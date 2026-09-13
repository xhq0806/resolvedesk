"""附件安全校验、隔离存储和资源授权服务。by AI.Coding"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.errors import ErrorCode, NotFoundError, ValidationError
from app.core.workspace import WorkspaceContext
from app.models.ai import AiConversation
from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import WorkspaceRole

ATTACHMENT_MIMES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class AttachmentUpload(Protocol):
    """上传对象所需的最小异步读取接口。by AI.Coding"""

    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes:
        """读取上传字节。by AI.Coding"""
        ...


def validate_attachment_bytes(
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> tuple[str, str]:
    """校验附件扩展名、MIME、大小和常见 magic number。by AI.Coding"""
    if not filename or Path(filename).name != filename:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    extension = Path(filename).suffix.lower()
    expected_mime = ATTACHMENT_MIMES.get(extension)
    if (
        expected_mime is None
        or not content
        or len(content) > settings.ATTACHMENT_MAX_FILE_BYTES
    ):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    supplied_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if supplied_mime and supplied_mime != expected_mime:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    signatures = {
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }
    signature = signatures.get(extension)
    if signature and not content.startswith(signature):
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return extension, expected_mime


class AttachmentService:
    """管理 Workspace 工单/会话附件的安全生命周期。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存数据库会话。by AI.Coding"""
        self.session = session

    async def upload_ticket_attachment(
        self,
        context: WorkspaceContext,
        actor: User,
        ticket_id: uuid.UUID,
        upload: AttachmentUpload,
    ) -> Attachment:
        """校验工单归属和附件内容后写入隔离存储。by AI.Coding"""
        ticket = self._authorized_ticket(context, actor, ticket_id)
        filename = upload.filename or ""
        content = await upload.read(settings.ATTACHMENT_MAX_FILE_BYTES + 1)
        extension, mime_type = validate_attachment_bytes(
            filename,
            upload.content_type,
            content,
        )
        attachment_id = uuid.uuid4()
        storage_key = f"{context.workspace_id}/{attachment_id}{extension}"
        path = self._storage_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        attachment = Attachment(
            id=attachment_id,
            workspace_id=context.workspace_id,
            ticket_id=ticket.id,
            storage_key=storage_key,
            display_name=Path(filename).name,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            uploaded_by_id=actor.id,
        )
        self.session.add(attachment)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            path.unlink(missing_ok=True)
            raise
        self.session.refresh(attachment)
        return attachment

    def list_ticket_attachments(
        self,
        context: WorkspaceContext,
        actor: User,
        ticket_id: uuid.UUID,
    ) -> list[Attachment]:
        """返回当前用户有权查看的工单附件。by AI.Coding"""
        self._authorized_ticket(context, actor, ticket_id)
        return list(
            self.session.exec(
                select(Attachment)
                .where(
                    col(Attachment.workspace_id) == context.workspace_id,
                    col(Attachment.ticket_id) == ticket_id,
                    col(Attachment.deleted_at).is_(None),
                )
                .order_by(col(Attachment.created_at))
            ).all()
        )

    def get_content(
        self,
        context: WorkspaceContext,
        actor: User,
        attachment_id: uuid.UUID,
    ) -> tuple[Attachment, Path]:
        """授权后返回附件元数据和安全存储路径。by AI.Coding"""
        attachment = self.session.exec(
            select(Attachment).where(
                col(Attachment.id) == attachment_id,
                col(Attachment.workspace_id) == context.workspace_id,
                col(Attachment.deleted_at).is_(None),
            )
        ).first()
        if attachment is None:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if attachment.ticket_id is not None:
            self._authorized_ticket(context, actor, attachment.ticket_id)
        elif attachment.conversation_id is not None:
            self._authorized_conversation(context, actor, attachment.conversation_id)
        path = self._storage_path(attachment.storage_key)
        if not path.is_file():
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return attachment, path

    def delete(
        self,
        context: WorkspaceContext,
        actor: User,
        attachment_id: uuid.UUID,
    ) -> None:
        """软删除附件并移除文件内容，保留元数据审计入口。by AI.Coding"""
        attachment, path = self.get_content(context, actor, attachment_id)
        if attachment.uploaded_by_id != actor.id and context.role not in {
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
            WorkspaceRole.AGENT,
        }:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        attachment.deleted_at = datetime.now(UTC)
        self.session.add(attachment)
        self.session.commit()
        path.unlink(missing_ok=True)

    def _authorized_ticket(
        self,
        context: WorkspaceContext,
        actor: User,
        ticket_id: uuid.UUID,
    ) -> Ticket:
        """校验工单属于当前租户且用户是请求者、负责人或客服。by AI.Coding"""
        ticket = self.session.exec(
            select(Ticket).where(
                col(Ticket.id) == ticket_id,
                col(Ticket.workspace_id) == context.workspace_id,
                col(Ticket.deleted_at).is_(None),
            )
        ).first()
        if ticket is None:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if (
            ticket.requester_id != actor.id
            and ticket.assignee_id != actor.id
            and context.role
            not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.AGENT}
        ):
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return ticket

    def _authorized_conversation(
        self,
        context: WorkspaceContext,
        actor: User,
        conversation_id: uuid.UUID,
    ) -> AiConversation:
        """校验会话属于当前 Workspace 且创建者或客服可访问。by AI.Coding"""
        conversation = self.session.exec(
            select(AiConversation).where(
                col(AiConversation.id) == conversation_id,
                col(AiConversation.workspace_id) == context.workspace_id,
            )
        ).first()
        if conversation is None:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if (
            conversation.created_by_id != actor.id
            and context.role
            not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.AGENT}
        ):
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return conversation

    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        """解析附件存储键并阻断路径穿越。by AI.Coding"""
        root = settings.ATTACHMENT_STORAGE_DIR.resolve()
        path = (root / storage_key).resolve()
        if root not in path.parents:
            raise ValueError("非法附件路径")
        return path
