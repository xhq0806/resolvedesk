"""验证角色回填、Ticket 建表与 Item 退出迁移。by AI.Coding"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

BACKEND_DIR = Path(__file__).resolve().parents[2]
OLD_HEAD = "fe56fa70289e"
NEW_HEAD = "7d8f3a1c2b4e"


def run_alembic(
    database_url: str, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """在独立进程中运行 Alembic，避免 Settings 缓存污染连接。by AI.Coding"""
    environment = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=BACKEND_DIR,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def insert_legacy_user(
    database_url: str,
    *,
    email: str,
    is_active: bool,
    is_superuser: bool,
) -> uuid.UUID:
    """向旧 head 插入用于角色回填的历史用户。by AI.Coding"""
    user_id = uuid.uuid4()
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO "user" (
                id, email, is_active, is_superuser, full_name, hashed_password
            )
            VALUES (%s, %s, %s, %s, NULL, %s)
            """,
            (user_id, email, is_active, is_superuser, "legacy-hash"),
        )
        conn.commit()
    return user_id


def test_upgrade_backfills_roles_and_replaces_items(
    migration_database_url: str,
) -> None:
    """合法旧库升级后应完成角色回填、工单建表和 Item 退出。by AI.Coding"""
    run_alembic(migration_database_url, "upgrade", OLD_HEAD)
    admin_id = insert_legacy_user(
        migration_database_url,
        email="admin@example.com",
        is_active=True,
        is_superuser=True,
    )
    customer_id = insert_legacy_user(
        migration_database_url,
        email="customer@example.com",
        is_active=True,
        is_superuser=False,
    )
    with psycopg.connect(migration_database_url) as conn:
        conn.execute(
            """
            INSERT INTO item (id, title, description, owner_id)
            VALUES (%s, %s, %s, %s)
            """,
            (uuid.uuid4(), "Legacy Item", "Removed by migration", customer_id),
        )
        conn.commit()

    run_alembic(migration_database_url, "upgrade", "head")

    with psycopg.connect(migration_database_url, row_factory=dict_row) as conn:
        roles = {
            row["id"]: row["role"]
            for row in conn.execute('SELECT id, role FROM "user"').fetchall()
        }
        tables = {
            row["tablename"]
            for row in conn.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        enum_names = {
            row["typname"]
            for row in conn.execute(
                """
                SELECT typname
                FROM pg_type
                WHERE typname = ANY(%s)
                """,
                (
                    [
                        "user_role",
                        "ticket_status",
                        "ticket_priority",
                        "ticket_category",
                        "ticket_message_type",
                        "ticket_audit_action",
                    ],
                ),
            ).fetchall()
        }
        user_columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'user'
                """
            ).fetchall()
        }
        indexes = {
            row["indexname"]
            for row in conn.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }

    assert roles[admin_id] == "ADMIN"
    assert roles[customer_id] == "CUSTOMER"
    assert {"ticket", "ticket_message", "ticket_audit_log"}.issubset(tables)
    assert "item" not in tables
    assert "role" in user_columns
    assert "is_superuser" not in user_columns
    assert enum_names == {
        "user_role",
        "ticket_status",
        "ticket_priority",
        "ticket_category",
        "ticket_message_type",
        "ticket_audit_action",
    }
    assert {
        "ix_user_role_active",
        "ux_ticket_ticket_number",
        "ix_ticket_requester_updated",
        "ix_ticket_assignee_updated",
        "ix_ticket_queue_updated",
        "ix_ticket_filter",
        "ix_ticket_message_timeline",
        "ix_ticket_audit_timeline",
    }.issubset(indexes)
    assert (
        run_alembic(migration_database_url, "current")
        .stdout.strip()
        .endswith(f"{NEW_HEAD} (head)")
    )


@pytest.mark.parametrize(
    ("is_active", "is_superuser"),
    [(True, False), (False, True)],
)
def test_upgrade_rejects_existing_database_without_active_admin(
    migration_database_url: str,
    is_active: bool,
    is_superuser: bool,
) -> None:
    """既有用户没有活跃 Admin 时迁移应失败且保留旧结构。by AI.Coding"""
    run_alembic(migration_database_url, "upgrade", OLD_HEAD)
    insert_legacy_user(
        migration_database_url,
        email="blocked@example.com",
        is_active=is_active,
        is_superuser=is_superuser,
    )

    result = run_alembic(migration_database_url, "upgrade", "head", check=False)

    assert result.returncode != 0
    assert "没有活跃管理员" in result.stderr
    with psycopg.connect(migration_database_url) as conn:
        current_revision = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        user_columns = {
            row[0]
            for row in conn.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'user'
                """
            ).fetchall()
        }

    assert current_revision == OLD_HEAD
    assert "item" in tables
    assert "ticket" not in tables
    assert "is_superuser" in user_columns
    assert "role" not in user_columns


def test_empty_database_can_bootstrap_and_downgrade_round_trip(
    migration_database_url: str,
) -> None:
    """空库可引导升级，且 downgrade 后可再次升级而无残留对象。by AI.Coding"""
    run_alembic(migration_database_url, "upgrade", "head")
    with psycopg.connect(migration_database_url) as conn:
        admin_id = uuid.uuid4()
        conn.execute(
            """
            INSERT INTO "user" (
                id, email, is_active, role, full_name, hashed_password
            )
            VALUES (%s, %s, TRUE, 'ADMIN', NULL, %s)
            """,
            (admin_id, "bootstrap@example.com", "bootstrap-hash"),
        )
        conn.commit()

    run_alembic(migration_database_url, "downgrade", OLD_HEAD)

    with psycopg.connect(migration_database_url) as conn:
        restored = conn.execute(
            'SELECT is_superuser FROM "user" WHERE id = %s', (admin_id,)
        ).fetchone()[0]
        item_count = conn.execute("SELECT count(*) FROM item").fetchone()[0]
        ticket_table = conn.execute("SELECT to_regclass('public.ticket')").fetchone()[0]
        role_type = conn.execute("SELECT to_regtype('public.user_role')").fetchone()[0]

    assert restored is True
    assert item_count == 0
    assert ticket_table is None
    assert role_type is None

    run_alembic(migration_database_url, "upgrade", "head")
    assert (
        run_alembic(migration_database_url, "current")
        .stdout.strip()
        .endswith(f"{NEW_HEAD} (head)")
    )
