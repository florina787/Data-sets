"""Deterministic answer rendering: every number in the text is formatted from result rows."""
from __future__ import annotations

from ..semantic.catalog import DIMENSIONS, METRICS
from ..semantic.planner import QueryPlan


def fmt(v, unit: str) -> str:
    if v is None:
        return "n/a"
    if unit == "usd":
        return ("-" if v < 0 else "") + f"${abs(v):,.2f}"
    if unit == "pct":
        return f"{v * 100:.2f}%"
    if unit == "score":
        return f"{v:.2f}"
    return f"{int(v):,}"


def filter_phrase(plan: QueryPlan) -> str:
    parts = []
    for k, v in plan.filters.items():
        if k == "invoice_year":
            parts.append("in " + " & ".join(str(x) for x in v))
        elif k == "csat_max":
            parts.append(f"CSAT ≤ {v[0]}")
        elif k == "churned":
            parts.append("churned accounts" if v[0] else "active accounts")
        else:
            parts.append(f"{k.replace('_', ' ')} {'/'.join(str(x) for x in v)}")
    return (" (" + ", ".join(parts) + ")") if parts else ""


def render(plan: QueryPlan, result: dict, context: dict | None = None) -> str:
    cols, rows = result["columns"], result["rows"]
    if not rows:
        return f"No matching data{filter_phrase(plan)}."
    m0 = METRICS[plan.primary]
    fp = filter_phrase(plan)
    idx = {c: i for i, c in enumerate(cols)}

    if not plan.group_by:
        r = rows[0]
        val = lambda mid: fmt(r[idx[mid]], METRICS[mid].unit)  # noqa: E731
        if plan.primary in ("refunds", "refund_count"):
            amt = r[idx["refunds"]] or 0
            return (f"We have given back **{fmt(abs(amt), 'usd')}** in refunds{fp}, across **{val('refund_count')}** refunded "
                    f"invoices. Refunds are stored as negative amounts ({fmt(amt, 'usd')}) and net against revenue.")
        if plan.primary in ("exposure", "exposure_count"):
            text = (f"**{val('exposure_count')}** invoices are stuck in pending/failed{fp}, with **{val('exposure')}** "
                    f"of billed value not collected.")
            if context and context.get("by_status"):
                text += " Breakdown: " + "; ".join(f"{s}: {fmt(n, 'count')} invoices, {fmt(a, 'usd')}" for s, n, a in context["by_status"]) + "."
            return text
        lead = f"**{m0.label}**{fp}: **{val(plan.primary)}**."
        extras = [f"{METRICS[m].label}: {val(m)}" for m in plan.metrics[1:]]
        return lead + (" " + "; ".join(extras) + "." if extras else "")

    dim = plan.group_by
    dcol = "account_id" if dim == "account" else dim
    label = DIMENSIONS[dim].label

    def name(r):
        if dim == "account":
            return f"{r[idx['account_name']]} ({r[idx['account_id']]})"
        return "(blank)" if r[idx[dcol]] is None else str(r[idx[dcol]])

    if dim == "account":
        lines = []
        for n, r in enumerate(rows, 1):
            csat = r[idx["csat_score"]]
            flag = ""
            if plan.flag_low_csat:
                flag = " — ⚠ **CSAT ≤ 2**" if r[idx["low_csat_flag"]] else (" — CSAT unknown" if csat is None else "")
            lines.append(f"{n}. {name(r)} — {fmt(r[idx[plan.primary]], m0.unit)} (CSAT {csat if csat is not None else 'n/a'}){flag}")
        head = f"Top {len(rows)} accounts by {m0.label}{fp}:"
        if plan.flag_low_csat:
            flagged = [name(r) for r in rows if r[idx["low_csat_flag"]]]
            tail = ("\n\nFlagged with CSAT ≤ 2: " + ", ".join(flagged)) if flagged else "\n\nNone of these accounts has CSAT ≤ 2."
            unknown = [name(r) for r in rows if r[idx["csat_score"]] is None]
            if unknown:
                tail += f" CSAT is blank for {', '.join(unknown)} — shown as unknown, not as low."
        else:
            tail = ""
        return head + "\n" + "\n".join(lines) + tail

    if dim in ("invoice_month", "invoice_year"):
        vals = [(name(r), r[idx[plan.primary]]) for r in rows if r[idx[plan.primary]] is not None]
        if not vals:
            return f"No {m0.label} values{fp}."
        peak = max(vals, key=lambda x: x[1])
        low = min(vals, key=lambda x: x[1])
        body = " · ".join(f"{k}: {fmt(v, m0.unit)}" for k, v in vals) if len(vals) <= 12 else ""
        return (f"{m0.label} by {label.lower()}{fp} across {len(vals)} periods. Peak: **{peak[0]}** at {fmt(peak[1], m0.unit)}; "
                f"lowest: {low[0]} at {fmt(low[1], m0.unit)}." + (f"\n{body}" if body else ""))

    ranked = [(name(r), r[idx[plan.primary]]) for r in rows]
    if len(ranked) == 2 and len(plan.filters.get(dim, [])) == 2:
        (a, va), (b, vb) = ranked
        diff = (va or 0) - (vb or 0)
        unit = m0.unit
        d = f"{abs(diff) * 100:.2f} percentage points" if unit == "pct" else fmt(abs(diff), unit)
        detail = ""
        if plan.primary == "churn_rate" and "churned_accounts" in idx:
            detail = " (" + "; ".join(f"{name(r)}: {fmt(r[idx['churned_accounts']], 'count')} of {fmt(r[idx['account_count']], 'count')} accounts churned" for r in rows) + ")"
        return f"{m0.label}{fp}: **{a} {fmt(va, unit)}** vs **{b} {fmt(vb, unit)}** — {a} is higher by {d}{detail}."
    top = ranked[0]
    word = "Lowest" if plan.order == "asc" else "Highest"
    rest = " · ".join(f"{k}: {fmt(v, m0.unit)}" for k, v in ranked)
    return f"{word} {label.lower()} by {m0.label}{fp}: **{top[0]}** at **{fmt(top[1], m0.unit)}**.\nAll {label.lower()}s: {rest}"


def chart_for(plan: QueryPlan | None, result: dict) -> dict | None:
    if not result or not result.get("rows") or len(result["rows"]) < 2:
        return None
    cols = result["columns"]
    if plan and plan.group_by:
        x = "account_name" if plan.group_by == "account" else plan.group_by
        y = [m for m in plan.metrics if METRICS[m].unit == METRICS[plan.primary].unit][:3]
        kind = "line" if plan.group_by == "invoice_month" else ("bar_h" if plan.group_by == "account" else "bar")
        return {"type": kind, "x": x, "y": y, "unit": METRICS[plan.primary].unit}
    nums = [c for c, v in zip(cols, result["rows"][0]) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    texts = [c for c, v in zip(cols, result["rows"][0]) if isinstance(v, str)]
    if texts and nums:
        return {"type": "bar", "x": texts[0], "y": nums[:2], "unit": "auto"}
    return None
