"""AI Provider 配置 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.user import StrictInput


class ProviderTestKind(StrEnum):
    """Provider 连接测试类型。by AI.Coding"""

    CHAT = "CHAT"
    EMBEDDING = "EMBEDDING"


class ProviderConfigPatch(StrictInput):
    """Owner/Admin 更新模型 Provider 配置的输入。by AI.Coding"""

    chat_provider: Literal["openai-compatible"] | None = None
    chat_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    chat_model: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_provider: Literal["openai-compatible"] | None = None
    embedding_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_dimension: Literal[1536] | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    clear_api_key: bool = False
    enabled: bool | None = None

    @field_validator(
        "chat_base_url",
        "chat_model",
        "embedding_base_url",
        "embedding_model",
        "api_key",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        """去除配置文本首尾空白。by AI.Coding"""
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def ensure_key_operation_is_clear(self) -> Self:
        """避免同一次请求同时写入和清除 API Key。by AI.Coding"""
        if self.api_key is not None and self.clear_api_key:
            raise ValueError("不能同时写入和清除 API Key。")
        return self


class ProviderConfigPublic(BaseModel):
    """不回显密钥原文的 Provider 配置响应。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    chat_provider: str
    chat_base_url: str | None
    chat_model: str
    embedding_provider: str
    embedding_base_url: str | None
    embedding_model: str
    embedding_dimension: int
    has_api_key: bool
    masked_api_key: str | None
    enabled: bool
    updated_at: datetime


class ProviderTestRequest(StrictInput):
    """触发 Chat 或 Embedding 连接测试的输入。by AI.Coding"""

    kind: ProviderTestKind


class ProviderTestResult(BaseModel):
    """Provider 连接测试的稳定业务结果。by AI.Coding"""

    kind: ProviderTestKind
    ok: bool
    code: str | None = None
    message: str
    latency_ms: int


class ConversationCreate(StrictInput):
    """创建 Workspace 或工单关联 AI 会话。by AI.Coding"""

    ticket_id: uuid.UUID | None = None


class ConversationPublic(BaseModel):
    """AI 会话公开状态。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    ticket_id: uuid.UUID | None
    mode: str
    status: str
    handed_off: bool
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MessageCreate(StrictInput):
    """发送 AI 用户消息的输入。by AI.Coding"""

    content: str = Field(min_length=1, max_length=10000)
    client_message_id: str = Field(min_length=1, max_length=120)

    @field_validator("content", "client_message_id", mode="before")
    @classmethod
    def strip_message_text(cls, value: object) -> object:
        """去除消息标识和正文首尾空白。by AI.Coding"""
        return value.strip() if isinstance(value, str) else value


class AgentEventPublic(BaseModel):
    """SSE 事件的稳定外部结构。by AI.Coding"""

    event: str
    data: dict[str, object]
