"""建立多租户 Workspace 基础并回填一期业务。by AI.Coding

Revision ID: a2c4e6f8b0d1
Revises: 7d8f3a1c2b4e
Create Date: 2026-09-11
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a2c4e6f8b0d1"
down_revision = "7d8f3a1c2b4e"
branch_labels = None
depends_on = None

WORKSPACE_STATUS = postgresql.ENUM(
    "ACTIVE", "SUSPENDED", name="workspace_status", create_type=False
)
WORKSPACE_ROLE = postgresql.ENUM(
    "OWNER", "ADMIN", "AGENT", "CUSTOMER", name="workspace_role", create_type=False
)
MEMBERSHIP_STATUS = postgresql.ENUM(
    "ACTIVE", "REMOVED", name="membership_status", create_type=False
)
AI_AGENT_STATUS = postgresql.ENUM(
    "ACTIVE", "DISABLED", name="ai_agent_status", create_type=False
)


def _create_enum_types() -> None:
    """按表依赖顺序创建 Workspace 基础枚举。by AI.Coding"""
    bind = op.get_bind()
    for enum_type in (
        WORKSPACE_STATUS,
        WORKSPACE_ROLE,
        MEMBERSHIP_STATUS,
        AI_AGENT_STATUS,
    ):
        enum_type.create(bind, checkfirst=True)


def _drop_enum_types() -> None:
    """在表删除后逆序清理 Workspace 枚举。by AI.Coding"""
    bind = op.get_bind()
    for enum_type in (
        AI_AGENT_STATUS,
        MEMBERSHIP_STATUS,
        WORKSPACE_ROLE,
        WORKSPACE_STATUS,
    ):
        enum_type.drop(bind, checkfirst=True)


def _create_workspace_tables() -> None:
    """创建租户、成员、邀请和 AI Agent 基础表。by AI.Coding"""
    op.create_table(
        "workspace",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", WORKSPACE_STATUS, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_workspace_owner_status", "workspace", ["owner_user_id", "status"]
    )

    op.create_table(
        "workspace_member",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", WORKSPACE_ROLE, nullable=False),
        sa.Column("status", MEMBERSHIP_STATUS, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="ux_workspace_member_pair"),
    )
    op.create_index(
        "ix_workspace_member_lookup", "workspace_member", ["user_id", "status"]
    )

    op.create_table(
        "workspace_invitation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", WORKSPACE_ROLE, nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_workspace_invitation_workspace",
        "workspace_invitation",
        ["workspace_id", "expires_at"],
    )
    op.create_index("ix_workspace_invitation_email", "workspace_invitation", ["email"])

    op.create_table(
        "ai_agent",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", AI_AGENT_STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="ux_ai_agent_workspace"),
    )


def _add_workspace_columns() -> None:
    """为一期工单、消息和审计增加可回填的租户键。by AI.Coding"""
    for table_name in ("ticket", "ticket_message", "ticket_audit_log"):
        op.add_column(
            table_name,
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_{table_name}_workspace_id", table_name, ["workspace_id"])


def _backfill_default_workspace() -> None:
    """创建默认租户并把一期用户和工单全部归入该租户。by AI.Coding"""
    bind = op.get_bind()
    owner_id = bind.execute(
        sa.text(
            "SELECT id FROM \"user\" WHERE is_active IS TRUE AND role = 'ADMIN'::user_role ORDER BY created_at, id LIMIT 1"
        )
    ).scalar()
    if owner_id is None:
        owner_id = bind.execute(
            sa.text('SELECT id FROM "user" ORDER BY created_at, id LIMIT 1')
        ).scalar()
    if owner_id is None:
        # 空库会在 Alembic 完成后由 init_db 创建首个 Admin 和默认 Workspace。by AI.Coding
        return

    workspace_id = uuid.uuid4()
    bind.execute(
        sa.text(
            "INSERT INTO workspace (id, name, slug, status, owner_user_id, created_at) "
            "VALUES (:id, :name, :slug, 'ACTIVE'::workspace_status, :owner, now())"
        ),
        {
            "id": workspace_id,
            "name": "Default Workspace",
            "slug": "default",
            "owner": owner_id,
        },
    )
    users = bind.execute(sa.text('SELECT id, role FROM "user"')).fetchall()
    for user_id, role in users:
        member_role = "CUSTOMER"
        if role == "ADMIN" and user_id == owner_id:
            member_role = "OWNER"
        elif role == "ADMIN":
            member_role = "ADMIN"
        elif role == "AGENT":
            member_role = "AGENT"
        bind.execute(
            sa.text(
                "INSERT INTO workspace_member (id, workspace_id, user_id, role, status, joined_at) "
                "VALUES (:id, :workspace_id, :user_id, CAST(:role AS workspace_role), 'ACTIVE'::membership_status, now())"
            ),
            {
                "id": uuid.uuid4(),
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": member_role,
            },
        )
    for table_name in ("ticket", "ticket_message", "ticket_audit_log"):
        bind.execute(
            sa.text(f"UPDATE {table_name} SET workspace_id = :workspace_id"),
            {"workspace_id": workspace_id},
        )
    bind.execute(
        sa.text(
            "INSERT INTO ai_agent (id, workspace_id, name, status, created_at, updated_at) "
            "VALUES (:id, :workspace_id, 'ResolveDesk AI', 'ACTIVE'::ai_agent_status, now(), now())"
        ),
        {"id": uuid.uuid4(), "workspace_id": workspace_id},
    )
    for table_name in ("ticket", "ticket_message", "ticket_audit_log"):
        op.alter_column(table_name, "workspace_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_workspace_id",
            table_name,
            "workspace",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def upgrade() -> None:
    """升级 Workspace 基础结构并完成一期数据回填。by AI.Coding"""
    _create_enum_types()
    _create_workspace_tables()
    _add_workspace_columns()
    _backfill_default_workspace()


def downgrade() -> None:
    """回滚 Workspace 基础结构并移除租户键。by AI.Coding"""
    for table_name in ("ticket_audit_log", "ticket_message", "ticket"):
        # 空库升级时不会创建回填外键，因此回滚必须允许约束不存在。by AI.Coding
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" '
                f'DROP CONSTRAINT IF EXISTS "fk_{table_name}_workspace_id"'
            )
        )
        op.drop_index(f"ix_{table_name}_workspace_id", table_name=table_name)
        op.drop_column(table_name, "workspace_id")
    op.drop_table("ai_agent")
    op.drop_index("ix_workspace_invitation_email", table_name="workspace_invitation")
    op.drop_index(
        "ix_workspace_invitation_workspace", table_name="workspace_invitation"
    )
    op.drop_table("workspace_invitation")
    op.drop_index("ix_workspace_member_lookup", table_name="workspace_member")
    op.drop_table("workspace_member")
    op.drop_index("ix_workspace_owner_status", table_name="workspace")
    op.drop_table("workspace")
    _drop_enum_types()
