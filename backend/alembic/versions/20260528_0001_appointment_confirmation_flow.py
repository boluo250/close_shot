"""appointment confirmation flow fields and status backfill

Revision ID: 20260528_0001
Revises: 20260527_0002
Create Date: 2026-05-28

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260528_0001"
down_revision = "20260527_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointment_requests", sa.Column("customer_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointment_requests", sa.Column("contact_unlocked_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE appointment_requests
            SET status = 'confirmed',
                customer_confirmed_at = COALESCE(customer_confirmed_at, accepted_at, created_at),
                contact_unlocked_at = COALESCE(contact_unlocked_at, accepted_at, created_at)
            WHERE status = 'accepted'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("appointment_requests", "contact_unlocked_at")
    op.drop_column("appointment_requests", "customer_confirmed_at")
