from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    customer = "customer"
    photographer = "photographer"
    admin = "admin"


class PhotographerStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CertificationLevel(int, enum.Enum):
    none = 0       # 未认证
    basic = 1      # Lv1 基础认证（实名 + 作品）
    advanced = 2   # Lv2 进阶认证（+ 历史订单/好评）
    premium = 3    # Lv3 优选摄影师（+ 押金/平台成交）


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.customer.value)

    wechat_openid: Mapped[str | None] = mapped_column(String(64), unique=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))

    display_name: Mapped[str | None] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(512))

    photographer: Mapped["Photographer | None"] = relationship(back_populates="user", uselist=False)


class Photographer(TimestampMixin, Base):
    __tablename__ = "photographers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    bio: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cover_url: Mapped[str | None] = mapped_column(String(512))
    # 设备清单（逗号分隔文本）
    equipment_list: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 无人机型号（逗号分隔文本）
    drone_models: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 服务报价单（JSON 文本）
    rate_card_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 接单状态（非实时在线）：映射历史列名 is_online，避免破坏已有数据库
    is_accepting_orders: Mapped[bool] = mapped_column("is_online", Boolean, nullable=False, default=False)
    # 认证状态
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PhotographerStatus.pending.value)
    # 驳回原因
    reject_reason: Mapped[str | None] = mapped_column(Text)
    # 常驻城市（用于筛选/展示）
    city: Mapped[str | None] = mapped_column(String(64))

    # ---- 认证字段 ----
    # Step 1: 实名认证
    real_name: Mapped[str | None] = mapped_column(String(64))
    id_card_number: Mapped[str | None] = mapped_column(String(18))
    id_card_front_url: Mapped[str | None] = mapped_column(String(512))
    id_card_back_url: Mapped[str | None] = mapped_column(String(512))
    # Step 2: 摄影师身份
    shooting_types: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 逗号分隔：见 /me.py VALID_SHOOTING_TYPES
    experience_years: Mapped[str | None] = mapped_column(String(16))  # "1年内" / "1-3年" / "3年以上"
    portfolio_link: Mapped[str | None] = mapped_column(String(512))  # 个人主页链接（可选）
    # Step 3: 联系方式
    phone: Mapped[str | None] = mapped_column(String(20))
    wechat_id: Mapped[str | None] = mapped_column(String(64))
    # 可选字段
    price_range: Mapped[str | None] = mapped_column(String(32))  # "199-399" / "399-699" / "699+"
    # 认证等级
    certification_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 服务中心点（非实时定位）：映射历史列名 lat/lng
    service_center_lat: Mapped[float | None] = mapped_column("lat", Float)
    service_center_lng: Mapped[float | None] = mapped_column("lng", Float)
    service_radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)

    # 最近活跃时间（用于排序；MVP 由业务写入/或后续用触发器维护）
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="photographer")
    portfolio_items: Mapped[list["PortfolioItem"]] = relationship(back_populates="photographer")
    packages: Mapped[list["Package"]] = relationship(back_populates="photographer")
    schedule_blocks: Mapped[list["ScheduleBlock"]] = relationship(back_populates="photographer")


class BioTemplate(TimestampMixin, Base):
    __tablename__ = "bio_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)


class PortfolioItem(TimestampMixin, Base):
    __tablename__ = "portfolio_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    photographer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("photographers.id", ondelete="CASCADE"))

    title: Mapped[str | None] = mapped_column(String(128))
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    image_object_key: Mapped[str | None] = mapped_column(String(512))
    watermark_url: Mapped[str | None] = mapped_column(String(512))
    watermark_object_key: Mapped[str | None] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    photographer: Mapped[Photographer] = relationship(back_populates="portfolio_items")


class Package(TimestampMixin, Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    photographer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("photographers.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    photographer: Mapped[Photographer] = relationship(back_populates="packages")


class ScheduleBlock(TimestampMixin, Base):
    __tablename__ = "schedule_blocks"
    __table_args__ = (UniqueConstraint("photographer_id", "date", name="uq_schedule_photographer_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    photographer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("photographers.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    photographer: Mapped[Photographer] = relationship(back_populates="schedule_blocks")


class Favorite(TimestampMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "photographer_id", name="uq_favorites_user_photographer"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    photographer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("photographers.id", ondelete="CASCADE"))


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    photographer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("photographers.id", ondelete="CASCADE"))

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)

