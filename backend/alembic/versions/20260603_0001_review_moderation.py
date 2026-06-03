"""add review moderation status

Revision ID: 20260603_0001
Revises: 20260601_0001
Create Date: 2026-06-03

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260603_0001"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="approved"),
    )
    op.create_index("ix_reviews_status", "reviews", ["status"])


def downgrade() -> None:
    op.drop_index("ix_reviews_status", table_name="reviews")
    op.drop_column("reviews", "status")
