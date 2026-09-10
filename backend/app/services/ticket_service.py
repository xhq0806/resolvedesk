"""工单创建、查询、原子接手与负责人事务服务。by AI.Coding"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TypeVar

from sqlmodel import Session

from app.core.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
)
from app.models.enums import (
    TicketAuditAction,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.ticket import Ticket, TicketAuditLog, TicketMessage
from app.models.user import User, get_datetime_utc
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ticket import (
    CustomerReplyCreate,
    DeleteTicketRequest,
    TicketAssign,
    TicketAttributesUpdate,
    TicketAuditPublic,
    TicketCreate,
    TicketDetailPublic,
    TicketFilters,
    TicketMessageCreate,
    TicketMessagePublic,
    TicketPublic,
    TicketsPublic,
    TicketStatusUpdate,
)
from app.services.ticket_permissions import (
    can_add_internal_note,
    can_manage_ticket,
    can_reply_publicly,
    can_view_internal_notes,
    can_view_ticket,
)
from app.services.ticket_state_machine import (
    allowed_status_targets,
    customer_reply_status_target,
)

ResultType = TypeVar("ResultType")


class TicketService:
    """编排 Ticket Repository、权限、审计与事务边界。by AI.Coding"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.ticket_repository = TicketRepository(session)
        self.user_repository = UserRepository(session)

    def create_ticket(self, actor: User, payload: TicketCreate) -> TicketDetailPublic:
        """由 Customer 创建默认 OPEN、MEDIUM、未分派工单。by AI.Coding"""
        if actor.role is not UserRole.CUSTOMER:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

        def operation() -> Ticket:
            # 角色、状态、优先级和负责人均由服务端固定，不能由请求越权覆盖。
            ticket = Ticket(
                title=payload.title,
                description=payload.description,
                category=payload.category,
                requester_id=actor.id,
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                assignee_id=None,
            )
            self.ticket_repository.add(ticket)
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def list_tickets(self, actor: User, filters: TicketFilters) -> TicketsPublic:
        """返回角色范围内筛选后的工单稳定分页。by AI.Coding"""
        tickets, count = self.ticket_repository.list_for_actor(actor, filters)
        return TicketsPublic(
            data=[TicketPublic.model_validate(ticket) for ticket in tickets],
            count=count,
            page=filters.page,
            page_size=filters.page_size,
        )

    def get_ticket(self, actor: User, ticket_id: uuid.UUID) -> TicketDetailPublic:
        """先鉴权再按角色裁剪并返回工单详情。by AI.Coding"""
        ticket = self._get_visible_ticket(actor, ticket_id)
        return self._build_detail(actor, ticket)

    def claim_ticket(self, actor: User, ticket_id: uuid.UUID) -> TicketDetailPublic:
        """由活跃 Agent 原子接手 OPEN 且未分派工单。by AI.Coding"""
        if actor.role not in {UserRole.AGENT, UserRole.ADMIN} or not actor.is_active:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

        def operation() -> Ticket:
            now = get_datetime_utc()
            ticket = self.ticket_repository.claim_if_available(ticket_id, actor.id, now)
            if ticket is None:
                # 条件更新失败后再读取，仅用于区分不存在与业务冲突。
                existing = self.ticket_repository.get_active_by_id(ticket_id)
                if existing is None:
                    raise NotFoundError(ErrorCode.TICKET_NOT_FOUND)
                raise ConflictError(ErrorCode.TICKET_ALREADY_CLAIMED)
            self.ticket_repository.add_audit(
                self._assignment_audit(
                    ticket=ticket,
                    actor=actor,
                    action=TicketAuditAction.TAKEN,
                    old_assignee_id=None,
                    old_status=TicketStatus.OPEN,
                )
            )
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def assign_ticket(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: TicketAssign,
    ) -> TicketDetailPublic:
        """由 Admin 分派或转派未关闭工单给活跃 Agent。by AI.Coding"""
        self._require_admin(actor)

        def operation() -> Ticket:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_open_for_assignment(ticket)
            assignee = self.user_repository.get_by_id(payload.assignee_id)
            if (
                assignee is None
                or assignee.role is not UserRole.AGENT
                or not assignee.is_active
            ):
                raise ConflictError(ErrorCode.INVALID_ASSIGNEE)
            if ticket.assignee_id == assignee.id:
                raise ConflictError(ErrorCode.INVALID_ASSIGNEE)

            old_assignee_id = ticket.assignee_id
            old_status = ticket.status
            action = (
                TicketAuditAction.ASSIGNED
                if old_assignee_id is None
                else TicketAuditAction.REASSIGNED
            )
            ticket.assignee_id = assignee.id
            # 初次处理 OPEN 工单时进入处理中；转派保留已有非 OPEN 状态。
            if ticket.status is TicketStatus.OPEN:
                ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = get_datetime_utc()
            self.ticket_repository.add(ticket)
            self.ticket_repository.add_audit(
                self._assignment_audit(
                    ticket=ticket,
                    actor=actor,
                    action=action,
                    old_assignee_id=old_assignee_id,
                    old_status=old_status,
                )
            )
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def unassign_ticket(self, actor: User, ticket_id: uuid.UUID) -> TicketDetailPublic:
        """由 Admin 取消负责人并将未关闭工单退回 OPEN 队列。by AI.Coding"""
        self._require_admin(actor)

        def operation() -> Ticket:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_open_for_assignment(ticket)
            if ticket.assignee_id is None:
                # 重复取消分派是无变化请求，直接返回当前详情且不写成功审计。
                return ticket
            old_assignee_id = ticket.assignee_id
            old_status = ticket.status
            ticket.assignee_id = None
            ticket.status = TicketStatus.OPEN
            ticket.updated_at = get_datetime_utc()
            self.ticket_repository.add(ticket)
            self.ticket_repository.add_audit(
                self._assignment_audit(
                    ticket=ticket,
                    actor=actor,
                    action=TicketAuditAction.UNASSIGNED,
                    old_assignee_id=old_assignee_id,
                    old_status=old_status,
                )
            )
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def add_customer_reply(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: CustomerReplyCreate,
    ) -> TicketMessagePublic:
        """Customer 发送公开回复，并按状态机自动重开等待或已解决工单。by AI.Coding"""
        if actor.role is not UserRole.CUSTOMER:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

        def operation() -> TicketMessage:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_writable(ticket)
            if not can_reply_publicly(actor, ticket):
                raise ForbiddenError(ErrorCode.TICKET_FORBIDDEN)

            now = get_datetime_utc()
            old_status = ticket.status
            target_status = customer_reply_status_target(ticket)
            message = TicketMessage(
                ticket_id=ticket.id,
                author_id=actor.id,
                message_type=TicketMessageType.PUBLIC_REPLY,
                content=payload.content,
            )
            # 消息与可能产生的状态重开必须处于同一个写事务内。
            self.ticket_repository.add_message(message)
            ticket.updated_at = now
            if target_status is not None:
                ticket.status = target_status
                self.ticket_repository.add_audit(
                    self._status_audit(
                        ticket=ticket,
                        actor=actor,
                        old_status=old_status,
                    )
                )
            self.ticket_repository.add(ticket)
            return message

        message = self._write(operation, refresh=True)
        return TicketMessagePublic.model_validate(message)

    def add_staff_message(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: TicketMessageCreate,
    ) -> TicketMessagePublic:
        """Agent 或 Admin 对未关闭工单发送公开回复或内部备注。by AI.Coding"""
        if actor.role not in {UserRole.AGENT, UserRole.ADMIN}:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

        def operation() -> TicketMessage:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_writable(ticket)
            if payload.message_type is TicketMessageType.INTERNAL_NOTE:
                allowed = can_add_internal_note(actor, ticket)
            else:
                allowed = can_reply_publicly(actor, ticket)
            if not allowed:
                raise ForbiddenError(ErrorCode.TICKET_FORBIDDEN)

            message = TicketMessage(
                ticket_id=ticket.id,
                author_id=actor.id,
                message_type=payload.message_type,
                content=payload.content,
            )
            # 普通消息不产生审计，但应推动工单更新时间用于队列排序。
            ticket.updated_at = get_datetime_utc()
            self.ticket_repository.add(ticket)
            self.ticket_repository.add_message(message)
            return message

        message = self._write(operation, refresh=True)
        return TicketMessagePublic.model_validate(message)

    def update_status(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: TicketStatusUpdate,
    ) -> TicketDetailPublic:
        """按状态机主动修改工单状态并写入状态审计。by AI.Coding"""

        def operation() -> Ticket:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_writable(ticket)
            if not can_manage_ticket(actor, ticket):
                raise ForbiddenError(ErrorCode.TICKET_FORBIDDEN)
            if payload.status not in allowed_status_targets(actor, ticket):
                raise ConflictError(ErrorCode.INVALID_STATUS_TRANSITION)

            old_status = ticket.status
            ticket.status = payload.status
            ticket.updated_at = get_datetime_utc()
            self.ticket_repository.add(ticket)
            self.ticket_repository.add_audit(
                self._status_audit(ticket=ticket, actor=actor, old_status=old_status)
            )
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def update_attributes(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: TicketAttributesUpdate,
    ) -> TicketDetailPublic:
        """修改工单优先级或分类，并为实际变化写入审计。by AI.Coding"""

        def operation() -> Ticket:
            ticket = self._get_locked_active_ticket(ticket_id)
            self._ensure_ticket_writable(ticket)
            if not can_manage_ticket(actor, ticket):
                raise ForbiddenError(ErrorCode.TICKET_FORBIDDEN)

            audits = self._attribute_audits(ticket=ticket, actor=actor, payload=payload)
            if audits:
                # 多个属性变化共享同一个更新时间，但分别保留可筛选的审计动作。
                ticket.updated_at = get_datetime_utc()
                self.ticket_repository.add(ticket)
                for audit in audits:
                    self.ticket_repository.add_audit(audit)
            return ticket

        ticket = self._write(operation, refresh=True)
        return self._build_detail(actor, ticket)

    def delete_ticket(
        self,
        actor: User,
        ticket_id: uuid.UUID,
        payload: DeleteTicketRequest,
    ) -> None:
        """Admin 确认后软删除工单，并在同一事务保留删除审计。by AI.Coding"""
        self._require_admin(actor)

        def operation() -> None:
            if payload.confirm is not True:
                raise ConflictError(ErrorCode.DELETE_CONFIRMATION_REQUIRED)

            ticket = self._get_locked_active_ticket(ticket_id)
            now = get_datetime_utc()
            ticket.deleted_at = now
            ticket.deleted_by_id = actor.id
            ticket.updated_at = now
            # 只记录删除标记的前后快照，避免把工单正文复制进审计 JSON。
            self.ticket_repository.add(ticket)
            self.ticket_repository.add_audit(
                TicketAuditLog(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    action=TicketAuditAction.DELETED,
                    old_value={"deleted_at": None, "deleted_by_id": None},
                    new_value={
                        "deleted_at": now.isoformat(),
                        "deleted_by_id": str(actor.id),
                    },
                )
            )

        self._write(operation, refresh=False)

    def _build_detail(self, actor: User, ticket: Ticket) -> TicketDetailPublic:
        """使用数据库侧裁剪结果显式组装安全详情。by AI.Coding"""
        messages = self.ticket_repository.list_messages(
            ticket.id,
            include_internal=can_view_internal_notes(actor, ticket),
        )
        audits = self.ticket_repository.list_audits(
            ticket.id,
            customer_safe_only=actor.role is UserRole.CUSTOMER,
        )
        public = TicketPublic.model_validate(ticket)
        return TicketDetailPublic(
            **public.model_dump(),
            messages=[
                TicketMessagePublic.model_validate(message) for message in messages
            ],
            audit_logs=[TicketAuditPublic.model_validate(audit) for audit in audits],
        )

    def _get_visible_ticket(self, actor: User, ticket_id: uuid.UUID) -> Ticket:
        """读取 active Ticket 并执行资源级可见性检查。by AI.Coding"""
        ticket = self.ticket_repository.get_active_by_id(ticket_id)
        if ticket is None:
            raise NotFoundError(ErrorCode.TICKET_NOT_FOUND)
        if not can_view_ticket(actor, ticket):
            raise ForbiddenError(ErrorCode.TICKET_FORBIDDEN)
        return ticket

    def _get_locked_active_ticket(self, ticket_id: uuid.UUID) -> Ticket:
        """锁定 active Ticket 供负责人变更事务使用。by AI.Coding"""
        ticket = self.ticket_repository.get_active_by_id(ticket_id, for_update=True)
        if ticket is None:
            raise NotFoundError(ErrorCode.TICKET_NOT_FOUND)
        return ticket

    @staticmethod
    def _ensure_ticket_open_for_assignment(ticket: Ticket) -> None:
        """拒绝 CLOSED 工单的任何负责人变更。by AI.Coding"""
        if ticket.status is TicketStatus.CLOSED:
            raise ConflictError(ErrorCode.TICKET_CLOSED)

    @staticmethod
    def _ensure_ticket_writable(ticket: Ticket) -> None:
        """拒绝 CLOSED 工单的普通业务写入。by AI.Coding"""
        if ticket.status is TicketStatus.CLOSED:
            raise ConflictError(ErrorCode.TICKET_CLOSED)

    @staticmethod
    def _require_admin(actor: User) -> None:
        """限制负责人管理能力仅对 Admin 开放。by AI.Coding"""
        if actor.role is not UserRole.ADMIN:
            raise ForbiddenError(ErrorCode.ROLE_FORBIDDEN)

    @staticmethod
    def _assignment_audit(
        *,
        ticket: Ticket,
        actor: User,
        action: TicketAuditAction,
        old_assignee_id: uuid.UUID | None,
        old_status: TicketStatus,
    ) -> TicketAuditLog:
        """创建负责人和状态的结构化前后快照审计。by AI.Coding"""
        return TicketAuditLog(
            ticket_id=ticket.id,
            actor_id=actor.id,
            action=action,
            old_value={
                "assignee_id": (
                    str(old_assignee_id) if old_assignee_id is not None else None
                ),
                "status": old_status.value,
            },
            new_value={
                "assignee_id": (
                    str(ticket.assignee_id) if ticket.assignee_id is not None else None
                ),
                "status": ticket.status.value,
            },
        )

    @staticmethod
    def _status_audit(
        *, ticket: Ticket, actor: User, old_status: TicketStatus
    ) -> TicketAuditLog:
        """创建状态变化的结构化前后快照审计。by AI.Coding"""
        return TicketAuditLog(
            ticket_id=ticket.id,
            actor_id=actor.id,
            action=TicketAuditAction.STATUS_CHANGED,
            old_value={"status": old_status.value},
            new_value={"status": ticket.status.value},
        )

    @staticmethod
    def _attribute_audits(
        *, ticket: Ticket, actor: User, payload: TicketAttributesUpdate
    ) -> list[TicketAuditLog]:
        """应用优先级和分类变化，并返回对应结构化审计。by AI.Coding"""
        audits: list[TicketAuditLog] = []
        if payload.priority is not None and payload.priority is not ticket.priority:
            old_priority = ticket.priority
            ticket.priority = payload.priority
            audits.append(
                TicketAuditLog(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    action=TicketAuditAction.PRIORITY_CHANGED,
                    old_value={"priority": old_priority.value},
                    new_value={"priority": ticket.priority.value},
                )
            )
        if payload.category is not None and payload.category is not ticket.category:
            old_category = ticket.category
            ticket.category = payload.category
            audits.append(
                TicketAuditLog(
                    ticket_id=ticket.id,
                    actor_id=actor.id,
                    action=TicketAuditAction.CATEGORY_CHANGED,
                    old_value={"category": old_category.value},
                    new_value={"category": ticket.category.value},
                )
            )
        return audits

    def _write(
        self,
        operation: Callable[[], ResultType],
        *,
        refresh: bool,
    ) -> ResultType:
        """执行单次 Ticket 写事务并在所有失败路径统一回滚。by AI.Coding"""
        try:
            result = operation()
            self.session.flush()
            self.session.commit()
            if refresh:
                self.session.refresh(result)
            return result
        except AppError:
            self.session.rollback()
            raise
        except Exception:
            self.session.rollback()
            raise
