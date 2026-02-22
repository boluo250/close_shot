# close_shot（近距离摄影师）

## 本地启动（推荐）

### 1）启动数据库（Postgres，可选 PostGIS）与对象存储（MinIO）

```bash
cd infra
docker compose up -d
```

如果你的机器没有安装 Docker，请先安装 Docker Desktop（macOS）。

### 2）启动后端（FastAPI）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 按需修改 DATABASE_URL/JWT_SECRET 等
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

打开：
- 健康检查：`http://localhost:8001/health`
- API 文档：`http://localhost:8001/docs`

### 3）启动后台 Web（Vue3）

```bash
cd admin-web
npm install
npm run dev
```

### 4）打开小程序（微信开发者工具）
- 用微信开发者工具打开 `miniprogram/`
- 开发环境建议关闭域名校验（已在 `project.config.json` 里设置 `urlCheck:false`）
- 小程序后端地址统一在 `miniprogram/env.js` 配置
  - 局域网模式：改 `DEV_API_HOST`
  - 内网穿透模式：改 `API_BASE_URL`（推荐 Cloudflare）

### 5）真机调试（Cloudflare Tunnel，推荐）
当局域网模式不稳定（例如开发者工具 ws 通道失败）时，建议改用 Cloudflare Tunnel：

```bash
# 安装（macOS）
brew install cloudflared

# 将本机 8001 暴露为公网 https 地址
cloudflared tunnel --url http://127.0.0.1:8001
```

启动后会看到类似 `https://xxxx-xxxx.trycloudflare.com` 的地址。  
把它填到 `miniprogram/env.js`：

```js
module.exports = {
  API_BASE_URL: "https://xxxx-xxxx.trycloudflare.com",
  DEV_API_HOST: "192.168.1.100",
  DEV_API_PORT: 8001
};
```

说明：
- `app.js` 已实现“优先使用 `API_BASE_URL`，为空时再走局域网 IP”
- 后端仍需在本机启动：`uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload`
- 每次重启临时隧道，`trycloudflare.com` 子域可能变化，记得同步更新 `miniprogram/env.js`

## 开发联调建议（快速有数据）
1) 先调用 `POST /dev/seed` 生成一些摄影师（`/docs` 里直接点就行）
2) 再在小程序地图页刷新，即可看到附近摄影师 markers

## 小程序端上传作品（MVP）
- 小程序新增了 `pages/studio/index`（摄影师工作台）：
  - 用后台摄影师账号登录（调用 `POST /auth/login`）
  - 选择图片后：`POST /upload/presign` → PUT 直传对象存储 → `POST /studio/portfolio` 创建作品
- 为了让小程序也能稳定加载图片，后端提供了 `GET /media/{object_key}` 作为对象存储代理域名（上传返回 `proxy_url`）

## 目录结构
- `backend/`：FastAPI 服务（LBS/摄影师资料/作品/套餐/收藏/评价/上传）
- `admin-web/`：运营/摄影师后台 Web（Vue3）
- `miniprogram/`：微信小程序用户端（骨架）
- `infra/`：docker-compose（Postgres/PostGIS、MinIO 等）

## MVP 已覆盖
- LBS：按经纬度 + 半径查询附近摄影师（PostGIS 优先，未启用 PostGIS 时可切换 Haversine 兜底）
- 摄影师详情：作品/套餐/评分聚合
- 收藏：收藏/取消/列表
- 上传：MinIO/S3 兼容预签名（开发环境）
- 摄影师后台（最小）：`/studio/*` 管理资料/作品/套餐/在线状态

