"""add photographer pending submission snapshot

Revision ID: 20260522_0001
Revises: 20260520_0001
Create Date: 2026-05-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260522_0001"
down_revision = "20260520_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("photographers", sa.Column("pending_submission_json", sa.Text(), nullable=True))
    op.add_column("photographers", sa.Column("pending_submission_submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("photographers", sa.Column("pending_reject_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("photographers", "pending_reject_reason")
    op.drop_column("photographers", "pending_submission_submitted_at")
    op.drop_column("photographers", "pending_submission_json")
