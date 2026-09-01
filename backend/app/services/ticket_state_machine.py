"""Ticket 状态转换与 Customer 回复重开纯策略。by AI.Coding"""

from __future__ import annotations

from app.models.enums import TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User


def allowed_status_targets(actor: User, ticket: Ticket) -> set[TicketStatus]:
    """返回用户对当前工单可执行的主动状态目标。by AI.Coding"""
    # 软删除和关闭工单不允许普通状态写入；前者应由 Service 映射为不存在。
    if ticket.deleted_at is not None or ticket.status is TicketStatus.CLOSED:
        return set()

    # Customer 只能通过公开回复触发特定自动重开，不能主动修改状态。
    if actor.role is UserRole.CUSTOMER:
        return set()

    # Agent 只有当前负责人可以主动处理工单，未分派队列不具备写权限。
    if actor.role is UserRole.AGENT and ticket.assignee_id != actor.id:
        return set()

    if ticket.status is TicketStatus.IN_PROGRESS:
        return {TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.RESOLVED}
    if ticket.status is TicketStatus.WAITING_FOR_CUSTOMER:
        return {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED}
    if ticket.status is TicketStatus.RESOLVED and actor.role is UserRole.ADMIN:
        return {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED}

    # OPEN → IN_PROGRESS 只允许由接手/分派专门流程完成，不能被普通状态接口绕过。
    return set()


def customer_reply_status_target(ticket: Ticket) -> TicketStatus | None:
    """计算 Customer 公开回复后是否需要自动重开工单。by AI.Coding"""
    # 已删除或 CLOSED 工单不产生自动写入目标，回复权限由权限策略单独判断。
    if ticket.deleted_at is not None or ticket.status is TicketStatus.CLOSED:
        return None
    if ticket.status in {
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
    }:
        return TicketStatus.IN_PROGRESS
    return None
