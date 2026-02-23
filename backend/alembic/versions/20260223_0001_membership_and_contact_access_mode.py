"""add membership fields and app settings

Revision ID: 20260223_0001
Revises: 20260219_0002
Create Date: 2026-02-23

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260223_0001"
down_revision = "20260219_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_member", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("member_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "is_member", server_default=None)

    op.create_table(
        "app_settings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.execute(
        sa.text(
            "INSERT INTO app_settings(key, value) VALUES (:k, :v)"
        ).bindparams(k="contact_access_mode", v="all")
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("users", "member_expires_at")
    op.drop_column("users", "is_member")
