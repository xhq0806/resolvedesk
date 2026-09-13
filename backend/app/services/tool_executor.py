"""AI Agent 白名单工具执行器。by AI.Coding"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.workspace import WorkspaceContext, WorkspacePolicy
from app.models.ai import AiAgent, AiAgentStatus, AiToolPermission
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import (
    TicketAttributesUpdate,
    TicketMessageCreate,
    TicketStatusUpdate,
)
from app.services.ticket_service import TicketService

ALLOWED_TOOLS = {
    "get_current_ticket",
    "update_ticket_attributes",
    "update_ticket_status",
    "send_public_reply",
    "add_internal_note",
}


@dataclass(frozen=True)
class ToolResult:
    """工具执行的脱敏最小结果。by AI.Coding"""

    tool_name: str
    ok: bool
    data: dict[str, object]
    code: str | None = None


class ToolExecutor:
    """在服务端重验 Workspace、绑定工单和工具权限后执行动作。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存数据库会话和一期工单服务。by AI.Coding"""
        self.session = session
        self.ticket_service = TicketService(session)

    def execute(
        self,
        context: WorkspaceContext,
        actor: User,
        *,
        agent_id: uuid.UUID,
        tool_name: str,
        ticket_id: uuid.UUID,
        arguments: dict[str, object],
    ) -> ToolResult:
        """执行已授权且绑定当前工单的白名单工具。by AI.Coding"""
        WorkspacePolicy.require_member(context.member)
        if tool_name not in ALLOWED_TOOLS:
            return ToolResult(tool_name, False, {}, ErrorCode.TOOL_NOT_ALLOWED.value)
        agent = self.session.exec(
            select(AiAgent).where(
                col(AiAgent.id) == agent_id,
                col(AiAgent.workspace_id) == context.workspace_id,
                col(AiAgent.status) == AiAgentStatus.ACTIVE,
            )
        ).first()
        if agent is None:
            return ToolResult(tool_name, False, {}, ErrorCode.TOOL_NOT_ALLOWED.value)
        self._ensure_enabled(context, agent_id, tool_name)
        ticket = self.session.exec(
            select(Ticket).where(
                col(Ticket.id) == ticket_id,
                col(Ticket.workspace_id) == context.workspace_id,
                col(Ticket.deleted_at).is_(None),
            )
        ).first()
        if ticket is None:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        if tool_name == "get_current_ticket":
            return ToolResult(
                tool_name,
                True,
                {
                    "ticket_number": ticket.ticket_number,
                    "title": ticket.title,
                    "status": ticket.status.value,
                    "priority": ticket.priority.value,
                    "category": ticket.category.value,
                },
            )
        if tool_name == "update_ticket_attributes":
            result = self.ticket_service.update_attributes(
                actor,
                ticket_id,
                TicketAttributesUpdate.model_validate(arguments),
                context=context,
            )
            return ToolResult(tool_name, True, {"ticket_id": str(result.id)})
        if tool_name == "update_ticket_status":
            result = self.ticket_service.update_status(
                actor,
                ticket_id,
                TicketStatusUpdate.model_validate(arguments),
                context=context,
            )
            return ToolResult(tool_name, True, {"ticket_id": str(result.id)})
        if tool_name == "send_public_reply":
            message = self.ticket_service.add_staff_message(
                actor,
                ticket_id,
                TicketMessageCreate.model_validate(
                    {**arguments, "message_type": "PUBLIC_REPLY"}
                ),
                context=context,
            )
            return ToolResult(tool_name, True, {"message_id": str(message.id)})
        message = self.ticket_service.add_staff_message(
            actor,
            ticket_id,
            TicketMessageCreate.model_validate(
                {**arguments, "message_type": "INTERNAL_NOTE"}
            ),
            context=context,
        )
        return ToolResult(tool_name, True, {"message_id": str(message.id)})

    def _ensure_enabled(
        self,
        context: WorkspaceContext,
        agent_id: uuid.UUID,
        tool_name: str,
    ) -> None:
        """从数据库重新读取工具授权，拒绝模型自行扩大权限。by AI.Coding"""
        permission = self.session.exec(
            select(AiToolPermission).where(
                col(AiToolPermission.ai_agent_id) == agent_id,
                col(AiToolPermission.workspace_id) == context.workspace_id,
                col(AiToolPermission.tool_name) == tool_name,
                col(AiToolPermission.enabled).is_(True),
            )
        ).first()
        if permission is None:
            raise ConflictError(ErrorCode.TOOL_NOT_ALLOWED)
