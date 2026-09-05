"""Ticket HTTP API 契约测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete

from app.core.config import settings
from app.core.db import engine
from app.core.security import get_password_hash
from app.models.enums import (
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from tests.utils.utils import random_email, random_lower_string


class TrackedGraph:
    """记录路由测试创建的临时数据。by AI.Coding"""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.ticket_ids: list[uuid.UUID] = []


@pytest.fixture
def tracked_graph() -> Iterator[TrackedGraph]:
    """按外键依赖顺序清理路由测试数据。by AI.Coding"""
    graph = TrackedGraph()
    yield graph
    with Session(engine) as session:
        if graph.ticket_ids:
            session.exec(
                delete(TicketAuditLog).where(
                    col(TicketAuditLog.ticket_id).in_(graph.ticket_ids)
                )
            )
            session.exec(
                delete(TicketMessage).where(col(TicketMessage.ticket_id).in_(graph.ticket_ids))
            )
        if graph.ticket_ids:
            session.exec(delete(Ticket).where(col(Ticket.id).in_(graph.ticket_ids)))
        if graph.user_ids:
            session.exec(delete(User).where(col(User.id).in_(graph.user_ids)))
        session.commit()


def create_user(
    db: Session,
    *,
    role: UserRole,
    active: bool = True,
    password: str | None = None,
) -> tuple[User, str]:
    """创建可登录的测试用户。by AI.Coding"""
    raw_password = password or random_lower_string()
    user = User(
        email=random_email(),
        role=role,
        is_active=active,
        hashed_password=get_password_hash(raw_password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, raw_password


def auth_headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    """用登录接口换取访问令牌。by AI.Coding"""
    response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_ticket(
    db: Session,
    *,
    requester: User,
    assignee: User | None = None,
    status: TicketStatus = TicketStatus.OPEN,
) -> Ticket:
    """直接落库一个工单，作为 HTTP 契约测试的数据底座。by AI.Coding"""
    ticket = Ticket(
        title="Route test ticket",
        description="Ticket route contract test.",
        category=TicketCategory.OTHER,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        status=status,
        priority=TicketPriority.MEDIUM,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def test_ticket_collection_and_detail_contract(
    client: TestClient,
    tracked_graph: TrackedGraph,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    """工单创建、列表、详情和统计路由应可直接命中。by AI.Coding"""
    create_payload = {
        "title": "  Need help  ",
        "description": "  Cannot sign in.  ",
        "category": "ACCOUNT",
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/tickets",
        headers=normal_user_token_headers,
        json=create_payload,
    )
    assert create_response.status_code == 201
    created_ticket = create_response.json()
    assert created_ticket["title"] == "Need help"
    assert created_ticket["status"] == "OPEN"
    assert created_ticket["priority"] == "MEDIUM"
    tracked_graph.ticket_ids.append(uuid.UUID(created_ticket["id"]))

    list_response = client.get(
        f"{settings.API_V1_STR}/tickets",
        headers=normal_user_token_headers,
    )
    assert list_response.status_code == 200
    ticket_list = list_response.json()
    assert ticket_list["count"] >= 1
    assert any(row["id"] == created_ticket["id"] for row in ticket_list["data"])

    detail_response = client.get(
        f"{settings.API_V1_STR}/tickets/{created_ticket['id']}",
        headers=normal_user_token_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["messages"] == []
    assert detail["audit_logs"] == []

    stats_response = client.get(
        f"{settings.API_V1_STR}/tickets/statistics",
        headers=superuser_token_headers,
    )
    assert stats_response.status_code == 200
    statistics = stats_response.json()
    assert statistics["role"] == "ADMIN"
    assert "status_counts" in statistics
    assert "unassigned_count" in statistics


def test_ticket_actions_enforce_permissions_and_errors(
    client: TestClient,
    db: Session,
    tracked_graph: TrackedGraph,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    """接手、分派、回复、状态与删除的路由契约应映射到领域错误。by AI.Coding"""
    customer_email = random_email()
    customer_password = random_lower_string()
    customer = User(
        email=customer_email,
        role=UserRole.CUSTOMER,
        is_active=True,
        hashed_password=get_password_hash(customer_password),
    )
    agent, agent_password = create_user(db, role=UserRole.AGENT)
    other_agent, other_agent_password = create_user(db, role=UserRole.AGENT)
    admin = User(
        email=random_email(),
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password=get_password_hash(random_lower_string()),
    )
    db.add_all([customer, admin])
    db.commit()
    db.refresh(customer)
    db.refresh(admin)
    tracked_graph.user_ids.extend(
        [customer.id, agent.id, other_agent.id, admin.id]
    )

    customer_headers = auth_headers(
        client, email=customer.email, password=customer_password
    )
    agent_headers = auth_headers(client, email=agent.email, password=agent_password)
    other_agent_headers = auth_headers(
        client, email=other_agent.email, password=other_agent_password
    )

    ticket = create_ticket(
        db,
        requester=customer,
        assignee=agent,
        status=TicketStatus.WAITING_FOR_CUSTOMER,
    )
    tracked_graph.ticket_ids.append(ticket.id)

    forbidden_response = client.get(
        f"{settings.API_V1_STR}/tickets/{ticket.id}",
        headers=other_agent_headers,
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["code"] == "TICKET_FORBIDDEN"

    missing_response = client.get(
        f"{settings.API_V1_STR}/tickets/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["code"] == "TICKET_NOT_FOUND"

    reply_response = client.post(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/replies",
        headers=customer_headers,
        json={"content": "  I have updated the details.  "},
    )
    assert reply_response.status_code == 201
    reply = reply_response.json()
    assert reply["message_type"] == TicketMessageType.PUBLIC_REPLY
    assert reply["content"] == "I have updated the details."

    assign_response = client.put(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/assignee",
        headers=superuser_token_headers,
        json={"assignee_id": str(other_agent.id)},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assignee"]["id"] == str(other_agent.id)

    unassign_response = client.delete(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/assignee",
        headers=superuser_token_headers,
    )
    assert unassign_response.status_code == 200
    assert unassign_response.json()["assignee"] is None

    claim_response = client.post(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/claim",
        headers=agent_headers,
    )
    assert claim_response.status_code == 200
    assert claim_response.json()["assignee"]["id"] == str(agent.id)

    conflict_response = client.post(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/claim",
        headers=other_agent_headers,
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["code"] == "TICKET_ALREADY_CLAIMED"

    status_response = client.patch(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/status",
        headers=agent_headers,
        json={"status": "RESOLVED"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "RESOLVED"

    attributes_response = client.patch(
        f"{settings.API_V1_STR}/tickets/{ticket.id}/attributes",
        headers=agent_headers,
        json={"priority": "HIGH", "category": "BUG"},
    )
    assert attributes_response.status_code == 200
    assert attributes_response.json()["priority"] == "HIGH"
    assert attributes_response.json()["category"] == "BUG"

    invalid_response = client.post(
        f"{settings.API_V1_STR}/tickets",
        headers=normal_user_token_headers,
        json={"title": "Only title"},
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["code"] == "VALIDATION_ERROR"

    delete_conflict = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/tickets/{ticket.id}",
        headers=superuser_token_headers,
        json={"confirm": False},
    )
    assert delete_conflict.status_code == 422
    assert delete_conflict.json()["code"] == "VALIDATION_ERROR"

    delete_response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/tickets/{ticket.id}",
        headers=superuser_token_headers,
        json={"confirm": True},
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    hidden_detail = client.get(
        f"{settings.API_V1_STR}/tickets/{ticket.id}",
        headers=superuser_token_headers,
    )
    assert hidden_detail.status_code == 404
    assert hidden_detail.json()["code"] == "TICKET_NOT_FOUND"
