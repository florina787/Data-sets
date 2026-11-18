variable "name" { type = string }
variable "region" { type = string }
variable "node_count" {
  type    = number
  default = 3
}
output "contract" {
  value = { name = var.name, region = var.region, nodes = var.node_count, pod_security = "restricted", network_policies = true,
  workload_identity = true, private_api = true }
}
