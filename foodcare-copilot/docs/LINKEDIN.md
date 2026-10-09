# LinkedIn demo script (60–90 seconds) and post

## Demo script

Screen-record at 1440 px wide. Run the guided demo first, so that the delivery records and live campaign orders exist.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:08 | Executive overview | "This is FoodCare Enterprise Copilot, for a fictional food and beverage company. Every number here is synthetic or comes from a local demo system." |
| 0:08–0:22 | Ask Copilot: *"Is there enough apple stock for the Ontario weekend campaign?"* → high risk, PO-55102 arrives too late, assumptions listed, `[S1]` citations | "Ask a question in plain English. The copilot runs read-only queries, and every number it gives you is cited. Here it finds that apple stock runs out before the weekend campaign starts, and shows its assumptions." |
| 0:22–0:32 | *"Which listings have allergen issues?"* → oat milk retail feed missing "oats (gluten)"; then *"What is the weather in Paris?"* → "I can't answer that" | "It checks every channel listing against the approved product record and finds a missing allergen statement. Off-topic questions get 'I don't know', not a guess." |
| 0:32–0:40 | Sales & promotions: uplift chart, Cold Brew revenue in red | "Promotions are measured, not assumed. This discount grew units but lost revenue." |
| 0:40–0:58 | Delivery workspace: clarification gate → failing pytest → same tests passing → engineer approval rejected (403) → approved deployment | "The copilot also runs digital delivery. A marketing brief is clarified before anyone builds. A real test catches a seeded pricing defect, and only a release approver can ship the exact tested commit." |
| 0:58–1:15 | Injected timeout → incident evidence vs hypotheses → rollback → repair → resolved | "When a labelled demo fault breaks checkout, the incident is linked to the release, mitigated by a rollback, and fixed in a reviewed release." |
| 1:15–1:25 | Ask Copilot: *"What happened in the checkout incident?"* | "Ask the copilot afterwards and it explains the incident from the records, keeping facts separate from hypotheses." |

## Post

> I built **FoodCare Enterprise Copilot**, a portfolio prototype of an enterprise copilot for a fictional food and beverage company. All data is synthetic and the payments are mocks.
>
> 💬 **Ask Copilot**: plain-English questions about sales, promotions, inventory, product compliance, releases and policy. Answers come from read-only queries, and every figure is cited. It says "I can't answer that" rather than guessing, and it refuses to take actions.
> 📈 **Measured, not invented**: promotion uplift is computed from the sales history, and one discount turns out to grow units while losing revenue. Stock projections state their assumptions.
> 🥛 **Compliance**: every channel listing is checked against the approved allergen record. The copilot finds a retail feed missing "oats (gluten)".
> 🚀 **Digital delivery with real evidence**: briefs are clarified before building; hash-locked pytest suites catch a seeded defect, then pass on the repaired commit; approvals are bound to the exact commit; a labelled fault drill runs from incident to rollback to verified repair.
>
> Stack: FastAPI, LangGraph (checkpoints and human-in-the-loop), SQLite, React/TypeScript/Vite/Tailwind, pytest, Playwright. Optional Claude mode writes copilot answers from the same facts, with validated citations. The demo runs with no API key.
>
> What it isn't: production software, real company data, or a replacement for analysts and engineers. The docs list the production gaps.
>
> #EnterpriseAI #Copilot #AgenticAI #FoodAndBeverage #LangGraph
