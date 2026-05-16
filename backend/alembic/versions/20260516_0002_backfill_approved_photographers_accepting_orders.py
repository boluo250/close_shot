"""backfill approved photographers accepting orders

Revision ID: 20260516_0002
Revises: 20260513_0001
Create Date: 2026-05-16

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260516_0002"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE photographers
            SET is_online = TRUE
            WHERE status = 'approved'
              AND is_online = FALSE
              AND lat IS NOT NULL
              AND lng IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    # Data backfill only: do not auto-disable accepting orders during downgrade.
    pass
