"""TicketService 创建、查询、接手与负责人事务测试。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from app.core.db import engine
from app.core.errors import ConflictError, ErrorCode, ForbiddenError, NotFoundError
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
from app.schemas.ticket import (
    CustomerReplyCreate,
    DeleteTicketRequest,
    TicketAssign,
    TicketAttributesUpdate,
    TicketCreate,
    TicketFilters,
    TicketMessageCreate,
    TicketStatusUpdate,
)
from app.services.ticket_service import TicketService


class TrackedGraph:
    """记录 TicketService 测试创建的领域图主键。by AI.Coding"""

    def __init__(self) -> None:
        self.user_ids: list[uuid.UUID] = []
        self.ticket_ids: list[uuid.UUID] = []
        self.message_ids: list[uuid.UUID] = []
        self.audit_ids: list[uuid.UUID] = []


@pytest.fixture
def tracked_graph() -> Iterator[TrackedGraph]:
    """按 RESTRICT 外键依赖顺序清理测试领域图。by AI.Coding"""
    graph = TrackedGraph()
    yield graph
    with Session(engine) as session:
        if graph.audit_ids:
            session.exec(
                delete(TicketAuditLog).where(
                    col(TicketAuditLog.id).in_(graph.audit_ids)
                )
            )
        if graph.message_ids:
            session.exec(
                delete(TicketMessage).where(
                    col(TicketMessage.id).in_(graph.message_ids)
                )
            )
        if graph.ticket_ids:
            session.exec(delete(Ticket).where(col(Ticket.id).in_(graph.ticket_ids)))
        if graph.user_ids:
            session.exec(delete(User).where(col(User.id).in_(graph.user_ids)))
        session.commit()


def make_user(role: UserRole, *, active: bool = True) -> User:
    """创建唯一邮箱的服务测试用户。by AI.Coding"""
    return User(
        email=f"ticket-service-{uuid.uuid4().hex}@example.com",
        role=role,
        is_active=active,
        hashed_password="not-a-real-password-hash",
    )


def make_ticket(
    requester: User,
    *,
    assignee: User | None = None,
    status: TicketStatus = TicketStatus.OPEN,
) -> Ticket:
    """创建服务测试工单。by AI.Coding"""
    return Ticket(
        title="Service ticket",
        description="TicketService test.",
        category=TicketCategory.OTHER,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        status=status,
    )


def persist(
    graph: TrackedGraph,
    *,
    users: list[User],
    tickets: list[Ticket] | None = None,
    messages: list[TicketMessage] | None = None,
    audits: list[TicketAuditLog] | None = None,
) -> None:
    """持久化并登记测试领域图。by AI.Coding"""
    tickets = tickets or []
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


def test_ticket_create_schema_normalizes_and_rejects_service_fields() -> None:
    """创建输入规范化文本并拒绝客户端控制字段。by AI.Coding"""
    payload = TicketCreate(
        title="  Need help  ",
        description="  Details  ",
        category=TicketCategory.OTHER,
    )
    assert payload.title == "Need help"
    assert payload.description == "Details"
    with pytest.raises(ValidationError):
        TicketCreate.model_validate(
            {
                "title": "Help",
                "description": "Details",
                "category": "OTHER",
                "status": "CLOSED",
            }
        )


def test_customer_creates_default_ticket_and_non_customer_is_forbidden(
    tracked_graph: TrackedGraph,
) -> None:
    """仅 Customer 可创建固定默认状态的工单。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    persist(tracked_graph, users=[customer, agent])
    payload = TicketCreate(
        title="  Login issue  ",
        description="  Cannot sign in.  ",
        category=TicketCategory.ACCOUNT,
    )

    with Session(engine) as session:
        detail = TicketService(session).create_ticket(customer, payload)
        tracked_graph.ticket_ids.append(detail.id)
        assert detail.requester.id == customer.id
        assert detail.status is TicketStatus.OPEN
        assert detail.assignee is None
        assert detail.messages == []
        assert detail.audit_logs == []
        assert detail.ticket_number.startswith("TKT-")

        with pytest.raises(ForbiddenError) as error:
            TicketService(session).create_ticket(agent, payload)
        assert error.value.code is ErrorCode.ROLE_FORBIDDEN


