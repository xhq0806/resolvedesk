"""Workspace 请求上下文和成员权限策略。by AI.Coding"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.errors import ErrorCode, ForbiddenError, NotFoundError
from app.models.user import User
from app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceStatus,
)


@dataclass(frozen=True)
class WorkspaceContext:
    """绑定当前用户、Workspace 和成员关系的不可变上下文。by AI.Coding"""

    workspace: Workspace
    member: WorkspaceMember

    @property
    def workspace_id(self) -> uuid.UUID:
        """返回当前 Workspace 主键。by AI.Coding"""
        return self.workspace.id

    @property
    def role(self) -> WorkspaceRole:
        """返回当前用户在 Workspace 内的角色。by AI.Coding"""
        return self.member.role


class WorkspacePolicy:
    """集中执行 Workspace 成员和管理角色策略。by AI.Coding"""

    @staticmethod
    def require_active_workspace(workspace: Workspace | None) -> Workspace:
        """要求 Workspace 存在且未停用。by AI.Coding"""
        if workspace is None or workspace.status is not WorkspaceStatus.ACTIVE:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return workspace

    @staticmethod
    def require_member(member: WorkspaceMember | None) -> WorkspaceMember:
        """要求成员存在且处于 ACTIVE 状态。by AI.Coding"""
        if member is None or member.status.value != "ACTIVE":
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return member

    @staticmethod
    def require_manager(context: WorkspaceContext) -> None:
        """要求当前成员拥有 Workspace 管理权限。by AI.Coding"""
        if context.role not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}:
            raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)

    @staticmethod
    def require_owner(context: WorkspaceContext) -> None:
        """要求当前成员是 Workspace Owner。by AI.Coding"""
        if context.role is not WorkspaceRole.OWNER:
            raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)


def build_workspace_context(
    workspace: Workspace | None,
    member: WorkspaceMember | None,
) -> WorkspaceContext:
    """从查询结果构造并校验 WorkspaceContext。by AI.Coding"""
    active_workspace = WorkspacePolicy.require_active_workspace(workspace)
    return WorkspaceContext(
        workspace=active_workspace, member=WorkspacePolicy.require_member(member)
    )


def ensure_workspace_owner(user: User, member: WorkspaceMember) -> None:
    """确认成员记录对应的用户身份，避免混用其他用户关系。by AI.Coding"""
    if member.user_id != user.id:
        raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)
