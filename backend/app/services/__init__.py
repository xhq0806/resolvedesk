"""Service 的稳定聚合导出入口。by AI.Coding"""

from app.services.ticket_service import TicketService
from app.services.user_service import UserService

__all__ = ["TicketService", "UserService"]
