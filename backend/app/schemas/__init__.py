"""API Schema 的稳定聚合导出入口。by AI.Coding"""

from app.schemas.auth import NewPassword, Token, TokenPayload, UpdatePassword
from app.schemas.common import ErrorResponse, Message
from app.schemas.ticket import (
    TicketAssign,
    TicketAuditPublic,
    TicketCreate,
    TicketDetailPublic,
    TicketFilters,
    TicketMessagePublic,
    TicketPublic,
    TicketsPublic,
    UserSummary,
)
from app.schemas.user import (
    UserCreate,
    UserCreateAdmin,
    UserFilters,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateAdmin,
    UserUpdateMe,
)

__all__ = [
    "ErrorResponse",
    "Message",
    "NewPassword",
    "TicketAssign",
    "TicketAuditPublic",
    "TicketCreate",
    "TicketDetailPublic",
    "TicketFilters",
    "TicketMessagePublic",
    "TicketPublic",
    "TicketsPublic",
    "Token",
    "TokenPayload",
    "UpdatePassword",
    "UserCreate",
    "UserCreateAdmin",
    "UserFilters",
    "UserPublic",
    "UserRegister",
    "UsersPublic",
    "UserSummary",
    "UserUpdate",
    "UserUpdateAdmin",
    "UserUpdateMe",
]
