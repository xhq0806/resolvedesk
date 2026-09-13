"""AI Agent 事件解析与工具白名单基础测试。by AI.Coding"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai import MessageCreate
from app.services.agent_service import AgentService
from app.services.tool_executor import ALLOWED_TOOLS


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
