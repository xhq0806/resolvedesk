"""工单原子接手 PostgreSQL 并发测试。by AI.Coding"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session

from app.core.db import engine
from app.models.enums import TicketCategory, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.ticket_repository import TicketRepository


def test_two_agents_cannot_claim_the_same_ticket() -> None:
    customer = User(
        email=f"claim-customer-{uuid.uuid4().hex}@example.com",
        role=UserRole.CUSTOMER,
        hashed_password="not-a-real-password-hash",
    )
    agent_a = User(
        email=f"claim-agent-a-{uuid.uuid4().hex}@example.com",
        role=UserRole.AGENT,
        hashed_password="not-a-real-password-hash",
    )
    agent_b = User(
        email=f"claim-agent-b-{uuid.uuid4().hex}@example.com",
        role=UserRole.AGENT,
        hashed_password="not-a-real-password-hash",
    )
    ticket = Ticket(
        title="Concurrent claim",
        description="Only one Agent may claim this ticket.",
        category=TicketCategory.OTHER,
        requester_id=customer.id,
    )
    customer_id = customer.id
    agent_a_id = agent_a.id
    agent_b_id = agent_b.id
    ticket_id = ticket.id
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([customer, agent_a, agent_b, ticket])
        session.commit()

    barrier = threading.Barrier(2)
    first_time = datetime(2026, 8, 27, 11, tzinfo=UTC)
    attempts = {
        agent_a_id: first_time,
        agent_b_id: first_time + timedelta(seconds=1),
    }

    def claim(agent_id: uuid.UUID) -> tuple[uuid.UUID | None, datetime | None]:
        with Session(engine) as session:
            barrier.wait(timeout=5)
            claimed = TicketRepository(session).claim_if_available(
                ticket_id, agent_id, attempts[agent_id]
            )
            session.commit()
            if claimed is None:
                return None, None
            return claimed.assignee_id, claimed.updated_at

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=5)
                for future in (
                    executor.submit(claim, agent_a_id),
                    executor.submit(claim, agent_b_id),
                )
            ]

        successes = [result for result in results if result[0] is not None]
        assert len(successes) == 1
        winning_agent_id, winning_time = successes[0]
        assert winning_agent_id in {agent_a_id, agent_b_id}
        assert winning_time == attempts[winning_agent_id]

        with Session(engine) as session:
            saved = session.get(Ticket, ticket_id)
            assert saved is not None
            assert saved.assignee_id == winning_agent_id
            assert saved.status is TicketStatus.IN_PROGRESS
            assert saved.updated_at == winning_time
    finally:
        with Session(engine) as session:
            session.exec(delete(Ticket).where(Ticket.id == ticket_id))
            session.exec(
                delete(User).where(User.id.in_([customer_id, agent_a_id, agent_b_id]))
            )
            session.commit()
