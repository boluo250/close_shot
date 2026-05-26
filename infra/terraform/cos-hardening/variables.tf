variable "tencentcloud_secret_id" {
  description = "Tencent Cloud SecretId. Leave null to use TENCENTCLOUD_SECRET_ID from the environment."
  type        = string
  default     = null
  sensitive   = true
  nullable    = true
}

variable "tencentcloud_secret_key" {
  description = "Tencent Cloud SecretKey. Leave null to use TENCENTCLOUD_SECRET_KEY from the environment."
  type        = string
  default     = null
  sensitive   = true
  nullable    = true
}

variable "bucket_name" {
  description = "Primary COS bucket name, for example close-shot-media-1250000000."
  type        = string
}

variable "bucket_region" {
  description = "Primary COS bucket region, for example ap-shanghai."
  type        = string
}

variable "bucket_acl" {
  description = "Bucket ACL. Keep this as private and expose public-read only through bucket policy when needed."
  type        = string
  default     = "private"
}

variable "force_clean" {
  description = "Whether Terraform can delete all objects when destroying the bucket."
  type        = bool
  default     = false
}

variable "versioning_enabled" {
  description = "Enable bucket versioning so accidental deletes can be recovered."
  type        = bool
  default     = true
}

variable "encryption_algorithm" {
  description = "Bucket default encryption algorithm. Supported values: AES256, KMS."
  type        = string
  default     = "AES256"

  validation {
    condition     = contains(["AES256", "KMS"], var.encryption_algorithm)
    error_message = "encryption_algorithm must be AES256 or KMS."
  }
}

variable "kms_key_id" {
  description = "Existing Tencent Cloud KMS key ID for the primary bucket. Required when encryption_algorithm is KMS unless create_kms_key is true."
  type        = string
  default     = null
  nullable    = true
}

variable "create_kms_key" {
  description = "Create a new KMS key for the primary bucket in Terraform."
  type        = bool
  default     = false
}

variable "kms_key_alias" {
  description = "Alias for a Terraform-managed primary bucket KMS key."
  type        = string
  default     = "close-shot-cos-primary"
}

variable "kms_key_description" {
  description = "Description for a Terraform-managed primary bucket KMS key."
  type        = string
  default     = "KMS key for Close Shot primary COS bucket encryption"
}

variable "kms_key_rotation_enabled" {
  description = "Enable automatic rotation on a Terraform-managed primary bucket KMS key."
  type        = bool
  default     = true
}

variable "kms_key_pending_delete_window_days" {
  description = "Pending delete window for a Terraform-managed primary bucket KMS key."
  type        = number
  default     = 30
}

variable "attach_bucket_policy" {
  description = "Manage the primary bucket policy in Terraform."
  type        = bool
  default     = true
}

variable "allow_public_read" {
  description = "Allow anonymous read access for selected prefixes. Keep false if all media should go through /media/*."
  type        = bool
  default     = true
}

variable "public_read_prefixes" {
  description = "Folder-like prefixes that can be read anonymously when allow_public_read is true."
  type        = list(string)
  default     = ["avatar/", "portfolio/", "watermark/", "uploads/"]
}

variable "bucket_policy_json_override" {
  description = "Optional raw COS bucket policy JSON. When set, Terraform will use it instead of the generated policy."
  type        = string
  default     = null
  nullable    = true
}

variable "lifecycle_rules" {
  description = "Lifecycle rules for the primary bucket. Defaults are tuned for backups and temporary prefixes used by this project."
  type = list(object({
    id                                      = optional(string)
    filter_prefix                           = string
    expiration_days                         = optional(number)
    expiration_date                         = optional(string)
    noncurrent_expiration_days              = optional(number)
    transitions = optional(list(object({
      storage_class = string
      days          = optional(number)
      date          = optional(string)
    })))
    noncurrent_transitions = optional(list(object({
      storage_class    = string
      non_current_days = number
    })))
    abort_incomplete_multipart_upload_days = optional(number)
  }))
  default = [
    {
      id                                      = "pg-backup-retention"
      filter_prefix                           = "pg-backup/"
      expiration_days                         = 30
      noncurrent_expiration_days              = 7
      abort_incomplete_multipart_upload_days  = 7
    },
    {
      id                                      = "tmp-upload-expiration"
      filter_prefix                           = "tmp/"
      expiration_days                         = 7
      abort_incomplete_multipart_upload_days  = 7
    },
    {
      id                                      = "draft-upload-expiration"
      filter_prefix                           = "draft/"
      expiration_days                         = 14
      abort_incomplete_multipart_upload_days  = 7
    },
    {
      id                                      = "review-rejected-expiration"
      filter_prefix                           = "review-rejected/"
      expiration_days                         = 30
      noncurrent_expiration_days              = 7
      abort_incomplete_multipart_upload_days  = 7
    }
  ]
}

variable "enable_replication" {
  description = "Enable cross-region replication for selected prefixes."
  type        = bool
  default     = false
}

variable "create_replica_bucket" {
  description = "Create the destination bucket for replication in Terraform. Set false if you will import or reference an existing bucket."
  type        = bool
  default     = false
}

variable "replica_bucket_name" {
  description = "Destination COS bucket name for replication."
  type        = string
  default     = null
  nullable    = true
}

variable "replica_bucket_region" {
  description = "Destination COS bucket region for replication."
  type        = string
  default     = null
  nullable    = true
}

variable "replica_bucket_acl" {
  description = "ACL for a Terraform-managed replica bucket."
  type        = string
  default     = "private"
}

variable "replica_destination_storage_class" {
  description = "Storage class for replicated objects."
  type        = string
  default     = "Standard"
}

variable "replicate_delete_markers" {
  description = "Replicate delete markers to the destination bucket."
  type        = bool
  default     = false
}

variable "replication_rule_prefixes" {
  description = "Prefixes replicated to the destination bucket."
  type        = list(string)
  default     = ["pg-backup/"]
}

variable "replication_operator_uin" {
  description = "Sub-UIN used in replica_role. Leave null to use the current caller UIN."
  type        = string
  default     = null
  nullable    = true
}

variable "replica_kms_key_id" {
  description = "Destination region KMS key ID used for replicated objects when encryption_algorithm is KMS."
  type        = string
  default     = null
  nullable    = true
}

variable "replica_lifecycle_rules" {
  description = "Optional lifecycle rules for a Terraform-managed replica bucket. When null, the primary lifecycle rules are reused."
  type = list(object({
    id                                      = optional(string)
    filter_prefix                           = string
    expiration_days                         = optional(number)
    expiration_date                         = optional(string)
    noncurrent_expiration_days              = optional(number)
    transitions = optional(list(object({
      storage_class = string
      days          = optional(number)
      date          = optional(string)
    })))
    noncurrent_transitions = optional(list(object({
      storage_class    = string
      non_current_days = number
    })))
    abort_incomplete_multipart_upload_days = optional(number)
  }))
  default  = null
  nullable = true
}

variable "attach_replica_bucket_policy" {
  description = "Manage a private owner-only policy on a Terraform-managed replica bucket."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags to attach to the buckets and KMS key."
  type        = map(string)
  default = {
    project   = "close-shot"
    managedBy = "terraform"
  }
}
