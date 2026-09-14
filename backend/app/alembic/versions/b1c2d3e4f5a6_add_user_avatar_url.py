"""add user avatar url

Revision ID: b1c2d3e4f5a6
Revises: a91d2f4c6b8e
Create Date: 2026-09-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a91d2f4c6b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为用户资料增加可选头像 URL。by AI.Coding"""
    op.add_column(
        "user",
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    """移除用户头像 URL 字段。by AI.Coding"""
    op.drop_column("user", "avatar_url")
