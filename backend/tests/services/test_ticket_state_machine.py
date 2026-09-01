"""Ticket 主动状态流转纯逻辑测试。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.enums import TicketCategory, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.services.ticket_state_machine import (
    allowed_status_targets,
    customer_reply_status_target,
)


def make_user(role: UserRole) -> User:
    """创建无需持久化的角色用户。by AI.Coding"""
    return User(
        email=f"state-{role.value.lower()}-{uuid.uuid4().hex}@example.com",
        role=role,
        hashed_password="not-a-real-password-hash",
    )


def make_ticket(
    requester: User,
    *,
    assignee: User | None = None,
    status: TicketStatus,
    deleted: bool = False,
) -> Ticket:
    """创建状态机测试工单。by AI.Coding"""
    return Ticket(
        title="State ticket",
        description="State test ticket.",
        category=TicketCategory.OTHER,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee is not None else None,
        status=status,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


def test_agent_allowed_targets_are_exact() -> None:
    """负责人 Agent 只允许规范的处理中和等待中转换。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)

    in_progress = make_ticket(
        customer, assignee=agent, status=TicketStatus.IN_PROGRESS
    )
    waiting = make_ticket(
        customer, assignee=agent, status=TicketStatus.WAITING_FOR_CUSTOMER
    )
    resolved = make_ticket(customer, assignee=agent, status=TicketStatus.RESOLVED)

    assert allowed_status_targets(agent, in_progress) == {
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
    }
    assert allowed_status_targets(agent, waiting) == {
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
    }
    assert allowed_status_targets(agent, resolved) == set()


def test_admin_allowed_targets_are_exact() -> None:
    """Admin 可按状态规则处理工单，并可关闭已解决工单。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)

    for status, expected in {
        TicketStatus.OPEN: set(),
        TicketStatus.IN_PROGRESS: {
            TicketStatus.WAITING_FOR_CUSTOMER,
            TicketStatus.RESOLVED,
        },
        TicketStatus.WAITING_FOR_CUSTOMER: {
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
        },
        TicketStatus.RESOLVED: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
        TicketStatus.CLOSED: set(),
    }.items():
        ticket = make_ticket(customer, status=status)
        assert allowed_status_targets(admin, ticket) == expected


def test_customer_and_non_owner_agent_have_no_active_targets() -> None:
    """Customer 和非负责人 Agent 不可主动修改状态。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    ticket = make_ticket(
        customer, assignee=agent, status=TicketStatus.IN_PROGRESS
    )

    assert allowed_status_targets(customer, ticket) == set()
    assert allowed_status_targets(other_agent, ticket) == set()

    unassigned = make_ticket(customer, status=TicketStatus.IN_PROGRESS)
    assert allowed_status_targets(agent, unassigned) == set()


def test_open_to_in_progress_requires_claim_or_assignment_flow() -> None:
    """普通状态策略不得绕过接手或分派流程进入处理中。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent, status=TicketStatus.OPEN)

    assert allowed_status_targets(agent, ticket) == set()
    assert allowed_status_targets(admin, ticket) == set()


def test_deleted_and_closed_tickets_have_no_active_targets() -> None:
    """已删除和已关闭工单没有任何主动状态目标。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    deleted = make_ticket(
        customer,
        status=TicketStatus.IN_PROGRESS,
        deleted=True,
    )
    closed = make_ticket(customer, status=TicketStatus.CLOSED)

    assert allowed_status_targets(admin, deleted) == set()
    assert allowed_status_targets(admin, closed) == set()


def test_status_target_result_is_not_shared_between_calls() -> None:
    """每次调用均返回独立集合，调用方修改结果不会污染策略。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, status=TicketStatus.RESOLVED)

    first = allowed_status_targets(admin, ticket)
    first.clear()

    assert allowed_status_targets(admin, ticket) == {
        TicketStatus.IN_PROGRESS,
        TicketStatus.CLOSED,
    }


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TicketStatus.OPEN, None),
        (TicketStatus.IN_PROGRESS, None),
        (TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.IN_PROGRESS),
        (TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS),
        (TicketStatus.CLOSED, None),
    ],
)
def test_customer_reply_status_target(
    status: TicketStatus,
    expected: TicketStatus | None,
) -> None:
    """Customer 回复仅在等待或已解决时计算自动重开目标。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    ticket = make_ticket(customer, status=status)

    original_status = ticket.status
    assert customer_reply_status_target(ticket) is expected
    assert ticket.status is original_status


def test_deleted_customer_reply_has_no_status_target() -> None:
    """软删除工单不产生 Customer 回复自动重开目标。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    ticket = make_ticket(customer, status=TicketStatus.RESOLVED, deleted=True)

    assert customer_reply_status_target(ticket) is None
