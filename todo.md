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