def test_list_and_detail_apply_role_scope_and_timeline_cropping(
    tracked_graph: TrackedGraph,
) -> None:
    """列表与详情复用角色范围并在数据库查询阶段裁剪时间线。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    other_customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent)
    other_ticket = make_ticket(other_customer)
    public = TicketMessage(
        ticket_id=ticket.id,
        author_id=customer.id,
        message_type=TicketMessageType.PUBLIC_REPLY,
        content="Public",
    )
    internal = TicketMessage(
        ticket_id=ticket.id,
        author_id=agent.id,
        message_type=TicketMessageType.INTERNAL_NOTE,
        content="Internal",
    )
    safe = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=agent.id,
        action=TicketAuditAction.STATUS_CHANGED,
    )
    sensitive = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=admin.id,
        action=TicketAuditAction.ASSIGNED,
    )
    persist(
        tracked_graph,
        users=[customer, other_customer, agent, admin],
        tickets=[ticket, other_ticket],
        messages=[public, internal],
        audits=[safe, sensitive],
    )

    with Session(engine) as session:
        service = TicketService(session)
        customer_page = service.list_tickets(customer, TicketFilters())
        customer_detail = service.get_ticket(customer, ticket.id)
        agent_detail = service.get_ticket(agent, ticket.id)

        assert [row.id for row in customer_page.data] == [ticket.id]
        assert customer_page.count == 1
        assert customer_page.page == 1
        assert customer_page.page_size == 20
        assert [row.id for row in customer_detail.messages] == [public.id]
        assert [row.id for row in customer_detail.audit_logs] == [safe.id]
        assert {row.id for row in agent_detail.messages} == {public.id, internal.id}
        assert {row.id for row in agent_detail.audit_logs} == {safe.id, sensitive.id}

        with pytest.raises(ForbiddenError) as error:
            service.get_ticket(other_customer, ticket.id)
        assert error.value.code is ErrorCode.TICKET_FORBIDDEN
        with pytest.raises(NotFoundError) as missing:
            service.get_ticket(admin, uuid.uuid4())
        assert missing.value.code is ErrorCode.TICKET_NOT_FOUND


def test_agent_claim_is_atomic_with_taken_audit(
    tracked_graph: TrackedGraph,
) -> None:
    """活跃 Agent 接手与 TAKEN 审计在同一事务持久化。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer)
    persist(tracked_graph, users=[customer, agent, admin], tickets=[ticket])

    with Session(engine) as session:
        detail = TicketService(session).claim_ticket(agent, ticket.id)
        assert detail.assignee is not None
        assert detail.assignee.id == agent.id
        assert detail.status is TicketStatus.IN_PROGRESS
        audit = session.exec(
            select(TicketAuditLog).where(
                TicketAuditLog.ticket_id == ticket.id,
                TicketAuditLog.action == TicketAuditAction.TAKEN,
            )
        ).one()
        tracked_graph.audit_ids.append(audit.id)
        assert audit.new_value == {
            "assignee_id": str(agent.id),
            "status": TicketStatus.IN_PROGRESS.value,
        }

        admin_ticket = make_ticket(customer)
        session.add(admin_ticket)
        session.commit()
        tracked_graph.ticket_ids.append(admin_ticket.id)

        admin_detail = TicketService(session).claim_ticket(admin, admin_ticket.id)
        assert admin_detail.assignee is not None
        assert admin_detail.assignee.id == admin.id
        assert admin_detail.status is TicketStatus.IN_PROGRESS
        admin_audit = session.exec(
            select(TicketAuditLog).where(
                TicketAuditLog.ticket_id == admin_ticket.id,
                TicketAuditLog.action == TicketAuditAction.TAKEN,
            )
        ).one()
        tracked_graph.audit_ids.append(admin_audit.id)

        with pytest.raises(ConflictError) as claimed:
            TicketService(session).claim_ticket(agent, ticket.id)
        assert claimed.value.code is ErrorCode.TICKET_ALREADY_CLAIMED


