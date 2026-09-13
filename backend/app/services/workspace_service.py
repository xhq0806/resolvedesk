"""Workspace、成员和邀请业务服务。by AI.Coding"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.workspace import WorkspaceContext, WorkspacePolicy
from app.models.ai import AiAgent
from app.models.user import User
from app.models.workspace import (
    MembershipStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceRole,
)
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import (
    InvitationCreate,
    MemberRoleUpdate,
    WorkspaceCreate,
)


class WorkspaceService:
    """编排 Workspace 资源和成员关系的事务行为。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求级数据库会话和仓储。by AI.Coding"""
        self.session = session
        self.repository = WorkspaceRepository(session)

    def list_workspaces(self, actor: User) -> list[tuple[Workspace, WorkspaceMember]]:
        """返回当前用户的有效 Workspace。by AI.Coding"""
        return self.repository.list_for_user(actor.id)

    def create_workspace(self, actor: User, payload: WorkspaceCreate) -> Workspace:
        """创建 Workspace 并将创建者设为 Owner。by AI.Coding"""
        workspace = Workspace(
            name=payload.name.strip(),
            slug=payload.slug.strip().lower(),
            owner_user_id=actor.id,
        )
        self.session.add(workspace)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(ErrorCode.WORKSPACE_MEMBER_CONFLICT) from exc
        self.session.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=actor.id, role=WorkspaceRole.OWNER
            )
        )
        self.session.add(AiAgent(workspace_id=workspace.id))
        self.session.commit()
        self.session.refresh(workspace)
        return workspace

    def invite(
        self, context: WorkspaceContext, payload: InvitationCreate
    ) -> WorkspaceInvitation:
        """创建 Workspace 邀请并仅保存 token hash。by AI.Coding"""
        WorkspacePolicy.require_manager(context)
        email = str(payload.email).lower()
        user = self.repository.get_user_by_email(email)
        if user and self.repository.get_member(context.workspace_id, user.id):
            raise ConflictError(ErrorCode.WORKSPACE_MEMBER_CONFLICT)
        raw_token = secrets.token_urlsafe(32)
        invitation = WorkspaceInvitation(
            workspace_id=context.workspace_id,
            email=email,
            role=payload.role,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        self.session.add(invitation)
        self.session.commit()
        self.session.refresh(invitation)
        return invitation

    def update_member_role(
        self, context: WorkspaceContext, user_id: uuid.UUID, payload: MemberRoleUpdate
    ) -> WorkspaceMember:
        """修改成员角色并保护 Owner 数量。by AI.Coding"""
        WorkspacePolicy.require_manager(context)
        member = self.repository.get_member(context.workspace_id, user_id)
        if member is None or member.status is not MembershipStatus.ACTIVE:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if (
            member.role is WorkspaceRole.OWNER
            and payload.role is not WorkspaceRole.OWNER
        ):
            owner_count = self.session.exec(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == context.workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.status == MembershipStatus.ACTIVE,
                )
            ).all()
            if len(owner_count) <= 1:
                raise ConflictError(ErrorCode.WORKSPACE_MEMBER_CONFLICT)
        member.role = payload.role
        self.session.add(member)
        self.session.commit()
        self.session.refresh(member)
        return member

    def remove_member(self, context: WorkspaceContext, user_id: uuid.UUID) -> None:
        """移除成员并保护最后一个 Owner。by AI.Coding"""
        WorkspacePolicy.require_manager(context)
        member = self.repository.get_member(context.workspace_id, user_id)
        if member is None or member.status is not MembershipStatus.ACTIVE:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if member.role is WorkspaceRole.OWNER:
            owner_count = self.session.exec(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == context.workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.status == MembershipStatus.ACTIVE,
                )
            ).all()
            if len(owner_count) <= 1:
                raise ConflictError(ErrorCode.WORKSPACE_MEMBER_CONFLICT)
        member.status = MembershipStatus.REMOVED
        self.session.add(member)
        self.session.commit()
