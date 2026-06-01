"""expand appointment status column length

Revision ID: 20260601_0001
Revises: 20260528_0001
Create Date: 2026-06-01

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260601_0001"
down_revision = "20260528_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "appointment_requests",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "appointment_requests",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
