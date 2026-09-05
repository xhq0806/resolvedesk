"""工单查询 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    TicketAuditAction,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.schemas.user import StrictInput


class TicketFilters(StrictInput):
    """按角色范围查询工单的筛选与分页参数。by AI.Coding"""

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: TicketCategory | None = None
    assignee_id: uuid.UUID | None = None
    query: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: object) -> object:
        """去除查询文本首尾空白，并将空文本视为未筛选。by AI.Coding"""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class TicketCreate(StrictInput):
    """Customer 创建工单的严格输入。by AI.Coding"""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    category: TicketCategory

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        """去除工单文本首尾空白后再执行长度校验。by AI.Coding"""
        if isinstance(value, str):
            return value.strip()
        return value


class TicketAssign(StrictInput):
    """Admin 分派或转派工单的严格输入。by AI.Coding"""

    assignee_id: uuid.UUID


class CustomerReplyCreate(StrictInput):
    """Customer 公开回复工单的严格输入。by AI.Coding"""

    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        """去除公开回复首尾空白后再执行长度校验。by AI.Coding"""
        if isinstance(value, str):
            return value.strip()
        return value


class TicketMessageCreate(StrictInput):
    """Staff 创建公开回复或内部备注的严格输入。by AI.Coding"""

    message_type: TicketMessageType
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        """去除 Staff 消息首尾空白后再执行长度校验。by AI.Coding"""
        if isinstance(value, str):
            return value.strip()
        return value


class TicketStatusUpdate(StrictInput):
    """主动修改工单状态的严格输入。by AI.Coding"""

    status: TicketStatus


class TicketAttributesUpdate(StrictInput):
    """修改工单优先级或分类的严格输入。by AI.Coding"""

    priority: TicketPriority | None = None
    category: TicketCategory | None = None

    @model_validator(mode="after")
    def ensure_any_attribute(self) -> Self:
        """至少提供一个可变更属性，避免空 PATCH 成为假成功。by AI.Coding"""
        if self.priority is None and self.category is None:
            raise ValueError("At least one ticket attribute is required.")
        return self


class DeleteTicketRequest(StrictInput):
    """Admin 删除工单时必须显式确认的输入。by AI.Coding"""

    confirm: Literal[True]


class TicketStatisticsPublic(BaseModel):
    """按角色返回工单统计计数。by AI.Coding"""

    role: UserRole
    status_counts: dict[TicketStatus, int] = Field(default_factory=dict)
    priority_counts: dict[TicketPriority, int] = Field(default_factory=dict)
    unassigned_count: int = 0
    assigned_to_me_count: int = 0
    waiting_for_customer_count: int = 0


class UserSummary(BaseModel):
    """嵌入工单响应的最小用户公开摘要。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    role: UserRole


class TicketPublic(BaseModel):
    """不包含消息和审计时间线的工单公开响应。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    requester: UserSummary
    assignee: UserSummary | None = None
    created_at: datetime
    updated_at: datetime


class TicketMessagePublic(BaseModel):
    """按角色裁剪后的工单消息响应。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author: UserSummary
    message_type: TicketMessageType
    content: str
    created_at: datetime


class TicketAuditPublic(BaseModel):
    """按角色裁剪后的结构化工单审计响应。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: TicketAuditAction
    actor: UserSummary
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    created_at: datetime


class TicketDetailPublic(TicketPublic):
    """包含角色安全时间线的工单详情响应。by AI.Coding"""

    messages: list[TicketMessagePublic]
    audit_logs: list[TicketAuditPublic]


class TicketsPublic(BaseModel):
    """工单服务端分页响应。by AI.Coding"""

    data: list[TicketPublic]
    count: int
    page: int
    page_size: int