def test_admin_assigns_reassigns_and_unassigns_with_audits(
    tracked_graph: TrackedGraph,
) -> None:
    """Admin 负责人变更更新状态并写入对应结构化审计。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent_a = make_user(UserRole.AGENT)
    agent_b = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer)
    persist(
        tracked_graph,
        users=[customer, agent_a, agent_b, admin],
        tickets=[ticket],
    )

    with Session(engine) as session:
        service = TicketService(session)
        assigned = service.assign_ticket(
            admin, ticket.id, TicketAssign(assignee_id=agent_a.id)
        )
        assert assigned.assignee is not None
        assert assigned.assignee.id == agent_a.id
        assert assigned.status is TicketStatus.IN_PROGRESS

        reassigned = service.assign_ticket(
            admin, ticket.id, TicketAssign(assignee_id=agent_b.id)
        )
        assert reassigned.assignee is not None
        assert reassigned.assignee.id == agent_b.id

        unassigned = service.unassign_ticket(admin, ticket.id)
        assert unassigned.assignee is None
        assert unassigned.status is TicketStatus.OPEN

        audits = list(
            session.exec(
                select(TicketAuditLog)
                .where(TicketAuditLog.ticket_id == ticket.id)
                .order_by(col(TicketAuditLog.created_at), col(TicketAuditLog.id))
            ).all()
        )
        tracked_graph.audit_ids.extend(audit.id for audit in audits)
        assert [audit.action for audit in audits] == [
            TicketAuditAction.ASSIGNED,
            TicketAuditAction.REASSIGNED,
            TicketAuditAction.UNASSIGNED,
        ]
        assert audits[1].old_value is not None
        assert audits[1].old_value["assignee_id"] == str(agent_a.id)
        assert audits[1].new_value is not None
        assert audits[1].new_value["assignee_id"] == str(agent_b.id)


def test_assignment_rejects_invalid_target_closed_ticket_and_non_admin(
    tracked_graph: TrackedGraph,
) -> None:
    """负责人变更拒绝无效目标、关闭工单和非 Admin。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    inactive_agent = make_user(UserRole.AGENT, active=False)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    closed = make_ticket(customer, status=TicketStatus.CLOSED)
    persist(
        tracked_graph,
        users=[customer, inactive_agent, agent, admin],
        tickets=[closed],
    )

    with Session(engine) as session:
        service = TicketService(session)
        with pytest.raises(ForbiddenError) as role_error:
            service.assign_ticket(
                agent, closed.id, TicketAssign(assignee_id=inactive_agent.id)
            )
        assert role_error.value.code is ErrorCode.ROLE_FORBIDDEN

        with pytest.raises(ConflictError) as closed_error:
            service.assign_ticket(
                admin, closed.id, TicketAssign(assignee_id=inactive_agent.id)
            )
        assert closed_error.value.code is ErrorCode.TICKET_CLOSED

    open_ticket = make_ticket(customer)
    open_ticket_id = open_ticket.id
    with Session(engine) as session:
        session.add(open_ticket)
        session.commit()
    tracked_graph.ticket_ids.append(open_ticket_id)
    with Session(engine) as session:
        with pytest.raises(ConflictError) as target_error:
            TicketService(session).assign_ticket(
                admin,
                open_ticket_id,
                TicketAssign(assignee_id=inactive_agent.id),
            )
        assert target_error.value.code is ErrorCode.INVALID_ASSIGNEE
        assert not session.in_transaction()


def test_audit_failure_rolls_back_claim(
    monkeypatch: pytest.MonkeyPatch, tracked_graph: TrackedGraph
) -> None:
    """审计插入失败时接手条件更新也必须整体回滚。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = make_ticket(customer)
    persist(tracked_graph, users=[customer, agent], tickets=[ticket])

    with Session(engine) as session:
        service = TicketService(session)

        def fail_audit(_: TicketAuditLog) -> None:
            """模拟审计持久化入口失败。by AI.Coding"""
            raise RuntimeError("audit failed")

        monkeypatch.setattr(service.ticket_repository, "add_audit", fail_audit)
        with pytest.raises(RuntimeError, match="audit failed"):
            service.claim_ticket(agent, ticket.id)
        assert not session.in_transaction()

    with Session(engine) as session:
        saved = session.get(Ticket, ticket.id)
        assert saved is not None
        assert saved.assignee_id is None
        assert saved.status is TicketStatus.OPEN
        audit_count = session.exec(
            select(func.count())
            .select_from(TicketAuditLog)
            .where(TicketAuditLog.ticket_id == ticket.id)
        ).one()
        assert audit_count == 0


def test_customer_reply_reopens_waiting_ticket_and_records_status_change(
    tracked_graph: TrackedGraph,
) -> None:
    """Customer 公开回复等待客户工单时写入消息、重开状态并保留负责人。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    ticket = make_ticket(
        customer,
        assignee=agent,
        status=TicketStatus.WAITING_FOR_CUSTOMER,
    )
    persist(tracked_graph, users=[customer, agent], tickets=[ticket])

    with Session(engine) as session:
        reply = TicketService(session).add_customer_reply(
            customer,
            ticket.id,
            CustomerReplyCreate(content="  I have attached the requested details.  "),
        )
        assert reply.message_type is TicketMessageType.PUBLIC_REPLY
        assert reply.content == "I have attached the requested details."
        assert reply.author.id == customer.id

        saved_ticket = session.get(Ticket, ticket.id)
        assert saved_ticket is not None
        assert saved_ticket.status is TicketStatus.IN_PROGRESS
        assert saved_ticket.assignee_id == agent.id

        message = session.exec(
            select(TicketMessage).where(TicketMessage.ticket_id == ticket.id)
        ).one()
        audit = session.exec(
            select(TicketAuditLog).where(
                TicketAuditLog.ticket_id == ticket.id,
                TicketAuditLog.action == TicketAuditAction.STATUS_CHANGED,
            )
        ).one()
        tracked_graph.message_ids.append(message.id)
        tracked_graph.audit_ids.append(audit.id)
        assert audit.old_value == {"status": TicketStatus.WAITING_FOR_CUSTOMER.value}
        assert audit.new_value == {"status": TicketStatus.IN_PROGRESS.value}


