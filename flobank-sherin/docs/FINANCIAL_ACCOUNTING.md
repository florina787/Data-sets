# Financial accounting rules

All money is calculated by one deterministic Python module, `backend/app/finance/engine.py`, using `Decimal`
arithmetic and stored as `NUMERIC(18,2)` in USD. Every chart, KPI card, chat answer and report calls the same
functions, so the same metric always shows the same number. No language-model output ever enters a figure.

## Accounting period

* The default period is the latest closed month (`2026-10` in demo mode). Month, quarter, calendar year and trailing
  twelve months (TTM) are selectable; the API also accepts any custom date range.
* Each KPI card is compared with the **prior period of the same length** (month vs prior month, and so on) and with
  the **budget** for the period. Monthly budgets are pro-rated by days for partial months.
* **Budget utilisation** (actual / budget) is reported separately from expenditure.

## Definitions

| Metric | Formula | Basis |
|---|---|---|
| Bank revenue | Σ ledger revenue lines: net interest income, fees and commissions, trading, wealth fees, other | actual |
| Bank operating expenditure | Σ ledger opex lines, **including** the line "Technology – Sherin AI" | actual |
| Bank operating profit | Bank revenue − Bank operating expenditure | actual |
| AI-assisted workflow cost (per task) | model + compute + infrastructure + tooling + human review + rework | actual |
| Human-equivalent value | baseline hours × loaded hourly rate, **verified tasks only** | estimated |
| Estimated cost avoidance | Human-equivalent value − AI-assisted workflow cost, **verified tasks only** | estimated |
| Unrecovered AI cost | workflow cost of failed / unverified tasks + platform overhead (storage, networking, monitoring, maintenance, subscriptions) | actual |
| Sherin AI operating cost (KPI) | Σ all AI cost records, including human review and allocated implementation | actual |
| Net AI economic benefit | Realized AI-attributed incremental profit + Estimated cost avoidance − Unrecovered AI cost − Allocated implementation cost | estimated |
| AI ROI | Net AI economic benefit ÷ **total Sherin AI cost in the same period** × 100 | estimated |

The net benefit has an equivalent form that the tests check for every period:

```
Net AI economic benefit = incremental profit + human-equivalent value of verified work − total Sherin AI cost
```

Every AI cost is subtracted exactly once.

## Avoiding double counting

1. **Workflow costs are netted once.** Cost avoidance already subtracts the AI-assisted workflow cost of verified
   tasks. Only costs *not* netted there (failed work, platform overhead, implementation) are subtracted afterwards.
2. **Attributed revenue is not additional revenue.** It is a carve-out of the *fees and commissions* ledger line. Only
   its incremental profit (revenue × direct margin, excluding AI costs) enters net benefit. Tests assert that attributed
   revenue never exceeds fee income in any month.
3. **Realized savings are a subset.** Cash savings booked against budgets (for example contractor purchase orders
   that were not renewed) are shown for context. They are never added to cost avoidance. Tests assert realized ≤ avoidance.
4. **The AI cash cost is inside bank opex.** The ledger line "Technology – Sherin AI" equals the AI cost records
   excluding human review, whose staff time already sits inside staff costs. Graph A labels this explicitly.
5. **Cost avoidance is never revenue.** It is labour capacity released, an estimate. It appears only in the
   contribution waterfall and the savings KPI, never in bank revenue or profit.
6. **Never bank revenue:** portfolio assets under management, unrealised portfolio returns and estimated labour
   capacity. The portfolio pages label AUM as "not revenue".

## Attribution assumptions (demo data)

* AI-attributed revenue: difference-in-differences against branches without AI assistance (synthetic). The method is
  stored on every attribution record and shown in the KPI drill-down.
* Incremental profit = attributed revenue × direct margin (33–42%), excluding AI costs, because those are subtracted separately.
* Human baselines are configured by Finance per workflow type (hours × loaded rate) and are editable in Settings.
  Each task stores the baseline in force when it completed, so later edits do not rewrite history.
* Only tasks that pass quality checks **and** the Independent Verification Agent earn cost avoidance. A task a human
  rejected earns nothing.

## Implementation cost

Synthetic programme capex of $1.2M is amortised over 36 months ($33,333.33/month, allocated daily). Break-even in
the forecast compares *cumulative* benefit before amortisation against the full capex outlay. If that point has
already passed, the forecast reports the historical month.

## Token and inference cost

* Paid model: synthetic price card of $3.00/M input, $15.00/M output, $0.30/M cached input.
* Local Qwen via Ollama: no API charge, but **allocated compute** (inference time × $1.10/h amortised GPU/host)
  and **electricity** (inference time × 0.45 kW × $0.16/kWh). Both are configurable.
* Token rows sum exactly to each task's model cost. A test checks every task.

## Currency

* The base currency is USD. INR and CAD are converted at the latest configured rate, with its source, timestamp,
  base and full history (`fx_rates` table, Settings page).
* Every money field is converted at output with the same rate, so a metric agrees across currencies and across
  charts. Ratios (ROI) and counts do not change. Offline demo rates are labelled "Synthetic FX assumption".
* Only `SHERIN_MANAGER` can set a rate. Each change is audited.

## Forecasts

Scenario forecasts (best, base, downside) project trailing six-month trends: a linear revenue trend, task growth,
verification rate, variable AI cost per task, platform overhead and incremental-profit growth. Each scenario
states its multipliers. Every forecast response carries the basis "forecast" and a disclaimer that it is not a
guarantee or management guidance.
