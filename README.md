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
# 开发环境（默认读取 .env.develop）
cp .env.example .env.develop
# 生产环境（默认读取 .env）
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

配置说明：
- 开发默认优先读取 `.env.develop`（当 `ENV=dev/develop/development/local` 且文件存在）
- 其他环境默认读取 `.env`
- 可通过环境变量显式指定：`ENV_FILE=.env uvicorn app.main:app --port 8001`

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

## Docker + Nginx 部署（新增）

已提供部署模板文件：
- `backend/Dockerfile`：后端服务镜像
- `admin-web/Dockerfile`：后台 Web 镜像（Vue3 构建产物）
- `infra/nginx/default.conf`：Nginx 反向代理配置
- `infra/docker-compose.deploy.yml`：一键启动 `db + minio + api + admin-web + nginx`

### 服务器依赖（Ubuntu）

- **Docker**：部署与运行容器必需（若未装请先 `sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin`）。
- **定时备份（可选）**：若需使用 [PostgreSQL 每日备份](backend/scripts/README-BACKUP.md)（pg_dump 上传 COS），需在宿主机安装：
  ```bash
  sudo apt-get update
  sudo apt-get install -y postgresql-client awscli
  ```
  或使用部署脚本一键安装：`./infra/deploy.sh install-backup-deps`

部署步骤（服务器）：

```bash
# 1) 准备后端生产环境变量（首次）
cd backend
cp .env.example .env

# 2) 回到基础设施目录并启动
cd ../infra
docker compose -f docker-compose.deploy.yml up -d --build
```

验证：
- API 健康检查：`http://<服务器IP或域名>/health`
- API 文档：`http://<服务器IP或域名>/docs`
- 后台登录页：`http://<服务器IP或域名>/ops-x8r7m2q4p9/login`

说明：
- Nginx 对外端口默认 `80/443`，可通过环境变量 `NGINX_HTTP_PORT`、`NGINX_HTTPS_PORT` 覆盖
- `DATABASE_URL` 会在 compose 内自动改为容器网络地址（`db:5432`）
- 默认挂载 `backend_local_media` 持久化本地媒体文件
- 管理端 API 前缀默认 `http://<域名>/admin-x8r7m2q4p9/*`（由 Nginx 转发到后端）

### 线上域名 + HTTPS（Let's Encrypt）

`infra/docker-compose.deploy.yml` 已内置 `nginx + certbot` 所需配置。  
首次签发证书请按下面顺序执行（在服务器）：

```bash
cd /opt/close_shot
cp backend/.env.example backend/.env

# 必填：线上域名与邮箱
export DOMAIN=your-domain.com
export EMAIL=you@example.com

# 先启动非 nginx 服务（避免 certbot 占用 80 端口冲突）
cd infra
docker compose -f docker-compose.deploy.yml up -d db minio api admin-web

# 首次签发证书（standalone）
docker compose --profile ops -f docker-compose.deploy.yml run --rm --service-ports certbot \
  certonly --standalone \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos --no-eff-email

# 启动 nginx（80/443）
docker compose -f docker-compose.deploy.yml up -d nginx
```

验证：
- `https://<你的域名>/health`
- `https://<你的域名>/docs`
- `https://<你的域名>/ops-x8r7m2q4p9/login`

证书续期（可放 cron，每月一次）：

```bash
cd /opt/close_shot/infra
export DOMAIN=your-domain.com

# standalone 续期需要临时释放 80 端口，会短暂中断
docker compose -f docker-compose.deploy.yml stop nginx
docker compose --profile ops -f docker-compose.deploy.yml run --rm --service-ports certbot renew
docker compose -f docker-compose.deploy.yml up -d nginx
```

## MVP 已覆盖
- LBS：按经纬度 + 半径查询附近摄影师（PostGIS 优先，未启用 PostGIS 时可切换 Haversine 兜底）
- 摄影师详情：作品/套餐/评分聚合
- 收藏：收藏/取消/列表
- 上传：MinIO/S3 兼容预签名（开发环境）
- 摄影师后台（最小）：`/studio/*` 管理资料/作品/套餐/在线状态

