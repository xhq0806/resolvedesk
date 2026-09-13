"""Workspace 领域查询和持久化仓储。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlmodel import Session, col, select

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceInvitation, WorkspaceMember


class WorkspaceRepository:
    """封装 Workspace 关系查询，保持 service 不直接拼接查询。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求级数据库会话。by AI.Coding"""
        self.session = session

    def list_for_user(
        self, user_id: uuid.UUID
    ) -> list[tuple[Workspace, WorkspaceMember]]:
        """返回用户当前可访问的 Workspace 及成员关系。by AI.Coding"""
        statement = (
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, col(WorkspaceMember.workspace_id) == Workspace.id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "ACTIVE",
            )
            .order_by(col(Workspace.created_at))
        )
        return list(self.session.exec(statement).all())

    def get_member(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        """按 Workspace 和用户读取成员关系。by AI.Coding"""
        return self.session.exec(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        ).first()

    def get_user_by_email(self, email: str) -> User | None:
        """按规范化邮箱读取用户。by AI.Coding"""
        return self.session.exec(select(User).where(User.email == email)).first()

    def get_invitation(self, invitation_id: uuid.UUID) -> WorkspaceInvitation | None:
        """读取指定邀请记录。by AI.Coding"""
        return self.session.get(WorkspaceInvitation, invitation_id)

    def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        """返回 Workspace 的有效成员列表。by AI.Coding"""
        return list(
            self.session.exec(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.status == "ACTIVE",
                )
            ).all()
        )
