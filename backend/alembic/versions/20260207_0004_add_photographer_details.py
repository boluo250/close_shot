"""add photographer details

Revision ID: 20260207_0004
Revises: 20260205_0003
Create Date: 2026-02-07

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260207_0004"
down_revision = "20260205_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photographers",
        sa.Column("equipment_list", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "photographers",
        sa.Column("drone_models", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "photographers",
        sa.Column("rate_card_json", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("photographers", "rate_card_json")
    op.drop_column("photographers", "drone_models")
    op.drop_column("photographers", "equipment_list")
