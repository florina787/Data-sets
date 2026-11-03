"""Deterministic synthetic FLO Bank environment.

Everything written here has data_class="synthetic". The generator is built so the books reconcile:
  * every workflow-linked AI cost record is derived 1:1 from an AgentTask cost field;
  * every token-usage row's cost sums exactly to its task's cost_model;
  * the bank ledger line "technology_sherin_ai" equals that day's AI cash costs (all AI cost records except
    human review, whose staff time already sits inside "staff" costs);
  * AI-attributed revenue is carved out of the "fees_commissions" ledger line, never added on top of it.
"""
from __future__ import annotations

import calendar
import datetime as dt
import math
import random
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, insert

from app import catalog as C
from app import models as M
from app.config import get_settings
from app.db import create_all, session_scope

CENT = Decimal("0.01")
MICRO = Decimal("0.000001")


def q(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def q6(x) -> Decimal:
    return Decimal(str(x)).quantize(MICRO, rounding=ROUND_HALF_UP)


def month_range(end_month: str, n: int) -> list[str]:
    y, m = map(int, end_month.split("-"))
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def days_of(period: str) -> list[dt.date]:
    y, m = map(int, period.split("-"))
    return [dt.date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def local_inference_cost(latency_ms: int) -> tuple[Decimal, Decimal]:
    s = get_settings()
    hours = Decimal(latency_ms) / Decimal(3_600_000)
    compute = hours * Decimal(str(s.local_gpu_hourly_usd))
    energy = hours * Decimal(str(s.local_power_kw)) * Decimal(str(s.electricity_usd_per_kwh))
    return q6(compute), q6(energy)


def paid_inference_cost(inp: int, out: int, cached: int) -> Decimal:
    p = C.PAID_PRICE_PER_M
    return q6((Decimal(inp - cached) * p["input"] + Decimal(cached) * p["cached"] + Decimal(out) * p["output"]) / Decimal(1_000_000))


TASK_TITLES = {
    "python_development": ["Fix KeyError in settlement batch parser", "Refactor FX rounding helper", "Add type hints to ledger loader",
                           "Debug flaky pandas merge in NAV job", "Patch timezone bug in coupon scheduler"],
    "azure_devops": ["Repair failing build pipeline for payments-api", "Diagnose ADO release gate timeout", "Review pipeline YAML for caching",
                     "Draft PR: bump Python base image", "Analyse repo for stale service connections"],
    "portfolio_reconciliation": ["Reconcile custodian vs book positions", "Investigate cash break on fund FLO-GRW", "Match corporate action entitlements"],
    "qa_testing": ["Generate regression tests for loan calculator", "Build test plan for KYC refresh", "Triage failed nightly UI suite"],
    "investment_risk_analysis": ["Concentration review for proposed bond buy", "Liquidity stress for balanced fund", "Pre-trade check on equity rebalance"],
    "compliance_reporting": ["Draft monthly conduct-risk MI", "Prepare suitability exceptions report", "Collate AML alert closure evidence"],
    "incident_investigation": ["Investigate AKS pod restarts in pricing", "Root-cause ADF copy failure", "Azure Functions cold-start latency spike",
                               "App Insights 5xx surge on mobile gateway"],
    "data_engineering": ["Fix schema drift in transactions feed", "Backfill missing FX ticks", "Optimise ADF pipeline partitioning"],
    "executive_reporting": ["Compile board pack AI value section", "Monthly CFO cost dashboard narrative", "Quarterly risk appetite summary"],
    "esg_review": ["Validate ESG scores for new issuers", "Exclusion list screen for green fund"],
    "security_review": ["Secrets scan on infra repo", "Review Key Vault access policies", "Assess NSG rules on AKS subnet"],
    "finops_review": ["Explain AI spend variance", "Right-size inference node pool", "Token budget review by agent"],
}

AGENT_WEIGHTS = {"python_coding": 14, "azure_devops": 9, "cicd": 9, "sre": 9, "data_engineering": 8, "portfolio_management": 9,
                 "investment_judgment": 5, "risk_analytics": 6, "esg": 4, "compliance": 7, "qa": 9, "reporting": 5,
                 "security": 4, "finops": 3}

TOKEN_PROFILE = {  # (input mean, output mean, minutes of agent time mean)
    "python_development": (60_000, 9_000, 14), "azure_devops": (45_000, 6_000, 11), "portfolio_reconciliation": (30_000, 3_500, 7),
    "qa_testing": (50_000, 11_000, 12), "investment_risk_analysis": (35_000, 5_000, 8), "compliance_reporting": (55_000, 12_000, 13),
    "incident_investigation": (70_000, 6_500, 15), "data_engineering": (48_000, 7_000, 12), "executive_reporting": (40_000, 10_000, 10),
    "esg_review": (25_000, 3_000, 6), "security_review": (38_000, 4_000, 9), "finops_review": (22_000, 3_000, 5),
}


def seed(scale: float = 1.0, reset: bool = True) -> dict:
    s = get_settings()
    rng = random.Random(s.seed)
    create_all()
    months = month_range(s.demo_end_month, s.demo_months)
    all_days = [d for p in months for d in days_of(p)]
    counts: dict[str, int] = {}

    with session_scope() as db:
        if reset:
            for tbl in [M.TokenUsage, M.AiCostRecord, M.Approval, M.AuditLog, M.Incident, M.AgentTask, M.LedgerLine, M.Budget,
                        M.RevenueAttribution, M.RealizedSaving, M.TradeProposal, M.PortfolioTransaction, M.Position, M.Portfolio,
                        M.HumanBaseline, M.FxRate, M.ComplianceEvent, M.SystemMetricDaily, M.Message, M.Conversation, M.HarnessRun]:
                db.execute(delete(tbl))

        # ---- FX (synthetic assumptions, with history) --------------------------------------------------
        fx_rows = []
        for i, p in enumerate(months):
            y, m = map(int, p.split("-"))
            ts = dt.datetime(y, m, 1, 9, 0)
            fx_rows.append(dict(base="USD", quote="INR", rate=Decimal(str(round(83.2 + 0.09 * i + rng.uniform(-0.2, 0.2), 4))),
                                source="Synthetic FX assumption (offline demo)", as_of=ts, data_class="synthetic"))
            fx_rows.append(dict(base="USD", quote="CAD", rate=Decimal(str(round(1.355 + 0.002 * i + rng.uniform(-0.006, 0.006), 4))),
                                source="Synthetic FX assumption (offline demo)", as_of=ts, data_class="synthetic"))
        db.execute(insert(M.FxRate), fx_rows)

        # ---- Human baselines --------------------------------------------------------------------------
        db.execute(insert(M.HumanBaseline), [
            dict(workflow_type=k, department=v[0], label=v[1], hours_per_task=Decimal(v[2]), hourly_rate_usd=Decimal(v[3]),
                 source="Synthetic baseline: FLO Bank time-and-motion study assumptions (demo)", data_class="synthetic",
                 configured_by="finance.controller", updated_at=dt.datetime(2025, 9, 1))
            for k, v in C.WORKFLOW_BASELINES.items()])
        baselines = {k: (Decimal(v[2]), Decimal(v[3]), v[0]) for k, v in C.WORKFLOW_BASELINES.items()}

        # ---- Agent tasks, token usage, workflow cost records ---------------------------------------------
        agents = list(AGENT_WEIGHTS)
        weights = [AGENT_WEIGHTS[a] for a in agents]
        tasks, tokens, costs = [], [], []
        n_days = len(all_days)
        tid = 0
        for di, day in enumerate(all_days):
            frac = di / max(1, n_days - 1)
            weekday = day.weekday() < 5
            mean = (8 + 32 * frac) * (1.0 if weekday else 0.35) * scale
            n = max(0, int(rng.gauss(mean, math.sqrt(max(mean, 1)))))
            local_share = 0.45 + 0.25 * frac          # cost optimisation: more work moves to local Qwen
            fail_rate = 0.08 - 0.04 * frac
            for _ in range(n):
                tid += 1
                agent = rng.choices(agents, weights)[0]
                wf = C.AGENTS[agent]["workflow"]
                hours, rate, dept = baselines[wf]
                inp_mu, out_mu, min_mu = TOKEN_PROFILE[wf]
                created = dt.datetime.combine(day, dt.time(rng.randint(7, 20), rng.randint(0, 59), rng.randint(0, 59)))
                duration_s = max(60, int(rng.gauss(min_mu * 60, min_mu * 15)))
                failed = rng.random() < fail_rate
                quality = (not failed) and rng.random() < (0.90 + 0.06 * frac)
                verified = quality and rng.random() < 0.975
                retries = rng.choices([0, 1, 2, 3], [70, 20, 7, 3])[0] + (1 if failed else 0)
                review_min = Decimal(str(round(max(5, rng.gauss(18, 6)), 1)))
                rework_min = Decimal(str(round(max(0, rng.gauss(30, 12)), 1))) if (not quality or rng.random() < 0.2) else Decimal("0")
                task_id = f"T{tid:06d}"

                # Primary agent model calls (1-3) + independent verification call.
                calls = []
                for _c in range(rng.choice([1, 1, 2, 3])):
                    calls.append((agent, int(rng.gauss(inp_mu, inp_mu * 0.3) * (1 + 0.3 * retries)), int(rng.gauss(out_mu, out_mu * 0.3))))
                calls.append(("verification", int(rng.gauss(12_000, 3_000)), int(rng.gauss(1_200, 300))))
                cost_model = Decimal(0)
                for a, inp, out in calls:
                    inp, out = max(inp, 800), max(out, 120)
                    local = rng.random() < local_share
                    if local:
                        lat = int(out / rng.uniform(22, 38) * 1000 + inp / 900 * 1000)
                        lc, le = local_inference_cost(lat)
                        api, cached = Decimal("0"), 0
                        prov, model = "local_qwen", C.LOCAL_MODEL
                    else:
                        lat = int(out / rng.uniform(55, 90) * 1000 + 400)
                        cached = int(inp * rng.uniform(0.0, 0.45))
                        api = paid_inference_cost(inp, out, cached)
                        lc, le = Decimal("0"), Decimal("0")
                        prov, model = "paid_api", C.PAID_MODEL
                    cost_model += api + lc + le
                    tokens.append(dict(ts=created, agent=a, task_id=task_id, provider=prov, model=model, input_tokens=inp, output_tokens=out,
                                       cached_tokens=cached, api_cost_usd=api, local_compute_usd=lc, local_energy_usd=le,
                                       latency_ms=lat, success=not failed, data_class="synthetic"))
                # cost_model stays at 6dp in token rows; the task carries the 2dp total and the remainder is assigned
                # to the last token row so the rows sum exactly to the task figure.
                cm2 = q(cost_model)
                diff = cm2 - cost_model
                last = tokens[-1]
                if last["provider"] == "paid_api":
                    last["api_cost_usd"] = q6(last["api_cost_usd"] + diff)
                else:
                    last["local_compute_usd"] = q6(last["local_compute_usd"] + diff)

                compute = q(rng.uniform(0.04, 0.55) * (duration_s / 600))
                infra = q(rng.uniform(0.08, 0.70))
                tooling = q(rng.uniform(0.02, 0.35))
                review_cost = q(review_min / 60 * rate)
                rework_cost = q(rework_min / 60 * rate)
                title = rng.choice(TASK_TITLES[wf])
                tasks.append(dict(id=task_id, run_id=None, agent=agent, department=dept, workflow_type=wf, title=title, created_at=created,
                                  duration_s=duration_s, status="failed" if failed else "succeeded", quality_pass=quality, verified=verified,
                                  retries=retries, tool_calls=rng.randint(2, 14), human_review_min=review_min, rework_min=rework_min,
                                  cost_model=cm2, cost_compute=compute, cost_infra=infra, cost_tooling=tooling, cost_human_review=review_cost,
                                  cost_rework=rework_cost, baseline_hours=hours, baseline_rate_usd=rate,
                                  summary=f"{C.AGENTS[agent]['label']}: {title}", data_class="synthetic"))
                for cat, sub, amt, vendor in [("llm_inference", "model calls", cm2, "mixed"), ("compute", "agent runtime", compute, "Azure Container Apps"),
                                              ("azure_infrastructure", "workflow infra", infra, "Azure"), ("third_party_tools", "per-task tooling", tooling, "tool APIs"),
                                              ("human_review", "review", review_cost, "internal staff"), ("human_review", "rework", rework_cost, "internal staff")]:
                    if amt > 0:
                        costs.append(dict(date=day, category=cat, subcategory=sub, agent=agent, task_id=task_id, amount_usd=amt,
                                          description=f"{task_id} {title}"[:240], vendor=vendor, basis="actual", data_class="synthetic"))

        # ---- Platform overhead and implementation allocation (not linked to any task) --------------------
        monthly_impl = (C.IMPLEMENTATION_CAPEX_USD / C.IMPLEMENTATION_AMORTISATION_MONTHS).quantize(CENT)
        for p in months:
            ds = days_of(p)
            per_day = (monthly_impl / len(ds)).quantize(CENT)
            for i, day in enumerate(ds):
                frac = all_days.index(day) / max(1, n_days - 1)
                amt = per_day if i < len(ds) - 1 else monthly_impl - per_day * (len(ds) - 1)
                costs.append(dict(date=day, category="implementation_allocated", subcategory="amortisation", agent=None, task_id=None,
                                  amount_usd=amt, description=f"Implementation capex {C.IMPLEMENTATION_CAPEX_USD} over {C.IMPLEMENTATION_AMORTISATION_MONTHS} months",
                                  vendor="programme", basis="actual", data_class="synthetic"))
                for cat, base, grow, vendor in [("storage", 35, 40, "Azure Blob / Postgres"), ("networking", 22, 20, "Azure networking"),
                                                ("monitoring", 28, 30, "Azure Monitor / App Insights"), ("maintenance", 140, 60, "platform engineering")]:
                    costs.append(dict(date=day, category=cat, subcategory="platform", agent=None, task_id=None,
                                      amount_usd=q(rng.uniform(0.85, 1.15) * (base + grow * frac) * scale ** 0.5),
                                      description=f"Daily {C.AI_COST_CATEGORIES[cat].lower()}", vendor=vendor, basis="actual", data_class="synthetic"))
            costs.append(dict(date=ds[0], category="third_party_tools", subcategory="subscriptions", agent=None, task_id=None,
                              amount_usd=q(3800 * scale ** 0.5), description="Monthly tool subscriptions (code search, vector DB, eval)",
                              vendor="SaaS", basis="actual", data_class="synthetic"))

        # ---- Bank ledger (revenue and opex), with Sherin AI cash cost as its own opex line ---------------
        ai_cash_by_day: dict[dt.date, Decimal] = {}
        for c in costs:
            if c["category"] != "human_review":
                ai_cash_by_day[c["date"]] = ai_cash_by_day.get(c["date"], Decimal(0)) + c["amount_usd"]
        ledger = []
        rev_mix = {"net_interest_income": 0.60, "fees_commissions": 0.22, "trading_income": 0.10, "wealth_management_fees": 0.06, "other_income": 0.02}
        opex_mix = {"staff": 0.56, "technology": 0.17, "premises": 0.08, "marketing": 0.05, "professional_services": 0.07, "other_opex": 0.07}
        for di, day in enumerate(all_days):
            frac = di / max(1, n_days - 1)
            season = 1 + 0.04 * math.sin(2 * math.pi * (day.month - 1) / 12)
            wk = 1.0 if day.weekday() < 5 else 0.55
            rev_day = 1_400_000 * (1 + 0.11 * frac) * season * wk
            opex_day = 900_000 * (1 + 0.06 * frac) * wk
            for k, w in rev_mix.items():
                vol = 0.35 if k == "trading_income" else 0.06
                ledger.append(dict(date=day, kind="revenue", category=k, amount_usd=q(rev_day * w * rng.uniform(1 - vol, 1 + vol)),
                                   basis="actual", data_class="synthetic"))
            for k, w in opex_mix.items():
                ledger.append(dict(date=day, kind="opex", category=k, amount_usd=q(opex_day * w * rng.uniform(0.95, 1.05)),
                                   basis="actual", data_class="synthetic"))
            ledger.append(dict(date=day, kind="opex", category="technology_sherin_ai", amount_usd=ai_cash_by_day.get(day, Decimal(0)),
                               basis="actual", data_class="synthetic"))

        # ---- Budgets ------------------------------------------------------------------------------------
        rev_month: dict[str, Decimal] = {}
        opex_month: dict[str, Decimal] = {}
        fees_month: dict[str, Decimal] = {}
        for r in ledger:
            p = r["date"].strftime("%Y-%m")
            if r["kind"] == "revenue":
                rev_month[p] = rev_month.get(p, Decimal(0)) + r["amount_usd"]
                if r["category"] == "fees_commissions":
                    fees_month[p] = fees_month.get(p, Decimal(0)) + r["amount_usd"]
            else:
                opex_month[p] = opex_month.get(p, Decimal(0)) + r["amount_usd"]
        ai_month: dict[str, Decimal] = {}
        for c in costs:
            p = c["date"].strftime("%Y-%m")
            ai_month[p] = ai_month.get(p, Decimal(0)) + c["amount_usd"]
        budgets = []
        for i, p in enumerate(months):
            budgets.append(dict(period=p, scope="bank_revenue", amount_usd=q(rev_month[p] * Decimal(str(rng.uniform(0.97, 1.03)))), data_class="synthetic"))
            budgets.append(dict(period=p, scope="bank_opex", amount_usd=q(opex_month[p] * Decimal(str(rng.uniform(0.98, 1.04)))), data_class="synthetic"))
            budgets.append(dict(period=p, scope="ai_cost", amount_usd=q(ai_month[p] * Decimal(str(rng.uniform(0.92, 1.12)))), data_class="synthetic"))

        # ---- AI revenue attribution (subset of fee income) and realized savings ----------------------------
        attributions, realized = [], []
        for i, p in enumerate(months):
            frac = i / max(1, len(months) - 1)
            for wf, dept, share, margin in [("Mortgage document processing turnaround", "portfolio_operations", 0.010, 0.38),
                                            ("Wealth rebalancing proposals issued same day", "risk_management", 0.007, 0.42),
                                            ("SME onboarding KYC packs", "compliance", 0.004, 0.33)]:
                rev = q(fees_month[p] * Decimal(str(share * (0.3 + 0.9 * frac) * rng.uniform(0.85, 1.15))))
                attributions.append(dict(period=p, workflow=wf, department=dept, revenue_category="fees_commissions", attributed_revenue_usd=rev,
                                         incremental_profit_usd=q(rev * Decimal(str(margin))),
                                         method="Synthetic: difference-in-differences vs. non-assisted control branches; profit = revenue x direct margin, excluding AI costs",
                                         realized=True, data_class="synthetic"))
        # realized savings are bounded later (after verified avoidance is known) to stay a strict subset
        avoid_month_dept: dict[tuple[str, str], Decimal] = {}
        for t in tasks:
            if t["verified"]:
                p = t["created_at"].strftime("%Y-%m")
                wc = t["cost_model"] + t["cost_compute"] + t["cost_infra"] + t["cost_tooling"] + t["cost_human_review"] + t["cost_rework"]
                k = (p, t["department"])
                avoid_month_dept[k] = avoid_month_dept.get(k, Decimal(0)) + q(t["baseline_hours"] * t["baseline_rate_usd"]) - wc
        for (p, dept), amt in sorted(avoid_month_dept.items()):
            if amt > 0:
                realized.append(dict(period=p, department=dept, amount_usd=q(amt * Decimal(str(rng.uniform(0.15, 0.35)))),
                                     evidence="Synthetic: contractor purchase orders not renewed / overtime avoided", data_class="synthetic"))

        # ---- Bulk insert --------------------------------------------------------------------------------
        def chunked(model, rows, size=5000):
            for i in range(0, len(rows), size):
                db.execute(insert(model), rows[i:i + size])
        chunked(M.LedgerLine, ledger)
        chunked(M.Budget, budgets)
        chunked(M.AgentTask, tasks)
        chunked(M.TokenUsage, tokens)
        chunked(M.AiCostRecord, costs)
        chunked(M.RevenueAttribution, attributions)
        chunked(M.RealizedSaving, realized)
        counts.update(ledger=len(ledger), tasks=len(tasks), tokens=len(tokens), ai_costs=len(costs), attributions=len(attributions))

        # ---- Portfolios, positions, transactions, proposals -------------------------------------------
        _seed_portfolios(db, rng, months)
        _seed_ops(db, rng, all_days, tasks)
        counts["months"] = len(months)
    return counts


# (issuer, sector, asset class, country, rating, ESG score, annualised volatility) - fixed so holdings comply with mandates.
ISSUERS = [("Northwind Utilities", "Utilities", "equity", "CA", "A", 78, 0.17), ("Contoso Energy", "Energy", "equity", "US", "BBB", 38, 0.31),
           ("Fabrikam Health", "Healthcare", "equity", "US", "A", 72, 0.19), ("Tailspin Airlines", "Industrials", "equity", "CA", "BB", 52, 0.36),
           ("Woodgrove Financial", "Financials", "equity", "US", "A", 66, 0.22), ("Adatum Semiconductors", "Technology", "equity", "US", "A", 71, 0.29),
           ("Litware Software", "Technology", "equity", "IN", "BBB", 61, 0.26), ("Proseware Telecom", "Communication", "equity", "IN", "BBB", 55, 0.21),
           ("Govt of Canada 2031", "Sovereign", "bond", "CA", "AAA", 80, 0.035), ("US Treasury 2030", "Sovereign", "bond", "US", "AAA", 70, 0.03),
           ("KfW Bund 2030", "Sovereign", "bond", "DE", "AAA", 82, 0.03), ("Govt of India 2033", "Sovereign", "bond", "IN", "BBB", 58, 0.05),
           ("Relecloud Green Bond 2029", "Utilities", "bond", "US", "A", 88, 0.05), ("Alpine Ski House Credit", "Consumer", "bond", "CA", "BB", 47, 0.09),
           ("Coho Vineyard", "Consumer", "equity", "US", "BBB", 63, 0.2), ("Trey Research Pharma", "Healthcare", "equity", "IN", "BBB", 59, 0.24),
           ("Wide World Importers", "Industrials", "equity", "US", "BBB", 50, 0.22)]

RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]

PORTFOLIOS = [
    ("PF-BAL", "FLO Balanced Growth Fund", 480e6, {"allowed_asset_classes": ["equity", "bond", "cash"], "max_issuer_pct": 10.0, "max_sector_pct": 30,
                                                  "min_esg_score": 40, "max_liquidity_days": 5, "min_rating": "BBB", "restricted_issuers": ["Tailspin Airlines"],
                                                  "max_portfolio_vol": 0.20, "material_trade_usd": 2_000_000}, "pm.ananya",
     {"Adatum Semiconductors": 0.076, "Woodgrove Financial": 0.05}),
    ("PF-GRN", "FLO Green Income Fund", 210e6, {"allowed_asset_classes": ["bond", "equity", "cash"], "max_issuer_pct": 20.0, "max_sector_pct": 35,
                                                "min_esg_score": 65, "max_liquidity_days": 7, "min_rating": "A", "restricted_issuers": ["Contoso Energy"],
                                                "excluded_sectors": ["Energy"], "max_portfolio_vol": 0.15, "material_trade_usd": 1_000_000}, "pm.liam",
     {"Relecloud Green Bond 2029": 0.12}),
    ("PF-TRS", "FLO Treasury Liquidity Book", 900e6, {"allowed_asset_classes": ["bond", "cash"], "max_issuer_pct": 50, "max_sector_pct": 100,
                                                      "min_esg_score": 0, "max_liquidity_days": 2, "min_rating": "AA", "restricted_issuers": [],
                                                      "max_portfolio_vol": 0.05, "material_trade_usd": 10_000_000}, "treasury.raj", {}),
]


def _eligible(mandate: dict) -> list[tuple]:
    out = []
    for i in ISSUERS:
        name, sector, ac, _c, rating, esg, _v = i
        if ac not in mandate["allowed_asset_classes"] or name in mandate.get("restricted_issuers", []) or sector in mandate.get("excluded_sectors", []):
            continue
        if RATING_ORDER.index(rating) > RATING_ORDER.index(mandate["min_rating"]) or esg < mandate.get("min_esg_score", 0):
            continue
        out.append(i)
    return out


def _seed_portfolios(db, rng: random.Random, months: list[str]):
    for pid, name, total, mandate, mgr, fixed in PORTFOLIOS:
        db.add(M.Portfolio(id=pid, name=name, mandate=mandate, manager=mgr, data_class="synthetic"))
    db.flush()
    for pid, _n, total, mandate, _m, fixed in PORTFOLIOS:
        pool = _eligible(mandate)
        cash_w = 0.03 if pid != "PF-TRS" else 0.05
        free = [i for i in pool if i[0] not in fixed]
        rest = 1 - cash_w - sum(fixed.values())
        noise = [rng.uniform(0.92, 1.08) for _ in free]
        weights = {i[0]: rest * n / sum(noise) for i, n in zip(free, noise)}
        weights.update(fixed)
        for issuer, sector, ac, country, rating, esg, vol in pool:
            db.add(M.Position(portfolio_id=pid, issuer=issuer, sector=sector, asset_class=ac, country=country, market_value_usd=q(total * weights[issuer]),
                              esg_score=Decimal(str(esg)), liquidity_days=Decimal(str(round(rng.uniform(0.2, 1.5 if ac == "bond" else 2.5), 2))),
                              rating=rating, volatility=Decimal(str(vol))))
        db.add(M.Position(portfolio_id=pid, issuer="Cash", sector="Cash", asset_class="cash", country="US", market_value_usd=q(total * cash_w),
                          esg_score=None, liquidity_days=Decimal("0"), rating="AAA", volatility=Decimal("0")))
        for p in months:
            for d in rng.sample(days_of(p), 4):
                i = rng.choice(pool)
                db.add(M.PortfolioTransaction(portfolio_id=pid, date=d, issuer=i[0], side=rng.choice(["BUY", "SELL"]),
                                              notional_usd=q(rng.uniform(0.2e6, 6e6)), data_class="synthetic"))
    # Intended Guardian outcomes: 1001 REVIEW (material + near issuer limit), 1002 BLOCK, 1003 PASS, 1004 PASS,
    # 1005 INSUFFICIENT_DATA, 1006 REVIEW (material).
    proposals = [
        ("TP-1001", "PF-BAL", "Adatum Semiconductors", "Technology", "equity", "US", "BUY", 3_500_000, 71, 0.6, "A", 0.29,
         "Add to AI infrastructure exposure after earnings beat.", ["Q3 earnings release", "Sell-side consensus revision"]),
        ("TP-1002", "PF-GRN", "Contoso Energy", "Energy", "equity", "US", "BUY", 800_000, 38, 0.8, "BBB", 0.31,
         "Tactical value position in integrated energy.", ["Valuation screen"]),
        ("TP-1003", "PF-BAL", "Woodgrove Financial", "Financials", "equity", "US", "BUY", 1_200_000, 66, 0.4, "A", 0.22,
         "Rebalance financials to target weight.", ["Model portfolio drift report", "Liquidity check"]),
        ("TP-1004", "PF-GRN", "Relecloud Green Bond 2029", "Utilities", "bond", "US", "BUY", 650_000, 88, 1.2, "A", 0.05,
         "Certified green bond, extends duration to target.", ["Green bond framework", "Second party opinion"]),
        ("TP-1005", "PF-BAL", "Alpine Ski House Credit", "Consumer", "bond", "CA", "BUY", 900_000, None, None, None, None,
         "High-yield carry opportunity.", []),
        ("TP-1006", "PF-TRS", "US Treasury 2030", "Sovereign", "bond", "US", "BUY", 25_000_000, 70, 0.1, "AAA", 0.03,
         "Deploy excess liquidity into short UST.", ["ALCO liquidity minute", "Cash forecast (treasury)"]),
    ]
    for (pid_, port, issuer, sector, ac, ctry, side, notional, esg, liq, rating, vol, why, ev) in proposals:
        db.add(M.TradeProposal(id=pid_, portfolio_id=port, issuer=issuer, sector=sector, asset_class=ac, country=ctry, side=side,
                               notional_usd=q(notional), esg_score=None if esg is None else Decimal(str(esg)),
                               liquidity_days=None if liq is None else Decimal(str(liq)), rating=rating,
                               volatility=None if vol is None else Decimal(str(vol)), rationale=why, evidence=ev,
                               proposed_by="pm.ananya" if port == "PF-BAL" else ("pm.liam" if port == "PF-GRN" else "treasury.raj"),
                               created_at=dt.datetime(2026, 10, 28, 10, 0), data_class="synthetic"))


def _seed_ops(db, rng: random.Random, all_days: list[dt.date], tasks: list[dict]):
    services = ["Azure Data Factory", "Azure Functions", "AKS", "Azure Pipelines", "App Insights", "Azure SQL"]
    sre_tasks = [t["id"] for t in tasks if t["workflow_type"] == "incident_investigation" and t["verified"]]
    for i in range(140):
        day = rng.choice(all_days)
        svc = rng.choice(services)
        resolved = rng.random() < 0.85
        db.add(M.Incident(id=f"INC-{4000 + i}", opened_at=dt.datetime.combine(day, dt.time(rng.randint(0, 23), rng.randint(0, 59))), service=svc,
                          severity=rng.choices(["Sev1", "Sev2", "Sev3"], [1, 4, 10])[0],
                          title=f"{svc}: " + rng.choice(["elevated failure rate", "latency regression", "deployment failed", "quota exceeded", "auth errors"]),
                          status="resolved" if resolved else "open", resolved_by_task=rng.choice(sre_tasks) if (resolved and sre_tasks) else None,
                          data_class="synthetic"))
    for day in all_days:
        if rng.random() < 0.18:
            db.add(M.ComplianceEvent(date=day, type=rng.choice(["Mandate breach (pre-trade)", "AML alert", "Model risk review", "Data access exception",
                                                               "ESG exclusion hit", "Policy attestation"]),
                                     severity=rng.choice(["low", "medium", "high"]), description="Synthetic compliance event for demonstration.",
                                     status=rng.choice(["closed", "closed", "open"]), data_class="synthetic"))
        frac = all_days.index(day) / max(1, len(all_days) - 1)
        db.add(M.SystemMetricDaily(date=day, requests=int(1500 + 6000 * frac * rng.uniform(0.8, 1.2)), p50_ms=int(rng.gauss(420, 40)),
                                   p95_ms=int(rng.gauss(1900, 200)), p99_ms=int(rng.gauss(4200, 500)), cpu_pct=Decimal(str(round(rng.uniform(25, 70), 1))),
                                   mem_pct=Decimal(str(round(rng.uniform(40, 75), 1))), gpu_pct=Decimal(str(round(rng.uniform(20, 85), 1))),
                                   data_class="synthetic"))
    # A few pending approvals so the inbox is populated.
    db.add(M.Approval(id="AP-2001", kind="deployment", title="Deploy payments-api pipeline fix to production",
                      summary="CI/CD Agent repaired a failing Azure Pipelines stage (cache key collision). Tests pass in staging.",
                      requested_by="agent.cicd", required_roles=["SHERIN_MANAGER"], status="pending", financial_impact_usd=Decimal("0"),
                      risk_evidence=["Staging run #8812 green", "Diff: 4 lines in azure-pipelines.yml"], data_class="synthetic"))
    db.add(M.Approval(id="AP-2002", kind="data_change", title="Backfill 3 days of missing FX ticks in risk mart",
                      summary="Data Engineering Agent prepared an idempotent backfill. Touches sensitive market data tables.",
                      requested_by="agent.data_engineering", required_roles=["SHERIN_MANAGER", "COMPLIANCE_OFFICER"], status="pending",
                      financial_impact_usd=Decimal("0"), risk_evidence=["Row count diff: +4,212", "Checksum validated"], data_class="synthetic"))


if __name__ == "__main__":  # pragma: no cover
    import sys
    sc = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    print(seed(scale=sc))
