"""AI Provider 配置与连接测试 HTTP 接口。by AI.Coding"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep, WorkspaceContextDep
from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.request_context import get_request_id
from app.models.ai import AiAgent, AiToolPermission
from app.schemas.ai import (
    ConversationCreate,
    ConversationPublic,
    HandoffTicketPublic,
    HandoffTicketRequest,
    MessageCreate,
    ProviderConfigPatch,
    ProviderConfigPublic,
    ProviderTestRequest,
    ProviderTestResult,
)
from app.schemas.tools import ToolPermissionPatch, ToolPermissionPublic
from app.services.agent_service import AgentService
from app.services.provider_service import ProviderService
from app.services.tool_executor import ALLOWED_TOOLS

router = APIRouter(prefix="/workspaces/{workspace_id}/ai", tags=["ai"])
conversation_router = APIRouter(prefix="/workspaces/{workspace_id}/conversations", tags=["ai"])
customer_router = APIRouter(prefix="/workspaces/{workspace_id}/customer", tags=["ai"])


def _ensure_same_workspace(
    workspace_id: uuid.UUID,
    context: WorkspaceContextDep,
) -> None:
    """校验路径租户与请求头租户一致，避免跨租户探测资源存在性。by AI.Coding"""
    if context.workspace_id != workspace_id:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)


@router.get("/provider", response_model=ProviderConfigPublic)
def get_provider_config(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> ProviderConfigPublic:
    """返回当前 Workspace 的脱敏 AI Provider 配置。by AI.Coding"""
    # 认证用户由依赖校验，这里保留参数以维持受保护接口语义。by AI.Coding
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return ProviderService(session).get_config(context)


@router.patch("/provider", response_model=ProviderConfigPublic)
def update_provider_config(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: ProviderConfigPatch,
) -> ProviderConfigPublic:
    """由 Owner/Admin 更新 Provider、base URL、模型、密钥和启用状态。by AI.Coding"""
    # Provider 密钥只进入服务层加密写入，路由层不记录、不回显。by AI.Coding
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return ProviderService(session).update_config(context, payload)


@router.post("/provider/test", response_model=ProviderTestResult)
async def test_provider_config(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: ProviderTestRequest,
) -> ProviderTestResult:
    """触发 Chat 或 Embedding Provider 的最小连接测试。by AI.Coding"""
    # 外部连接测试在 service 内先提交配置事务，再调用 Provider。by AI.Coding
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return await ProviderService(session).test_provider(context, payload)


@router.get("/tools", response_model=list[ToolPermissionPublic])
def list_tool_permissions(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> list[ToolPermissionPublic]:
    """返回当前 Workspace AI Agent 的白名单工具授权状态。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    agent = session.exec(
        select(AiAgent).where(col(AiAgent.workspace_id) == context.workspace_id)
    ).first()
    if agent is None:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    permissions = {
        permission.tool_name: permission.enabled
        for permission in session.exec(
            select(AiToolPermission).where(
                col(AiToolPermission.ai_agent_id) == agent.id,
                col(AiToolPermission.workspace_id) == context.workspace_id,
            )
        ).all()
    }
    return [
        ToolPermissionPublic(tool_name=tool_name, enabled=permissions.get(tool_name, False))
        for tool_name in sorted(ALLOWED_TOOLS)
    ]


@router.patch("/tools", response_model=list[ToolPermissionPublic])
def update_tool_permissions(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: list[ToolPermissionPatch],
) -> list[ToolPermissionPublic]:
    """由 Owner/Admin 更新 AI Agent 工具逐项授权状态。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    from app.core.workspace import WorkspacePolicy

    WorkspacePolicy.require_manager(context)
    if any(item.tool_name not in ALLOWED_TOOLS for item in payload):
        raise ConflictError(ErrorCode.TOOL_NOT_ALLOWED)
    agent = session.exec(
        select(AiAgent).where(col(AiAgent.workspace_id) == context.workspace_id)
    ).first()
    if agent is None:
        raise NotFoundError(ErrorCode.WORKSPACE_RESOURCE_NOT_FOUND)
    for item in payload:
        permission = session.exec(
            select(AiToolPermission).where(
                col(AiToolPermission.ai_agent_id) == agent.id,
                col(AiToolPermission.workspace_id) == context.workspace_id,
                col(AiToolPermission.tool_name) == item.tool_name,
            )
        ).first()
        if permission is None:
            permission = AiToolPermission(
                ai_agent_id=agent.id,
                workspace_id=context.workspace_id,
                tool_name=item.tool_name,
            )
        permission.enabled = item.enabled
        permission.updated_by_id = current_user.id
        session.add(permission)
    session.commit()
    return list_tool_permissions(session, current_user, context, workspace_id)


@conversation_router.post("", response_model=ConversationPublic)
def create_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: ConversationCreate,
) -> ConversationPublic:
    """创建当前 Workspace 的 AI 会话。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    conversation = AgentService(session).create_conversation(context, current_user, payload)
    return ConversationPublic.model_validate(conversation)


