# Integration matrix

The live source of truth is `GET /api/v1/platforms`. "Connected" is only ever shown after a live health check passes.

| Platform | Status | Read | Actions | Verified how |
|---|---|---|---|---|
| Sandbox (simulated multi-cloud) | **Simulated** | resources, status, logs, metrics, traces, deployments, config changes | rollback_deployment, replay_ingestion, rerun_job, refresh_cache, create_ticket | End-to-end tests |
| MCP (stdio servers) | **Implemented** | tool discovery, read tools | none (write tools refused) | Tests against real stdio subprocesses |
| GitHub | **Implemented, not verified live** | repo, workflows, workflow runs | rerun_failed_jobs, create_issue | Mocked HTTP transport only; no token was available |
| Azure DevOps, Azure Monitor, App Insights, AI Foundry, Fabric, Entra ID, Graph, Teams, SharePoint, Power BI, Functions, AKS | Not implemented | n/a | n/a | n/a |
| CloudWatch, Lambda, ECS, EKS, Step Functions, Bedrock, SageMaker, S3, CloudTrail, Cost Explorer, IAM | Not implemented | n/a | n/a | n/a |
| Databricks Jobs, Workflows, MLflow, Mosaic AI, Unity Catalog, SQL, Delta Lake | Not implemented | n/a | n/a | n/a |
| Jenkins, Kubernetes, Jira, Confluence, ServiceNow, Salesforce, Workday | Not implemented | n/a | n/a | n/a |

The Phase 6 priority order is Azure DevOps, then AWS CloudWatch plus one approved AWS action, then Databricks Jobs, then GitHub live verification. Each needs non-production credentials from you.
