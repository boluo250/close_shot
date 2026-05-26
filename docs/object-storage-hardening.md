# Object Storage Hardening

当前仓库已经接入 S3 兼容对象存储上传，但没有在代码或基础设施里自动声明以下桶级治理能力：

- 生命周期（Lifecycle）
- 版本控制（Versioning）
- 跨区域冗余 / 跨区域复制（CRR）
- 服务端加密（SSE）

这几项大多属于云资源配置，不应该只依赖应用代码；建议在 COS / S3 控制台或 IaC 中配置，并把结果纳入上线检查。

如果当前使用的是不支持桶版本控制的轻量对象存储，仓库现在提供了应用层兜底：

- 删除对象时先归档到 `STORAGE_SOFT_DELETE_PREFIX`（默认 `_recycle_bin/`）下，再删除原对象。
- 可通过 [restore-soft-deleted-object.py](/Users/kkk/kkk-magic/close_shot/backend/scripts/restore-soft-deleted-object.py:1) 将归档对象恢复回原路径或新路径。
- 相关配置见 [backend/app/core/config.py](/Users/kkk/kkk-magic/close_shot/backend/app/core/config.py:25) 和 [backend/.env.example](/Users/kkk/kkk-magic/close_shot/backend/.env.example:12)。

## 当前代码现状

- 上传链路使用 `POST /upload/presign` + 预签名 PUT，代码位置：[backend/app/api/routes/upload.py](/Users/kkk/kkk-magic/close_shot/backend/app/api/routes/upload.py:56)。
- 对象存储读写走 S3 兼容接口，代码位置：[backend/app/services/storage.py](/Users/kkk/kkk-magic/close_shot/backend/app/services/storage.py:32)。
- 删除对象是直接硬删除，没有应用侧回收站，代码位置：[backend/app/services/storage.py](/Users/kkk/kkk-magic/close_shot/backend/app/services/storage.py:214)。
- 数据库备份脚本会把备份上传到同一套 `S3_*` 配置指向的桶，并用脚本按天删除旧备份，代码位置：[backend/scripts/pg-backup.sh](/Users/kkk/kkk-magic/close_shot/backend/scripts/pg-backup.sh:128)。

## 要不要做

### 生命周期

建议做。

原因：

- 代码里只有数据库备份做了脚本清理，见 [backend/scripts/pg-backup.sh](/Users/kkk/kkk-magic/close_shot/backend/scripts/pg-backup.sh:155)，但这依赖 cron 正常执行。
- 图片上传、审核驳回残留、未来的临时文件如果没有桶生命周期，容易持续堆积。

推荐策略：

- `pg-backup/`：按合规要求保留，例如 14 天、30 天或 90 天后自动过期。
- `tmp/`、`draft/`、`review-rejected/` 之类临时前缀：7 到 30 天自动过期。
- `avatar/`、`portfolio/`：不要默认过期，除非你们已经定义“删除后保留 N 天”的业务规则。

### 版本控制

建议生产开启。

原因：

- 当前删除是直接 `delete_object`，误删后无法从应用层恢复。
- 后台已有“删除后不可恢复”的业务动作，如果没有版本控制，运维补救空间很小。

开启后建议同步约束：

- 给核心媒体桶打开版本控制。
- 对删除操作增加运维说明：恢复时先查历史版本或删除标记。
- 如果担心成本，可只对核心媒体桶开启，不必对所有临时桶统一开启。

### 跨区域冗余 / 跨区域复制

这项取决于你们对区域级故障的容忍度，但数据库备份至少建议做。

建议优先级：

- `pg-backup/`：高，建议复制到第二地域或第二桶。
- `avatar/`、`portfolio/`：中，如果用户内容重要且重传成本高，建议做。
- 临时或可重建资源：低，可暂缓。

如果暂时不做，需要明确接受：

- 单地域 COS/S3 故障时，媒体和备份可能同时不可用。
- 当前备份脚本上传到同一套 `S3_*` 目标，并不天然提供异地容灾。

## 怎么增加

### 方案 1：先在控制台补齐

适合当前阶段最快落地。

1. 找到生产桶。
2. 开启服务端加密。
3. 开启版本控制。
4. 按前缀新增生命周期规则。
5. 为 `pg-backup/` 或整桶开启跨区域复制到第二地域桶。
6. 在上线检查单里记录已完成的桶名、地域、规则名称和保留天数。

### 方案 2：补 IaC

更推荐长期做法。

把以下内容放进 Terraform / Pulumi / 云厂商模板：

- 桶创建
- 桶策略 / 公私权限
- 生命周期规则
- 版本控制
- SSE / KMS
- 跨区域复制规则

这样后续环境迁移、重建、审计都会稳定很多。

仓库里已经补了一套 Terraform 目录，可直接接管现有 COS 桶：

- [infra/terraform/cos-hardening/README.md](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/README.md)
- [infra/terraform/cos-hardening/main.tf](/Users/kkk/kkk-magic/close_shot/infra/terraform/cos-hardening/main.tf)

## 对这个项目的最小可执行建议

按优先级建议先做这 4 件事：

1. 给生产媒体桶开启版本控制。
2. 给 `pg-backup/` 增加桶生命周期，不再只依赖脚本删历史文件。
3. 给数据库备份加第二地域复制。
4. 明确媒体访问策略：要么统一走后端 `/media/*`，要么把桶设置成只读公开且禁止公有写。
