"""add photographer last_active_at

Revision ID: 20260204_0002
Revises: 20260204_0001
Create Date: 2026-02-04

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260204_0002"
down_revision = "20260204_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photographers",
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_photographers_last_active_at", "photographers", ["last_active_at"])


def downgrade() -> None:
    op.drop_index("ix_photographers_last_active_at", table_name="photographers")
    op.drop_column("photographers", "last_active_at")

