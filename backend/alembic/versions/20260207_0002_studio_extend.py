"""studio extend

Revision ID: 20260207_0002
Revises: 20260204_0001
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260207_0002"
down_revision = "20260204_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("photographers", sa.Column("cover_url", sa.String(length=512), nullable=True))

    op.add_column("portfolio_items", sa.Column("image_object_key", sa.String(length=512), nullable=True))
    op.add_column("portfolio_items", sa.Column("watermark_url", sa.String(length=512), nullable=True))
    op.add_column("portfolio_items", sa.Column("watermark_object_key", sa.String(length=512), nullable=True))
    op.add_column(
        "portfolio_items", sa.Column("category", sa.String(length=64), nullable=False, server_default="")
    )
    op.add_column(
        "portfolio_items", sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false"))
    )

    op.create_table(
        "schedule_blocks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("photographer_id", sa.BigInteger(), sa.ForeignKey("photographers.id", ondelete="CASCADE")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.UniqueConstraint("photographer_id", "date", name="uq_schedule_photographer_date"),
    )
    op.create_index("ix_schedule_blocks_photographer_id", "schedule_blocks", ["photographer_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_blocks_photographer_id", table_name="schedule_blocks")
    op.drop_table("schedule_blocks")

    op.drop_column("portfolio_items", "is_pinned")
    op.drop_column("portfolio_items", "category")
    op.drop_column("portfolio_items", "watermark_object_key")
    op.drop_column("portfolio_items", "watermark_url")
    op.drop_column("portfolio_items", "image_object_key")

    op.drop_column("photographers", "cover_url")
