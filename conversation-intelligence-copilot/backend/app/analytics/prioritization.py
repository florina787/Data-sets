"""Leadership prioritisation of recurring concerns with a transparent, configurable score.

priority = Σ wᵢ · minmax(signalᵢ) over topics, with the weights below (they sum to 1).
Signals that are not in the data (cost, churn, handle time) are deliberately absent.
A sensitivity analysis re-ranks under perturbed and equal weights and reports how
stable the top of the list is.
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import kendalltau

from app.analytics.db import AnalyticsDB, where
from app.analytics.stats import chi_square_independence, minmax
from app.analytics.topics import _rows, representative_conversations
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

DEFAULT_WEIGHTS: dict[str, float] = {
    "frequency": 0.30,  # how many conversations raise the concern
    "negative_rate": 0.25,  # share of those conversations that are negative
    "escalation_rate": 0.15,  # customer escalation requests per conversation
    "unresolved_rate": 0.15,  # conversations whose last customer message is negative
    "resolution_misfit_rate": 0.10,  # closing action does not fit the issue
    "trend": 0.05,  # change in conversation count vs previous month
}
SIGNAL_LABELS = {
    "frequency": "Volume", "negative_rate": "Negative rate", "escalation_rate": "Escalation requests / conv.",
    "unresolved_rate": "Ends unresolved", "resolution_misfit_rate": "Resolution misfit", "trend": "Month-on-month change",
}
OWNERS = {
    "resolution_misfit_rate": "QA & training lead",
    "escalation_rate": "Escalations / tier-2 manager",
    "unresolved_rate": "Contact-centre operations manager",
    "negative_rate": "Customer experience lead",
    "frequency": "Product owner for the affected journey",
    "trend": "Contact-centre operations manager",
}
ACTIONS = {
    "resolution_misfit_rate": "Review the resolution playbook and macros for this issue: closing actions often do not match the problem raised.",
    "escalation_rate": "Audit the escalation path for this issue and check first-contact resolution guidance.",
    "unresolved_rate": "Sample unresolved conversations to find where the process stalls and add a follow-up step.",
    "negative_rate": "Run a root-cause review of negative conversations for this issue with the owning product team.",
    "frequency": "Investigate upstream causes and self-service deflection for this high-volume issue.",
    "trend": "Monitor next month; volume is rising faster than for other issues.",
}


def _signals(db: AnalyticsDB, scope: Scope) -> pd.DataFrame:
    w, p = where(scope)
    df = db.query(
        f"""SELECT topic AS key, topic_label AS name, COUNT(*) AS conversations,
                   AVG((sentiment='negative')::INT) AS negative_rate, SUM((sentiment='negative')::INT) AS negative,
                   AVG(escalation_requests) AS escalation_rate, AVG(ends_negative::INT) AS unresolved_rate,
                   AVG(CASE WHEN resolution_relevant IS NULL THEN NULL ELSE (NOT resolution_relevant)::INT END) AS resolution_misfit_rate,
                   SUM(urgency_signals) AS urgency_signals
            FROM conversations c WHERE {w} GROUP BY topic, topic_label""", p)
    # Trend: latest month in scope vs the month before (computed over the whole dataset period).
    ws, ps = where(scope, skip={"window"})
    monthly = db.query(f"SELECT topic AS key, month, COUNT(*) AS n FROM conversations c WHERE {ws} AND month IS NOT NULL GROUP BY 1, 2", ps)
    if scope.window.start:
        latest = pd.Period(scope.window.start[:7], freq="M")
    else:
        latest = pd.Period(monthly["month"].max(), freq="M") if not monthly.empty else None
    if latest is not None:
        cur = monthly[monthly["month"] == latest.strftime("%Y-%m")].set_index("key")["n"]
        prev = monthly[monthly["month"] == (latest - 1).strftime("%Y-%m")].set_index("key")["n"]
        df["current_month_count"] = df["key"].map(cur).fillna(0).astype(int)
        df["previous_month_count"] = df["key"].map(prev).fillna(0).astype(int)
        df["trend"] = [(c - p_) / p_ if p_ else 0.0 for c, p_ in zip(df["current_month_count"], df["previous_month_count"])]
        df.attrs["trend_months"] = ((latest - 1).strftime("%Y-%m"), latest.strftime("%Y-%m"))
    else:
        df["trend"] = 0.0
    df["frequency"] = df["conversations"]
    df["resolution_misfit_rate"] = df["resolution_misfit_rate"].fillna(0.0)
    return df


def _score(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    total = sum(weights.values())
    score = sum((w / total) * pd.Series(minmax(df[k].astype(float).tolist()), index=df.index) for k, w in weights.items())
    return (score * 100).round(1)


def sensitivity(df: pd.DataFrame, weights: dict[str, float], top_n: int) -> dict:
    base_order = df.sort_values("priority_score", ascending=False)["key"].tolist()
    scenarios = {"equal weights": {k: 1.0 for k in weights}}
    for k in weights:
        for f in (0.5, 1.5):
            scenarios[f"{k} ×{f}"] = {**weights, k: weights[k] * f}
    rows = []
    top1_same = 0
    topn_overlap = []
    for name, w in scenarios.items():
        s = _score(df, w)
        order = df.assign(s=s).sort_values("s", ascending=False)["key"].tolist()
        tau = kendalltau([base_order.index(k) for k in order], list(range(len(order)))).statistic
        top1_same += int(order[0] == base_order[0])
        overlap = len(set(order[:top_n]) & set(base_order[:top_n])) / max(1, min(top_n, len(order)))
        topn_overlap.append(overlap)
        rows.append({"scenario": name, "top_concern": order[0], "kendall_tau": round(float(tau), 3), "top_n_overlap": round(overlap, 3)})
    return {"scenarios": rows, "top1_stability": round(top1_same / len(scenarios), 3), "mean_top_n_overlap": round(sum(topn_overlap) / len(topn_overlap), 3)}


def leadership_priorities(db: AnalyticsDB, scope: Scope, top_n: int = 5, weights: dict[str, float] | None = None) -> AnalysisResult:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    df = _signals(db, scope)
    if df.empty:
        return AnalysisResult(operation="leadership_priorities", scope=scope, status="insufficient_data", uncertainty_notes=["No conversations in scope."])
    df["priority_score"] = _score(df, weights)
    norm = {k: pd.Series(minmax(df[k].astype(float).tolist()), index=df.index) for k in weights}
    contrib = pd.DataFrame({k: norm[k] * weights[k] / sum(weights.values()) * 100 for k in weights})
    df["main_driver"] = contrib.idxmax(axis=1)
    for k in weights:
        df[f"contrib_{k}"] = contrib[k].round(1)
    df = df.sort_values(["priority_score", "conversations"], ascending=[False, False]).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    df["priority"] = ["High" if i < 2 else "Medium" if i < 4 else "Low" for i in range(len(df))]
    sens = sensitivity(df, weights, top_n)
    chi = chi_square_independence([[int(a), int(n - a)] for a, n in zip(df["negative"], df["conversations"])])

    unc = ["Financial impact, churn, handle time and repeat contact are not in the dataset and are not part of the score."]
    if chi["p_value"] is not None and chi["p_value"] >= 0.05:
        unc.append(f"Negative rate does not differ significantly between concerns (chi-square p = {chi['p_value']}); min-max scaling stretches small gaps, "
                   "so adjacent ranks should be treated as ties.")
    unc.append(f"Sensitivity: the #1 concern stays #1 in {sens['top1_stability']:.0%} of {len(sens['scenarios'])} weight scenarios; "
               f"mean top-{top_n} overlap {sens['mean_top_n_overlap']:.0%}.")
    if df.attrs.get("trend_months"):
        unc.append(f"Trend compares {df.attrs['trend_months'][1]} with {df.attrs['trend_months'][0]} conversation counts.")

    total = int(df["conversations"].sum())
    recs = []
    for _, r in df.head(top_n).iterrows():
        driver = r["main_driver"]
        ev = representative_conversations(db, scope, "topic", r["key"], k=2)
        recs.append({
            "concern": r["name"], "topic": r["key"], "rank": int(r["rank"]), "priority": r["priority"],
            "finding": f"{r['name']}: {int(r['conversations'])} conversations ({r['conversations'] / total:.0%} of scope), "
                       f"{r['negative_rate']:.0%} negative, {r['unresolved_rate']:.0%} end unresolved, "
                       f"{r['resolution_misfit_rate']:.0%} closing actions misfit the issue.",
            "supporting_metric": {"label": SIGNAL_LABELS[driver], "value": round(float(r[driver]), 4), "signal": driver},
            "rationale": f"Largest contribution to the priority score comes from {SIGNAL_LABELS[driver].lower()} "
                         f"({float(r[f'contrib_{driver}']):.1f} of {float(r['priority_score']):.1f} points).",
            "suggested_action": ACTIONS[driver],
            "decision_owner": OWNERS[driver],
            "evidence": ev,
            "uncertainty": "Score differences under ~5 points are within the range that weight changes can reorder." if sens["top1_stability"] < 1 else
                           "Rank is stable across the tested weight scenarios.",
        })
    cols = ["rank", "name", "key", "priority", "priority_score", "conversations", "negative", "negative_rate", "escalation_rate", "unresolved_rate",
            "resolution_misfit_rate", "trend", "main_driver"] + [f"contrib_{k}" for k in weights]
    matrix = df[["name", "key", "conversations", "negative_rate", "priority_score", "priority"]]
    return AnalysisResult(
        operation="leadership_priorities", params={"top_n": top_n, "weights": weights}, scope=scope,
        metrics=[
            Metric(id="conversations_in_scope", label="Conversations in scope", value=total, unit="count"),
            Metric(id="concerns", label="Recurring concerns", value=len(df), unit="count"),
            Metric(id="top_concern", label="Top concern", value=str(df.iloc[0]["name"])),
            Metric(id="top_score", label="Top priority score", value=float(df.iloc[0]["priority_score"]), unit="score"),
            Metric(id="top1_stability", label="Top-1 stability under weight changes", value=sens["top1_stability"], unit="percent"),
            Metric(id="unresolved_rate_overall", label="Conversations ending unresolved",
                   value=round(float((df["unresolved_rate"] * df["conversations"]).sum() / total), 4), unit="percent"),
        ],
        table=Table(columns=cols, rows=_rows(df[cols].round(4))),
        series={
            "priority_matrix": Table(columns=list(matrix.columns), rows=_rows(matrix.round(4))),
            "sensitivity": Table(columns=["scenario", "top_concern", "kendall_tau", "top_n_overlap"], rows=sens["scenarios"]),
            "weights": Table(columns=["signal", "label", "weight"], rows=[{"signal": k, "label": SIGNAL_LABELS[k], "weight": v} for k, v in weights.items()]),
            "recommendations": Table(columns=list(recs[0].keys()) if recs else [], rows=recs),
        },
        evidence_refs=[e for r in recs[:3] for e in r["evidence"]],
        method_notes=["priority = Σ weight × min-max normalised signal across concerns, scaled to 0–100.",
                      "Weights: " + ", ".join(f"{SIGNAL_LABELS[k]} {v:.2f}" for k, v in weights.items()) + ".",
                      "A concern is the primary issue raised in the customer's opening message."],
        uncertainty_notes=unc,
        coverage={"conversations": total, "concerns": len(df)},
    )

