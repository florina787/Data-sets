# Contract: PostgreSQL 16 + pgvector for FLO data products, audit log (dedicated database recommended) and checkpoints.
variable "name" { type = string }
variable "region" { type = string }
variable "instance_class" {
  type    = string
  default = "medium"
}
variable "backup_retention_days" {
  type    = number
  default = 14
  validation {
    condition     = var.backup_retention_days >= 7
    error_message = "FLO requires at least 7 days of point-in-time recovery."
  }
}
variable "extensions" {
  type    = list(string)
  default = ["vector"]
}
output "contract" {
  value = { name = var.name, region = var.region, class = var.instance_class, pitr_days = var.backup_retention_days, extensions = var.extensions,
  encryption_at_rest = true, public_access = false }
}
