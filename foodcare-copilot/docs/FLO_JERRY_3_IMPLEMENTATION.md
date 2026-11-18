# Flo & Jerry 3.0 implementation map

Where each 3.0 capability lives. Everything runs locally: FastAPI + SQLite backend, React/Vite
frontend, optional local Qwen. No paid or cloud service is added.

| Capability | Backend | Frontend | Doc |
|---|---|---|---|
| Enterprise Pulse, priorities, continuity, lenses | `app/pulse.py` (migration 7) | `screens/Pulse.tsx`, `Priorities.tsx`, `components/pulse/*`, `Layout.tsx` | `CTO_UX_AUDIT.md` |
| Conversation and commands | `app/copilot/router.py`, `engine.py`, `command.py`, `command_ops.py` | `screens/Copilot.tsx` (welcome, answers) | `CONVERSATIONAL_AI_ARCHITECTURE.md` |
| Visual Response Engine | `app/visuals.py` | `components/visuals/VisualRenderer.tsx` | `VISUAL_RESPONSE_SCHEMAS.md` |
| Enterprise X-Ray | `GET /api/xray/{id}` in `app/main.py` | `components/visuals/Actions.tsx` (`XrayPanel`) | `ENTERPRISE_XRAY_ARCHITECTURE.md` |
| Connectors, MCP | `app/connectors.py`, `app/mcp_server.py` | `screens/Connect.tsx` | `MCP_CONNECTOR_ARCHITECTURE.md` |
| Databricks / Kubernetes | `app/connectors.py`; `deploy/k8s/components/jerry-readonly-rbac` | Connect page | `DATABRICKS_INTEGRATION.md`, `KUBERNETES_INTEGRATION.md` |
| Privacy Shield | `app/privacy.py` | policy chips | `PRIVACY_SHIELD.md` |
| Export Studio | `app/exports.py` | `screens/Exports.tsx` | `EXECUTIVE_EXPORT_STUDIO.md` |
| Motion Stories | `app/motion.py`, `command._story` | `Motion` in `VisualRenderer.tsx` | `MOTION_STORIES.md` |
| Defense Command | `app/defense.py` | `screens/Defense.tsx` | `DEFENSE_COMMAND.md` |
| Team Intelligence | `app/portfolio.py` | `screens/Portfolio.tsx` | `TEAM_INTELLIGENCE.md` |
| Guided demo | — (uses Jerry) | `screens/Demo.tsx` | `CTO_SALES_DEMO.md` |

## New API endpoints

`/api/pulse`, `/api/me/lens`, `/api/priorities`, `/api/decisions`, `/api/investigations`,
`/api/copilot/feedback`, `/api/technology`, `/api/reports/weekly`, `/api/reports/history`,
`/mcp`, `/api/connectors`, `/api/connectors/{id}/test`, `/api/exports`, `/api/exports/{kind}.pdf`,
`/api/xray/{agent_run_id}`, `/api/motion/{story}.gif`, `/api/suppliers`, `/api/privacy/policy`,
`/api/defense/{threats,downtime,alerts,licenses,briefing}`, `/api/defense/containment[/preview|/{id}/approve|/{id}/execute]`,
`/api/portfolio`.

## New permissions (`auth.PERMISSIONS`)

`connector.test`, `alert.manage` and `containment.approve` (engineer, release approver);
`containment.propose` (engineer). Nothing existing was widened.

## New dependency

`reportlab==4.2.5` (BSD) for PDFs. Pillow (already present) for GIFs.
