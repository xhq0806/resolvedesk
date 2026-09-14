"""AI 会话生命周期、流式运行与人工接管服务。by AI.Coding"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.errors import ConflictError, ErrorCode, ForbiddenError, NotFoundError
from app.core.workspace import WorkspaceContext, WorkspacePolicy
from app.models.ai import (
    AiConversation,
    AiMessage,
    AiMessageRole,
    AiMessageStatus,
    AiRun,
    AiRunEvent,
    AiRunEventType,
    AiRunStatus,
    ConversationMode,
    ConversationStatus,
)
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.providers.chat import ChatMessage, ChatProvider
from app.providers.embedding import EmbeddingProvider
from app.repositories.ai_repository import AiRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.ai import ConversationCreate, MessageCreate
from app.schemas.ticket import TicketDetailPublic
from app.services.assignment_service import AgentAssignmentPolicy
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalService,
    RetrievedChunk,
)
from app.services.ticket_service import TicketService


@dataclass(frozen=True)
class HandoffTicketResult:
    """在线咨询转人工的内部返回结构。by AI.Coding"""

    conversation: AiConversation
    ticket: TicketDetailPublic
    assigned_agent_id: uuid.UUID | None


class AgentService:
    """编排 Workspace 隔离的 AI 会话与 Provider 流。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求级数据库会话和 AI 资源仓储。by AI.Coding"""
        self.session = session
        self.repository = AiRepository(session)

    def create_conversation(
        self,
        context: WorkspaceContext,
        actor: User,
        payload: ConversationCreate,
    ) -> AiConversation:
        """创建 Workspace 或工单关联会话并校验工单归属。by AI.Coding"""
        if payload.ticket_id is not None:
            ticket = self.session.exec(
                select(Ticket).where(
                    col(Ticket.id) == payload.ticket_id,
                    col(Ticket.workspace_id) == context.workspace_id,
                    col(Ticket.deleted_at).is_(None),
                )
            ).first()
            if ticket is None:
                raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
            mode = ConversationMode.TICKET
        else:
            mode = ConversationMode.WORKSPACE
        conversation = AiConversation(
            workspace_id=context.workspace_id,
            ticket_id=payload.ticket_id,
            mode=mode,
            created_by_id=actor.id,
        )
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def get_or_create_customer_conversation(
        self,
        context: WorkspaceContext,
        actor: User,
    ) -> AiConversation:
        """为客户浮窗复用一个未转人工的活跃 Workspace 会话。by AI.Coding"""
        if context.role is not WorkspaceRole.CUSTOMER:
            raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)
        conversation = self.session.exec(
            select(AiConversation)
            .where(
                col(AiConversation.workspace_id) == context.workspace_id,
                col(AiConversation.created_by_id) == actor.id,
                col(AiConversation.mode) == ConversationMode.WORKSPACE,
                col(AiConversation.ticket_id).is_(None),
                col(AiConversation.status) == ConversationStatus.ACTIVE,
                col(AiConversation.handed_off).is_(False),
            )
            .order_by(col(AiConversation.updated_at).desc())
        ).first()
        if conversation is not None:
            return conversation
        return self.create_conversation(context, actor, ConversationCreate())

    def get_conversation(
        self,
        context: WorkspaceContext,
        conversation_id: uuid.UUID,
    ) -> AiConversation:
        """按 Workspace 查询会话并隐藏跨租户资源。by AI.Coding"""
        conversation = self.repository.get_conversation(context, conversation_id)
        if conversation is None:
            raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
        return conversation

    def handoff(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> AiConversation:
        """人工接管会话并取消当前运行。by AI.Coding"""
        conversation = self.get_conversation(context, conversation_id)
        conversation.handed_off = True
        conversation.status = ConversationStatus.HANDED_OFF
        self._cancel_running_run(context, conversation.id)
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def resume(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> AiConversation:
        """明确恢复 AI 自动处理能力。by AI.Coding"""
        conversation = self.get_conversation(context, conversation_id)
        conversation.handed_off = False
        conversation.status = ConversationStatus.ACTIVE
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return conversation

    def cancel_run(
        self,
        context: WorkspaceContext,
        conversation_id: uuid.UUID,
    ) -> AiConversation:
        """取消会话中的运行并保持已有消息历史。by AI.Coding"""
        conversation = self.get_conversation(context, conversation_id)
        self._cancel_running_run(context, conversation.id)
        self.session.commit()
        return conversation

    async def stream_message(
        self,
        context: WorkspaceContext,
        actor: User,
        conversation_id: uuid.UUID,
        payload: MessageCreate,
        provider: ChatProvider,
        *,
        request_id: str,
        system_context: str | None = None,
        sources: list[RetrievedChunk] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """持久化用户消息后流式生成 AI 回复并发出稳定事件。by AI.Coding"""
        WorkspacePolicy.require_member(context.member)
        conversation = self.get_conversation(context, conversation_id)
        if conversation.handed_off or conversation.status is not ConversationStatus.ACTIVE:
            raise ConflictError(ErrorCode.AI_RUN_IN_PROGRESS)
        if self.repository.get_running_run(context, conversation.id) is not None:
            raise ConflictError(ErrorCode.AI_RUN_IN_PROGRESS)
        if self._duplicate_client_message(context, conversation.id, payload.client_message_id):
            raise ConflictError(ErrorCode.AI_RUN_IN_PROGRESS)

        user_message = AiMessage(
            conversation_id=conversation.id,
            workspace_id=context.workspace_id,
            role=AiMessageRole.USER,
            content=payload.content,
            client_message_id=payload.client_message_id,
        )
        run = AiRun(
            conversation_id=conversation.id,
            workspace_id=context.workspace_id,
            request_id=request_id,
            model=str(getattr(provider, "model", "configured")),
        )
        self.session.add(user_message)
        self.session.add(run)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(ErrorCode.AI_RUN_IN_PROGRESS) from exc
        self.session.refresh(run)
        self._record_event(
            run,
            0,
            AiRunEventType.RUN_STARTED,
            {"run_id": str(run.id)},
        )
        yield self._event(AiRunEventType.RUN_STARTED, run, {"run_id": str(run.id)})

        sequence = 1
        for source in sources or []:
            payload_source = {
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "display_name": source.display_name,
                "locator": source.locator,
                "preview": source.content[:500],
                "distance": source.distance,
            }
            self._record_event(run, sequence, AiRunEventType.SOURCE_FOUND, payload_source)
            sequence += 1
            yield self._event(AiRunEventType.SOURCE_FOUND, run, payload_source)

        messages = [
            ChatMessage(role=message.role.value.lower(), content=message.content)
            for message in self.repository.list_messages(context, conversation.id)
            if message.status is AiMessageStatus.CONFIRMED
        ]
        if system_context:
            messages.insert(0, ChatMessage(role="system", content=system_context))
        deltas: list[str] = []
        try:
            async for chunk in provider.stream(messages):
                delta = self._extract_delta(chunk)
                if not delta:
                    continue
                deltas.append(delta)
                event = self._event(
                    AiRunEventType.MESSAGE_DELTA,
                    run,
                    {"run_id": str(run.id), "text": delta},
                )
                self._record_event(
                    run,
                    sequence,
                    AiRunEventType.MESSAGE_DELTA,
                    {"text": delta},
                )
                sequence += 1
                yield event
            content = "".join(deltas).strip()
            if not content:
                raise ValueError("AI 返回空内容")
            assistant = AiMessage(
                conversation_id=conversation.id,
                workspace_id=context.workspace_id,
                role=AiMessageRole.ASSISTANT,
                content=content,
                ai_generated=True,
            )
            run.status = AiRunStatus.COMPLETED
            run.finished_at = datetime.now(UTC)
            self.session.add(assistant)
            self.session.add(run)
            self.session.commit()
            self._record_event(
                run,
                sequence,
                AiRunEventType.MESSAGE_COMPLETED,
                {"message_id": str(assistant.id), "ai_generated": True},
            )
            yield self._event(
                AiRunEventType.MESSAGE_COMPLETED,
                run,
                {"message_id": str(assistant.id), "ai_generated": True},
            )
            self._record_event(
                run,
                sequence + 1,
                AiRunEventType.RUN_COMPLETED,
                {"run_id": str(run.id)},
            )
            yield self._event(AiRunEventType.RUN_COMPLETED, run, {"run_id": str(run.id)})
        except asyncio.CancelledError:
            self._finish_run(run, AiRunStatus.CANCELLED, "RUN_CANCELLED")
            self._record_event(
                run,
                sequence,
                AiRunEventType.RUN_CANCELLED,
                {"run_id": str(run.id)},
            )
            yield self._event(AiRunEventType.RUN_CANCELLED, run, {"run_id": str(run.id)})
        except Exception:
            self._finish_run(run, AiRunStatus.FAILED, "PROVIDER_UNAVAILABLE")
            self._record_event(
                run,
                sequence,
                AiRunEventType.RUN_FAILED,
                {"run_id": str(run.id), "error_code": "PROVIDER_UNAVAILABLE"},
            )
            yield self._event(
                AiRunEventType.RUN_FAILED,
                run,
                {"run_id": str(run.id), "error_code": "PROVIDER_UNAVAILABLE"},
            )

    async def stream_customer_message(
        self,
        context: WorkspaceContext,
        actor: User,
        payload: MessageCreate,
        chat_provider: ChatProvider,
        embedding_provider: EmbeddingProvider,
        *,
        request_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """客户在线咨询专用流式回复，先内部检索知识库再回答。by AI.Coding"""
        conversation = self.get_or_create_customer_conversation(context, actor)
        sources = await KnowledgeRetrievalService(
            KnowledgeRepository(self.session),
            embedding_provider,
        ).search(context, payload.content)
        system_context = self._customer_system_context(sources)
        async for event in self.stream_message(
            context,
            actor,
            conversation.id,
            payload,
            chat_provider,
            request_id=request_id,
            system_context=system_context,
            sources=sources,
        ):
            yield event

    def handoff_to_ticket(
        self,
        context: WorkspaceContext,
        actor: User,
        conversation_id: uuid.UUID,
        *,
        reason: str | None = None,
    ) -> HandoffTicketResult:
        """客户会话转人工，创建工单并按空闲 Agent 自动分派。by AI.Coding"""
        if context.role is not WorkspaceRole.CUSTOMER:
            raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)
        conversation = self.get_conversation(context, conversation_id)
        if conversation.created_by_id != actor.id:
            raise ForbiddenError(ErrorCode.WORKSPACE_ROLE_FORBIDDEN)
        if conversation.ticket_id is not None:
            ticket = TicketService(self.session).get_ticket(
                actor, conversation.ticket_id, context=context
            )
            return HandoffTicketResult(
                conversation=conversation,
                ticket=ticket,
                assigned_agent_id=ticket.assignee.id if ticket.assignee else None,
            )

        messages = self.repository.list_messages(context, conversation.id)
        assignee = AgentAssignmentPolicy(self.session).pick_agent(context)
        ticket = TicketService(self.session).create_from_ai_handoff(
            actor,
            title=self._handoff_title(messages),
            description=self._handoff_description(
                messages,
                reason=reason,
                conversation_id=conversation.id,
            ),
            assignee=assignee,
            conversation_id=conversation.id,
            context=context,
        )
        conversation.ticket_id = ticket.id
        conversation.handed_off = True
        conversation.status = ConversationStatus.HANDED_OFF
        conversation.updated_at = datetime.now(UTC)
        self._cancel_running_run(context, conversation.id)
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(conversation)
        return HandoffTicketResult(
            conversation=conversation,
            ticket=ticket,
            assigned_agent_id=ticket.assignee.id if ticket.assignee else None,
        )

    def _duplicate_client_message(
        self,
        context: WorkspaceContext,
        conversation_id: uuid.UUID,
        client_message_id: str,
    ) -> bool:
        """检测会话内幂等消息标识。by AI.Coding"""
        return (
            self.session.exec(
                select(AiMessage.id).where(
                    col(AiMessage.conversation_id) == conversation_id,
                    col(AiMessage.workspace_id) == context.workspace_id,
                    col(AiMessage.client_message_id) == client_message_id,
                )
            ).first()
            is not None
        )

    def _cancel_running_run(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> None:
        """将当前会话的运行标记为取消。by AI.Coding"""
        run = self.repository.get_running_run(context, conversation_id)
        if run is not None:
            self._finish_run(run, AiRunStatus.CANCELLED, "RUN_CANCELLED")

    def _finish_run(self, run: AiRun, status: AiRunStatus, error_code: str | None) -> None:
        """写入运行终态，避免半条 AI 内容被标记为完整回复。by AI.Coding"""
        run.status = status
        run.error_code = error_code
        run.finished_at = datetime.now(UTC)
        self.session.add(run)
        self.session.commit()

    @staticmethod
    def _customer_system_context(sources: list[RetrievedChunk]) -> str:
        """把知识库来源压缩为客户咨询 Prompt，不暴露管理能力。by AI.Coding"""
        if not sources:
            return (
                "你是 ResolveDesk 在线咨询 AI Agent。当前没有检索到可引用的知识库内容。"
                "请先给出谨慎、简短的回应，并在信息不足时建议客户转人工。"
            )
        source_blocks = []
        for index, source in enumerate(sources, start=1):
            source_blocks.append(
                f"[来源{index}] {source.display_name}\n{source.content[:1200]}"
            )
        return (
            "你是 ResolveDesk 在线咨询 AI Agent。必须优先依据以下知识库来源回答客户，"
            "不要声称客户可以访问或管理知识库；如果知识库不足以回答，请说明信息不足并建议转人工。\n\n"
            + "\n\n".join(source_blocks)
        )

    @staticmethod
    def _handoff_title(messages: list[AiMessage]) -> str:
        """从最近一条客户消息生成工单标题。by AI.Coding"""
        for message in reversed(messages):
            if message.role is AiMessageRole.USER and message.content.strip():
                return message.content.strip().splitlines()[0][:80]
        return "在线咨询转人工"

    @staticmethod
    def _handoff_description(
        messages: list[AiMessage],
        *,
        reason: str | None,
        conversation_id: uuid.UUID,
    ) -> str:
        """把会话上下文整理成客服可读的工单描述。by AI.Coding"""
        lines = [
            "客户从在线咨询请求转人工。",
            f"AI 会话 ID：{conversation_id}",
        ]
        if reason:
            lines.append(f"转人工原因：{reason}")
        lines.append("")
        lines.append("最近会话：")
        for message in messages[-12:]:
            role = "客户" if message.role is AiMessageRole.USER else "AI"
            if message.role not in {AiMessageRole.USER, AiMessageRole.ASSISTANT}:
                continue
            lines.append(f"{role}：{message.content.strip()[:1000]}")
        return "\n".join(lines).strip()[:10_000]

    @staticmethod
    def _extract_delta(chunk: dict[str, Any]) -> str:
        """从 OpenAI-compatible chunk 中提取文本增量。by AI.Coding"""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        delta = first.get("delta") if isinstance(first, dict) else None
        text = delta.get("content") if isinstance(delta, dict) else None
        return text if isinstance(text, str) else ""

    def _record_event(
        self,
        run: AiRun,
        sequence: int,
        event_type: AiRunEventType,
        payload: dict[str, object],
    ) -> None:
        """持久化可重放事件，payload 只包含脱敏字段。by AI.Coding"""
        self.session.add(
            AiRunEvent(
                run_id=run.id,
                workspace_id=run.workspace_id,
                sequence=sequence,
                event_type=event_type,
                payload_json=payload,
            )
        )
        self.session.commit()

    @staticmethod
    def _event(
        event_type: AiRunEventType,
        run: AiRun,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        """构造不含密钥和 Prompt 原文的 SSE 事件。by AI.Coding"""
        return {"event": event_type.value, "data": payload}
