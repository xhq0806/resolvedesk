"""以角色与工单平台替换模板 Item 数据结构。by AI.Coding

Revision ID: 7d8f3a1c2b4e
Revises: fe56fa70289e
Create Date: 2026-08-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7d8f3a1c2b4e"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None

USER_ROLE_VALUES = ("CUSTOMER", "AGENT", "ADMIN")
TICKET_STATUS_VALUES = (
    "OPEN",
    "IN_PROGRESS",
    "WAITING_FOR_CUSTOMER",
    "RESOLVED",
    "CLOSED",
)
TICKET_PRIORITY_VALUES = ("LOW", "MEDIUM", "HIGH", "URGENT")
TICKET_CATEGORY_VALUES = (
    "ACCOUNT",
    "BILLING",
    "PRODUCT",
    "BUG",
    "FEATURE_REQUEST",
    "OTHER",
)
TICKET_MESSAGE_TYPE_VALUES = ("PUBLIC_REPLY", "INTERNAL_NOTE")
TICKET_AUDIT_ACTION_VALUES = (
    "TAKEN",
    "ASSIGNED",
    "REASSIGNED",
    "UNASSIGNED",
    "STATUS_CHANGED",
    "PRIORITY_CHANGED",
    "CATEGORY_CHANGED",
    "DELETED",
)

user_role = postgresql.ENUM(*USER_ROLE_VALUES, name="user_role", create_type=False)
ticket_status = postgresql.ENUM(
    *TICKET_STATUS_VALUES, name="ticket_status", create_type=False
)
ticket_priority = postgresql.ENUM(
    *TICKET_PRIORITY_VALUES, name="ticket_priority", create_type=False
)
ticket_category = postgresql.ENUM(
    *TICKET_CATEGORY_VALUES, name="ticket_category", create_type=False
)
ticket_message_type = postgresql.ENUM(
    *TICKET_MESSAGE_TYPE_VALUES, name="ticket_message_type", create_type=False
)
ticket_audit_action = postgresql.ENUM(
    *TICKET_AUDIT_ACTION_VALUES, name="ticket_audit_action", create_type=False
)

ENUM_TYPES = (
    user_role,
    ticket_status,
    ticket_priority,
    ticket_category,
    ticket_message_type,
    ticket_audit_action,
)


def _create_enum_types() -> None:
    """按依赖顺序创建本次迁移使用的 PostgreSQL 枚举。by AI.Coding"""
    bind = op.get_bind()
    for enum_type in ENUM_TYPES:
        enum_type.create(bind, checkfirst=False)


def _drop_enum_types() -> None:
    """在所有引用对象删除后逆序删除 PostgreSQL 枚举。by AI.Coding"""
    bind = op.get_bind()
    for enum_type in reversed(ENUM_TYPES):
        enum_type.drop(bind, checkfirst=False)


def _backfill_and_validate_roles() -> None:
    """回填历史角色，并阻止无活跃管理员的既有数据库升级。by AI.Coding"""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE "user"
            SET role = CASE
                WHEN is_superuser IS TRUE THEN 'ADMIN'::user_role
                ELSE 'CUSTOMER'::user_role
            END
            """
        )
    )

    null_role_count = bind.execute(
        sa.text('SELECT count(*) FROM "user" WHERE role IS NULL')
    ).scalar_one()
    if null_role_count:
        raise RuntimeError("角色回填失败：仍存在未分配角色的历史用户。")

    user_count = bind.execute(sa.text('SELECT count(*) FROM "user"')).scalar_one()
    active_admin_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM "user"
            WHERE is_active IS TRUE AND role = 'ADMIN'::user_role
            """
        )
    ).scalar_one()

    # 空库由紧随迁移执行的 initial_data 创建首个 Admin；既有库必须先修复管理员。
    if user_count > 0 and active_admin_count == 0:
        raise RuntimeError(
            "迁移已中止：既有用户中没有活跃管理员，请在旧版本中激活或创建超级管理员后重试。"
        )


def upgrade() -> None:
    """迁移角色并建立完整工单领域数据库结构。by AI.Coding"""
    _create_enum_types()

    op.add_column("user", sa.Column("role", user_role, nullable=True))
    _backfill_and_validate_roles()
    op.alter_column(
        "user",
        "role",
        existing_type=user_role,
        nullable=False,
        server_default=sa.text("'CUSTOMER'::user_role"),
    )
    op.create_index("ix_user_role_active", "user", ["role", "is_active"])

    op.create_table(
        "ticket",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            ticket_status,
            server_default=sa.text("'OPEN'::ticket_status"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            ticket_priority,
            server_default=sa.text("'MEDIUM'::ticket_priority"),
            nullable=False,
        ),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_ticket_ticket_number", "ticket", ["ticket_number"], unique=True
    )
    op.create_index(
        "ix_ticket_requester_updated",
        "ticket",
        ["requester_id", "deleted_at", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_ticket_assignee_updated",
        "ticket",
        ["assignee_id", "deleted_at", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_ticket_queue_updated",
        "ticket",
        ["assignee_id", "status", "deleted_at", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_ticket_filter",
        "ticket",
        ["status", "priority", "category", "deleted_at"],
    )
    for column_name in (
        "status",
        "priority",
        "category",
        "requester_id",
        "assignee_id",
        "updated_at",
        "deleted_at",
    ):
        op.create_index(f"ix_ticket_{column_name}", "ticket", [column_name])

    op.create_table(
        "ticket_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_type", ticket_message_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["ticket.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_message_timeline",
        "ticket_message",
        ["ticket_id", sa.text("created_at ASC")],
    )
    for column_name in ("ticket_id", "message_type", "created_at"):
        op.create_index(
            f"ix_ticket_message_{column_name}", "ticket_message", [column_name]
        )

    op.create_table(
        "ticket_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", ticket_audit_action, nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["ticket.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_audit_timeline",
        "ticket_audit_log",
        ["ticket_id", sa.text("created_at ASC")],
    )
    for column_name in ("ticket_id", "action", "created_at"):
        op.create_index(
            f"ix_ticket_audit_log_{column_name}",
            "ticket_audit_log",
            [column_name],
        )

    # 先保证新权限与工单结构完整，再移除旧业务结构。
    op.drop_table("item")
    op.drop_column("user", "is_superuser")


def downgrade() -> None:
    """恢复旧权限结构并有损删除全部工单领域数据。by AI.Coding"""
    op.add_column(
        "user",
        sa.Column(
            "is_superuser", sa.Boolean(), server_default=sa.false(), nullable=True
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET is_superuser = (role = 'ADMIN'::user_role)
            """
        )
    )
    op.alter_column(
        "user",
        "is_superuser",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )

    # Downgrade 仅恢复空的模板 Item 表，不从 Ticket 反向生成示例数据。
    op.create_table(
        "item",
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("ticket_audit_log")
    op.drop_table("ticket_message")
    op.drop_table("ticket")
    op.drop_index("ix_user_role_active", table_name="user")
    op.drop_column("user", "role")
    _drop_enum_types()
