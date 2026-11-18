# Cross-functional Team Intelligence

**Operations → Team & delivery portfolio** (`/portfolio`) and Jerry questions such as "What is
Marketing building?", "Which business initiatives are blocked by data engineering?", "Which
projects are exceeding budget?", "What decisions need my approval this week?".
Code: `backend/app/portfolio.py`, `backend/app/copilot/command_ops.py`, `screens/Portfolio.tsx`.

> Synthetic portfolio fixture. Jira / Azure DevOps / GitHub Projects are `simulated`;
> Confluence / SharePoint are `planned`. Owners use synthetic display names.

## Portfolio

14 initiatives across 9 departments (Technology, Marketing, Commercial, Sales, Retail,
Operations, Supply Chain, Finance, People), each with owner, status, progress, milestones,
budget, spend, dependencies and supporting technology. Schedule slip and budget variance are
calculated, not stored (as of 2026-10-31).

The guided example: **Loyalty programme relaunch (Marketing)** is blocked — it depends on
**Promotional pricing governance (Commercial)** approval and on **Loyalty API on Kubernetes** and
**Customer segmentation pipeline (Databricks)** from Technology.

## Business-to-technology mapping

Each link is labelled **verified** (recorded dependency) or **inferred** (dashed in the graph).
Inferred links are never presented as fact.

## Visuals

Department metric tiles · delivery Gantt with milestones (done, overdue, upcoming) and today line ·
dependency graph · budget-used bars (overruns highlighted) · decisions awaiting approval ·
detailed table.

## Privacy

Vendor contract values are banded (e.g. "CAD 150–500k"). Personnel performance ratings exist
in the fixture only as canaries (`CANARY-RATING-*`) and are never output — tested in
`test_portfolio_calculations_and_privacy` and in the browser test.

## Reports

`delivery_board`, `portfolio_weekly`, `project_status`, `tech_dependencies`, `commercial_review`,
`marketing_readiness` (see `EXECUTIVE_EXPORT_STUDIO.md`).
