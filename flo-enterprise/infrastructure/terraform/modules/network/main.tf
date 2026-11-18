# Contract: a private network for FLO. Implementations live per provider (see examples/).
variable "name" { type = string }
variable "region" { type = string }
variable "cidr" {
  type    = string
  default = "10.40.0.0/16"
}
variable "egress_allowlist" {
  type        = list(string)
  description = "FQDNs FLO workloads may reach (e.g. model provider endpoint in an approved region)."
  default     = []
}
output "contract" {
  value = { name = var.name, region = var.region, cidr = var.cidr, egress_allowlist = var.egress_allowlist }
}
