"""AI Agent 事件解析与工具白名单基础测试。by AI.Coding"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlmodel import Session, col, select

from app.core.workspace import WorkspaceContext
from app.models.ai import AiConversation, AiMessage, AiMessageRole
from app.models.enums import TicketCategory, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.ai import MessageCreate
from app.services.agent_service import AgentService
from app.services.tool_executor import ALLOWED_TOOLS


def _make_user(db: Session, email_prefix: str, role: UserRole = UserRole.CUSTOMER) -> User:
    """创建测试用户并保持邮箱唯一。by AI.Coding"""
    user = User(
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        hashed_password="not-used",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_member(
    db: Session,
    workspace: Workspace,
    user: User,
    role: WorkspaceRole,
) -> WorkspaceMember:
    """创建当前 Workspace 的测试成员关系。by AI.Coding"""
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def test_extract_delta_reads_openai_compatible_chunk() -> None:
    """AgentService 应只从标准 delta.content 中提取文本。by AI.Coding"""
    assert (
        AgentService._extract_delta({"choices": [{"delta": {"content": "hello"}}]})
        == "hello"
    )
    assert AgentService._extract_delta({"choices": [{"delta": {"role": "assistant"}}]}) == ""


def test_message_create_rejects_blank_or_oversized_content() -> None:
    """AI 用户消息必须有正文和幂等 client_message_id。by AI.Coding"""
    with pytest.raises(ValidationError):
        MessageCreate(content="   ", client_message_id="client-1")
    with pytest.raises(ValidationError):
        MessageCreate(content="hello", client_message_id="")


def test_tool_whitelist_excludes_destructive_and_admin_tools() -> None:
    """本期 Agent 白名单不得包含删除工单或成员管理等越权工具。by AI.Coding"""
    assert {
        "get_current_ticket",
        "update_ticket_attributes",
        "update_ticket_status",
        "send_public_reply",
        "add_internal_note",
    } == ALLOWED_TOOLS
    assert "delete_ticket" not in ALLOWED_TOOLS
    assert "manage_members" not in ALLOWED_TOOLS


def test_customer_handoff_creates_ticket_and_assigns_idle_agent(db: Session) -> None:
    """客户在线咨询转人工后应创建工单并分派给负载更低的 Agent。by AI.Coding"""
    workspace = db.exec(select(Workspace).where(Workspace.slug == "default")).one()
    customer = _make_user(db, "handoff-customer")
    busy_agent = _make_user(db, "handoff-busy-agent", UserRole.AGENT)
    idle_agent = _make_user(db, "handoff-idle-agent", UserRole.AGENT)
    customer_member = _add_member(db, workspace, customer, WorkspaceRole.CUSTOMER)
    _add_member(db, workspace, busy_agent, WorkspaceRole.AGENT)
    _add_member(db, workspace, idle_agent, WorkspaceRole.AGENT)
    db.add(
        Ticket(
            workspace_id=workspace.id,
            title="existing busy ticket",
            description="busy",
            category=TicketCategory.OTHER,
            requester_id=customer.id,
            assignee_id=busy_agent.id,
            status=TicketStatus.IN_PROGRESS,
        )
    )
    conversation = AiConversation(
        workspace_id=workspace.id,
        created_by_id=customer.id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    db.add(
        AiMessage(
            conversation_id=conversation.id,
            workspace_id=workspace.id,
            role=AiMessageRole.USER,
            content="API 报错怎么处理？",
        )
    )
    db.commit()

    context = WorkspaceContext(workspace=workspace, member=customer_member)
    result = AgentService(db).handoff_to_ticket(
        context,
        customer,
        conversation.id,
        reason="需要人工确认",
    )

    assert result.ticket.title == "API 报错怎么处理？"
    assert result.assigned_agent_id == idle_agent.id
    assert result.ticket.assignee is not None
    assert result.ticket.assignee.id == idle_agent.id
    assert result.ticket.status is TicketStatus.IN_PROGRESS
    assert result.conversation.handed_off is True
    assert result.conversation.ticket_id == result.ticket.id


def test_customer_handoff_is_idempotent(db: Session) -> None:
    """重复转人工应返回既有工单，避免同一会话创建多个工单。by AI.Coding"""
    workspace = db.exec(select(Workspace).where(Workspace.slug == "default")).one()
    customer = _make_user(db, "handoff-repeat-customer")
    agent = _make_user(db, "handoff-repeat-agent", UserRole.AGENT)
    customer_member = _add_member(db, workspace, customer, WorkspaceRole.CUSTOMER)
    _add_member(db, workspace, agent, WorkspaceRole.AGENT)
    conversation = AiConversation(workspace_id=workspace.id, created_by_id=customer.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    context = WorkspaceContext(workspace=workspace, member=customer_member)
    service = AgentService(db)
    first = service.handoff_to_ticket(context, customer, conversation.id)
    second = service.handoff_to_ticket(context, customer, conversation.id)
    ticket_count = db.exec(
        select(Ticket)
        .where(
            col(Ticket.workspace_id) == workspace.id,
            col(Ticket.requester_id) == customer.id,
        )
    ).all()

    assert second.ticket.id == first.ticket.id
    assert len(ticket_count) == 1
