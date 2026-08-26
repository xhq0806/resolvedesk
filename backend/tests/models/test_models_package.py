"""验证模型、Schema 与 Ticket 持久化 metadata 边界。by AI.Coding"""

import re
import uuid
from datetime import UTC
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import JSON, DateTime, Enum, Text, inspect
from sqlalchemy.orm import configure_mappers
from sqlmodel import SQLModel

import app.models
import app.schemas
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
from app.schemas.auth import NewPassword, UpdatePassword
from app.schemas.legacy_item import ItemCreate, ItemUpdate
from app.schemas.user import UserCreate, UserRegister, UserUpdate, UserUpdateMe


def test_domain_enum_values_match_design() -> None:
    """领域枚举值应与技术设计保持完全一致。by AI.Coding"""
    expected_values = {
        UserRole: ["CUSTOMER", "AGENT", "ADMIN"],
        TicketStatus: [
            "OPEN",
            "IN_PROGRESS",
            "WAITING_FOR_CUSTOMER",
            "RESOLVED",
            "CLOSED",
        ],
        TicketPriority: ["LOW", "MEDIUM", "HIGH", "URGENT"],
        TicketCategory: [
            "ACCOUNT",
            "BILLING",
            "PRODUCT",
            "BUG",
            "FEATURE_REQUEST",
            "OTHER",
        ],
        TicketMessageType: ["PUBLIC_REPLY", "INTERNAL_NOTE"],
        TicketAuditAction: [
            "TAKEN",
            "ASSIGNED",
            "REASSIGNED",
            "UNASSIGNED",
            "STATUS_CHANGED",
            "PRIORITY_CHANGED",
            "CATEGORY_CHANGED",
            "DELETED",
        ],
    }

    # 直接比较字符串值，防止 API、数据库和前端之间发生大小写漂移。
    for enum_type, values in expected_values.items():
        assert [member.value for member in enum_type] == values
        assert all(isinstance(member, str) for member in enum_type)


@pytest.mark.parametrize(
    ("schema_type", "payload"),
    [
        (UserCreate, {"email": "user@example.com", "password": "password123"}),
        (UserRegister, {"email": "user@example.com", "password": "password123"}),
        (UserUpdate, {"full_name": "Updated User"}),
        (UserUpdateMe, {"full_name": "Updated User"}),
        (
            UpdatePassword,
            {"current_password": "password123", "new_password": "newpass123"},
        ),
        (NewPassword, {"token": "token", "new_password": "newpass123"}),
        (ItemCreate, {"title": "Item"}),
        (ItemUpdate, {"title": "Updated Item"}),
    ],
)
def test_external_input_schemas_forbid_unknown_fields(
    schema_type: type[BaseModel], payload: dict[str, Any]
) -> None:
    """外部输入 Schema 应拒绝未声明字段。by AI.Coding"""
    with pytest.raises(ValidationError):
        schema_type.model_validate({**payload, "unexpected": "value"})


def test_public_registration_rejects_privilege_fields() -> None:
    """公开注册不得静默接受角色或超级用户字段。by AI.Coding"""
    base_payload = {"email": "user@example.com", "password": "password123"}

    for privileged_payload in (
        {"role": "ADMIN"},
        {"is_superuser": True},
        {"is_active": False},
    ):
        with pytest.raises(ValidationError):
            UserRegister.model_validate({**base_payload, **privileged_payload})


def test_current_user_schema_contract_remains_compatible() -> None:
    """数据库迁移前继续保留现有用户管理字段。by AI.Coding"""
    user_create = UserCreate(
        email="admin@example.com",
        password="password123",
        is_active=True,
        is_superuser=True,
    )

    assert user_create.is_superuser is True
    assert user_create.is_active is True
    assert "role" not in UserCreate.model_fields


def test_models_package_registers_ticket_domain_tables() -> None:
    """模型包应注册当前兼容表与完整 Ticket 领域表。by AI.Coding"""
    tables = set(SQLModel.metadata.tables)

    assert {
        "user",
        "item",
        "ticket",
        "ticket_message",
        "ticket_audit_log",
    }.issubset(tables)
    assert "is_superuser" in User.model_fields
    assert "role" not in User.model_fields


def test_ticket_instances_have_expected_defaults() -> None:
    """Ticket 模型应生成稳定编号、默认枚举和 UTC 时间。by AI.Coding"""
    ticket = Ticket(
        title="Cannot sign in",
        description="The account cannot sign in.",
        category=TicketCategory.ACCOUNT,
        requester_id=uuid.uuid4(),
    )
    message = TicketMessage(
        ticket_id=ticket.id,
        author_id=uuid.uuid4(),
        message_type=TicketMessageType.PUBLIC_REPLY,
        content="We are checking this issue.",
    )
    audit = TicketAuditLog(
        ticket_id=ticket.id,
        actor_id=uuid.uuid4(),
        action=TicketAuditAction.TAKEN,
    )

    assert re.fullmatch(r"TKT-[0-9a-f]{32}", ticket.ticket_number)
    assert len(ticket.ticket_number) == 36
    assert ticket.status is TicketStatus.OPEN
    assert ticket.priority is TicketPriority.MEDIUM
    for value in (
        ticket.created_at,
        ticket.updated_at,
        message.created_at,
        audit.created_at,
    ):
        assert value.utcoffset() == UTC.utcoffset(value)


