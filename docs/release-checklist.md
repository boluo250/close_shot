# Release Checklist

上线前建议先等待以下 GitHub Actions 全绿：

- `backend-smoke`
- `admin-web-build`
- `admin-web-e2e`
- `miniprogram-syntax`

随后按下面顺序做一轮人工回归。

## Backend / Deploy

- 打开 `/health`，确认返回 `200`。
- 打开 `/health/ready` 或 `/readyz`，确认数据库就绪。
- 确认 `deploy-production` 的 `preflight` 全部通过后再执行正式部署。
- 部署完成后再次检查生产域名下的 `/health`、`/readyz`、`/docs`。

## Admin Web

- 管理员账号登录后应落到 `/ops-x8r7m2q4p9/admin/certifications`。
- 摄影师账号登录后应落到 `/ops-x8r7m2q4p9/studio/profile`。
- 摄影师直接访问 `/ops-x8r7m2q4p9/admin/*` 时应被重定向回摄影师工作台。
- 风险管理页能正常搜索、编辑并保存风险状态。
- 认证审核页能正常查看详情、通过、驳回、上下线、删除离线摄影师。

## Mini Program

- 微信登录成功，首页、地图页、摄影师详情页可正常加载。
- 首次进入时，隐私协议/授权链路可正常完成。
- 摄影师入驻申请可正常提交，资料字段、图片和联系方式都能保存。
- 摄影师工作台可正常上传作品、编辑资料、编辑套餐。
- 收藏、取消收藏、查看摄影师详情与联系方式权限表现正常。

## Media / Storage

- 上传接口返回的 `proxy_url` 可在小程序和浏览器中正常访问。
- 已存在的头像、作品图、水印图在管理端和小程序里都能正常展示。
- 删除摄影师或删除作品后，对应资源不会再被前端引用。
