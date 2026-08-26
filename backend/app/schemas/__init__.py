"""API Schema 的稳定聚合导出入口。by AI.Coding"""

from app.schemas.auth import NewPassword, Token, TokenPayload, UpdatePassword
from app.schemas.common import Message
from app.schemas.user import (
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    "Message",
    "NewPassword",
    "Token",
    "TokenPayload",
    "UpdatePassword",
    "UserCreate",
    "UserPublic",
    "UserRegister",
    "UsersPublic",
    "UserUpdate",
    "UserUpdateMe",
]
