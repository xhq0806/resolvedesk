"""工单角色化统计服务。by AI.Coding"""

from __future__ import annotations

from sqlmodel import Session

from app.core.workspace import WorkspaceContext
from app.models.enums import UserRole
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketStatisticsPublic


class StatisticsService:
    """编排统计仓储查询并按角色裁剪公开响应。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        self.ticket_repository = TicketRepository(session)

    def get_ticket_statistics(
        self,
        actor: User,
        *,
        context: WorkspaceContext | None = None,
    ) -> TicketStatisticsPublic:
        """返回当前角色授权范围内的工单统计。by AI.Coding"""
        role = self._role(context, actor)
        statistics = self.ticket_repository.get_statistics(
            actor,
            workspace_id=context.workspace_id if context else None,
            role=context.role if context else None,
        )
        if role is UserRole.CUSTOMER:
            return TicketStatisticsPublic(
                role=role,
                status_counts=statistics.status_counts,
            )
        if role is UserRole.AGENT:
            return TicketStatisticsPublic(
                role=role,
                unassigned_count=statistics.unassigned_count,
                assigned_to_me_count=statistics.assigned_to_me_count,
                waiting_for_customer_count=statistics.waiting_for_customer_count,
            )
        return TicketStatisticsPublic(
            role=role,
            status_counts=statistics.status_counts,
            priority_counts=statistics.priority_counts,
            unassigned_count=statistics.unassigned_count,
        )

    @staticmethod
    def _role(context: WorkspaceContext | None, actor: User) -> UserRole:
        """将 Workspace 角色转换为统计响应沿用的一期角色。by AI.Coding"""
        if context is None:
            return actor.role
        if context.role is WorkspaceRole.CUSTOMER:
            return UserRole.CUSTOMER
        if context.role is WorkspaceRole.AGENT:
            return UserRole.AGENT
        return UserRole.ADMIN
