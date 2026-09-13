"""工单附件上传、下载和删除 HTTP 接口。by AI.Coding"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, SessionDep, WorkspaceContextDep
from app.core.errors import ErrorCode, NotFoundError
from app.schemas.attachment import AttachmentPublic
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/workspaces/{workspace_id}/tickets", tags=["attachments"])


def _ensure_same_workspace(
    workspace_id: uuid.UUID,
    context: WorkspaceContextDep,
) -> None:
    """校验路径租户与请求头租户一致。by AI.Coding"""
    if workspace_id != context.workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)


@router.post(
    "/{ticket_id}/attachments",
    response_model=AttachmentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    ticket_id: uuid.UUID,
    file: UploadFile = File(...),
) -> AttachmentPublic:
    """上传与当前工单关联的附件。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    attachment = await AttachmentService(session).upload_ticket_attachment(
        context, current_user, ticket_id, file
    )
    return AttachmentPublic.model_validate(attachment)


@router.get("/{ticket_id}/attachments", response_model=list[AttachmentPublic])
def list_attachments(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    ticket_id: uuid.UUID,
) -> list[AttachmentPublic]:
    """列出当前用户可见的工单附件元数据。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    return [
        AttachmentPublic.model_validate(item)
        for item in AttachmentService(session).list_ticket_attachments(
            context, current_user, ticket_id
        )
    ]


@router.get("/attachments/{attachment_id}/content")
def download_attachment(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> FileResponse:
    """授权下载附件内容，响应不暴露内部存储路径。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    attachment, path = AttachmentService(session).get_content(
        context, current_user, attachment_id
    )
    return FileResponse(
        path,
        media_type=attachment.mime_type,
        filename=attachment.display_name,
    )


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> None:
    """删除本人附件或由客服删除工单附件。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    AttachmentService(session).delete(context, current_user, attachment_id)
