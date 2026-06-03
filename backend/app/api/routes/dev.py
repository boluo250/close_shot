from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Package, Photographer, PortfolioItem, Review, ReviewStatus, User, UserRole
from app.db.session import get_db

router = APIRouter()


@router.post("/seed")
def seed(
    lat: float = 31.2304,
    lng: float = 121.4737,
    city: str = "上海",
    n: int = 10,
    seed: int | None = 42,
    reset: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    if not settings.is_dev:
        raise HTTPException(status_code=403, detail="seed is dev-only")

    n = min(max(n, 1), 50)
    rng = random.Random(seed) if seed is not None else random.Random()

    # 默认允许重复执行 seed：先清空再播种，避免 username/外键冲突
    if reset:
        # 注意：dev-only；生产环境禁用 seed
        db.execute(
            text(
                "TRUNCATE TABLE favorites, reviews, appointment_requests, portfolio_items, packages, photographers, users "
                ", analytics_events "
                "RESTART IDENTITY CASCADE"
            )
        )

    def picsum_url(image_id: int, w: int, h: int) -> str:
        # 返回图片内容（无跳转），小程序 dev 环境更稳定
        return f"https://picsum.photos/id/{image_id}/{w}/{h}"

    def picsum_seed_url(seed_value: str, w: int, h: int) -> str:
        # 使用 seed 生成稳定的图，避免风格随机漂移
        return f"https://picsum.photos/seed/{seed_value}/{w}/{h}"

    avatar_ids = [64, 91, 1005, 1011, 1012, 1015, 1016, 1024, 1025, 1035, 1037, 1044, 1050, 1062, 1067]
    portrait_style_seeds = [
        ("日系", "japanese"),
        ("欧美", "european"),
        ("中式", "chinese"),
        ("韩系", "korean"),
        ("复古", "vintage"),
        ("胶片", "film"),
        ("森系", "forest"),
        ("极简", "minimal"),
    ]
    portrait_ids = [
        64,
        91,
        1005,
        1011,
        1012,
        1015,
        1016,
        1024,
        1025,
        1035,
        1037,
        1044,
        1050,
        1062,
        1067,
        1074,
    ]

    display_names = [
        "阿辰",
        "小北",
        "柚子",
        "Luna",
        "Momo",
        "一一",
        "阿澈",
        "木木",
        "Cici",
        "大熊",
        "夏夏",
        "阿布",
        "Yuki",
        "小南",
        "Kiki",
        "阿洛",
    ]
    bios = [
        "擅长日系清透人像，喜欢自然光与轻微氛围感。",
        "欧美街拍风，强调对比度与线条表现。",
        "中式人像与新中式造型，氛围温柔。",
        "韩系清新风，妆造与动作引导细致。",
        "复古胶片感人像，颗粒与色调耐看。",
        "森系人像，偏自然与治愈的情绪表达。",
    ]
    tag_pools = [
        "日系,人像,清透",
        "欧美,人像,街拍",
        "中式,人像,写真",
        "韩系,人像,清新",
        "复古,人像,胶片感",
        "森系,人像,氛围感",
        "极简,人像,自然光",
        "个人,人像,电影感",
    ]
    review_contents = [
        "沟通很顺畅，拍摄过程很放松，成片超满意！",
        "很会引导动作，表情自然了很多，推荐。",
        "效率高，构图好看，修图风格也很舒服。",
        "准时、耐心、出片快，体验很好。",
        "非常懂光线，现场就能拍出氛围感。",
    ]
    customer_names = ["可可", "小麦", "阿七", "小宇", "小鹿", "阿宁", "Mia", "Evan", "Sunny", "小桃"]
    equipment_pools = [
        ["Sony A7M4", "GM 24-70", "GM 85", "Godox V1"],
        ["Canon R6", "RF 28-70", "RF 85", "AD200Pro"],
        ["Nikon Z6II", "Z 24-70", "Z 35", "LED常亮灯"],
        ["Fujifilm X-T5", "XF 16-55", "XF 56", "反光板"],
    ]
    drone_pools = [
        ["DJI Air 3"],
        ["DJI Mini 4 Pro"],
        ["DJI Mavic 3 Classic"],
        [],
    ]
    created = 0
    usernames: list[str] = []
    now = datetime.now(timezone.utc)
    customers: list[User] = []
    for i, name in enumerate(customer_names):
        u = User(
            role=UserRole.customer.value,
            display_name=name,
            username=f"c{rng.randint(100000, 999999)}",
            password_hash=hash_password("123456"),
            avatar_url=picsum_seed_url(f"cust-{i}", 120, 120),
        )
        db.add(u)
        customers.append(u)
    db.flush()
    for i in range(n):
        username = f"p{rng.randint(100000, 999999)}"
        u = User(
            role=UserRole.photographer.value,
            display_name=f"{rng.choice(display_names)} · 摄影师",
            username=username,
            password_hash=hash_password("123456"),
            avatar_url=picsum_url(avatar_ids[i % len(avatar_ids)], 160, 160),
        )
        db.add(u)
        db.flush()
        usernames.append(username)

        # 在中心点附近抖动（大约 1~6 公里内）
        dlat = rng.uniform(-0.05, 0.05)
        dlng = rng.uniform(-0.05, 0.05)
        tags = rng.choice(tag_pools)
        style_label, _style_seed = rng.choice(portrait_style_seeds)
        equipment_list = rng.choice(equipment_pools)
        drone_models = rng.choice(drone_pools)
        hour_price = rng.choice([19900, 24900, 29900, 34900])
        item_price = rng.choice([4900, 6900, 9900, 12900])
        rate_card = [
            {"name": "人像拍摄", "mode": "hour", "price_cents": hour_price, "unit": "小时"},
            {"name": "精修照片", "mode": "item", "price_cents": item_price, "unit": "张"},
        ]
        if drone_models:
            rate_card.append(
                {
                    "name": "航拍补充",
                    "mode": "hour",
                    "price_cents": hour_price + rng.choice([8000, 12000, 16000]),
                    "unit": "小时",
                }
            )
        p = Photographer(
            user_id=u.id,
            bio=rng.choice(bios),
            tags=tags,
            equipment_list=",".join(equipment_list),
            drone_models=",".join(drone_models),
            rate_card_json=json.dumps(rate_card, ensure_ascii=False),
            is_accepting_orders=rng.random() < 0.85,
            status="approved",
            certification_level=1,
            city=city,
            service_center_lat=lat + dlat,
            service_center_lng=lng + dlng,
            service_radius_m=rng.choice([5000, 8000, 10000, 12000, 15000, 20000]),
            last_active_at=now - timedelta(days=rng.randint(0, 21)),
        )
        db.add(p)
        db.flush()

        # 样片：用于首页卡片预览（默认最多取前 3 张）
        items: list[PortfolioItem] = []
        for j in range(6):
            img_id = portrait_ids[(i * 7 + j) % len(portrait_ids)]
            items.append(
                PortfolioItem(
                    photographer_id=p.id,
                    title=f"{style_label}人像 {j+1}",
                    image_url=picsum_url(img_id, 480, 720),
                    sort_order=j,
                    tags=f"{tags},{style_label}人像",
                )
            )
        db.add_all(items)

        # 套餐：用于起步价展示
        base_price = rng.choice([19900, 29900, 39900])
        db.add_all(
            [
                Package(
                    photographer_id=p.id,
                    name="30分钟快拍",
                    price_cents=base_price,
                    duration_minutes=30,
                    description="适合打卡/轻量记录",
                    is_active=True,
                ),
                Package(
                    photographer_id=p.id,
                    name="2小时精修",
                    price_cents=base_price + rng.choice([40000, 50000, 60000]),
                    duration_minutes=120,
                    description="含精修/指导动作与取景",
                    is_active=True,
                ),
                Package(
                    photographer_id=p.id,
                    name="半日旅拍",
                    price_cents=base_price + rng.choice([90000, 110000, 130000]),
                    duration_minutes=240,
                    description="适合旅行/街拍/多机位切换",
                    is_active=rng.random() < 0.7,
                ),
            ]
        )

        # 评价：用于星级展示（绑定真实用户）
        review_n = rng.randint(0, 18)
        reviews: list[Review] = []
        for _ in range(review_n):
            r = rng.random()
            rating = 5 if r < 0.65 else 4 if r < 0.93 else 3
            content = rng.choice(review_contents) if rng.random() < 0.8 else None
            reviewer = rng.choice(customers)
            reviews.append(
                Review(
                    user_id=reviewer.id,
                    photographer_id=p.id,
                    rating=rating,
                    content=content,
                    status=ReviewStatus.approved.value,
                )
            )
        if reviews:
            db.add_all(reviews)
        created += 1

    db.commit()
    return {"ok": True, "created": created, "default_password": "123456", "usernames": usernames}
