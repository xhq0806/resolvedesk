"""为 D-B03 迁移测试创建隔离 PostgreSQL 数据库。by AI.Coding"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

TEST_DATABASE_PREFIX = "resolvedesk_migration_test_"


def _maintenance_url() -> str:
    """读取显式维护库地址，或从应用地址安全派生 postgres 库。by AI.Coding"""
    configured_url = os.getenv("MIGRATION_TEST_ADMIN_URL")
    if configured_url:
        return configured_url.replace("postgresql+psycopg://", "postgresql://", 1)

    application_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:changethis@localhost:5432/app"
    ).replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(application_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/postgres", "", ""))


def _database_url(maintenance_url: str, database_name: str) -> str:
    """从维护库连接串派生指定临时数据库连接串。by AI.Coding"""
    parsed = urlsplit(maintenance_url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, "")
    )


@pytest.fixture
def migration_database_url() -> Generator[str]:
    """为单个迁移场景创建并最终删除独立临时数据库。by AI.Coding"""
    maintenance_url = _maintenance_url()
    database_name = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex}"

    try:
        with psycopg.connect(
            maintenance_url, autocommit=True, connect_timeout=3
        ) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )
    except psycopg.Error as exc:
        pytest.skip(f"PostgreSQL 迁移测试环境不可用：{exc}")

    try:
        yield _database_url(maintenance_url, database_name)
    finally:
        # 仅允许清理本 fixture 创建且带固定前缀的数据库。
        if not database_name.startswith(TEST_DATABASE_PREFIX):
            raise RuntimeError("拒绝删除非迁移测试数据库。")
        with psycopg.connect(
            maintenance_url, autocommit=True, connect_timeout=3
        ) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )
