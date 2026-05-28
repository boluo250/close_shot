"""add appointment requests and bind reviews to appointments

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260527_0002"
down_revision = "20260527_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_requests",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("photographer_id", sa.BigInteger(), nullable=False),
        sa.Column("package_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("contact_phone", sa.String(length=20), nullable=True),
        sa.Column("shooting_type", sa.String(length=64), nullable=True),
        sa.Column("budget_cents", sa.Integer(), nullable=True),
        sa.Column("participant_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("photographer_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["packages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["photographer_id"], ["photographers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_requests_customer_user_id", "appointment_requests", ["customer_user_id"])
    op.create_index("ix_appointment_requests_photographer_id", "appointment_requests", ["photographer_id"])
    op.create_index("ix_appointment_requests_status", "appointment_requests", ["status"])
    op.create_index("ix_appointment_requests_scheduled_at", "appointment_requests", ["scheduled_at"])

    op.add_column("reviews", sa.Column("appointment_request_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_reviews_appointment_request_id_appointment_requests",
        "reviews",
        "appointment_requests",
        ["appointment_request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_reviews_appointment_request_id", "reviews", ["appointment_request_id"])
    op.create_unique_constraint("uq_reviews_appointment_request_id", "reviews", ["appointment_request_id"])

    op.alter_column("appointment_requests", "participant_count", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_reviews_appointment_request_id", "reviews", type_="unique")
    op.drop_index("ix_reviews_appointment_request_id", table_name="reviews")
    op.drop_constraint("fk_reviews_appointment_request_id_appointment_requests", "reviews", type_="foreignkey")
    op.drop_column("reviews", "appointment_request_id")

    op.drop_index("ix_appointment_requests_scheduled_at", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_status", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_photographer_id", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_customer_user_id", table_name="appointment_requests")
    op.drop_table("appointment_requests")
