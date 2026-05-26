# COS Hardening Terraform

这套 Terraform 用来把 Close Shot 的 COS / S3 兼容对象存储治理收回到代码里，避免继续只靠控制台手工操作。

它覆盖的能力：

- 桶 ACL 与桶策略
- 版本控制
- SSE / KMS 默认加密
- 生命周期规则
- 可选跨区域复制（CRR）
- 可选跨区域副本桶

## 目录

- [versions.tf](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/versions.tf)
- [variables.tf](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/variables.tf)
- [main.tf](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/main.tf)
- [terraform.tfvars.example](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/terraform.tfvars.example)

## 设计取舍

- 主桶默认 `acl = "private"`，公共读通过桶策略按前缀放开，而不是公有写。
- 默认保留项目当前常见的公开媒体前缀：`avatar/`、`portfolio/`、`watermark/`、`uploads/`。如果你们准备统一走后端 `/media/*`，把 `allow_public_read = false` 即可。
- 生命周期默认对 `pg-backup/` 和临时前缀生效，避免只依赖脚本清理。
- 版本控制默认开启，和当前应用的硬删除路径配套。
- 跨区域复制默认示例只复制 `pg-backup/`，先保住数据库备份容灾，再视业务决定是否复制用户媒体。

## 准备凭证

Terraform Provider 可以直接读取环境变量：

```bash
export TENCENTCLOUD_SECRET_ID=xxxx
export TENCENTCLOUD_SECRET_KEY=xxxx
```

也可以写进 `terraform.tfvars`，但不推荐把密钥留在仓库里。

## 首次接管现有生产桶

1. 进入目录：

```bash
cd /Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening
```

2. 复制变量模板并按实际值修改：

```bash
cp terraform.tfvars.example terraform.tfvars
```

3. 初始化 Provider：

```bash
terraform init
```

4. 如果主桶已经在生产上存在，先导入再 `plan`：

```bash
terraform import tencentcloud_cos_bucket.primary your-bucket-appid
```

5. 如果你要让 Terraform 接管已有桶策略，再导入它：

```bash
terraform import 'tencentcloud_cos_bucket_policy.primary[0]' your-bucket-appid
```

6. 预览变更：

```bash
terraform plan
```

7. 确认无误后执行：

```bash
terraform apply
```

## 接管现有副本桶

如果跨区域副本桶也已经存在：

```bash
terraform import 'tencentcloud_cos_bucket.replica[0]' your-replica-bucket-appid
terraform import 'tencentcloud_cos_bucket_policy.replica[0]' your-replica-bucket-appid
```

前提是：

- `create_replica_bucket = true`
- `replica_bucket_name` 已填写

## 变量重点

- `bucket_name` / `bucket_region`：当前生产主桶。
- `allow_public_read`：是否保留匿名读。
- `public_read_prefixes`：允许匿名读的目录前缀。
- `encryption_algorithm`：`AES256` 或 `KMS`。
- `kms_key_id`：主桶现有 KMS Key ID；如果不想复用现有 key，也可以设 `create_kms_key = true`。
- `enable_replication`：打开 CRR。
- `replication_rule_prefixes`：哪些前缀需要复制，建议先从 `pg-backup/` 开始。
- `replica_bucket_region` / `replica_bucket_name`：CRR 目标桶。
- `replica_kms_key_id`：当源桶用 `KMS` 时必填，且必须是目标地域里的 KMS Key。
- `attach_replica_bucket_policy`：默认关闭，避免和复制链路的实际权限模型冲突；确认 CRR 正常后再决定是否接管。

## 和当前项目的对应关系

- 应用上传前缀白名单在 [backend/app/core/config.py](/Users/kkk/kkk-magic/close_shot/backend/app/core/config.py:39)。
- 备份上传前缀默认是 `pg-backup/`，见 [backend/scripts/pg-backup.sh](/Users/kkk/kkk-magic/close_shot/backend/scripts/pg-backup.sh:16)。
- 当前上传链路会返回 `public_url`，见 [backend/app/services/storage.py](/Users/kkk/kkk-magic/close_shot/backend/app/services/storage.py:170)，所以如果你们还在用 `S3_PUBLIC_BASE_URL`，请保留 `allow_public_read = true` 或改为统一走 `/media/*`。

## 建议的上线顺序

1. 先只导入主桶并 `plan`，确认不会误关现有公开读。
2. 再接管桶策略和生命周期。
3. 然后打开版本控制。
4. 最后再启用跨区域复制，先复制 `pg-backup/`，稳定后再考虑 `avatar/` 和 `portfolio/`。

## 注意

- 这个目录还没有配置远端 state backend；先本地验证，后续可再把 Terraform state 放进专用 COS 状态桶。
- 由于当前仓库里没有 Terraform 二进制，本次提交没有执行 `terraform fmt` / `terraform validate`；首次在有 Terraform 的环境里执行前，建议先跑一遍。
