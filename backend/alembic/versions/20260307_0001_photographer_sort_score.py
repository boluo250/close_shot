"""add photographer quality_score and sort_score

Revision ID: 20260307_0001
Revises: 20260223_0002
Create Date: 2026-03-07

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260307_0001"
down_revision = "20260223_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photographers",
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="5"),
    )
    op.add_column(
        "photographers",
        sa.Column("sort_score", sa.Float(), nullable=False, server_default="50"),
    )
    op.create_index("ix_photographers_sort_score", "photographers", ["sort_score"])
    op.alter_column("photographers", "quality_score", server_default=None)
    op.alter_column("photographers", "sort_score", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_photographers_sort_score", table_name="photographers")
    op.drop_column("photographers", "sort_score")
    op.drop_column("photographers", "quality_score")
