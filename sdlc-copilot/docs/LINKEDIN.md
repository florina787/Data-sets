# LinkedIn demo script (60–90 seconds) and post

## Demo script

Screen-record the control room at 1440 px wide. Run the guided demo, or click through by hand using the scenario guide.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:08 | Brief intake, the one-sentence brief | "Marketing asks for a weekend Ontario promo: buy two FreshSip drinks, get one free, once per customer. All of this is synthetic demo data." |
| 0:08–0:18 | Nine clarifications; Q-ONCE flagged as a policy gap; "Try to start implementation" rejected | "Before any code, the platform asks what the brief doesn't say. Once per order, or once per campaign? The policy has no answer, so the server won't start implementation until a decision is recorded." |
| 0:18–0:32 | Quality: the failing pytest output (REG-001, exit code 1) | "The implementation patch, a seeded fixture, is applied to an isolated git worktree. The protected acceptance tests really run, and they catch it: remove the paid drinks and the free one stays in the cart." |
| 0:32–0:42 | Engineering diff → Quality: the same tests pass, exit code 0 | "A candidate fix is applied. The same hash-locked tests run again on the new revision and pass. That's real output, not an animation." |
| 0:42–0:52 | Release center: engineer approval → 403; approver approves the manifest hash; Deploy | "An engineer can't approve. The release approver signs off on the exact commit and manifest hash, and the platform starts that commit as the live local storefront." |
| 0:52–0:58 | Storefront: 2 mango + free orange, $4.98, order paid | "The storefront works: two paid, one free." |
| 0:58–1:12 | Incidents: inject the labelled demo fault, traffic fails, incident with evidence vs hypotheses | "Now I inject a timeout. It's a scripted fault, and the screen says so. Checkouts fail and get recorded. The incident view ties the failures to the release and its diff, and keeps evidence separate from hypotheses." |
| 1:12–1:25 | Rollback; repair release; storefront says "temporarily unavailable" and keeps the cart; clear the fault; incident resolved | "Roll back to last known good, ship a reviewed repair that fails fast and keeps the cart, clear the fault, and the platform verifies recovery." |
| 1:25–1:30 | Overview with measured metrics | "Every step is traceable, from brief to requirement to test to release to incident to repair." |

## Post

> I built **SDLC Copilot**, a portfolio prototype of an agentic delivery workspace for marketing-driven changes. It comes with a small storefront that the platform actually changes, tests, deploys and operates. All the data is synthetic and the payments are mocks.
>
> One brief ("buy 2 FreshSip drinks, get 1 free in Ontario, once per customer") goes through:
>
> 🔎 **Clarification first.** A deterministic analyst flags 9 ambiguities against versioned policy documents. Implementation is blocked server-side until decisions are recorded.
> 🧪 **Real tests on real revisions.** Agents apply patches to an isolated git worktree. A protected, hash-locked pytest suite catches a seeded defect (the free item survives removal of the paid ones), then passes on the repaired commit.
> ✅ **Release gates that mean something.** Evidence must belong to the exact revision. Approval binds to the commit and manifest hash, and an engineer's approval attempt is rejected.
> 🚀 **Local deployment, not a status flag.** The approved commit starts as its own process, with health checks and a last-known-good rollback.
> 🚨 **Incident drill.** An injected (and clearly labelled) inventory timeout causes real failures. The incident view links telemetry to the release diff and separates evidence from hypotheses. A reviewed repair then fails fast, keeps the customer's cart, and recovery is verified.
>
> Stack: FastAPI, LangGraph (SQLite checkpoints and human-in-the-loop interrupts), SQLite, React/TypeScript/Vite/Tailwind, pytest, Playwright. Optional Claude integration for brief analysis with schema-validated output. The demo runs with no API key.
>
> What it isn't: production software, a replacement for engineers, or proof of autonomous root-cause analysis. The fault is scripted, and the docs list the production gaps.
>
> #AgenticAI #SoftwareEngineering #LangGraph #QualityEngineering #DevOps
