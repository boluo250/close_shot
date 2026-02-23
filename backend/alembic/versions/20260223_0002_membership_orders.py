"""add membership orders table

Revision ID: 20260223_0002
Revises: 20260223_0001
Create Date: 2026-02-23

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260223_0002"
down_revision = "20260223_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership_orders",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="wechat_mini"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("out_trade_no", sa.String(length=64), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("notify_raw_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("out_trade_no"),
    )
    op.create_index("ix_membership_orders_user_id", "membership_orders", ["user_id"])
    op.create_index("ix_membership_orders_status", "membership_orders", ["status"])
    op.alter_column("membership_orders", "channel", server_default=None)
    op.alter_column("membership_orders", "status", server_default=None)
    op.alter_column("membership_orders", "notify_raw_json", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_membership_orders_status", table_name="membership_orders")
    op.drop_index("ix_membership_orders_user_id", table_name="membership_orders")
    op.drop_table("membership_orders")
