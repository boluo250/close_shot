data "tencentcloud_user_info" "current" {}

resource "tencentcloud_kms_key" "primary" {
  count = var.create_kms_key ? 1 : 0

  alias                         = var.kms_key_alias
  description                   = var.kms_key_description
  key_rotation_enabled          = var.kms_key_rotation_enabled
  is_enabled                    = true
  pending_delete_window_in_days = var.kms_key_pending_delete_window_days
  tags                          = var.tags
}

locals {
  owner_uin        = tostring(data.tencentcloud_user_info.current.owner_uin)
  current_uin      = tostring(data.tencentcloud_user_info.current.uin)
  app_id           = tostring(data.tencentcloud_user_info.current.app_id)
  source_kms_key   = var.kms_key_id != null && trimspace(var.kms_key_id) != "" ? trimspace(var.kms_key_id) : try(tencentcloud_kms_key.primary[0].id, null)
  replica_kms_key  = var.replica_kms_key_id != null && trimspace(var.replica_kms_key_id) != "" ? trimspace(var.replica_kms_key_id) : null
  primary_bucket_qcs = "qcs::cos:${var.bucket_region}:uid/${local.app_id}:${var.bucket_name}"

  owner_principals = distinct(compact([
    "qcs::cam::uin/${local.owner_uin}:uin/${local.owner_uin}",
    local.current_uin != local.owner_uin ? "qcs::cam::uin/${local.owner_uin}:uin/${local.current_uin}" : null,
  ]))

  public_read_resources = [
    for prefix in var.public_read_prefixes :
    "${local.primary_bucket_qcs}/${trim(prefix, "/")}/*"
  ]

  generated_bucket_policy = jsonencode({
    version   = "2.0"
    Statement = concat(
      [
        {
          Sid = "OwnerFullControl"
          Principal = {
            qcs = local.owner_principals
          }
          Action   = ["name/cos:*"]
          Effect   = "allow"
          Resource = [local.primary_bucket_qcs, "${local.primary_bucket_qcs}/*"]
        }
      ],
      var.allow_public_read && length(local.public_read_resources) > 0 ? [
        {
          Sid = "AllowAnonymousReadForSelectedPrefixes"
          Principal = {
            qcs = ["qcs::cam::anyone:anyone"]
          }
          Action   = ["name/cos:GetObject"]
          Effect   = "allow"
          Resource = local.public_read_resources
        }
      ] : []
    )
  })

  effective_bucket_policy = var.bucket_policy_json_override != null && trimspace(var.bucket_policy_json_override) != "" ? var.bucket_policy_json_override : local.generated_bucket_policy

  replica_enabled             = var.enable_replication
  effective_replica_region    = coalesce(var.replica_bucket_region, var.bucket_region)
  effective_replica_bucket    = var.create_replica_bucket ? try(tencentcloud_cos_bucket.replica[0].bucket, null) : var.replica_bucket_name
  effective_replica_bucket_qcs = local.effective_replica_bucket != null ? "qcs::cos:${local.effective_replica_region}::${local.effective_replica_bucket}" : null
  replica_role                = "qcs::cam::uin/${local.owner_uin}:uin/${coalesce(var.replication_operator_uin, local.current_uin)}"
  replication_uses_kms        = var.encryption_algorithm == "KMS"

  effective_replica_lifecycle_rules = var.replica_lifecycle_rules != null ? var.replica_lifecycle_rules : var.lifecycle_rules
  replica_bucket_qcs               = var.create_replica_bucket ? "qcs::cos:${local.effective_replica_region}:uid/${local.app_id}:${var.replica_bucket_name}" : null

  generated_replica_bucket_policy = local.replica_bucket_qcs == null ? null : jsonencode({
    version   = "2.0"
    Statement = [
      {
        Sid = "OwnerOnlyAccess"
        Principal = {
          qcs = local.owner_principals
        }
        Action   = ["name/cos:*"]
        Effect   = "allow"
        Resource = [local.replica_bucket_qcs, "${local.replica_bucket_qcs}/*"]
      }
    ]
  })
}

