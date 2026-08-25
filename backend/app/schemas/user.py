"""用户请求与响应 API Schema。by AI.Coding"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictInput(BaseModel):
    """拒绝未声明字段的外部输入基类。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


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
