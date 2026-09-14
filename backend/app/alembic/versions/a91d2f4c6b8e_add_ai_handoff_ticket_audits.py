"""add ai handoff ticket audits

Revision ID: a91d2f4c6b8e
Revises: c8e4f1a7d2b9
Create Date: 2026-09-14 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


revision: str = "a91d2f4c6b8e"
down_revision: str | None = "f2b7c4d9e6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 AI 转人工工单补充审计动作枚举。by AI.Coding"""
    op.execute(
        "ALTER TYPE ticket_audit_action ADD VALUE IF NOT EXISTS 'AI_HANDOFF_CREATED'"
    )
    op.execute("ALTER TYPE ticket_audit_action ADD VALUE IF NOT EXISTS 'AUTO_ASSIGNED'")


def downgrade() -> None:
    """PostgreSQL 枚举值无法安全回滚，保留空降级。by AI.Coding"""