def test_ticket_domain_column_metadata_matches_design() -> None:
    """工单领域列类型、空值和枚举名称应与设计一致。by AI.Coding"""
    ticket_table = SQLModel.metadata.tables["ticket"]
    message_table = SQLModel.metadata.tables["ticket_message"]
    audit_table = SQLModel.metadata.tables["ticket_audit_log"]

    assert ticket_table.c.ticket_number.type.length == 40
    assert ticket_table.c.title.type.length == 200
    assert isinstance(ticket_table.c.description.type, Text)
    assert isinstance(message_table.c.content.type, Text)
    assert ticket_table.c.assignee_id.nullable is True
    assert ticket_table.c.deleted_at.nullable is True
    assert ticket_table.c.deleted_by_id.nullable is True
    assert audit_table.c.old_value.nullable is True
    assert audit_table.c.new_value.nullable is True
    assert isinstance(audit_table.c.old_value.type, JSON)
    assert isinstance(audit_table.c.new_value.type, JSON)

    enum_columns = {
        ticket_table.c.status: "ticket_status",
        ticket_table.c.priority: "ticket_priority",
        ticket_table.c.category: "ticket_category",
        message_table.c.message_type: "ticket_message_type",
        audit_table.c.action: "ticket_audit_action",
    }
    for column, enum_name in enum_columns.items():
        assert isinstance(column.type, Enum)
        assert column.type.native_enum is True
        assert column.type.name == enum_name

    for table_name, column_name in (
        ("ticket", "created_at"),
        ("ticket", "updated_at"),
        ("ticket", "deleted_at"),
        ("ticket_message", "created_at"),
        ("ticket_audit_log", "created_at"),
    ):
        column_type = SQLModel.metadata.tables[table_name].c[column_name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True


def test_ticket_domain_foreign_keys_are_restrictive() -> None:
    """新工单领域外键应全部显式使用 RESTRICT。by AI.Coding"""
    expected_foreign_keys = {
        ("ticket", "requester_id"): "user.id",
        ("ticket", "assignee_id"): "user.id",
        ("ticket", "deleted_by_id"): "user.id",
        ("ticket_message", "ticket_id"): "ticket.id",
        ("ticket_message", "author_id"): "user.id",
        ("ticket_audit_log", "ticket_id"): "ticket.id",
        ("ticket_audit_log", "actor_id"): "user.id",
    }

    for (table_name, column_name), target in expected_foreign_keys.items():
        foreign_keys = list(
            SQLModel.metadata.tables[table_name].c[column_name].foreign_keys
        )
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target
        assert foreign_keys[0].ondelete == "RESTRICT"


def test_ticket_domain_relationships_are_unambiguous() -> None:
    """多 User 外键关系应能完成 mapper 配置且配对正确。by AI.Coding"""
    configure_mappers()

    ticket_relationships = inspect(Ticket).relationships
    message_relationships = inspect(TicketMessage).relationships
    audit_relationships = inspect(TicketAuditLog).relationships

    assert set(ticket_relationships.keys()) == {
        "requester",
        "assignee",
        "deleted_by",
        "messages",
        "audit_logs",
    }
    assert ticket_relationships.messages.back_populates == "ticket"
    assert message_relationships.ticket.back_populates == "messages"
    assert ticket_relationships.audit_logs.back_populates == "ticket"
    assert audit_relationships.ticket.back_populates == "audit_logs"
    assert {column.name for column in ticket_relationships.requester.local_columns} == {
        "requester_id"
    }
    assert {column.name for column in ticket_relationships.assignee.local_columns} == {
        "assignee_id"
    }
    assert {
        column.name for column in ticket_relationships.deleted_by.local_columns
    } == {"deleted_by_id"}


def test_ticket_domain_named_indexes_match_design() -> None:
    """命名索引应保持设计要求的列顺序和排序方向。by AI.Coding"""
    expected_indexes = {
        "ux_ticket_ticket_number": ("ticket_number",),
        "ix_ticket_requester_updated": (
            "requester_id",
            "deleted_at",
            "updated_at DESC",
        ),
        "ix_ticket_assignee_updated": (
            "assignee_id",
            "deleted_at",
            "updated_at DESC",
        ),
        "ix_ticket_queue_updated": (
            "assignee_id",
            "status",
            "deleted_at",
            "updated_at DESC",
        ),
        "ix_ticket_filter": ("status", "priority", "category", "deleted_at"),
        "ix_ticket_message_timeline": ("ticket_id", "created_at ASC"),
        "ix_ticket_audit_timeline": ("ticket_id", "created_at ASC"),
    }
    indexes = {
        index.name: tuple(
            str(expression).split(".")[-1] for expression in index.expressions
        )
        for table_name in ("ticket", "ticket_message", "ticket_audit_log")
        for index in SQLModel.metadata.tables[table_name].indexes
        if index.name in expected_indexes
    }

    assert indexes == expected_indexes
    unique_index = next(
        index
        for index in SQLModel.metadata.tables["ticket"].indexes
        if index.name == "ux_ticket_ticket_number"
    )
    assert unique_index.unique is True


def test_package_exports_keep_models_and_schemas_separate() -> None:
    """模型包和 Schema 包不得恢复为混合导出入口。by AI.Coding"""
    assert not hasattr(app.models, "SQLModel")
    assert not hasattr(app.models, "UserCreate")
    assert hasattr(app.models, "Ticket")
    assert hasattr(app.models, "TicketMessage")
    assert hasattr(app.models, "TicketAuditLog")
    assert hasattr(app.schemas, "UserCreate")
    assert hasattr(app.schemas, "Token")
