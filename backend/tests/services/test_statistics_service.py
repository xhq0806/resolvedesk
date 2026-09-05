"""StatisticsService 角色化统计测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlmodel import Session, col

from app.core.db import engine
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketStatisticsPublic
from app.services.statistics_service import StatisticsService


class TrackedGraph:
    """记录统计测试创建的数据主键。by AI.Coding"""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.ticket_ids: list[uuid.UUID] = []


@pytest.fixture
def tracked_graph() -> Iterator[TrackedGraph]:
    """按外键依赖顺序清理统计测试数据。by AI.Coding"""
    graph = TrackedGraph()
    yield graph
    with Session(engine) as session:
        if graph.ticket_ids:
            session.exec(delete(Ticket).where(col(Ticket.id).in_(graph.ticket_ids)))
        if graph.user_ids:
            session.exec(delete(User).where(col(User.id).in_(graph.user_ids)))
        session.commit()


def make_user(role: UserRole) -> User:
    """创建统计服务测试用户。by AI.Coding"""
    return User(
        email=f"statistics-service-{uuid.uuid4().hex}@example.com",
        role=role,
        hashed_password="not-a-real-password-hash",
    )


def make_ticket(
    requester: User,
    *,
    assignee: User | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    priority: TicketPriority = TicketPriority.MEDIUM,
    deleted: bool = False,
) -> Ticket:
    """创建统计服务测试工单。by AI.Coding"""
    return Ticket(
        title="Statistics service ticket",
        description="StatisticsService test.",
        category=TicketCategory.OTHER,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        status=status,
        priority=priority,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


def persist(graph: TrackedGraph, users: list[User], tickets: list[Ticket]) -> None:
    """持久化并登记统计测试数据。by AI.Coding"""
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(users)
        session.add_all(tickets)
        session.commit()
    graph.user_ids.extend(user.id for user in users)
    graph.ticket_ids.extend(ticket.id for ticket in tickets)


def test_statistics_service_returns_role_specific_public_fields(
    tracked_graph: TrackedGraph,
) -> None:
    """统计服务只公开当前角色契约定义的字段和授权范围计数。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    other_customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    tickets = [
        make_ticket(customer, status=TicketStatus.OPEN, priority=TicketPriority.HIGH),
        make_ticket(
            customer,
            status=TicketStatus.WAITING_FOR_CUSTOMER,
            priority=TicketPriority.URGENT,
        ),
        make_ticket(other_customer, assignee=agent, status=TicketStatus.IN_PROGRESS),
        make_ticket(
            other_customer,
            assignee=agent,
            status=TicketStatus.WAITING_FOR_CUSTOMER,
        ),
        make_ticket(other_customer, deleted=True, status=TicketStatus.CLOSED),
        make_ticket(other_customer, assignee=other_agent, status=TicketStatus.RESOLVED),
        make_ticket(other_customer, status=TicketStatus.OPEN),
    ]
    persist(
        tracked_graph,
        [customer, other_customer, agent, other_agent, admin],
        tickets,
    )

    with Session(engine) as session:
        service = StatisticsService(session)
        customer_stats = service.get_ticket_statistics(customer)
        agent_stats = service.get_ticket_statistics(agent)
        admin_stats = service.get_ticket_statistics(admin)

    assert isinstance(customer_stats, TicketStatisticsPublic)
    assert customer_stats.role is UserRole.CUSTOMER
    assert customer_stats.status_counts[TicketStatus.OPEN] == 1
    assert customer_stats.status_counts[TicketStatus.WAITING_FOR_CUSTOMER] == 1
    assert customer_stats.priority_counts == {}
    assert customer_stats.unassigned_count == 0
    assert customer_stats.assigned_to_me_count == 0
    assert customer_stats.waiting_for_customer_count == 0

    assert agent_stats.role is UserRole.AGENT
    assert agent_stats.status_counts == {}
    assert agent_stats.priority_counts == {}
    assert agent_stats.unassigned_count == 3
    assert agent_stats.assigned_to_me_count == 2
    assert agent_stats.waiting_for_customer_count == 2

    assert admin_stats.role is UserRole.ADMIN
    assert admin_stats.status_counts[TicketStatus.OPEN] == 2
    assert admin_stats.status_counts[TicketStatus.IN_PROGRESS] == 1
    assert admin_stats.status_counts[TicketStatus.WAITING_FOR_CUSTOMER] == 2
    assert admin_stats.status_counts[TicketStatus.RESOLVED] == 1
    assert admin_stats.status_counts[TicketStatus.CLOSED] == 0
    assert admin_stats.priority_counts[TicketPriority.HIGH] == 1
    assert admin_stats.priority_counts[TicketPriority.MEDIUM] == 4
    assert admin_stats.priority_counts[TicketPriority.URGENT] == 1
    assert admin_stats.unassigned_count == 3
    assert admin_stats.assigned_to_me_count == 0
    assert admin_stats.waiting_for_customer_count == 0
