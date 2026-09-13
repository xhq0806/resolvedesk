"""TicketService 多租户隔离回归测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete
from sqlmodel import Session, col

from app.core.db import engine
from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.workspace import WorkspaceContext
from app.models.enums import TicketCategory, TicketStatus, UserRole
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.ticket import TicketAssign, TicketFilters
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService


class WorkspaceGraph:
    """记录多租户测试创建的领域对象主键。by AI.Coding"""

    def __init__(self) -> None:
        """初始化待清理主键集合。by AI.Coding"""
        self.user_ids: list[uuid.UUID] = []
        self.workspace_ids: list[uuid.UUID] = []
        self.ticket_ids: list[uuid.UUID] = []


@pytest.fixture
def workspace_graph() -> Iterator[WorkspaceGraph]:
    """按外键依赖顺序清理多租户测试数据。by AI.Coding"""
    graph = WorkspaceGraph()
    yield graph
    with Session(engine) as session:
        if graph.ticket_ids:
            session.exec(
                delete(TicketAuditLog).where(
                    col(TicketAuditLog.ticket_id).in_(graph.ticket_ids)
                )
            )
            session.exec(
                delete(TicketMessage).where(
                    col(TicketMessage.ticket_id).in_(graph.ticket_ids)
                )
            )
            session.exec(delete(Ticket).where(col(Ticket.id).in_(graph.ticket_ids)))
        if graph.workspace_ids:
            session.exec(
                delete(WorkspaceMember).where(
                    col(WorkspaceMember.workspace_id).in_(graph.workspace_ids)
                )
            )
            session.exec(
                delete(Workspace).where(col(Workspace.id).in_(graph.workspace_ids))
            )
        if graph.user_ids:
            session.exec(delete(User).where(col(User.id).in_(graph.user_ids)))
        session.commit()


def make_user(marker: str, role: UserRole = UserRole.CUSTOMER) -> User:
    """创建可被 Workspace 角色覆盖的一期用户。by AI.Coding"""
    return User(
        email=f"workspace-ticket-{marker}-{uuid.uuid4().hex}@example.com",
        role=role,
        hashed_password="not-a-real-password-hash",
    )


def make_workspace(marker: str, owner: User) -> Workspace:
    """创建测试专用 Workspace。by AI.Coding"""
    return Workspace(
        name=f"Workspace {marker}",
        slug=f"workspace-ticket-{marker}-{uuid.uuid4().hex}",
        owner_user_id=owner.id,
    )


def make_member(
    workspace: Workspace, user: User, role: WorkspaceRole
) -> WorkspaceMember:
    """创建用户在指定 Workspace 内的成员角色。by AI.Coding"""
    return WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
    )


def make_ticket(
    workspace: Workspace,
    requester: User,
    *,
    status: TicketStatus = TicketStatus.OPEN,
) -> Ticket:
    """创建归属于指定 Workspace 的工单。by AI.Coding"""
    return Ticket(
        title="Workspace scoped ticket",
        description="Tenant isolation regression.",
        category=TicketCategory.OTHER,
        workspace_id=workspace.id,
        requester_id=requester.id,
        status=status,
    )


def persist(
    graph: WorkspaceGraph,
    *,
    users: list[User],
    workspaces: list[Workspace],
    members: list[WorkspaceMember],
    tickets: list[Ticket],
) -> None:
    """持久化完整多租户测试图。by AI.Coding"""
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(users)
        session.add_all(workspaces)
        session.add_all(members)
        session.add_all(tickets)
        session.commit()
    graph.user_ids.extend(user.id for user in users)
    graph.workspace_ids.extend(workspace.id for workspace in workspaces)
    graph.ticket_ids.extend(ticket.id for ticket in tickets)


def test_ticket_queries_and_statistics_are_scoped_to_workspace(
    workspace_graph: WorkspaceGraph,
) -> None:
    """同一用户切换 Workspace 后只能读取当前租户工单。by AI.Coding"""
    owner = make_user("owner")
    customer = make_user("customer")
    workspace_a = make_workspace("a", owner)
    workspace_b = make_workspace("b", owner)
    owner_a = make_member(workspace_a, owner, WorkspaceRole.OWNER)
    owner_b = make_member(workspace_b, owner, WorkspaceRole.OWNER)
    customer_a = make_member(workspace_a, customer, WorkspaceRole.CUSTOMER)
    customer_b = make_member(workspace_b, customer, WorkspaceRole.CUSTOMER)
    ticket_a = make_ticket(workspace_a, customer, status=TicketStatus.OPEN)
    ticket_b = make_ticket(
        workspace_b,
        customer,
        status=TicketStatus.WAITING_FOR_CUSTOMER,
    )
    persist(
        workspace_graph,
        users=[owner, customer],
        workspaces=[workspace_a, workspace_b],
        members=[owner_a, owner_b, customer_a, customer_b],
        tickets=[ticket_a, ticket_b],
    )

    with Session(engine) as session:
        service = TicketService(session)
        customer_context_a = WorkspaceContext(workspace_a, customer_a)
        customer_context_b = WorkspaceContext(workspace_b, customer_b)
        owner_context_a = WorkspaceContext(workspace_a, owner_a)

        page_a = service.list_tickets(
            customer, TicketFilters(), context=customer_context_a
        )
        page_b = service.list_tickets(
            customer, TicketFilters(), context=customer_context_b
        )
        stats_a = StatisticsService(session).get_ticket_statistics(
            owner, context=owner_context_a
        )

        assert [row.id for row in page_a.data] == [ticket_a.id]
        assert [row.id for row in page_b.data] == [ticket_b.id]
        assert stats_a.status_counts[TicketStatus.OPEN] == 1
        assert stats_a.status_counts[TicketStatus.WAITING_FOR_CUSTOMER] == 0
        with pytest.raises(NotFoundError) as hidden:
            service.get_ticket(customer, ticket_b.id, context=customer_context_a)
        assert hidden.value.code is ErrorCode.TICKET_NOT_FOUND


def test_assignment_uses_workspace_member_role_as_source_of_truth(
    workspace_graph: WorkspaceGraph,
) -> None:
    """负责人分派应按 WorkspaceMember 角色而不是全局 User.role 判断。by AI.Coding"""
    owner = make_user("manager")
    workspace_agent = make_user("workspace-agent")
    global_agent = make_user("global-agent", role=UserRole.AGENT)
    workspace = make_workspace("assign", owner)
    owner_member = make_member(workspace, owner, WorkspaceRole.OWNER)
    agent_member = make_member(workspace, workspace_agent, WorkspaceRole.AGENT)
    ticket = make_ticket(workspace, owner)
    persist(
        workspace_graph,
        users=[owner, workspace_agent, global_agent],
        workspaces=[workspace],
        members=[owner_member, agent_member],
        tickets=[ticket],
    )

    with Session(engine) as session:
        service = TicketService(session)
        owner_context = WorkspaceContext(workspace, owner_member)
        assigned = service.assign_ticket(
            owner,
            ticket.id,
            TicketAssign(assignee_id=workspace_agent.id),
            context=owner_context,
        )
        assert assigned.assignee is not None
        assert assigned.assignee.id == workspace_agent.id

        with pytest.raises(ConflictError) as invalid:
            service.assign_ticket(
                owner,
                ticket.id,
                TicketAssign(assignee_id=global_agent.id),
                context=owner_context,
            )
        assert invalid.value.code is ErrorCode.INVALID_ASSIGNEE
