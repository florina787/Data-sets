# Illustrative AWS implementation (Canada Central). Requires credentials; not applied by this project.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

provider "aws" { region = var.region }

variable "region" {
  type    = string
  default = "ca-central-1"
}
variable "name" {
  type    = string
  default = "flo-demo"
}
variable "db_password" {
  type      = string
  sensitive = true
}

module "network_contract" {
  source = "../../modules/network"
  name   = var.name
  region = var.region
}

resource "aws_vpc" "this" {
  cidr_block           = "10.40.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = var.name, data = "synthetic-demo" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(aws_vpc.this.cidr_block, 4, count.index)
  availability_zone = "${var.region}${count.index == 0 ? "a" : "b"}"
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_kms_key" "data" {
  description         = "FLO data-at-rest key"
  enable_key_rotation = true
}

resource "aws_db_instance" "postgres" {
  identifier                          = "${var.name}-pg"
  engine                              = "postgres"
  engine_version                      = "16"
  instance_class                      = "db.r6g.large"
  allocated_storage                   = 100
  username                            = "flo"
  password                            = var.db_password
  db_subnet_group_name                = aws_db_subnet_group.this.name
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.data.arn
  backup_retention_period             = 14
  multi_az                            = true
  publicly_accessible                 = false
  deletion_protection                 = true
  iam_database_authentication_enabled = true
  skip_final_snapshot                 = false
  final_snapshot_identifier           = "${var.name}-final"
}

resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.name}-redis"
  description                = "FLO cache"
  engine                     = "redis"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = 2
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  automatic_failover_enabled = true
}

resource "aws_secretsmanager_secret" "flo" {
  name       = "${var.name}/app"
  kms_key_id = aws_kms_key.data.arn
}

output "postgres_endpoint" { value = aws_db_instance.postgres.address }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
