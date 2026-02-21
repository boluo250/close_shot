"""add wechat unionid unique to users

Revision ID: 20260219_0002
Revises: 20260219_0001
Create Date: 2026-02-19

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0002"
down_revision = "20260219_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("wechat_unionid", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_users_wechat_unionid", "users", ["wechat_unionid"])


def downgrade() -> None:
    op.drop_constraint("uq_users_wechat_unionid", "users", type_="unique")
    op.drop_column("users", "wechat_unionid")
