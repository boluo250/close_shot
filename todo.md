## 近距离摄影师小程序（MVP）Todo

### 目标与范围（MVP）
- 小程序用户端：地图页 LBS 搜附近摄影师、摄影师详情页（作品墙/套餐/评分/收藏/联系入口）
- 后台 Web（Vue）：摄影师入驻/认证资料、作品管理（上传/排序/标签）、套餐价格管理、接单区域/在线状态
- 后端 FastAPI：Auth（微信登录占位 + 后台账号登录）、LBS 查询、摄影师资料/作品/套餐、收藏/评价、上传与媒体存储（本地/MinIO/S3 兼容）
- DB：PostgreSQL + PostGIS（优先），没有 PostGIS 时用 Haversine 兜底
- 订单/支付：MVP 先不做（只保留咨询线索/联系记录接口占位）

### 里程碑
#### M0：工程初始化（可启动）
- [ ] 建立 monorepo 目录：`backend/`、`admin-web/`、`miniprogram/`、`infra/`
- [ ] `docker-compose`：Postgres(+PostGIS) + MinIO（可选）+ Adminer/pgAdmin（可选）
- [ ] 后端：FastAPI 启动、健康检查、环境变量与配置管理、Alembic 迁移
- [ ] README：本地启动指南、接口概览、目录说明

#### M1：后端数据模型与基础接口
- [ ] 数据模型（SQLAlchemy）：User、Photographer、PortfolioItem、Package、Favorite、Review、Lead(Contact)
- [ ] 地理字段：PostGIS `geography(Point,4326)`（优先）+ 经纬度字段（兜底）
- [ ] 基础 CRUD：
  - [ ] 摄影师列表（带距离排序/分页/筛选：在线/标签/价格区间）
  - [ ] 摄影师详情（含作品/套餐/评分聚合）
  - [ ] 收藏/取消收藏
  - [ ] 评价创建/列表（防重复占位规则）
- [ ] 上传：生成直传签名/预签名 URL（MinIO/S3 兼容）+ 本地存储兜底

#### M2：Auth（最小可用）
- [ ] 小程序登录：`wx.login` code 换 openid/session_key（先做 mock/占位，后续替换真实微信接口）
- [ ] 后台登录：用户名密码 + JWT（管理员/摄影师）
- [ ] 权限：摄影师只能管理自己的资料/作品/套餐

#### M3：后台 Web（Vue3）MVP 页面
- [ ] 登录页
- [ ] 摄影师资料/认证资料编辑页（最小字段）
- [ ] 作品管理：上传、列表、排序、标签
- [ ] 套餐管理：增删改查
- [ ] 接单区域/在线状态：开关 + 可选半径/多边形（MVP 先做半径）

#### M4：小程序端骨架（先能跑通页面与接口）
- [ ] 地图页：获取定位、请求 `/photographers/nearby`
- [ ] 详情页：请求 `/photographers/{id}`、收藏、展示作品/套餐/评分
- [ ] 收藏页：请求 `/me/favorites`
- [ ] 联系/咨询：创建 `Lead`（仅记录，不支付）

### 技术决策（默认）
- 后端：FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2
- DB：Postgres 16 + PostGIS 3（docker 一键）
- 存储：MinIO（S3 兼容）开发环境；可切 OSS/COS/S3
- Admin Web：Vue3 + Vite + Pinia + Element Plus（或 Naive UI）
- 小程序：原生小程序（WXML/WXSS/JS）先做骨架

### 接口草案（会在代码中落地）
- `GET /health`
- `POST /auth/wechat`（MVP：mock 版）
- `POST /auth/login`（后台）
- `GET /photographers/nearby?lat=&lng=&radius_m=&limit=&offset=`
- `GET /photographers/{id}`
- `POST /photographers/{id}/favorite` / `DELETE /photographers/{id}/favorite`
- `GET /me/favorites`
- `POST /photographers/{id}/reviews` / `GET /photographers/{id}/reviews`
- `POST /upload/presign`（返回直传信息）

