"""工单仓储角色范围、筛选、时间线和条件接手测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session

from app.core.db import engine
from app.models.enums import (
    TicketAuditAction,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketFilters


class TrackedGraph:
    """记录测试创建的工单图主键。by AI.Coding"""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.ticket_ids: list[uuid.UUID] = []
        self.message_ids: list[uuid.UUID] = []
        self.audit_ids: list[uuid.UUID] = []


@pytest.fixture
def tracked_graph() -> Iterator[TrackedGraph]:
    graph = TrackedGraph()
    yield graph
    with Session(engine) as session:
        if graph.audit_ids:
            session.exec(
                delete(TicketAuditLog).where(TicketAuditLog.id.in_(graph.audit_ids))
            )
        if graph.message_ids:
            session.exec(
                delete(TicketMessage).where(TicketMessage.id.in_(graph.message_ids))
            )
        if graph.ticket_ids:
            session.exec(delete(Ticket).where(Ticket.id.in_(graph.ticket_ids)))
        if graph.user_ids:
            session.exec(delete(User).where(User.id.in_(graph.user_ids)))
        session.commit()


def make_user(marker: str, role: UserRole) -> User:
    return User(
        email=f"{marker}-{uuid.uuid4().hex}@example.com",
        role=role,
        hashed_password="not-a-real-password-hash",
    )


def make_ticket(
    marker: str,
    requester: User,
    *,
    assignee: User | None = None,
    status: TicketStatus = TicketStatus.OPEN,
    priority: TicketPriority = TicketPriority.MEDIUM,
    category: TicketCategory = TicketCategory.OTHER,
    updated_at: datetime | None = None,
    deleted_at: datetime | None = None,
    ticket_id: uuid.UUID | None = None,
) -> Ticket:
    return Ticket(
        id=ticket_id or uuid.uuid4(),
        ticket_number=f"TKT-{uuid.uuid4().hex}",
        title=f"Title {marker}",
        description=f"Description {marker}",
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        status=status,
        priority=priority,
        category=category,
        updated_at=updated_at or datetime.now(UTC),
        deleted_at=deleted_at,
    )


def persist(
    graph: TrackedGraph,
    *,
    users: list[User],
    tickets: list[Ticket],
    messages: list[TicketMessage] | None = None,
    audits: list[TicketAuditLog] | None = None,
) -> None:
    messages = messages or []
    audits = audits or []
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(users)
        session.add_all(tickets)
        session.add_all(messages)
        session.add_all(audits)
        session.commit()
    graph.user_ids.extend(user.id for user in users)
    graph.ticket_ids.extend(ticket.id for ticket in tickets)
    graph.message_ids.extend(message.id for message in messages)
    graph.audit_ids.extend(audit.id for audit in audits)


def test_ticket_filters_normalize_query_and_validate_pagination() -> None:
    assert TicketFilters(query="  TKT-123  ").query == "TKT-123"
    assert TicketFilters(query="   ").query is None
    for invalid in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        with pytest.raises(ValidationError):
            TicketFilters.model_validate(invalid)


def test_add_methods_use_callers_session() -> None:
    customer = make_user("pending-customer", UserRole.CUSTOMER)
    ticket = make_ticket("pending", customer)
    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=customer.id,
        message_type=TicketMessageType.PUBLIC_REPLY,
        content="Pending message",
    )
    audit = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=customer.id,
        action=TicketAuditAction.STATUS_CHANGED,
    )
    with Session(engine) as session:
        repository = TicketRepository(session)
        repository.add(ticket)
        repository.add_message(message)
        repository.add_audit(audit)
        assert ticket in session.new
        assert message in session.new
        assert audit in session.new
        session.rollback()


def test_active_getters_hide_soft_deleted_and_lock_refreshes_identity_map(
    tracked_graph: TrackedGraph,
) -> None:
    customer = make_user("getter-customer", UserRole.CUSTOMER)
    active = make_ticket("active-getter", customer)
    deleted = make_ticket(
        "deleted-getter", customer, deleted_at=datetime.now(UTC)
    )
    persist(tracked_graph, users=[customer], tickets=[active, deleted])

    with Session(engine, expire_on_commit=False) as stale_session:
        stale = stale_session.get(Ticket, active.id)
        assert stale is not None
        with Session(engine) as updating_session:
            updated = updating_session.get(Ticket, active.id)
            assert updated is not None
            updated.title = "Updated elsewhere"
            updating_session.add(updated)
            updating_session.commit()

        repository = TicketRepository(stale_session)
        refreshed = repository.get_active_by_id(active.id, for_update=True)
        assert refreshed is stale
        assert refreshed.title == "Updated elsewhere"
        assert repository.get_active_by_number(active.ticket_number) is refreshed
        assert repository.get_active_by_id(deleted.id) is None
        assert repository.get_active_by_number(deleted.ticket_number) is None
        stale_session.rollback()


def test_list_for_actor_enforces_role_scope_and_soft_delete(
    tracked_graph: TrackedGraph,
) -> None:
    customer_a = make_user("scope-customer-a", UserRole.CUSTOMER)
    customer_b = make_user("scope-customer-b", UserRole.CUSTOMER)
    agent_a = make_user("scope-agent-a", UserRole.AGENT)
    agent_b = make_user("scope-agent-b", UserRole.AGENT)
    admin = make_user("scope-admin", UserRole.ADMIN)
    own = make_ticket("scope-own", customer_a, assignee=agent_a)
    other = make_ticket("scope-other", customer_b, assignee=agent_b)
    unassigned = make_ticket("scope-unassigned", customer_b)
    deleted = make_ticket(
        "scope-deleted", customer_a, deleted_at=datetime.now(UTC)
    )
    persist(
        tracked_graph,
        users=[customer_a, customer_b, agent_a, agent_b, admin],
        tickets=[own, other, unassigned, deleted],
    )

    with Session(engine) as session:
        repository = TicketRepository(session)
        customer_rows, _ = repository.list_for_actor(customer_a, TicketFilters())
        agent_rows, _ = repository.list_for_actor(agent_a, TicketFilters())
        admin_rows, _ = repository.list_for_actor(admin, TicketFilters())

    assert {row.id for row in customer_rows} == {own.id}
    assert {row.id for row in agent_rows} == {own.id, unassigned.id}
    assert {row.id for row in admin_rows} == {own.id, other.id, unassigned.id}


def test_list_for_actor_combines_filters_search_count_and_stable_pagination(
    tracked_graph: TrackedGraph,
) -> None:
    marker = uuid.uuid4().hex
    customer = make_user("filter-customer", UserRole.CUSTOMER)
    agent = make_user("filter-agent", UserRole.AGENT)
    admin = make_user("filter-admin", UserRole.ADMIN)
    same_time = datetime(2026, 8, 27, 8, tzinfo=UTC)
    matching_high = make_ticket(
        f"literal-100%_match-{marker}",
        customer,
        assignee=agent,
        status=TicketStatus.IN_PROGRESS,
        priority=TicketPriority.HIGH,
        category=TicketCategory.BUG,
        updated_at=same_time,
        ticket_id=uuid.UUID(int=302),
    )
    matching_low = make_ticket(
        f"literal-100%_match-{marker}-second",
        customer,
        assignee=agent,
        status=TicketStatus.IN_PROGRESS,
        priority=TicketPriority.HIGH,
        category=TicketCategory.BUG,
        updated_at=same_time,
        ticket_id=uuid.UUID(int=301),
    )
    description_only = make_ticket("no-title-hit", customer)
    description_only.description = f"literal 100%_match {marker}"
    persist(
        tracked_graph,
        users=[customer, agent, admin],
        tickets=[matching_high, matching_low, description_only],
    )

    filters = TicketFilters(
        status=TicketStatus.IN_PROGRESS,
        priority=TicketPriority.HIGH,
        category=TicketCategory.BUG,
        assignee_id=agent.id,
        query=f"100%_match-{marker}",
        page=1,
        page_size=1,
    )
    with Session(engine) as session:
        repository = TicketRepository(session)
        first_page, count = repository.list_for_actor(admin, filters)
        second_page, second_count = repository.list_for_actor(
            admin, filters.model_copy(update={"page": 2})
        )
        state = sa_inspect(first_page[0])

    assert count == second_count == 2
    assert [row.id for row in first_page] == [matching_high.id]
    assert [row.id for row in second_page] == [matching_low.id]
    assert "requester" not in state.unloaded
    assert "assignee" not in state.unloaded
    assert "messages" in state.unloaded
    assert "audit_logs" in state.unloaded


def test_message_and_audit_queries_apply_database_side_visibility(
    tracked_graph: TrackedGraph,
) -> None:
    customer = make_user("timeline-customer", UserRole.CUSTOMER)
    agent = make_user("timeline-agent", UserRole.AGENT)
    ticket = make_ticket("timeline", customer, assignee=agent)
    base = datetime(2026, 8, 27, 9, tzinfo=UTC)
    public = TicketMessage(
        ticket_id=ticket.id,
        author_id=customer.id,
        message_type=TicketMessageType.PUBLIC_REPLY,
        content="Public",
        created_at=base + timedelta(minutes=2),
    )
    internal = TicketMessage(
        ticket_id=ticket.id,
        author_id=agent.id,
        message_type=TicketMessageType.INTERNAL_NOTE,
        content="Internal",
        created_at=base + timedelta(minutes=1),
    )
    safe = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=agent.id,
        action=TicketAuditAction.STATUS_CHANGED,
        created_at=base + timedelta(minutes=2),
    )
    sensitive = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=agent.id,
        action=TicketAuditAction.ASSIGNED,
        created_at=base + timedelta(minutes=1),
    )
    persist(
        tracked_graph,
        users=[customer, agent],
        tickets=[ticket],
        messages=[public, internal],
        audits=[safe, sensitive],
    )

    with Session(engine) as session:
        repository = TicketRepository(session)
        public_only = repository.list_messages(ticket.id, include_internal=False)
        all_messages = repository.list_messages(ticket.id, include_internal=True)
        safe_only = repository.list_audits(ticket.id, customer_safe_only=True)
        all_audits = repository.list_audits(ticket.id, customer_safe_only=False)

    assert [message.id for message in public_only] == [public.id]
    assert [message.id for message in all_messages] == [internal.id, public.id]
    assert [audit.id for audit in safe_only] == [safe.id]
    assert [audit.id for audit in all_audits] == [sensitive.id, safe.id]


def test_claim_if_available_updates_only_matching_ticket(
    tracked_graph: TrackedGraph,
) -> None:
    customer = make_user("claim-customer", UserRole.CUSTOMER)
    agent = make_user("claim-agent", UserRole.AGENT)
    available = make_ticket("claim-available", customer)
    assigned = make_ticket("claim-assigned", customer, assignee=agent)
    closed = make_ticket("claim-closed", customer, status=TicketStatus.CLOSED)
    deleted = make_ticket("claim-deleted", customer, deleted_at=datetime.now(UTC))
    persist(
        tracked_graph,
        users=[customer, agent],
        tickets=[available, assigned, closed, deleted],
    )
    claimed_at = datetime(2026, 8, 27, 10, tzinfo=UTC)

    with Session(engine) as session:
        repository = TicketRepository(session)
        claimed = repository.claim_if_available(available.id, agent.id, claimed_at)
        assert claimed is not None
        assert claimed.assignee_id == agent.id
        assert claimed.status is TicketStatus.IN_PROGRESS
        assert claimed.updated_at == claimed_at
        assert repository.claim_if_available(assigned.id, agent.id, claimed_at) is None
        assert repository.claim_if_available(closed.id, agent.id, claimed_at) is None
        assert repository.claim_if_available(deleted.id, agent.id, claimed_at) is None
        assert repository.claim_if_available(uuid.uuid4(), agent.id, claimed_at) is None
        session.commit()
