"""init

Revision ID: 20260204_0001
Revises: 
Create Date: 2026-02-04

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260204_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("wechat_openid", sa.String(length=64), nullable=True, unique=True),
        sa.Column("username", sa.String(length=64), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
    )

    op.create_table(
        "photographers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("service_radius_m", sa.Integer(), nullable=False, server_default="5000"),
    )

    op.create_index("ix_photographers_lat_lng", "photographers", ["lat", "lng"])

    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("photographer_id", sa.BigInteger(), sa.ForeignKey("photographers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_portfolio_items_photographer_id", "portfolio_items", ["photographer_id"])

    op.create_table(
        "packages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("photographer_id", sa.BigInteger(), sa.ForeignKey("photographers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_packages_photographer_id", "packages", ["photographer_id"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photographer_id", sa.BigInteger(), sa.ForeignKey("photographers.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "photographer_id", name="uq_favorites_user_photographer"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("photographer_id", sa.BigInteger(), sa.ForeignKey("photographers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.create_index("ix_reviews_photographer_id", "reviews", ["photographer_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("favorites")
    op.drop_table("packages")
    op.drop_table("portfolio_items")
    op.drop_index("ix_photographers_lat_lng", table_name="photographers")
    op.drop_table("photographers")
    op.drop_table("users")

