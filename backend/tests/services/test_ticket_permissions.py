"""Ticket 三角色资源权限纯逻辑测试。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.enums import TicketCategory, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.services.ticket_permissions import (
    can_add_internal_note,
    can_manage_ticket,
    can_reply_publicly,
    can_view_internal_notes,
    can_view_ticket,
)


def make_user(role: UserRole) -> User:
    """创建无需持久化的角色用户。by AI.Coding"""
    return User(
        email=f"policy-{role.value.lower()}-{uuid.uuid4().hex}@example.com",
        role=role,
        hashed_password="not-a-real-password-hash",
    )


def make_ticket(
    requester: User,
    *,
    assignee: User | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    deleted: bool = False,
) -> Ticket:
    """创建仅包含策略所需标量字段的未持久化工单。by AI.Coding"""
    return Ticket(
        title="Policy ticket",
        description="Policy test ticket.",
        category=TicketCategory.OTHER,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee is not None else None,
        status=status,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


def test_ticket_visibility_follows_role_scope() -> None:
    """Customer、Agent 和 Admin 只能看到各自角色范围。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    other_customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)

    own = make_ticket(customer)
    other = make_ticket(other_customer)
    assigned_to_agent = make_ticket(other_customer, assignee=agent)
    assigned_to_other = make_ticket(other_customer, assignee=other_agent)

    # Customer 只按 requester 关系访问，负责人不改变其所有权。
    assert can_view_ticket(customer, own)
    assert not can_view_ticket(customer, other)
    assert can_view_ticket(agent, other)
    assert can_view_ticket(agent, assigned_to_agent)
    assert not can_view_ticket(agent, assigned_to_other)
    assert can_view_ticket(admin, other)
    assert can_view_ticket(admin, assigned_to_other)


@pytest.mark.parametrize("role", list(UserRole))
def test_soft_deleted_ticket_is_hidden_from_every_role(role: UserRole) -> None:
    """软删除工单在普通业务权限中统一视为不存在。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    actor = customer if role is UserRole.CUSTOMER else make_user(role)
    ticket = make_ticket(customer, assignee=actor, deleted=True)

    assert not can_view_ticket(actor, ticket)
    assert not can_view_internal_notes(actor, ticket)
    assert not can_reply_publicly(actor, ticket)
    assert not can_add_internal_note(actor, ticket)
    assert not can_manage_ticket(actor, ticket)


@pytest.mark.parametrize("role", list(UserRole))
def test_closed_ticket_remains_visible_but_read_only(role: UserRole) -> None:
    """关闭工单保留历史读取能力并拒绝普通业务写入。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    actor = customer if role is UserRole.CUSTOMER else make_user(role)
    assignee = actor if role is UserRole.AGENT else None
    ticket = make_ticket(customer, assignee=assignee, status=TicketStatus.CLOSED)

    assert can_view_ticket(actor, ticket)
    assert not can_reply_publicly(actor, ticket)
    assert not can_add_internal_note(actor, ticket)
    assert not can_manage_ticket(actor, ticket)

    # Closed 只限制新增写入，不隐藏 Staff 可见的历史内部备注。
    expected_internal_visibility = role in {UserRole.AGENT, UserRole.ADMIN}
    assert can_view_internal_notes(actor, ticket) is expected_internal_visibility


def test_unassigned_agent_can_view_but_cannot_access_internal_or_write() -> None:
    """Agent 浏览未分派队列时只能读取基础信息。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = make_ticket(customer)

    assert can_view_ticket(agent, ticket)
    assert not can_view_internal_notes(agent, ticket)
    assert not can_reply_publicly(agent, ticket)
    assert not can_add_internal_note(agent, ticket)
    assert not can_manage_ticket(agent, ticket)


def test_internal_note_visibility_requires_staff_scope() -> None:
    """内部备注仅对当前负责人 Agent 和 Admin 可见。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent)

    assert not can_view_internal_notes(customer, ticket)
    assert can_view_internal_notes(agent, ticket)
    assert not can_view_internal_notes(other_agent, ticket)
    assert can_view_internal_notes(admin, ticket)


@pytest.mark.parametrize(
    "status",
    [
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
    ],
)
def test_public_reply_permissions_cover_every_non_closed_status(
    status: TicketStatus,
) -> None:
    """三角色仅在各自资源范围内回复未关闭工单。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    other_customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent, status=status)

    assert can_reply_publicly(customer, ticket)
    assert not can_reply_publicly(other_customer, ticket)
    assert can_reply_publicly(agent, ticket)
    assert not can_reply_publicly(other_agent, ticket)
    assert can_reply_publicly(admin, ticket)


@pytest.mark.parametrize(
    ("role", "assigned_to_actor", "expected"),
    [
        (UserRole.CUSTOMER, False, False),
        (UserRole.AGENT, False, False),
        (UserRole.AGENT, True, True),
        (UserRole.ADMIN, False, True),
        (UserRole.ADMIN, True, True),
    ],
)
def test_internal_note_and_management_permissions(
    role: UserRole,
    assigned_to_actor: bool,
    expected: bool,
) -> None:
    """内部备注和普通管理写入遵循相同 Staff 资源边界。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    actor = customer if role is UserRole.CUSTOMER else make_user(role)
    ticket = make_ticket(
        customer,
        assignee=actor if assigned_to_actor else None,
        status=TicketStatus.RESOLVED,
    )

    assert can_add_internal_note(actor, ticket) is expected
    assert can_manage_ticket(actor, ticket) is expected
