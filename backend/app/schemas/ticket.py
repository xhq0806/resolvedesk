"""工单查询 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid

from pydantic import Field, field_validator

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
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
