"""人工客服自动分派策略，按 Workspace 内空闲度选择 Agent。by AI.Coding"""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.workspace import WorkspaceContext
from app.models.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import MembershipStatus, WorkspaceMember, WorkspaceRole


class AgentAssignmentPolicy:
    """选择当前 Workspace 内活跃且未满载的人工客服。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        """保存请求级数据库会话。by AI.Coding"""
        self.session = session

    def pick_agent(self, context: WorkspaceContext) -> User | None:
        """按未关闭工单数量升序、用户创建顺序稳定选取 Agent。by AI.Coding"""
        load_column = func.count(col(Ticket.id)).label("open_ticket_count")
        statement = (
            select(User, load_column)
            .join(WorkspaceMember, col(WorkspaceMember.user_id) == col(User.id))
            .outerjoin(
                Ticket,
                (col(Ticket.assignee_id) == col(User.id))
                & (col(Ticket.workspace_id) == context.workspace_id)
                & (col(Ticket.deleted_at).is_(None))
                & (col(Ticket.status) != TicketStatus.CLOSED),
            )
            .where(
                col(WorkspaceMember.workspace_id) == context.workspace_id,
                col(WorkspaceMember.status) == MembershipStatus.ACTIVE,
                col(WorkspaceMember.role) == WorkspaceRole.AGENT,
                col(User.is_active).is_(True),
            )
            .group_by(col(User.id))
            .order_by(load_column.asc(), col(User.created_at).asc(), col(User.id).asc())
            .limit(1)
        )
        row = self.session.exec(statement).first()
        return row[0] if row is not None else None