def test_staff_message_respects_internal_note_permissions_and_cropping(
    tracked_graph: TrackedGraph,
) -> None:
    """Staff 消息按负责人权限写入，未分派 Agent 详情不泄露内部备注。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    assigned = make_ticket(customer, assignee=agent, status=TicketStatus.IN_PROGRESS)
    unassigned = make_ticket(customer, status=TicketStatus.OPEN)
    persist(
        tracked_graph,
        users=[customer, agent, other_agent, admin],
        tickets=[assigned, unassigned],
    )

    with Session(engine) as session:
        service = TicketService(session)
        internal = service.add_staff_message(
            agent,
            assigned.id,
            TicketMessageCreate(
                message_type=TicketMessageType.INTERNAL_NOTE,
                content="  Internal handling note.  ",
            ),
        )
        assert internal.message_type is TicketMessageType.INTERNAL_NOTE
        assert internal.content == "Internal handling note."

        admin_note = service.add_staff_message(
            admin,
            unassigned.id,
            TicketMessageCreate(
                message_type=TicketMessageType.INTERNAL_NOTE,
                content="Visible to admins only until claimed.",
            ),
        )

        with pytest.raises(ForbiddenError) as forbidden:
            service.add_staff_message(
                other_agent,
                assigned.id,
                TicketMessageCreate(
                    message_type=TicketMessageType.PUBLIC_REPLY,
                    content="I should not touch this ticket.",
                ),
            )
        assert forbidden.value.code is ErrorCode.TICKET_FORBIDDEN

        queue_detail = service.get_ticket(other_agent, unassigned.id)
        assert queue_detail.messages == []
        admin_detail = service.get_ticket(admin, unassigned.id)
        assert [message.id for message in admin_detail.messages] == [admin_note.id]

        saved_messages = list(
            session.exec(
                select(TicketMessage).where(
                    col(TicketMessage.ticket_id).in_([assigned.id, unassigned.id])
                )
            ).all()
        )
        tracked_graph.message_ids.extend(message.id for message in saved_messages)


def test_staff_updates_status_with_state_machine_audit(
    tracked_graph: TrackedGraph,
) -> None:
    """负责人 Agent 按状态机修改状态，非法目标被拒绝且不写审计。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent, status=TicketStatus.IN_PROGRESS)
    persist(tracked_graph, users=[customer, agent, admin], tickets=[ticket])

    with Session(engine) as session:
        service = TicketService(session)
        detail = service.update_status(
            agent,
            ticket.id,
            TicketStatusUpdate(status=TicketStatus.WAITING_FOR_CUSTOMER),
        )
        assert detail.status is TicketStatus.WAITING_FOR_CUSTOMER

        with pytest.raises(ConflictError) as invalid:
            service.update_status(
                agent,
                ticket.id,
                TicketStatusUpdate(status=TicketStatus.CLOSED),
            )
        assert invalid.value.code is ErrorCode.INVALID_STATUS_TRANSITION

        reopened = service.update_status(
            agent,
            ticket.id,
            TicketStatusUpdate(status=TicketStatus.IN_PROGRESS),
        )
        assert reopened.status is TicketStatus.IN_PROGRESS

        audits = list(
            session.exec(
                select(TicketAuditLog)
                .where(TicketAuditLog.ticket_id == ticket.id)
                .order_by(col(TicketAuditLog.created_at), col(TicketAuditLog.id))
            ).all()
        )
        tracked_graph.audit_ids.extend(audit.id for audit in audits)
        assert [audit.action for audit in audits] == [
            TicketAuditAction.STATUS_CHANGED,
            TicketAuditAction.STATUS_CHANGED,
        ]
        assert audits[0].old_value == {"status": TicketStatus.IN_PROGRESS.value}
        assert audits[0].new_value == {
            "status": TicketStatus.WAITING_FOR_CUSTOMER.value
        }


