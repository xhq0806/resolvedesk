"""领域枚举定义，统一数据库与 API 使用的字符串值。by AI.Coding"""

from enum import StrEnum


class UserRole(StrEnum):
    """用户单角色枚举。by AI.Coding"""

    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"


class TicketStatus(StrEnum):
    """工单状态枚举。by AI.Coding"""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    """工单优先级枚举。by AI.Coding"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(StrEnum):
    """工单分类枚举。by AI.Coding"""

    ACCOUNT = "ACCOUNT"
    BILLING = "BILLING"
    PRODUCT = "PRODUCT"
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    OTHER = "OTHER"


class TicketMessageType(StrEnum):
    """工单消息类型枚举。by AI.Coding"""

    PUBLIC_REPLY = "PUBLIC_REPLY"
    INTERNAL_NOTE = "INTERNAL_NOTE"


class TicketAuditAction(StrEnum):
    """工单审计动作枚举。by AI.Coding"""

    TAKEN = "TAKEN"
    ASSIGNED = "ASSIGNED"
    REASSIGNED = "REASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    CATEGORY_CHANGED = "CATEGORY_CHANGED"
    DELETED = "DELETED"
