"""add system monitor events

Revision ID: 20260527_0001
Revises: 20260522_0001
Create Date: 2026-05-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260527_0001"
down_revision = "20260522_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_monitor_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("monitor_key", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="firing"),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_monitor_events_monitor_key", "system_monitor_events", ["monitor_key"])
    op.create_index("ix_system_monitor_events_severity", "system_monitor_events", ["severity"])
    op.create_index("ix_system_monitor_events_status", "system_monitor_events", ["status"])
    op.create_index("ix_system_monitor_events_source", "system_monitor_events", ["source"])
    op.alter_column("system_monitor_events", "message", server_default=None)
    op.alter_column("system_monitor_events", "detail_json", server_default=None)
    op.alter_column("system_monitor_events", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_system_monitor_events_source", table_name="system_monitor_events")
    op.drop_index("ix_system_monitor_events_status", table_name="system_monitor_events")
    op.drop_index("ix_system_monitor_events_severity", table_name="system_monitor_events")
    op.drop_index("ix_system_monitor_events_monitor_key", table_name="system_monitor_events")
    op.drop_table("system_monitor_events")