def test_admin_closes_resolved_ticket_and_closed_ticket_rejects_writes(
    tracked_graph: TrackedGraph,
) -> None:
    """Admin 可关闭已解决工单，关闭后回复、状态和属性写入都被拒绝。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent, status=TicketStatus.RESOLVED)
    persist(tracked_graph, users=[customer, agent, admin], tickets=[ticket])

    with Session(engine) as session:
        service = TicketService(session)
        closed = service.update_status(
            admin,
            ticket.id,
            TicketStatusUpdate(status=TicketStatus.CLOSED),
        )
        assert closed.status is TicketStatus.CLOSED

        for operation in (
            lambda: service.add_customer_reply(
                customer, ticket.id, CustomerReplyCreate(content="Please reopen.")
            ),
            lambda: service.add_staff_message(
                admin,
                ticket.id,
                TicketMessageCreate(
                    message_type=TicketMessageType.PUBLIC_REPLY,
                    content="Closed reply.",
                ),
            ),
            lambda: service.update_status(
                admin,
                ticket.id,
                TicketStatusUpdate(status=TicketStatus.IN_PROGRESS),
            ),
            lambda: service.update_attributes(
                admin,
                ticket.id,
                TicketAttributesUpdate(priority=TicketPriority.URGENT),
            ),
        ):
            with pytest.raises(ConflictError) as closed_error:
                operation()
            assert closed_error.value.code is ErrorCode.TICKET_CLOSED

        audits = list(
            session.exec(
                select(TicketAuditLog).where(TicketAuditLog.ticket_id == ticket.id)
            ).all()
        )
        tracked_graph.audit_ids.extend(audit.id for audit in audits)
        assert [audit.action for audit in audits] == [TicketAuditAction.STATUS_CHANGED]


def test_update_attributes_records_each_actual_change(
    tracked_graph: TrackedGraph,
) -> None:
    """负责人 Agent 修改优先级和分类时分别写入属性审计。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    other_agent = make_user(UserRole.AGENT)
    ticket = make_ticket(customer, assignee=agent, status=TicketStatus.IN_PROGRESS)
    persist(tracked_graph, users=[customer, agent, other_agent], tickets=[ticket])

    with Session(engine) as session:
        service = TicketService(session)
        detail = service.update_attributes(
            agent,
            ticket.id,
            TicketAttributesUpdate(
                priority=TicketPriority.URGENT,
                category=TicketCategory.BUG,
            ),
        )
        assert detail.priority is TicketPriority.URGENT
        assert detail.category is TicketCategory.BUG

        with pytest.raises(ForbiddenError) as forbidden:
            service.update_attributes(
                other_agent,
                ticket.id,
                TicketAttributesUpdate(priority=TicketPriority.LOW),
            )
        assert forbidden.value.code is ErrorCode.TICKET_FORBIDDEN

        audits = list(
            session.exec(
                select(TicketAuditLog)
                .where(TicketAuditLog.ticket_id == ticket.id)
                .order_by(col(TicketAuditLog.action))
            ).all()
        )
        tracked_graph.audit_ids.extend(audit.id for audit in audits)
        assert {audit.action for audit in audits} == {
            TicketAuditAction.PRIORITY_CHANGED,
            TicketAuditAction.CATEGORY_CHANGED,
        }
        assert {
            audit.new_value and next(iter(audit.new_value.values())) for audit in audits
        } == {
            TicketPriority.URGENT.value,
            TicketCategory.BUG.value,
        }


