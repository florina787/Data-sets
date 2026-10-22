variable "name" { type = string }
variable "region" { type = string }
variable "node_size" {
  type    = string
  default = "small"
}
output "contract" {
  value = { name = var.name, region = var.region, size = var.node_size, tls = true, auth = true, public_access = false }
}
