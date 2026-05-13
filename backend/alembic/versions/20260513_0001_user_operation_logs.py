"""add user operation logs

Revision ID: 20260513_0001
Revises: 20260307_0002
Create Date: 2026-05-13

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260513_0001"
down_revision = "20260307_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_operation_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(length=128), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("action_label", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("query_string", sa.Text(), nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("request_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_operation_logs_user_id", "user_operation_logs", ["user_id"])
    op.create_index("ix_user_operation_logs_actor_name", "user_operation_logs", ["actor_name"])
    op.create_index("ix_user_operation_logs_actor_role", "user_operation_logs", ["actor_role"])
    op.create_index("ix_user_operation_logs_channel", "user_operation_logs", ["channel"])
    op.create_index("ix_user_operation_logs_action", "user_operation_logs", ["action"])
    op.create_index("ix_user_operation_logs_resource_type", "user_operation_logs", ["resource_type"])
    op.create_index("ix_user_operation_logs_resource_id", "user_operation_logs", ["resource_id"])
    op.create_index("ix_user_operation_logs_path", "user_operation_logs", ["path"])
    op.alter_column("user_operation_logs", "query_string", server_default=None)
    op.alter_column("user_operation_logs", "request_body", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_user_operation_logs_path", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_resource_id", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_resource_type", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_action", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_channel", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_actor_role", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_actor_name", table_name="user_operation_logs")
    op.drop_index("ix_user_operation_logs_user_id", table_name="user_operation_logs")
    op.drop_table("user_operation_logs")