def test_delete_ticket_requires_true_confirmation_and_admin_role(
    tracked_graph: TrackedGraph,
) -> None:
    """删除仅允许 Admin，且服务层拒绝未确认请求。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer)
    persist(tracked_graph, users=[customer, agent, admin], tickets=[ticket])

    with pytest.raises(ValidationError):
        DeleteTicketRequest.model_validate({"confirm": False})

    with Session(engine) as session:
        service = TicketService(session)
        for actor in (customer, agent):
            with pytest.raises(ForbiddenError) as forbidden:
                service.delete_ticket(
                    actor, ticket.id, DeleteTicketRequest(confirm=True)
                )
            assert forbidden.value.code is ErrorCode.ROLE_FORBIDDEN

        unconfirmed = DeleteTicketRequest.model_construct(confirm=False)
        with pytest.raises(ConflictError) as confirmation:
            service.delete_ticket(admin, ticket.id, unconfirmed)
        assert confirmation.value.code is ErrorCode.DELETE_CONFIRMATION_REQUIRED

    with Session(engine) as session:
        saved = session.get(Ticket, ticket.id)
        assert saved is not None
        assert saved.deleted_at is None
        assert saved.deleted_by_id is None


def test_admin_delete_soft_deletes_and_retains_ticket_graph(
    tracked_graph: TrackedGraph,
) -> None:
    """Admin 删除后业务不可见，但 Ticket、Message 和删除审计均保留。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    agent = make_user(UserRole.AGENT)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer, assignee=agent, status=TicketStatus.IN_PROGRESS)
    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=customer.id,
        message_type=TicketMessageType.PUBLIC_REPLY,
        content="Retained after deletion.",
    )
    existing_audit = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=agent.id,
        action=TicketAuditAction.STATUS_CHANGED,
    )
    persist(
        tracked_graph,
        users=[customer, agent, admin],
        tickets=[ticket],
        messages=[message],
        audits=[existing_audit],
    )

    with Session(engine) as session:
        service = TicketService(session)
        service.delete_ticket(admin, ticket.id, DeleteTicketRequest(confirm=True))

        assert (
            service.list_tickets(admin, TicketFilters(query=ticket.ticket_number)).data
            == []
        )
        with pytest.raises(NotFoundError) as hidden:
            service.get_ticket(admin, ticket.id)
        assert hidden.value.code is ErrorCode.TICKET_NOT_FOUND

        saved = session.get(Ticket, ticket.id)
        assert saved is not None
        assert saved.deleted_at is not None
        assert saved.deleted_by_id == admin.id
        assert session.get(TicketMessage, message.id) is not None

        audits = list(
            session.exec(
                select(TicketAuditLog)
                .where(TicketAuditLog.ticket_id == ticket.id)
                .order_by(col(TicketAuditLog.created_at), col(TicketAuditLog.id))
            ).all()
        )
        deleted_audits = [
            audit for audit in audits if audit.action is TicketAuditAction.DELETED
        ]
        assert len(deleted_audits) == 1
        deleted_audit = deleted_audits[0]
        tracked_graph.audit_ids.append(deleted_audit.id)
        assert deleted_audit.actor_id == admin.id
        assert deleted_audit.old_value == {"deleted_at": None, "deleted_by_id": None}
        assert deleted_audit.new_value is not None
        assert deleted_audit.new_value["deleted_by_id"] == str(admin.id)
        assert deleted_audit.new_value["deleted_at"] == saved.deleted_at.isoformat()

        with pytest.raises(NotFoundError):
            service.delete_ticket(admin, ticket.id, DeleteTicketRequest(confirm=True))
        assert (
            len(
                list(
                    session.exec(
                        select(TicketAuditLog).where(
                            TicketAuditLog.ticket_id == ticket.id,
                            TicketAuditLog.action == TicketAuditAction.DELETED,
                        )
                    ).all()
                )
            )
            == 1
        )


def test_delete_ticket_rolls_back_when_deletion_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
    tracked_graph: TrackedGraph,
) -> None:
    """删除审计写入失败时，软删除标记必须随事务整体回滚。by AI.Coding"""
    customer = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    ticket = make_ticket(customer)
    persist(tracked_graph, users=[customer, admin], tickets=[ticket])

    with Session(engine) as session:
        service = TicketService(session)

        def fail_audit(_: TicketAuditLog) -> None:
            """模拟删除审计持久化失败。by AI.Coding"""
            raise RuntimeError("audit failed")

        monkeypatch.setattr(service.ticket_repository, "add_audit", fail_audit)
        with pytest.raises(RuntimeError, match="audit failed"):
            service.delete_ticket(admin, ticket.id, DeleteTicketRequest(confirm=True))
        assert not session.in_transaction()

    with Session(engine) as session:
        saved = session.get(Ticket, ticket.id)
        assert saved is not None
        assert saved.deleted_at is None
        assert saved.deleted_by_id is None
        assert (
            session.exec(
                select(func.count())
                .select_from(TicketAuditLog)
                .where(
                    TicketAuditLog.ticket_id == ticket.id,
                    TicketAuditLog.action == TicketAuditAction.DELETED,
                )
            ).one()
            == 0
        )
