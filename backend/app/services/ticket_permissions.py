"""Ticket 三角色可见性与普通写权限纯策略。by AI.Coding"""

from __future__ import annotations

from app.models.enums import TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User


def can_view_ticket(actor: User, ticket: Ticket) -> bool:
    """判断当前用户是否可读取普通业务工单。by AI.Coding"""
    # 软删除资源在所有普通业务入口中统一视为不存在。
    if ticket.deleted_at is not None:
        return False
    if actor.role is UserRole.CUSTOMER:
        return ticket.requester_id == actor.id
    if actor.role is UserRole.AGENT:
        return ticket.assignee_id is None or ticket.assignee_id == actor.id
    return actor.role is UserRole.ADMIN


def can_view_internal_notes(actor: User, ticket: Ticket) -> bool:
    """判断当前用户是否可读取工单内部备注。by AI.Coding"""
    # 内部备注采用比基础工单更窄的 Staff 资源范围。
    if not can_view_ticket(actor, ticket):
        return False
    if actor.role is UserRole.AGENT:
        return ticket.assignee_id == actor.id
    return actor.role is UserRole.ADMIN


def can_reply_publicly(actor: User, ticket: Ticket) -> bool:
    """判断当前用户是否可向工单发送公开回复。by AI.Coding"""
    # CLOSED 仍可读取历史，但所有普通业务写入均被拒绝。
    if ticket.status is TicketStatus.CLOSED or not can_view_ticket(actor, ticket):
        return False
    if actor.role is UserRole.CUSTOMER:
        return ticket.requester_id == actor.id
    if actor.role is UserRole.AGENT:
        return ticket.assignee_id == actor.id
    return actor.role is UserRole.ADMIN


def can_add_internal_note(actor: User, ticket: Ticket) -> bool:
    """判断当前用户是否可向工单添加内部备注。by AI.Coding"""
    # 写入权限要求未关闭且处于 Staff 可管理的资源范围。
    if ticket.status is TicketStatus.CLOSED or ticket.deleted_at is not None:
        return False
    if actor.role is UserRole.AGENT:
        return ticket.assignee_id == actor.id
    return actor.role is UserRole.ADMIN


def can_manage_ticket(actor: User, ticket: Ticket) -> bool:
    """判断用户是否可修改普通状态、优先级或分类。by AI.Coding"""
    # 接手、分派、取消分派和删除属于后续专门流程，不包含在本策略中。
    if ticket.status is TicketStatus.CLOSED or ticket.deleted_at is not None:
        return False
    if actor.role is UserRole.AGENT:
        return ticket.assignee_id == actor.id
    return actor.role is UserRole.ADMIN
