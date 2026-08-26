"""用户请求与响应 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


class StrictInput(BaseModel):
    """拒绝未声明字段的外部输入基类。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class UserFilters(StrictInput):
    """管理员用户列表筛选与分页参数。by AI.Coding"""

    role: UserRole | None = None
    is_active: bool | None = None
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


class UserCreate(StrictInput):
    """管理员创建用户请求，保持当前模板字段兼容。by AI.Coding"""

    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRegister(StrictInput):
    """公开注册请求，不接受角色和启用状态字段。by AI.Coding"""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(StrictInput):
    """管理员更新用户请求，保持现有接口名称和字段。by AI.Coding"""

    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(StrictInput):
    """当前用户更新个人资料请求。by AI.Coding"""

    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UserPublic(BaseModel):
    """用户公开响应，不包含密码字段。by AI.Coding"""

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(BaseModel):
    """用户分页响应。by AI.Coding"""

    data: list[UserPublic]
    count: int
