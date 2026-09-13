"""Workspace、成员和邀请 HTTP 接口。by AI.Coding"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, SessionDep, WorkspaceContextDep
from app.core.errors import ErrorCode, NotFoundError
from app.models.workspace import WorkspaceRole
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import (
    InvitationCreate,
    InvitationPublic,
    MemberPublic,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceSummary,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceSummary])
def list_workspaces(
    session: SessionDep, current_user: CurrentUser
) -> list[WorkspaceSummary]:
    """返回当前用户可以切换的 Workspace。by AI.Coding"""
    memberships = WorkspaceService(session).list_workspaces(current_user)
    return [
        WorkspaceSummary(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            status=workspace.status,
            role=member.role,
        )
        for workspace, member in memberships
    ]


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
def create_workspace(
    session: SessionDep, current_user: CurrentUser, payload: WorkspaceCreate
) -> WorkspaceDetail:
    """创建 Workspace 并将当前用户设为 Owner。by AI.Coding"""
    workspace = WorkspaceService(session).create_workspace(current_user, payload)
    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        status=workspace.status,
        role=WorkspaceRole.OWNER,
        owner_user_id=workspace.owner_user_id,
        created_at=workspace.created_at,
    )


@router.get("/{workspace_id}/members", response_model=list[MemberPublic])
def list_members(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> list[MemberPublic]:
    """返回当前 Workspace 的有效成员。by AI.Coding"""
    del current_user
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    members = WorkspaceRepository(session).list_members(context.workspace_id)
    return [MemberPublic.model_validate(member) for member in members]


@router.post(
    "/{workspace_id}/invitations",
    response_model=InvitationPublic,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: InvitationCreate,
) -> InvitationPublic:
    """由 Owner/Admin 创建成员邀请。by AI.Coding"""
    del current_user
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    invitation = WorkspaceService(session).invite(context, payload)
    return InvitationPublic.model_validate(invitation)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberPublic)
def update_member_role(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
) -> MemberPublic:
    """修改指定 Workspace 成员角色。by AI.Coding"""
    del current_user
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    member = WorkspaceService(session).update_member_role(context, user_id, payload)
    return MemberPublic.model_validate(member)


@router.delete(
    "/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Response:
    """移除成员并保护最后一个 Owner。by AI.Coding"""
    del current_user
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    WorkspaceService(session).remove_member(context, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
