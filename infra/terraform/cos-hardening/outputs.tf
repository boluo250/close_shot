output "primary_bucket_name" {
  description = "Primary COS bucket name managed by Terraform."
  value       = tencentcloud_cos_bucket.primary.bucket
}

output "primary_bucket_region" {
  description = "Primary COS bucket region."
  value       = var.bucket_region
}

output "primary_bucket_qcs" {
  description = "Primary COS bucket QCS identifier."
  value       = local.primary_bucket_qcs
}

output "primary_kms_key_id" {
  description = "KMS key ID used by the primary bucket when encryption_algorithm is KMS."
  value       = local.source_kms_key
  sensitive   = true
}

output "replication_destination_bucket" {
  description = "Destination bucket name for replication."
  value       = local.effective_replica_bucket
}

output "replication_destination_qcs" {
  description = "Destination bucket QCS identifier used in replication rules."
  value       = local.effective_replica_bucket_qcs
}

output "replica_role" {
  description = "replica_role value applied to the primary bucket when replication is enabled."
  value       = local.replica_enabled ? local.replica_role : null
}

output "import_commands" {
  description = "Helpful commands for taking over existing buckets and policies."
  value = {
    primary_bucket = "terraform import tencentcloud_cos_bucket.primary ${var.bucket_name}"
    primary_policy = var.attach_bucket_policy ? "terraform import tencentcloud_cos_bucket_policy.primary[0] ${var.bucket_name}" : null
    replica_bucket = var.create_replica_bucket ? "terraform import 'tencentcloud_cos_bucket.replica[0]' ${var.replica_bucket_name}" : null
    replica_policy = var.create_replica_bucket && var.attach_replica_bucket_policy ? "terraform import 'tencentcloud_cos_bucket_policy.replica[0]' ${var.replica_bucket_name}" : null
  }
}

