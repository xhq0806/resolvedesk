"""ORM 模型与领域枚举的稳定导出入口。by AI.Coding"""

from app.models.enums import (
    TicketAuditAction,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User

# 显式导入当前全部 ORM，保证导入 app.models 时只注册迁移后仍存在的表。
__all__ = [
    "Ticket",
    "TicketAuditAction",
    "TicketAuditLog",
    "TicketCategory",
    "TicketMessage",
    "TicketMessageType",
    "TicketPriority",
    "TicketStatus",
    "User",
    "UserRole",
]
