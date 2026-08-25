"""用户持久化模型，保持当前数据库结构兼容。by AI.Coding"""

import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    """返回带 UTC 时区的当前时间。by AI.Coding"""
    return datetime.now(UTC)


class User(SQLModel, table=True):
    """用户数据库模型；角色迁移前继续保留 is_superuser。by AI.Coding"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
