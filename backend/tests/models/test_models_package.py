"""验证 D-B01 模型与 Schema 拆分边界。by AI.Coding"""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
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


def test_models_package_registers_only_current_tables() -> None:
    """模型包应注册当前表且不得提前注册 Ticket 表。by AI.Coding"""
    tables = set(SQLModel.metadata.tables)

    assert {"user", "item"}.issubset(tables)
    assert {"ticket", "ticket_message", "ticket_audit_log"}.isdisjoint(tables)


def test_package_exports_keep_models_and_schemas_separate() -> None:
    """模型包和 Schema 包不得恢复为混合导出入口。by AI.Coding"""
    assert not hasattr(app.models, "SQLModel")
    assert not hasattr(app.models, "UserCreate")
    assert hasattr(app.schemas, "UserCreate")
    assert hasattr(app.schemas, "Token")
