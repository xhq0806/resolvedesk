"""ORM 模型与领域枚举的稳定导出入口。by AI.Coding"""

from app.models.ai import (
    AiAgent,
    AiAgentStatus,
    AiConversation,
    AiMessage,
    AiMessageRole,
    AiMessageStatus,
    AiProviderConfig,
    AiRun,
    AiRunEvent,
    AiRunEventType,
    AiRunStatus,
    AiToolPermission,
    ConversationMode,
    ConversationStatus,
)
from app.models.attachment import Attachment
from app.models.enums import (
    TicketAuditAction,
    TicketCategory,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.knowledge import (
    DocumentIngestionJob,
    IngestionJobStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from app.models.workspace import (
    MembershipStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceStatus,
)

# 显式导入当前全部 ORM，保证导入 app.models 时只注册迁移后仍存在的表。by AI.Coding
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
    "AiAgent",
    "AiAgentStatus",
    "AiProviderConfig",
    "AiConversation",
    "AiMessage",
    "AiMessageRole",
    "AiMessageStatus",
    "AiRun",
    "AiRunEvent",
    "AiRunEventType",
    "AiRunStatus",
    "AiToolPermission",
    "Attachment",
    "ConversationMode",
    "ConversationStatus",
    "DocumentIngestionJob",
    "IngestionJobStatus",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeDocumentStatus",
    "MembershipStatus",
    "Workspace",
    "WorkspaceInvitation",
    "WorkspaceMember",
    "WorkspaceRole",
    "WorkspaceStatus",
]
