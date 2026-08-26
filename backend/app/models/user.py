"""用户角色化持久化模型。by AI.Coding"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, Enum, Index, text
from sqlmodel import Field, SQLModel

from app.models.enums import UserRole


def get_datetime_utc() -> datetime:
    """返回带 UTC 时区的当前时间。by AI.Coding"""
    return datetime.now(UTC)


def get_enum_values[EnumType: StrEnum](
    enum_type: type[EnumType],
) -> Callable[[type[EnumType]], list[str]]:
    """返回 SQLAlchemy Enum 使用的稳定字符串值提取器。by AI.Coding"""

    def values_callable(_: type[EnumType]) -> list[str]:
        """按声明顺序提取字符串枚举值。by AI.Coding"""
        return [member.value for member in enum_type]

    return values_callable


class User(SQLModel, table=True):
    """使用单角色权限模型的用户数据库模型。by AI.Coding"""

    __table_args__ = (Index("ix_user_role_active", "role", "is_active"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    role: UserRole = Field(
        default=UserRole.CUSTOMER,
        sa_column=Column(
            Enum(
                UserRole,
                name="user_role",
                native_enum=True,
                values_callable=get_enum_values(UserRole),
            ),
            nullable=False,
            server_default=text("'CUSTOMER'::user_role"),
        ),
    )
    full_name: str | None = Field(default=None, max_length=255)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    @property
    def is_superuser(self) -> bool:
        """迁移期兼容旧权限调用，并由角色单向派生管理员身份。by AI.Coding"""
        return self.role is UserRole.ADMIN
