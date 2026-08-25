"""遗留 Item API Schema，仅用于当前模板兼容。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictInput(BaseModel):
    """拒绝未声明字段的遗留 Item 输入基类。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class ItemCreate(StrictInput):
    """创建遗留 Item 请求。by AI.Coding"""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemUpdate(StrictInput):
    """更新遗留 Item 请求。by AI.Coding"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemPublic(BaseModel):
    """遗留 Item 公开响应。by AI.Coding"""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(BaseModel):
    """遗留 Item 列表响应。by AI.Coding"""

    data: list[ItemPublic]
    count: int
