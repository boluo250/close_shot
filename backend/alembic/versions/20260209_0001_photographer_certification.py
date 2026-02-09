"""add photographer certification fields

Revision ID: 20260209_0001
Revises: 22704c88860c
Create Date: 2026-02-09

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260209_0001"
down_revision = "22704c88860c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: 实名认证字段
    op.add_column("photographers", sa.Column("real_name", sa.String(64), nullable=True))
    op.add_column("photographers", sa.Column("id_card_number", sa.String(18), nullable=True))
    op.add_column("photographers", sa.Column("id_card_front_url", sa.String(512), nullable=True))
    op.add_column("photographers", sa.Column("id_card_back_url", sa.String(512), nullable=True))

    # Step 2: 摄影师身份字段
    op.add_column(
        "photographers",
        sa.Column("shooting_types", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("photographers", sa.Column("experience_years", sa.String(16), nullable=True))
    op.add_column("photographers", sa.Column("portfolio_link", sa.String(512), nullable=True))

    # Step 3: 联系方式
    op.add_column("photographers", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("photographers", sa.Column("wechat_id", sa.String(64), nullable=True))

    # 可选字段
    op.add_column("photographers", sa.Column("price_range", sa.String(32), nullable=True))

    # 认证等级
    op.add_column(
        "photographers",
        sa.Column("certification_level", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("photographers", "certification_level")
    op.drop_column("photographers", "price_range")
    op.drop_column("photographers", "wechat_id")
    op.drop_column("photographers", "phone")
    op.drop_column("photographers", "portfolio_link")
    op.drop_column("photographers", "experience_years")
    op.drop_column("photographers", "shooting_types")
    op.drop_column("photographers", "id_card_back_url")
    op.drop_column("photographers", "id_card_front_url")
    op.drop_column("photographers", "id_card_number")
    op.drop_column("photographers", "real_name")
