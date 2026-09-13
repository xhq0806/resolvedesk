"""AI 会话生命周期、流式运行与人工接管服务。by AI.Coding"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.errors import ConflictError, ErrorCode, NotFoundError
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
from app.providers.chat import ChatMessage, ChatProvider
from app.repositories.ai_repository import AiRepository
from app.schemas.ai import ConversationCreate, MessageCreate


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

        messages = [
            ChatMessage(role=message.role.value.lower(), content=message.content)
            for message in self.repository.list_messages(context, conversation.id)
            if message.status is AiMessageStatus.CONFIRMED
        ]
        deltas: list[str] = []
        sequence = 1
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
