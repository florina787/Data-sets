variable "name" { type = string }
variable "keys" {
  type    = list(string)
  default = ["FLO_DATABASE_URL", "FLO_AUDIT_DATABASE_URL", "FLO_REDIS_URL", "FLO_JWT_SECRET", "FLO_VAULT_KEY", "LANGSMITH_API_KEY", "GEMINI_API_KEY"]
}
variable "rotation_days" {
  type    = number
  default = 90
}
output "contract" { value = { name = var.name, keys = var.keys, rotation_days = var.rotation_days } }
