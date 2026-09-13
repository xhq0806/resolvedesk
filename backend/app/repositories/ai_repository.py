"""AI 会话、运行和事件的 Workspace 隔离仓储。by AI.Coding"""

from __future__ import annotations

import uuid

from sqlmodel import Session, col, select

from app.core.workspace import WorkspaceContext
from app.models.ai import AiConversation, AiMessage, AiRun, AiRunEvent, AiRunStatus


class AiRepository:
    """封装 AI 资源查询和运行状态读取。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存数据库会话。by AI.Coding"""
        self.session = session

    def get_conversation(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> AiConversation | None:
        """按 Workspace 查询会话，跨租户统一返回空。by AI.Coding"""
        return self.session.exec(
            select(AiConversation).where(
                col(AiConversation.id) == conversation_id,
                col(AiConversation.workspace_id) == context.workspace_id,
            )
        ).first()

    def get_running_run(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> AiRun | None:
        """读取会话中唯一 RUNNING 的生成任务。by AI.Coding"""
        return self.session.exec(
            select(AiRun).where(
                col(AiRun.conversation_id) == conversation_id,
                col(AiRun.workspace_id) == context.workspace_id,
                col(AiRun.status) == AiRunStatus.RUNNING,
            )
        ).first()

    def list_messages(
        self, context: WorkspaceContext, conversation_id: uuid.UUID
    ) -> list[AiMessage]:
        """读取当前租户会话消息并保持创建顺序。by AI.Coding"""
        return list(
            self.session.exec(
                select(AiMessage)
                .where(
                    col(AiMessage.conversation_id) == conversation_id,
                    col(AiMessage.workspace_id) == context.workspace_id,
                )
                .order_by(col(AiMessage.created_at))
            ).all()
        )

    def list_events(
        self, context: WorkspaceContext, run_id: uuid.UUID
    ) -> list[AiRunEvent]:
        """读取当前租户运行事件用于断线重放。by AI.Coding"""
        return list(
            self.session.exec(
                select(AiRunEvent)
                .where(
                    col(AiRunEvent.run_id) == run_id,
                    col(AiRunEvent.workspace_id) == context.workspace_id,
                )
                .order_by(col(AiRunEvent.sequence))
            ).all()
        )
