"""add admin operation logs and security defaults

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260307_0002"
down_revision = "20260307_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_operation_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("query_string", sa.Text(), nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("request_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_operation_logs_admin_user_id", "admin_operation_logs", ["admin_user_id"])
    op.create_index("ix_admin_operation_logs_username", "admin_operation_logs", ["username"])
    op.create_index("ix_admin_operation_logs_path", "admin_operation_logs", ["path"])
    op.alter_column("admin_operation_logs", "query_string", server_default=None)
    op.alter_column("admin_operation_logs", "request_body", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_admin_operation_logs_path", table_name="admin_operation_logs")
    op.drop_index("ix_admin_operation_logs_username", table_name="admin_operation_logs")
    op.drop_index("ix_admin_operation_logs_admin_user_id", table_name="admin_operation_logs")
    op.drop_table("admin_operation_logs")