---

## PRD：附近摄影师展示（非实时位置，不误导）

### 核心原则（必须满足）
- [ ] “附近”=可为我服务（覆盖能力），不是摄影师实时定位
- [ ] 明确区分：常驻城市 / 服务中心点（地图选点）/ 服务半径 / 接单状态
- [ ] 距离仅用于“通勤成本估算”，文案必须避免暗示实时位置
- [ ] 排序不是纯距离：距离权重 + 活跃度 + 评分/成交量（可解释、可扩展）

### 数据模型（后端）
- [ ] 摄影师位置语义重命名（不做实时定位）：
  - [ ] `service_center_lat/lng`（映射现有 `lat/lng`）
  - [ ] `service_radius_m`（已有）
  - [ ] `is_accepting_orders`（映射现有 `is_online`，语义改为“接单中/暂停接单”）
  - [ ] `last_active_at`（先用 `updated_at` 兜底；后续可单独字段）
- [ ] 指标字段（可先计算、后续可落库做反范式）：
  - [ ] `rating_avg` / `rating_count`（来自 reviews 聚合）
  - [ ] `orders_count`（MVP 可先不做，后续接订单）
  - [ ] `starting_price_cents`（从 active 套餐取最小值用于列表展示）

### 查询与排序（后端）
- [ ] Nearby 查询输入：用户 `lat/lng`（可选 `city` / `limit/offset` / `tag`）
- [ ] Nearby 硬条件：
  - [ ] `is_accepting_orders = true`
  - [ ] `distance(user, service_center) <= service_radius_m`
  - [ ] `service_center_lat/lng` 非空
- [ ] Nearby 输出字段（给小程序直接用）：
  - [ ] 摄影师基础信息（id、昵称/头像、tags、city）
  - [ ] `service_center_lat/lng`、`service_radius_m`
  - [ ] `distance_m` / `distance_km`
  - [ ] `distance_copy`（后端生成：如“覆盖你所在区域 / 服务于你附近 · 约 X km / 工作室约 X km”）
  - [ ] `is_accepting_orders`（用于状态展示）
- [ ] 排序（示例，可调权重）：
  - [ ] `score = 0.35*f_distance + 0.25*f_activity + 0.25*f_rating + 0.15*f_volume`
  - [ ] 距离：`f_distance = exp(-d_km/8)`
  - [ ] 活跃：`f_activity = exp(-days_since_active/14)`
  - [ ] 评分：`f_rating = clamp((rating_avg-4.0)/1.0,0,1)`
  - [ ] 成交：`f_volume = clamp(log(1+orders_count)/log(1+200),0,1)`（MVP 可先置 0）

### 地理实现（技术）
- [ ] 优先：PostGIS（可选）：
  - [ ] `ST_DWithin` 做覆盖判断，`ST_Distance` 计算距离
  - [ ] GIST 索引（若引入 geography）
- [ ] 兜底：Haversine SQL（当前 `services/geo.py` 已有）+ bounding box（后续优化）

### 小程序展示规范（C端）
- [ ] 地图：
  - [ ] marker 固定在“服务中心点”（头像点位）
  - [ ] 点击 marker 展示服务半径圈（circle）与说明文案：“可在 X km 范围内接拍”
  - [ ] 地图角落常驻提示：“摄影师位置为服务范围，并非实时位置”
- [ ] 列表卡片字段：
  - [ ] 头像 / 昵称（或临时占位）
  - [ ] 距离文案（用 `distance_copy`，禁止直接展示“距离你Xkm”）
  - [ ] 接单状态（接单中/暂停接单）
  - [ ] 起步价（从最便宜套餐或 `starting_price_cents`）
  - [ ] 风格标签

### 摄影师侧（B端 / Studio）
- [ ] 表单字段与文案改名：
  - [ ] “在线状态”→“接单状态”
  - [ ] “定位 lat/lng”→“服务中心点 lat/lng（非实时）”
  - [ ] “接单半径（米）”→“服务半径（米）”