@conversation_router.post("/{conversation_id}/handoff", response_model=ConversationPublic)
def handoff_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> ConversationPublic:
    """人工接管会话并取消运行中的 AI 生成。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return ConversationPublic.model_validate(
        AgentService(session).handoff(context, conversation_id)
    )


@conversation_router.post(
    "/{conversation_id}/handoff-ticket",
    response_model=HandoffTicketPublic,
)
def handoff_conversation_to_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: HandoffTicketRequest,
) -> HandoffTicketPublic:
    """客户在线咨询转人工，创建工单并尝试自动分派客服。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    result = AgentService(session).handoff_to_ticket(
        context,
        current_user,
        conversation_id,
        reason=payload.reason,
    )
    return HandoffTicketPublic(
        conversation=ConversationPublic.model_validate(result.conversation),
        ticket_id=result.ticket.id,
        ticket_number=result.ticket.ticket_number,
        assigned_agent_id=result.assigned_agent_id,
        assigned=result.assigned_agent_id is not None,
    )


@conversation_router.post("/{conversation_id}/resume", response_model=ConversationPublic)
def resume_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> ConversationPublic:
    """恢复已接管会话的 AI 生成能力。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return ConversationPublic.model_validate(
        AgentService(session).resume(context, conversation_id)
    )


@conversation_router.post("/{conversation_id}/cancel", response_model=ConversationPublic)
def cancel_conversation_run(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> ConversationPublic:
    """取消会话中当前运行的 AI 生成。by AI.Coding"""
    del current_user
    _ensure_same_workspace(workspace_id, context)
    return ConversationPublic.model_validate(
        AgentService(session).cancel_run(context, conversation_id)
    )


@conversation_router.post("/{conversation_id}/messages/stream")
async def stream_conversation_message(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: MessageCreate,
) -> StreamingResponse:
    """以 SSE 返回 AI 消息增量、完成和失败事件。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    provider = ProviderService(session).build_chat_provider(context)
    request_id = get_request_id() or str(uuid.uuid4())

    async def events() -> AsyncIterator[str]:
        """把内部 Agent 事件编码为标准 SSE 文本帧。by AI.Coding"""
        service = AgentService(session)
        try:
            async for event in service.stream_message(
                context,
                current_user,
                conversation_id,
                payload,
                provider,
                request_id=request_id,
            ):
                if await request.is_disconnected():
                    # 客户端断流后立即终止当前生成，避免继续写入完整 AI 回复。by AI.Coding
                    service.cancel_run(context, conversation_id)
                    break
                yield (
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                )
        except asyncio.CancelledError:
            service.cancel_run(context, conversation_id)
            raise

    return StreamingResponse(events(), media_type="text/event-stream")


@customer_router.get("/conversation", response_model=ConversationPublic)
def get_customer_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> ConversationPublic:
    """返回或创建当前客户的在线咨询会话。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    conversation = AgentService(session).get_or_create_customer_conversation(
        context, current_user
    )
    return ConversationPublic.model_validate(conversation)


@customer_router.post("/conversation", response_model=ConversationPublic)
def create_customer_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
) -> ConversationPublic:
    """显式创建或复用客户在线咨询会话。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    conversation = AgentService(session).get_or_create_customer_conversation(
        context, current_user
    )
    return ConversationPublic.model_validate(conversation)


@customer_router.post("/conversation/messages/stream")
async def stream_customer_conversation_message(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    workspace_id: uuid.UUID,
    payload: MessageCreate,
) -> StreamingResponse:
    """客户在线咨询专用 SSE，AI 内部结合知识库回答。by AI.Coding"""
    _ensure_same_workspace(workspace_id, context)
    chat_provider = ProviderService(session).build_chat_provider(context)
    embedding_provider = ProviderService(session).build_embedding_provider(context)
    request_id = get_request_id() or str(uuid.uuid4())

    async def events() -> AsyncIterator[str]:
        """把客户咨询事件编码为标准 SSE 文本帧。by AI.Coding"""
        service = AgentService(session)
        try:
            async for event in service.stream_customer_message(
                context,
                current_user,
                payload,
                chat_provider,
                embedding_provider,
                request_id=request_id,
            ):
                if await request.is_disconnected():
                    conversation = service.get_or_create_customer_conversation(
                        context, current_user
                    )
                    service.cancel_run(context, conversation.id)
                    break
                yield (
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                )
        except asyncio.CancelledError:
            conversation = service.get_or_create_customer_conversation(
                context, current_user
            )
            service.cancel_run(context, conversation.id)
            raise

    return StreamingResponse(events(), media_type="text/event-stream")
