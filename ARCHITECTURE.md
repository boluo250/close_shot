## 总体架构图（文字版）

### 组件
- **微信小程序（用户端）**
  - 地图页：LBS 搜附近摄影师（按距离排序）
  - 摄影师详情：作品墙 / 套餐 / 评分 / 收藏 / 联系入口
  - 收藏页
  - （可选）订单/预约：MVP 不做支付，仅保留留资/咨询线索入口

- **后台 Web（运营/摄影师）**
  - 摄影师入驻/认证资料（MVP 可先做基础资料）
  - 作品管理：上传 / 排序 / 标签
  - 套餐价格管理
  - 接单区域 / 在线状态
  - （可选）订单/咨询线索

- **后端（FastAPI）**
  - Auth：微信登录（MVP mock，可替换真实微信 code2session）/ 后台账号登录（JWT）
  - LBS 查询：按经纬度与距离排序（PostGIS 优先；无 PostGIS 用 Haversine 兜底）
  - 摄影师资料/作品/套餐：读写接口（用户端读；摄影师后台写）
  - 收藏/评价
  - 上传与媒体存储：S3 兼容（MinIO/OSS/COS/S3）预签名直传
  - （可选）预约/订单/支付

- **数据库（PostgreSQL + PostGIS 推荐）**
  - 摄影师经纬度、范围检索、距离排序
  - 没 PostGIS 也能做（Haversine），但规模上来性能更吃力

- **对象存储**
  - 作品图、头像：S3 / 阿里 OSS / 腾讯 COS / MinIO（开发）

### 数据流（主链路）
1) 小程序获取定位（lat/lng）
2) 调用后端 `GET /photographers/nearby?lat=&lng=&radius_m=`
3) 点击 marker/列表进入详情：`GET /photographers/{id}`
4) 收藏：`POST|DELETE /photographers/{id}/favorite`，收藏列表：`GET /me/favorites`
5) 摄影师后台：
   - 登录 `POST /auth/login`
   - 管理资料/作品/套餐：`/studio/*`
6) 图片上传：
   - 前端向后端拿预签名 `POST /upload/presign`
   - 前端直传到对象存储（MinIO/S3）
   - 后端保存图片 URL / object_key

