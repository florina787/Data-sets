"""Deterministic semantic planner: question → QueryPlan → SQL (specs/query_interface.md §2.1).

Composable: any catalog metric × any dimension × any filter. There is no question→answer table;
the six stakeholder questions are just inputs to the same parser as everything else.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .catalog import DIMENSIONS, FILTER_COLUMNS, METRICS

REGION_WORDS = {"na": "NA", "north america": "NA", "emea": "EMEA", "europe": "EMEA", "apac": "APAC", "asia": "APAC",
                "latam": "LATAM", "latin america": "LATAM", "south america": "LATAM"}
PLAN_WORDS = {"starter": "Starter", "pro": "Pro", "professional": "Pro", "enterprise": "Enterprise"}
INDUSTRIES = ["Travel", "Manufacturing", "Education", "Healthcare", "Retail", "Gaming", "Media", "Energy", "Logistics", "Fintech"]
DIM_WORDS = [
    ("region", r"regions?|geograph(?:y|ies)|geo"), ("plan", r"plans?|tiers?|products?"),
    ("industry", r"industr(?:y|ies)|verticals?|sectors?"), ("billing_cycle", r"billing cycles?|cycles?"),
    ("currency", r"currenc(?:y|ies)"), ("status", r"status(?:es)?"), ("payment_method", r"payment methods?"),
    ("invoice_year", r"years?|yearly|annually"), ("invoice_month", r"months?|monthly"),
    ("account", r"accounts?|customers?|clients?"),
]


@dataclass
class QueryPlan:
    metrics: list[str]
    group_by: str | None = None
    filters: dict[str, list] = field(default_factory=dict)
    order: str | None = None          # desc | asc | None
    limit: int | None = None
    flag_low_csat: bool = False
    chart: bool = False
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def primary(self) -> str:
        return self.metrics[0]

    @property
    def grain(self) -> str:
        return METRICS[self.primary].grain

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "QueryPlan":
        return QueryPlan(**d)


def _prep(q: str) -> str:
    s = " " + q.strip() + " "
    s = re.sub(r"monthly recurring revenue", "mrr", s, flags=re.I)
    s = s.replace("≤", "<=").replace("≥", ">=")
    return s


def detect_metrics(q: str) -> list[str]:
    s = q.lower()
    count_q = bool(re.search(r"how many|number of|\bcount\b|(most|fewest|least) (\w+ )?(invoices|accounts|customers)", s))
    if re.search(r"churn", s):
        return ["churn_rate", "churned_accounts", "account_count"]
    if re.search(r"\bmrr\b", s):
        return ["avg_mrr", "active_accounts"] if re.search(r"average|avg|mean|per account", s) else ["total_mrr", "active_accounts"]
    if re.search(r"refund|given back|giving back|charge.?backs?", s):
        return ["refund_count", "refunds"] if count_q and "how much" not in s else ["refunds", "refund_count"]
    if re.search(r"pending|failed|stuck|exposure|exposed|outstanding|uncollected|unpaid|at risk", s) and not re.search(r"\bpaid invoices\b.*revenue|revenue.*\bpaid\b", s):
        return ["exposure_count", "exposure"] if count_q else ["exposure", "exposure_count"]
    if re.search(r"discount", s):
        return ["discount_given"]
    if re.search(r"average (paid )?invoice|avg invoice|invoice value|deal size|ticket size", s):
        return ["avg_invoice_value", "invoice_count"]
    if re.search(r"seats", s):
        return ["seats_billed"]
    if re.search(r"(average|avg|mean) (csat|satisfaction)|(csat|satisfaction) (score )?(by|per|across)", s):
        return ["avg_csat", "account_count"]
    if count_q and re.search(r"invoices", s):
        return ["invoice_count"]
    if count_q and re.search(r"accounts|customers|clients", s):
        return ["active_accounts", "account_count"] if "active" in s else ["account_count", "active_accounts"]
    if re.search(r"revenue|sales|billings|earn|income|made|top \d* ?(accounts|customers|clients)|biggest (accounts|customers)", s):
        if re.search(r"\bpaid\b|gross", s):
            return ["paid_revenue", "net_revenue"]
        return ["net_revenue", "paid_revenue", "refunds"]
    if re.search(r"csat|satisfaction", s):
        return ["avg_csat", "account_count"]
    if re.search(r"\b(accounts|customers|clients)\b", s):  # "compare Enterprise and Pro accounts" → account profile
        return ["account_count", "active_accounts", "avg_mrr", "churn_rate"]
    return []


def detect_filters(q: str, metrics: list[str]) -> tuple[dict[str, list], bool]:
    s = q.lower()
    f: dict[str, list] = {}
    years = [int(y) for y in re.findall(r"\b(20[12]\d)\b", s)]
    if m := re.search(r"between (20[12]\d) and (20[12]\d)|from (20[12]\d) to (20[12]\d)", s):
        a, b = [int(x) for x in m.groups() if x]
        years = list(range(min(a, b), max(a, b) + 1))
    if years:
        f["invoice_year"] = sorted(set(years))
    regions = []
    for w, code in REGION_WORDS.items():
        pat = r"\bNA\b" if w == "na" else rf"\b{w}\b"
        if re.search(pat, q if w == "na" else s):
            regions.append(code)
    if regions:
        f["region"] = sorted(set(regions))
    plans = sorted({v for w, v in PLAN_WORDS.items() if re.search(rf"\b{w}\b", s)})
    if plans:
        f["plan"] = plans
    inds = [i for i in INDUSTRIES if re.search(rf"\b{i.lower()}\b", s)]
    if inds:
        f["industry"] = inds
    if m := re.findall(r"\b(eur|gbp|usd)[- ]?(?:denominated|invoices|customers|accounts|billing)", s):
        f["currency"] = sorted({c.upper() for c in m})
    if re.search(r"\bannual (invoices|plans|billing|subscriptions|contracts)\b", s):
        f["billing_cycle"] = ["annual"]
    elif re.search(r"\bmonthly (invoices|plans|billing|subscriptions)\b", s):
        f["billing_cycle"] = ["monthly"]
    flag = False
    if re.search(r"csat|satisfaction|unhappy|dissatisfied", s):
        if re.search(r"\bflag", s):
            flag = True
        elif re.search(r"low csat|csat (score )?(<=|of|at or below|below|under|≤)? ?2|unhappy|dissatisfied|poor csat", s):
            f["csat_max"] = [2]
    if metrics and METRICS[metrics[0]].id not in ("churn_rate", "churned_accounts"):
        if re.search(r"churned (accounts|customers)|(customers|accounts) (that|who) churned", s):
            f["churned"] = [True]
        elif re.search(r"\bactive (accounts|customers)\b", s) and metrics[0] not in ("active_accounts",):
            f["churned"] = [False]
    if metrics and metrics[0] in ("invoice_count", "avg_invoice_value"):
        sts = [st for st in ("paid", "pending", "failed", "refunded", "void") if re.search(rf"\b{st}\b", s)]
        if sts:
            f["status"] = sts
    if metrics and metrics[0] in ("exposure", "exposure_count"):
        sts = [st for st in ("pending", "failed") if re.search(rf"\b{st}\b", s)]
        if len(sts) == 1:
            f["status"] = sts
    return f, flag


def detect_dimension(q: str, metrics: list[str], filters: dict) -> tuple[str | None, str | None, int | None]:
    s = q.lower()
    s = re.sub(r"per (active )?account", "", s) if metrics and metrics[0] in ("avg_mrr", "avg_csat") else s
    limit = None
    order = None
    if m := re.search(r"\b(top|bottom|largest|biggest|smallest|best|worst)\s+(\d+)?\s*(\w+)", s):
        limit = int(m.group(2)) if m.group(2) else (5 if m.group(3) in ("accounts", "customers", "clients") else None)
        order = "asc" if m.group(1) in ("bottom", "smallest", "worst") else "desc"
    if re.search(r"over time|trend|month over month|per month|by month|monthly (trend|revenue|breakdown)", s):
        return "invoice_month", None, None
    for dim, pat in DIM_WORDS:
        if re.search(rf"\b(by|per|each|across|which|what|top \d*|bottom \d*|largest|biggest|compare|breakdown of)\s+(\w+\s)?({pat})\b", s) \
                or re.search(rf"\b({pat})\s+(breakdown|split|comparison|ranking)\b", s):
            if dim == "account" and metrics and metrics[0] in ("account_count", "active_accounts", "churn_rate", "churned_accounts", "avg_mrr"):
                if not re.search(r"top|bottom|which (accounts|customers)", s):
                    continue
            return dim, order or ("desc" if re.search(r"which|highest|most|largest|biggest|top", s) else None), limit
    # "Enterprise vs Starter" → compare by plan
    if re.search(r"\bvs\.?\b|versus|compar(e|ed|ing|ison)|against|\band\b", s):
        for fld in ("plan", "region", "industry"):
            if len(filters.get(fld, [])) >= 2:
                return fld, None, None
    return None, order, limit


def plan_question(question: str) -> QueryPlan | None:
    q = _prep(question)
    metrics = detect_metrics(q)
    if not metrics:
        return None
    filters, flag = detect_filters(q, metrics)
    dim, order, limit = detect_dimension(q, metrics, filters)
    if dim == "account" and limit is None:
        limit = 10
    plan = QueryPlan(metrics=metrics, group_by=dim, filters=filters, order=order, limit=limit, flag_low_csat=flag,
                     chart=bool(re.search(r"chart|plot|graph|visuali[sz]e", q, re.I)), confidence=0.9)
    if flag and dim != "account":
        plan.flag_low_csat = False
    if UNMODELED.search(q):
        plan.confidence = 0.3
        plan.notes.append("Question mentions a measure outside the approved metric catalog.")
    return validate_plan(plan)


def validate_plan(plan: QueryPlan) -> QueryPlan:
    """Drop combinations the semantic layer cannot express, with a note (never silently)."""
    grain = plan.grain
    if plan.group_by and DIMENSIONS[plan.group_by].__getattribute__(f"{grain}_sql") is None:
        plan.notes.append(f"'{DIMENSIONS[plan.group_by].label}' breakdown is not available for {METRICS[plan.primary].label} "
                          f"(account snapshot metric); showing the total instead.")
        plan.group_by, plan.limit = None, None
        plan.confidence = 0.5
    for fld in list(plan.filters):
        inv_col, acc_col = FILTER_COLUMNS[fld]
        if (grain == "account" and acc_col is None):
            plan.notes.append(f"Filter on {fld} = {plan.filters[fld]} ignored: {METRICS[plan.primary].label} is an account "
                              f"snapshot metric with no invoice-level {fld}.")
            del plan.filters[fld]
    return plan


# measures the catalog does not model: if a question names one, the plan would silently answer something else,
# so confidence drops below the threshold and the supervisor hands the question to Qwen text-to-SQL instead.
UNMODELED = re.compile(r"support tickets?|\btickets?\b|signup|sign-up|tenure|lifetime|email|median|percentile|correlat|"
                       r"standard deviation|variance|days (between|to|from)|growth rate|retention|cohort|per seat|seats per", re.I)
CONCEPT = re.compile(r"^\s*(what is|what's|what are|define|explain|tell me about|how does)\b(?!.*\b(our|we|us|cloudnova|20\d\d|"
                     r"by (region|plan|industry|month)|which|top \d|how much|how many)\b)", re.I)


FOLLOWUP_HINT = re.compile(r"^\s*(only|just|now|and|what about|how about|same|instead|but|filter|exclude|limit|show (only|just)|"
                           r"make it|turn it|as a|chart|plot|visuali[sz]e|by |per |for |in )", re.I)


def apply_followup(prev: QueryPlan, question: str) -> QueryPlan | None:
    """Patch the previous plan with a short follow-up ("only Enterprise", "now by plan", "as a chart")."""
    q = _prep(question)
    if not FOLLOWUP_HINT.search(q) and len(q.split()) > 6:
        return None
    new_metrics = detect_metrics(q)
    filters, flag = detect_filters(q, new_metrics or prev.metrics)
    dim, order, limit = detect_dimension(q, new_metrics or prev.metrics, filters)
    if not (new_metrics or filters or dim or re.search(r"chart|plot|graph|visuali[sz]e|table", q, re.I)):
        return None
    merged = QueryPlan.from_dict(prev.to_dict())
    merged.notes = []
    if new_metrics:
        merged.metrics = new_metrics
    for k, v in filters.items():
        merged.filters[k] = v
    if dim:
        merged.group_by, merged.order, merged.limit = dim, order, limit if dim == "account" else None
        if dim == "account" and merged.limit is None:
            merged.limit = 10
    if re.search(r"chart|plot|graph|visuali[sz]e", q, re.I):
        merged.chart = True
    merged.flag_low_csat = merged.flag_low_csat or flag
    merged.confidence = 0.85
    return validate_plan(merged)


# --------------------------------------------------------------------------- SQL compilation
def _lit(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def compile_sql(plan: QueryPlan) -> str:
    grain = plan.grain
    alias = "i" if grain == "invoice" else "a"
    needs_join = grain == "invoice" and (plan.group_by == "account" or any(FILTER_COLUMNS[f][0].startswith("a.") for f in plan.filters))
    select, group = [], []
    if plan.group_by:
        d = DIMENSIONS[plan.group_by]
        expr = d.invoice_sql if grain == "invoice" else d.account_sql
        if plan.group_by == "account":
            select += [f"{expr} AS account_id"]
            group.append(expr)
            if grain == "invoice":
                select += ["ANY_VALUE(a.account_name) AS account_name", "ANY_VALUE(a.csat_score) AS csat_score"]
                if plan.flag_low_csat:
                    select.append("COALESCE(ANY_VALUE(a.csat_score) <= 2, FALSE) AS low_csat_flag")
            else:
                select += ["a.account_name", "a.csat_score"]
                group += ["a.account_name", "a.csat_score"]
                if plan.flag_low_csat:
                    select.append("COALESCE(a.csat_score <= 2, FALSE) AS low_csat_flag")
                    group.append("low_csat_flag")
        else:
            select.append(f"{expr} AS {plan.group_by}")
            group.append(expr)
    for mid in plan.metrics:
        select.append(f"{METRICS[mid].sql} AS {mid}")
    frm = "invoices i" if grain == "invoice" else "accounts a"
    if needs_join:
        frm += " JOIN accounts a ON a.account_id = i.account_id"
    where = []
    for fld, vals in plan.filters.items():
        col = FILTER_COLUMNS[fld][0 if grain == "invoice" else 1]
        if fld == "csat_max":
            where.append(f"{col} <= {int(vals[0])}")
        elif len(vals) == 1:
            where.append(f"{col} = {_lit(vals[0])}")
        else:
            where.append(f"{col} IN ({', '.join(_lit(v) for v in vals)})")
    sql = f"SELECT {', '.join(select)}\nFROM {frm}"
    if where:
        sql += "\nWHERE " + " AND ".join(where)
    if group:
        sql += "\nGROUP BY " + ", ".join(group)
        if plan.group_by in ("invoice_month", "invoice_year"):
            sql += f"\nORDER BY {plan.group_by}"
        else:
            direction = "ASC" if plan.order == "asc" else "DESC"
            tie = f", {plan.group_by if plan.group_by != 'account' else 'account_id'}"
            sql += f"\nORDER BY {plan.primary} {direction} NULLS LAST{tie}"
        if plan.limit:
            sql += f"\nLIMIT {int(plan.limit)}"
    return sql


def describe_filters(plan: QueryPlan) -> dict:
    return {k: (v[0] if len(v) == 1 else v) for k, v in plan.filters.items()}
