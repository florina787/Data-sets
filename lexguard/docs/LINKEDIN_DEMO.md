# 90-second demo script

**Setup:** `docker compose up --build` → http://localhost:3000 · signed in as Priya Raman (Senior Associate).

| Time | Action | What to point at |
|---|---|---|
| 0:00 | Open LexGuard. Matter: **Project Maple**. | Left panel: client Maple Industries, Corporate/M&A, *AI use: Permitted with Controls*, risk Medium, human review Required. |
| 0:08 | Ask: *"Review our contracts for change-of-control clauses and compare them against the firm's M&A playbook."* | One Copilot - no agent picker. |
| 0:15 | Read the result. | **MatterGuard ✓ · AI permitted ✓** · 487 documents analysed · **63 clauses · 11 deviations · 3 escalations · 2 evidence issues**. |
| 0:22 | Expand *How LexGuard analyzed this*. | Access → wall → client policy → router → analysis → playbook → citation verification (⚠ 2 issues) → confidentiality → assurance → ○ lawyer approval pending. |
| 0:32 | Click the *Automatic termination* escalation. | Evidence tab: highlighted source clause · citation verification · playbook side-by-side (MA-COC-06: partner escalation). |
| 0:42 | Point at the assurance card. | 99 % **REVIEW REQUIRED** - "measures traceability, not legal correctness"; a missing Schedule 4 and a `[●]` placeholder keep it in review. |
| 0:48 | Approval tab → approve as Priya → refused. Switch to **Eleanor Hart (Partner)** → approve. | Escalations need a partner. |
| 0:56 | Audit tab. | **User → Matter → Policy → Workflow → Evidence → AI Output → Assurance → Lawyer Approval** - hash-chained. |
| 1:04 | Open **ValueIQ**. | Net hours saved and productivity improvement - labelled synthetic estimates. |
| 1:12 | Switch matter to **Project Aurora**. Click *"Send these documents to the external legal AI provider for analysis."* | **BLOCKED** - NorthStar prohibits external GenAI (POL-CLIENT-003), internal alternative offered, audit event logged, nothing sent. |
| 1:22 | Closing line. | |

**Closing statement:**

> "LexGuard isn't another legal chatbot.
> The Copilot is the user experience.
> A governed multi-agent architecture handles reasoning and orchestration.
> Deterministic controls enforce matter security and AI policy.
> RAG provides evidence.
> External legal-AI platforms provide optional execution.
> The lawyer remains the final decision-maker."

*All data is synthetic. Demo mode uses no API key and makes zero paid LLM calls.*
