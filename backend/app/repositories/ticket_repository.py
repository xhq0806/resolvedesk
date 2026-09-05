"""工单角色查询、时间线裁剪与原子接手仓储。by AI.Coding"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, or_, update
from sqlalchemy.orm import QueryableAttribute, joinedload
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.models.enums import (
    TicketAuditAction,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User
from app.schemas.ticket import TicketFilters

_CUSTOMER_SAFE_AUDIT_ACTIONS = (
    TicketAuditAction.STATUS_CHANGED,
    TicketAuditAction.PRIORITY_CHANGED,
    TicketAuditAction.CATEGORY_CHANGED,
)


@dataclass(frozen=True)
class TicketStatisticsRow:
    """Repository 聚合后供 Service 裁剪的统计行。by AI.Coding"""

    status_counts: dict[TicketStatus, int]
    priority_counts: dict[TicketPriority, int]
    unassigned_count: int
    assigned_to_me_count: int
    waiting_for_customer_count: int


class TicketRepository:
    """封装工单数据范围与并发写入，并将事务留给调用方。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, ticket: Ticket) -> None:
        """将工单加入当前 Session，但不提交事务。by AI.Coding"""
        self.session.add(ticket)

    def get_active_by_id(
        self, ticket_id: uuid.UUID, *, for_update: bool = False
    ) -> Ticket | None:
        """按主键读取未软删除工单，并可锁定和刷新该行。by AI.Coding"""
        statement = select(Ticket).where(
            Ticket.id == ticket_id,
            col(Ticket.deleted_at).is_(None),
        )
        if for_update:
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        return self.session.exec(statement).one_or_none()

    def get_active_by_number(self, ticket_number: str) -> Ticket | None:
        """按外部工单编号读取未软删除工单。by AI.Coding"""
        statement = select(Ticket).where(
            Ticket.ticket_number == ticket_number,
            col(Ticket.deleted_at).is_(None),
        )
        return self.session.exec(statement).one_or_none()

    def list_for_actor(
        self, actor: User, filters: TicketFilters
    ) -> tuple[list[Ticket], int]:
        """按角色数据范围和组合筛选返回稳定分页及总数。by AI.Coding"""
        conditions = self._build_list_conditions(actor, filters)
        count_statement = select(func.count()).select_from(Ticket).where(*conditions)
        count = self.session.exec(count_statement).one()

        offset = (filters.page - 1) * filters.page_size
        statement = (
            select(Ticket)
            .where(*conditions)
            .options(
                joinedload(self._relationship(Ticket.requester)),
                joinedload(self._relationship(Ticket.assignee)),
            )
            .order_by(
                col(Ticket.updated_at).desc(),
                col(Ticket.id).desc(),
            )
            .offset(offset)
            .limit(filters.page_size)
        )
        tickets = list(self.session.exec(statement).all())
        return tickets, count

    def claim_if_available(
        self,
        ticket_id: uuid.UUID,
        agent_id: uuid.UUID,
        updated_at: datetime,
    ) -> Ticket | None:
        """以单条条件更新原子接手 OPEN 且未分派的活跃工单。by AI.Coding"""
        statement = (
            update(Ticket)
            .where(
                col(Ticket.id) == ticket_id,
                col(Ticket.deleted_at).is_(None),
                col(Ticket.status) == TicketStatus.OPEN,
                col(Ticket.assignee_id).is_(None),
            )
            .values(
                assignee_id=agent_id,
                status=TicketStatus.IN_PROGRESS,
                updated_at=updated_at,
            )
            .returning(Ticket)
        )
        result = self.session.execute(statement).scalars().one_or_none()  # ty: ignore[deprecated]
        return cast(Ticket | None, result)

    def list_messages(
        self, ticket_id: uuid.UUID, *, include_internal: bool
    ) -> list[TicketMessage]:
        """按可见性读取工单消息时间线。by AI.Coding"""
        statement = select(TicketMessage).where(
            TicketMessage.ticket_id == ticket_id
        )
        if not include_internal:
            statement = statement.where(
                TicketMessage.message_type == TicketMessageType.PUBLIC_REPLY
            )
        statement = statement.options(
            joinedload(self._relationship(TicketMessage.author))
        ).order_by(
            col(TicketMessage.created_at),
            col(TicketMessage.id),
        )
        return list(self.session.exec(statement).all())

    def list_audits(
        self, ticket_id: uuid.UUID, *, customer_safe_only: bool
    ) -> list[TicketAuditLog]:
        """读取完整或 Customer 安全的结构化审计时间线。by AI.Coding"""
        statement = select(TicketAuditLog).where(
            TicketAuditLog.ticket_id == ticket_id
        )
        if customer_safe_only:
            statement = statement.where(
                col(TicketAuditLog.action).in_(_CUSTOMER_SAFE_AUDIT_ACTIONS)
            )
        statement = statement.options(
            joinedload(self._relationship(TicketAuditLog.actor))
        ).order_by(
            col(TicketAuditLog.created_at),
            col(TicketAuditLog.id),
        )
        return list(self.session.exec(statement).all())

    def add_message(self, message: TicketMessage) -> None:
        """将消息加入当前 Session，但不提交事务。by AI.Coding"""
        self.session.add(message)

    def add_audit(self, audit: TicketAuditLog) -> None:
        """将审计记录加入当前 Session，但不提交事务。by AI.Coding"""
        self.session.add(audit)

    def get_statistics(self, actor: User) -> TicketStatisticsRow:
        """在角色数据范围内聚合活跃工单统计。by AI.Coding"""
        conditions = self._build_list_conditions(actor, TicketFilters())
        status_counts = dict.fromkeys(TicketStatus, 0)
        status_statement = (
            select(Ticket.status, func.count())
            .where(*conditions)
            .group_by(Ticket.status)
        )
        for row in self.session.exec(status_statement).all():
            status, count = cast(tuple[TicketStatus, int], row)
            status_counts[status] = int(count)

        priority_counts = dict.fromkeys(TicketPriority, 0)
        priority_statement = (
            select(Ticket.priority, func.count())
            .where(*conditions)
            .group_by(Ticket.priority)
        )
        for row in self.session.exec(priority_statement).all():
            priority, count = cast(tuple[TicketPriority, int], row)
            priority_counts[priority] = int(count)

        unassigned_count = self._count_statistics(
            conditions,
            col(Ticket.assignee_id).is_(None),
        )
        assigned_to_me_count = self._count_statistics(
            conditions,
            col(Ticket.assignee_id) == actor.id,
        )
        waiting_for_customer_count = self._count_statistics(
            conditions,
            col(Ticket.status) == TicketStatus.WAITING_FOR_CUSTOMER,
        )
        return TicketStatisticsRow(
            status_counts=status_counts,
            priority_counts=priority_counts,
            unassigned_count=unassigned_count,
            assigned_to_me_count=assigned_to_me_count,
            waiting_for_customer_count=waiting_for_customer_count,
        )

    @staticmethod
    def _relationship(value: object) -> QueryableAttribute[Any]:
        """收窄 SQLModel Relationship 的静态类型供加载器使用。by AI.Coding"""
        return cast(QueryableAttribute[Any], value)

    @staticmethod
    def _build_list_conditions(
        actor: User, filters: TicketFilters
    ) -> list[ColumnElement[bool]]:
        """构造 active、角色范围与筛选共用谓词。by AI.Coding"""
        conditions: list[ColumnElement[bool]] = [
            col(Ticket.deleted_at).is_(None)
        ]
        if actor.role is UserRole.CUSTOMER:
            conditions.append(col(Ticket.requester_id) == actor.id)
        elif actor.role is UserRole.AGENT:
            conditions.append(
                or_(
                    col(Ticket.assignee_id).is_(None),
                    col(Ticket.assignee_id) == actor.id,
                )
            )

        if filters.status is not None:
            conditions.append(col(Ticket.status) == filters.status)
        if filters.priority is not None:
            conditions.append(col(Ticket.priority) == filters.priority)
        if filters.category is not None:
            conditions.append(col(Ticket.category) == filters.category)
        if filters.assignee_id is not None:
            conditions.append(col(Ticket.assignee_id) == filters.assignee_id)
        if filters.query is not None:
            escaped_query = (
                filters.query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped_query}%"
            conditions.append(
                or_(
                    col(Ticket.ticket_number).ilike(pattern, escape="\\"),
                    col(Ticket.title).ilike(pattern, escape="\\"),
                )
            )
        return conditions

    def _count_statistics(
        self,
        conditions: list[ColumnElement[bool]],
        condition: ColumnElement[bool],
    ) -> int:
        """在已授权的数据范围内执行单个条件计数。by AI.Coding"""
        statement = select(func.count()).select_from(Ticket).where(
            *conditions,
            condition,
        )
        return int(self.session.exec(statement).one())
