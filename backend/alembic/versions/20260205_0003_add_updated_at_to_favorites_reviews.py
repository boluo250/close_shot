"""add updated_at to favorites/reviews

Revision ID: 20260205_0003
Revises: 20260204_0002
Create Date: 2026-02-05

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260205_0003"
down_revision = "20260204_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 与 SQLAlchemy 模型的 TimestampMixin 对齐（favorites/reviews 之前缺 updated_at）
    op.add_column(
        "favorites",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("reviews", "updated_at")
    op.drop_column("favorites", "updated_at")

