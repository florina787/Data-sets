# Terraform reference modules (provider-neutral contract + one example)

FLO does **not** assume any cloud provider. `modules/` defines the *contract* each platform team implements
(inputs/outputs), and `examples/aws-ca-central-1/` is one illustrative implementation of that contract
(Canadian region, to satisfy the `tenant_residency: CA` policy). Azure (Canada Central) or GCP
(northamerica-northeast1) implementations follow the same module interfaces.

| Module | Provides | Must guarantee |
|---|---|---|
| `network` | private subnets, egress control | no public DB/cache endpoints; egress allowlist |
| `postgres` | PostgreSQL 16 with `vector` extension | encryption at rest, PITR backups >= 7 days, private access, IAM/short-lived auth |
| `redis` | Redis 7 | TLS in transit, AUTH, private access |
| `secrets` | secret store entries | rotation; workload-identity access only |
| `kubernetes` | cluster + workload identity | pod security `restricted`, network policies, private API |

Status: reference only — `terraform validate`-level checks; never applied against a real account in this project.
