"""add bio templates

Revision ID: 20260218_0001
Revises: 20260209_0001
Create Date: 2026-02-18

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0001"
down_revision = "20260209_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bio_templates",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("text", sa.String(length=256), nullable=False, unique=True),
    )

    bio_table = sa.table("bio_templates", sa.column("text", sa.String(length=256)))
    op.bulk_insert(
        bio_table,
        [{"text": t} for t in _seed_templates()],
    )


def downgrade() -> None:
    op.drop_table("bio_templates")


def _seed_templates() -> list[str]:
    return [
        "善于捕捉自然光影的记录者，偏爱真实与松弛的氛围。",
        "喜欢用镜头讲故事，擅长把情绪拍进画面里。",
        "人像与写真为主，追求干净肤色与高级质感。",
        "温柔系摄影师，擅长引导，让你自然好看。",
        "偏纪实风格，记录当下的细节与温度。",
        "擅长电影感氛围营造，色彩克制、质感在线。",
        "喜欢胶片感与复古调色，画面更有故事性。",
        "擅长街拍与旅拍，抓拍自然表情与互动。",
        "注重构图与光线，成片干净耐看不浮夸。",
        "拍摄节奏轻松，适合第一次拍照也不紧张。",
        "会根据你的气质定制拍摄方案与动作引导。",
        "擅长半身与特写，细节更显高级。",
        "自然光优先，必要时补光，保证肤色通透。",
        "沟通细致，拍摄前会一起确认风格与参考图。",
        "擅长室外人像，利用环境做氛围与层次。",
        "擅长室内人像，控光到位，画面更干净。",
        "喜欢清新日系风，色调明亮、氛围温柔。",
        "偏法式松弛风，画面高级又不刻意。",
        "偏高级感肖像，光影对比强，轮廓更立体。",
        "擅长情侣写真，互动引导自然，氛围甜但不腻。",
        "擅长亲子与儿童，抓拍为主，记录真实成长瞬间。",
        "擅长活动/跟拍，节奏快但画面稳，重点不漏拍。",
        "擅长婚礼/仪式跟拍，情绪与细节双在线。",
        "擅长证件照与形象照，干净背景、精修自然。",
        "擅长商业人像，适合品牌、电商、门店宣传。",
        "擅长探店拍摄，画面通透，氛围感强。",
        "擅长宠物拍摄，耐心引导，抓住可爱瞬间。",
        "审美统一，出片风格稳定，适合长期合作。",
        "会给到姿势与表情小技巧，拍前拍中都能轻松上手。",
        "偏轻复古色调，皮肤质感自然，不做“假白”。",
        "喜欢干净背景与简约构图，突出人物本身。",
        "擅长利用前景与反射，画面更有层次与氛围。",
        "擅长逆光与侧光，拍出通透光感与轮廓。",
        "注重人物状态，先聊天放松，再进入拍摄节奏。",
        "拍摄前可一起选服装/配饰，保证整体风格统一。",
        "偏纪实与生活方式，像朋友一样记录你的一天。",
        "擅长都市街景人像，干净利落，氛围在线。",
        "擅长公园/草地人像，自然清新，色彩舒适。",
        "擅长夜景人像，灯光氛围拿捏到位。",
        "擅长室内咖啡馆风，温柔光线与松弛情绪。",
        "擅长运动/户外风，动态抓拍更有力量感。",
        "擅长小红书风格出片，构图与色调更上镜。",
        "偏高级质感修图，保留皮肤纹理与真实细节。",
        "拍摄过程高效，交付及时，沟通不拖沓。",
        "尊重你的想法，会在参考图基础上做更适合你的呈现。",
        "擅长多人合照与全家福，站位引导清晰不尴尬。",
        "擅长毕业照/团体照，流程熟练，效率高。",
        "擅长孕妇写真，光线柔和，氛围温暖。",
        "拍摄风格可甜可酷，按你的气质与需求定制。",
    ]

