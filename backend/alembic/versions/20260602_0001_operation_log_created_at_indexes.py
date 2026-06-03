"""add operation log created_at indexes

Revision ID: 20260602_0001
Revises: 20260601_0001
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260602_0001"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_admin_operation_logs_created_at "
                "ON admin_operation_logs (created_at)"
            )
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_user_operation_logs_created_at "
                "ON user_operation_logs (created_at)"
            )
        return

    op.create_index("ix_admin_operation_logs_created_at", "admin_operation_logs", ["created_at"])
    op.create_index("ix_user_operation_logs_created_at", "user_operation_logs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_user_operation_logs_created_at")
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_admin_operation_logs_created_at")
        return

    op.drop_index("ix_user_operation_logs_created_at", table_name="user_operation_logs")
    op.drop_index("ix_admin_operation_logs_created_at", table_name="admin_operation_logs")