resource "tencentcloud_cos_bucket" "primary" {
  bucket               = var.bucket_name
  acl                  = var.bucket_acl
  force_clean          = var.force_clean
  versioning_enable    = var.versioning_enabled
  encryption_algorithm = var.encryption_algorithm
  kms_id               = var.encryption_algorithm == "KMS" ? local.source_kms_key : null
  tags                 = var.tags

  lifecycle_rules = [
    for rule in var.lifecycle_rules : merge(
      {
        filter_prefix = rule.filter_prefix
      },
      rule.id == null ? {} : { id = rule.id },
      rule.expiration_days == null && rule.expiration_date == null ? {} : {
        expiration = [merge(
          rule.expiration_days == null ? {} : { days = rule.expiration_days },
          rule.expiration_date == null ? {} : { date = rule.expiration_date }
        )]
      },
      rule.transitions == null ? {} : {
        transition = [
          for transition in rule.transitions : merge(
            { storage_class = transition.storage_class },
            transition.days == null ? {} : { days = transition.days },
            transition.date == null ? {} : { date = transition.date }
          )
        ]
      },
      rule.noncurrent_expiration_days == null ? {} : {
        non_current_expiration = [{ non_current_days = rule.noncurrent_expiration_days }]
      },
      rule.noncurrent_transitions == null ? {} : {
        non_current_transition = [
          for transition in rule.noncurrent_transitions : {
            storage_class    = transition.storage_class
            non_current_days = transition.non_current_days
          }
        ]
      },
      rule.abort_incomplete_multipart_upload_days == null ? {} : {
        abort_incomplete_multipart_upload = [{ days = rule.abort_incomplete_multipart_upload_days }]
      }
    )
  ]

  replica_role = local.replica_enabled ? local.replica_role : null

  replica_rules = local.replica_enabled ? [
    for idx, prefix in var.replication_rule_prefixes : merge(
      {
        id                        = "rule-${idx + 1}-${replace(trimsuffix(prefix, "/"), "/", "-")}"
        status                    = "Enabled"
        priority                  = idx + 1
        prefix                    = prefix
        destination_bucket        = local.effective_replica_bucket_qcs
        destination_storage_class = var.replica_destination_storage_class
        delete_marker_replication = [{ status = var.replicate_delete_markers ? "Enabled" : "Disabled" }]
      },
      local.replication_uses_kms ? {
        destination_encryption_kms_key_id = local.replica_kms_key
        source_selection_criteria = [{
          sse_kms_encrypted_objects = [{ status = "Enabled" }]
        }]
      } : {}
    )
  ] : null

  lifecycle {
    precondition {
      condition     = var.encryption_algorithm != "KMS" || local.source_kms_key != null
      error_message = "When encryption_algorithm is KMS, provide kms_key_id or set create_kms_key = true."
    }

    precondition {
      condition     = !local.replica_enabled || local.effective_replica_bucket != null
      error_message = "Replication is enabled but replica_bucket_name is not set."
    }

    precondition {
      condition     = !local.replica_enabled || (var.replica_bucket_region != null && trimspace(var.replica_bucket_region) != "" && var.replica_bucket_region != var.bucket_region)
      error_message = "Replication requires replica_bucket_region, and it must be different from bucket_region."
    }

    precondition {
      condition     = !local.replication_uses_kms || !local.replica_enabled || local.replica_kms_key != null
      error_message = "KMS replication requires replica_kms_key_id in the destination region."
    }
  }
}

resource "tencentcloud_cos_bucket" "replica" {
  count    = var.create_replica_bucket ? 1 : 0
  provider = tencentcloud.dr

  bucket               = var.replica_bucket_name
  acl                  = var.replica_bucket_acl
  force_clean          = var.force_clean
  versioning_enable    = true
  encryption_algorithm = var.encryption_algorithm
  kms_id               = var.encryption_algorithm == "KMS" ? local.replica_kms_key : null
  tags                 = merge(var.tags, { role = "replica" })

  lifecycle_rules = [
    for rule in local.effective_replica_lifecycle_rules : merge(
      {
        filter_prefix = rule.filter_prefix
      },
      rule.id == null ? {} : { id = rule.id },
      rule.expiration_days == null && rule.expiration_date == null ? {} : {
        expiration = [merge(
          rule.expiration_days == null ? {} : { days = rule.expiration_days },
          rule.expiration_date == null ? {} : { date = rule.expiration_date }
        )]
      },
      rule.transitions == null ? {} : {
        transition = [
          for transition in rule.transitions : merge(
            { storage_class = transition.storage_class },
            transition.days == null ? {} : { days = transition.days },
            transition.date == null ? {} : { date = transition.date }
          )
        ]
      },
      rule.noncurrent_expiration_days == null ? {} : {
        non_current_expiration = [{ non_current_days = rule.noncurrent_expiration_days }]
      },
      rule.noncurrent_transitions == null ? {} : {
        non_current_transition = [
          for transition in rule.noncurrent_transitions : {
            storage_class    = transition.storage_class
            non_current_days = transition.non_current_days
          }
        ]
      },
      rule.abort_incomplete_multipart_upload_days == null ? {} : {
        abort_incomplete_multipart_upload = [{ days = rule.abort_incomplete_multipart_upload_days }]
      }
    )
  ]

  lifecycle {
    precondition {
      condition     = !var.create_replica_bucket || var.replica_bucket_name != null
      error_message = "create_replica_bucket is true but replica_bucket_name is not set."
    }

    precondition {
      condition     = var.encryption_algorithm != "KMS" || local.replica_kms_key != null
      error_message = "When creating a KMS-encrypted replica bucket, provide replica_kms_key_id."
    }
  }
}

resource "tencentcloud_cos_bucket_policy" "primary" {
  count = var.attach_bucket_policy ? 1 : 0

  bucket = tencentcloud_cos_bucket.primary.bucket
  policy = local.effective_bucket_policy
}

resource "tencentcloud_cos_bucket_policy" "replica" {
  count    = var.create_replica_bucket && var.attach_replica_bucket_policy ? 1 : 0
  provider = tencentcloud.dr

  bucket = tencentcloud_cos_bucket.replica[0].bucket
  policy = local.generated_replica_bucket_policy
}
