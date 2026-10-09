# Scenario guide

## Enterprise copilot tour (2 minutes)

1. Open <http://127.0.0.1:8700>. The **Executive overview** shows revenue and units (synthetic, last 4 weeks vs prior), stock alerts, listing-compliance issues, live storefront orders and a "needs attention" list.
2. Sign in as any account (the viewer is fine) and click **Ask Copilot for a briefing**. The drawer answers with `[S1]`-style citations; click a citation to highlight its source, or open *How this was answered* to see the tools that were called.
3. Ask:
   * *"Is there enough apple stock for the Ontario weekend campaign?"* gives a high risk for FreshSip Apple at DC-TOR (stock-out before the start; PO-55102 arrives after the weekend), with the forecast assumptions listed.
   * *"Which listings have allergen issues?"* finds NutriTerra Oat Milk on the retail feed missing "oats (gluten)": critical.
   * *"How did past promotions perform?"* shows the multi-buy in Quebec had the strongest unit uplift, while Cold Brew Mornings grew units but lost revenue to the discount.
   * *"What does the returns policy say about partial returns?"* cites POL-RET v2.0 §2–3.
   * *"What is the weather in Paris?"* gets "I can't answer that from FoodCare's data". *"Approve the release"* gets "I'm read-only".
4. **Sales & promotions**, **Inventory** and **Product compliance** show the same figures as charts and tables (every chart has a *Show table* toggle).
5. Run the guided demo (below) and ask *"How is the Ontario weekend campaign doing so far?"*. The answer now includes the real orders placed on the deployed storefront.

## Delivery workspace


Start with `scripts/start.sh` and open <http://127.0.0.1:8700>. You can run everything below with **Run Guided Demo** (about 40 s, 13 checked steps) or click it through by hand. Switch roles with the **Signed in as** picker in the header.

## Seeded rules (selected demo decisions)

The brief deliberately leaves out SKUs, stacking, returns, dates, timezone, identity and the scope of "once per customer". The seeded answers, each labelled *Selected demo decision*, are:

| ID | Decision |
|---|---|
| Q-ONCE | Once per **authenticated customer per campaign** (policy gap: POL-PROMO §5 defines no default) |
| Q-SKU | FS-MANGO-355, FS-ORANGE-355, FS-APPLE-355 only (Sparkling Lime excluded, REC-PROD §2) |
| Q-DATES / Q-TZ | Sat 2026-10-31 00:00 → Mon 2026-11-02 00:00 (end exclusive), America/Toronto = 04:00Z → 05:00Z. The window spans the end of DST. |
| Q-PROVINCE | Shipping province ON (not browser location) |
| Q-STACK | No stacking with discount codes, in either order |
| Q-RETURNS | Seeded POL-RET v2.0: a full cancellation restores the entitlement; a partial return refunds the amount allocated to the unit at order time (2 × $2.49 = $4.98 spread over 3 units = $1.66 each); units outside the promotion group are returned first |
| Q-IDENTITY | Signed-in customer only (the demo uses synthetic customer fixtures) |
| Q-PRICE | All eligible SKUs cost $2.49. **Documented simplification**: mixed-price behaviour is not generalised |

The demo clock is fixed at 2026-10-31 12:00 EDT, inside the window, so real dates never break the walkthrough. Inventory is reserved when the order is created. Quotes consume nothing. A mock payment failure releases the reservation and the redemption. Checkout is idempotent by key.

## Manual walkthrough

1. **Brief intake** (Maya, marketing). Submit the prefilled brief (DEMO mode). Nine clarifications appear, three of them flagged as **policy gaps**, each with its retrieved source sections.
2. **Episode A.** Sign in as Eli and click **Try to start implementation**. The server rejects it with the list of open decisions, and the rejection is audited. As Maya, click **Apply seeded demo decisions** (or record your own), then **Continue workflow**. Requirement set v1 is drafted: 8 requirements, 16 ACs.
3. **Requirements** (Omar, product owner). **Approve v1**. This freezes the SHA-256 hashes of the acceptance-test files.
4. **Delivery board.** Click **Continue**. Design → patch 01 in an isolated worktree → pytest (exit 1, REG-001 fails) → repair patch 02 → the same tests pass (exit 0) → ruff and scan → gates → waits for release approval. Pause and Step mode stop the run between agent steps.
5. **Episode B evidence.**
   * **Quality** shows both test runs (failed, then passed, on different revisions) with full pytest output.
   * **Engineering** shows the real `git diff` of each change set, labelled *Fixture proposal*.
   * **Requirements** shows each AC linked to tests on each revision.
6. **Release center.**
   * As Eli, **Approve manifest**. The server rejects it (403, audited).
   * As Rina, **Approve manifest**. The approval binds to the exact SHA and manifest hash.
   * **Deploy to local storefront** starts a new process; see the PID and lifecycle in the deployments table.
7. **Storefront** (<http://127.0.0.1:8801>). Choose *Amara (demo)*, add 2 Mango, ship to ON, **Add free unit**. Remove one Mango and the free unit disappears. Add it back and claim again: the total is $4.98. Place the order. Try Cancel, or Return one unit, to see the allocated refunds.
8. **Episode C** (Incidents, Eli).
   1. **Inject inventory timeout** (labelled demo fault).
   2. **Send synthetic shopper traffic**: real checkouts fail with 500 after about 4 s.
   3. **Analyse telemetry**: the incident links to the release, with evidence (telemetry, dependency latency, fault control, release diff) shown separately from hypotheses (H1 `timeout=None` in the new reservation call; H2 injected slow dependency). The disclaimer says it is a scripted fault demonstration.
9. **Mitigate.** As Rina, **Roll back to last-known-good**. The baseline v1.0 fails fast with 503 and keeps the cart.
10. **Repair.**
    1. As Omar, **Approve v2**. It adds REQ-9 and the regression REG-002.
    2. On the board, click **Continue**. The incident flow runs suite v2 on the released revision (fails), applies patch 03 and re-tests (passes).
    3. As Rina, approve and deploy the repair release.
    4. The flow verifies fail-fast under the fault (incident *mitigated*).
11. **Recover.** As Eli, **Clear injected fault**. The waiting incident flow resumes, sends traffic, sees successful orders and marks the incident *resolved*.

**Reset Demo** (header) wipes `var/` and redeploys the baseline. The reset recreates the accounts, so sign in again afterwards.

## Secondary scenario templates (preview only)

The **Scenario templates** screen shows reusable brief, clarification, requirement and test-plan templates. **None of them is implemented as an application.**

| Template | Focus |
|---|---|
| QR loyalty redemption | duplicate scans, invalid codes, rate limits |
| Multilingual campaign page | missing translations, text overflow |
| Campaign expiry | cache invalidation, timezone and DST boundaries |
| Product information update | ingredients and allergens match the approved record |
| Delivery promotion | landing-page promise matches fulfilment eligibility |
