"""photographer status

Revision ID: 20260207_0003
Revises: 20260207_0002
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260207_0003"
down_revision = "20260207_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photographers",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="approved"),
    )
    op.add_column("photographers", sa.Column("reject_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("photographers", "reject_reason")
    op.drop_column("photographers", "status")
