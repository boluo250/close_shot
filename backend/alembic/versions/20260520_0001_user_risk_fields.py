"""add user risk management fields

Revision ID: 20260520_0001
Revises: 20260516_0002
Create Date: 2026-05-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260520_0001"
down_revision = "20260516_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("trust_score", sa.Integer(), nullable=False, server_default="70"))
    op.add_column("users", sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"))
    op.add_column(
        "users",
        sa.Column("blacklist_status", sa.String(length=16), nullable=False, server_default="normal"),
    )


def downgrade() -> None:
    op.drop_column("users", "blacklist_status")
    op.drop_column("users", "risk_level")
    op.drop_column("users", "trust_score")
