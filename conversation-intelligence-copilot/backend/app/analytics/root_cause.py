"""Autonomous Root Cause Investigator (associational, never causal).

For one topic (or the most negative topic in scope), it tests candidate factors
observable in the data. Each test compares the negative rate of conversations with
the factor against those without it, and reports:
  - both rates with Wilson 95% intervals, the risk difference and the relative risk;
  - a two-proportion z-test p-value and the support on each side;
  - for agent behaviours, a temporal-precedence check: does the behaviour occur
    before the customer's last negative message?
  - the factor's role. Customer reactions such as escalation and urgency are
    expressions of negativity, so they are reported as symptoms, not drivers.

It also checks alternative explanations: concentration by product or agent, and
whether the topic's negative rate differs from the rest of the scope. The language
is strictly associational. The data cannot show causes, and unmeasured factors
(wait time, customer history, channel) are absent.
"""

from __future__ import annotations

import pandas as pd

from app.analytics.db import AnalyticsDB, where
from app.analytics.stats import chi_square_independence, two_proportion_test, wilson_interval
from app.analytics.topics import topic_sentiment_table
from app.labeling.taxonomy import HINGLISH_MARKERS, RELEVANT_RESOLUTIONS, TOPICS
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

MIN_TOPIC_CONVERSATIONS = 20
MIN_SUPPORT = 8  # conversations needed on each side of a factor before it is tested
ROLE_LABEL = {"agent_behaviour": "Agent behaviour (candidate driver)", "customer_reaction": "Customer reaction (likely symptom)",
              "context": "Context"}


def _factors(df: pd.DataFrame, topic: str) -> list[tuple[str, str, str, pd.Series]]:
    fitting = RELEVANT_RESOLUTIONS.get(topic)
    long_cut = df["message_count"].median()
    f = [
        ("low_empathy", "Replies to negative turns rarely acknowledge frustration (empathy response rate below 50%)", "agent_behaviour",
         (df["negative_turns_with_reply"] > 0) & (df["empathy_response_rate"].fillna(1.0) < 0.5)),
        ("scripted_repeats", "Agent repeated the same scripted reply", "agent_behaviour", df["repeated_agent_phrases"] > 0),
        ("no_resolution", "No resolution statement from the agent", "agent_behaviour", df["final_resolution"].isna()),
        ("hinglish_agent", "Agent replied in Hinglish", "agent_behaviour", df["agent_hinglish_turns"] > 0),
        ("escalation", "Customer asked to escalate", "customer_reaction", df["escalation_requests"] > 0),
        ("urgency", "Customer stressed urgency", "customer_reaction", df["urgency_signals"] > 0),
        ("long_conversation", f"Longer conversation (more than {int(long_cut)} messages, the topic median)", "context", df["message_count"] > long_cut),
        ("hinglish_opening", "Customer opened in Hinglish", "context", df["opening_language"] == "hinglish"),
    ]
    if fitting:
        f.insert(2, ("resolution_mismatch", "Closing action does not fit the issue", "agent_behaviour",
                     df["final_resolution"].notna() & ~df["final_resolution"].isin(list(fitting))))
    return f


def _precedence(db: AnalyticsDB, ids: list[str], topic: str) -> dict[str, dict[str, bool]]:
    """Per conversation: does each agent behaviour occur before the customer's last negative message?"""
    if not ids:
        return {}
    m = db.frame(
        f"""SELECT m.conversation_id, m.turn_index, m.speaker_role, m.clean_text, l.act, l.sentiment, l.empathy, l.resolution
            FROM messages m JOIN message_labels l USING (message_id)
            WHERE m.conversation_id IN ({','.join('?' * len(ids))}) ORDER BY m.conversation_id, m.turn_index""", ids)
    fitting = RELEVANT_RESOLUTIONS.get(topic) or set()
    out: dict[str, dict[str, bool]] = {}
    for cid, g in m.groupby("conversation_id", sort=False):
        neg_c = g[(g["speaker_role"] == "customer") & (g["sentiment"] == "negative")]["turn_index"]
        last_neg = int(neg_c.max()) if len(neg_c) else -1
        agent = g[g["speaker_role"] == "agent"]
        first: dict[str, int] = {}
        for t in neg_c:
            reply = agent[agent["turn_index"] > t].head(1)
            if len(reply) and not bool(reply["empathy"].iloc[0]):
                first["low_empathy"] = int(reply["turn_index"].iloc[0])
                break
        seen: set[str] = set()
        for _, a in agent.iterrows():
            if a["clean_text"] in seen and not a["resolution"]:
                first.setdefault("scripted_repeats", int(a["turn_index"]))
            seen.add(a["clean_text"])
        res = agent[agent["resolution"].notna()]
        if len(res) and fitting and res["resolution"].iloc[-1] not in fitting:
            first["resolution_mismatch"] = int(res["turn_index"].iloc[-1])
        hin = agent[agent["clean_text"].fillna("").map(lambda t: bool(HINGLISH_MARKERS.search(t)))]
        if len(hin):
            first["hinglish_agent"] = int(hin["turn_index"].iloc[0])
        out[cid] = {k: v < last_neg for k, v in first.items()}
    return out


def _strength(p: float | None, rd: float, n_with: int, n_without: int) -> str:
    if min(n_with, n_without) < MIN_SUPPORT or p is None:
        return "insufficient support"
    if rd <= 0:
        return "not associated (lower or equal negative rate)"
    if p < 0.01 and rd >= 0.15:
        return "strong association"
    if p < 0.05:
        return "moderate association"
    return "weak — not distinguishable from noise"


def root_cause_investigation(db: AnalyticsDB, scope: Scope, topic: str | None = None, top_n: int = 6) -> AnalysisResult:
    params = {"topic": topic, "top_n": top_n}
    notes: list[str] = []
    if not topic:
        if scope.topics:
            topic = scope.topics[0]
            notes.append(f"Investigating {TOPICS[topic].label}, the topic in the current filter.")
        else:
            t = topic_sentiment_table(db, scope)
            if t.empty:
                return AnalysisResult(operation="root_cause_investigation", params=params, scope=scope, status="insufficient_data",
                                      uncertainty_notes=["No conversations in scope."])
            t = t[t["conversations"] >= MIN_TOPIC_CONVERSATIONS].sort_values(["negative", "negative_rate"], ascending=False)
            if t.empty:
                return AnalysisResult(operation="root_cause_investigation", params=params, scope=scope, status="insufficient_data",
                                      uncertainty_notes=[f"No topic has at least {MIN_TOPIC_CONVERSATIONS} conversations in scope."])
            topic = str(t.iloc[0]["key"])
            notes.append(f"No topic named: investigating {TOPICS[topic].label}, the topic with the most negative conversations in scope.")
    params["topic"] = topic
    tscope = scope.model_copy(update={"topics": [topic], "sentiments": []})
    w, p = where(tscope)
    df = db.query(f"SELECT * FROM conversations c WHERE {w}", p)
    n = len(df)
    label = TOPICS[topic].label if topic in TOPICS else topic
    if n < MIN_TOPIC_CONVERSATIONS:
        return AnalysisResult(operation="root_cause_investigation", params=params, scope=tscope, status="insufficient_data",
                              metrics=[Metric(id="conversations", label="Conversations", value=n, unit="count")],
                              uncertainty_notes=[f"{label} has {n} conversation(s) in scope; at least {MIN_TOPIC_CONVERSATIONS} are needed to compare factors."])
    neg = df["sentiment"] == "negative"
    n_neg = int(neg.sum())
    prec = _precedence(db, df.loc[neg, "conversation_id"].tolist(), topic)

    hyps = []
    unobserved = []
    for fid, desc, role, mask in _factors(df, topic):
        mask = mask.fillna(False).astype(bool)
        n_w, n_wo = int(mask.sum()), int((~mask).sum())
        if n_w == 0 or n_wo == 0:
            unobserved.append(desc)
            continue
        x_w, x_wo = int((mask & neg).sum()), int((~mask & neg).sum())
        r_w = x_w / n_w if n_w else None
        r_wo = x_wo / n_wo if n_wo else None
        rd = (r_w - r_wo) if (r_w is not None and r_wo is not None) else 0.0
        test = two_proportion_test(x_w, n_w, x_wo, n_wo)
        ci_w, ci_wo = wilson_interval(x_w, n_w), wilson_interval(x_wo, n_wo)
        ids = df.loc[mask & neg].sort_values(["sentiment_score_mean", "conversation_id"])["conversation_id"].tolist()
        pre = [prec[c][fid] for c in ids if c in prec and fid in prec[c]] if role == "agent_behaviour" else []
        hyps.append({
            "factor": fid, "description": desc, "role": role, "role_label": ROLE_LABEL[role],
            "with_factor": n_w, "with_factor_negative": x_w, "negative_rate_with": round(r_w, 4) if r_w is not None else None,
            "ci_with_low": round(ci_w[0], 4), "ci_with_high": round(ci_w[1], 4),
            "without_factor": n_wo, "without_factor_negative": x_wo, "negative_rate_without": round(r_wo, 4) if r_wo is not None else None,
            "ci_without_low": round(ci_wo[0], 4), "ci_without_high": round(ci_wo[1], 4),
            "risk_difference": round(rd, 4), "relative_risk": round(r_w / r_wo, 3) if (r_w is not None and r_wo) else None,
            "p_value": test["p_value"], "strength": _strength(test["p_value"], rd, n_w, n_wo),
            "precedes_negative_share": round(sum(pre) / len(pre), 3) if pre else None, "precedence_checked": len(pre),
            "evidence": ids[:4],
        })
    order = {"strong association": 0, "moderate association": 1, "weak — not distinguishable from noise": 2,
             "not associated (lower or equal negative rate)": 3, "insufficient support": 4}
    hyps.sort(key=lambda h: (h["role"] == "customer_reaction", order.get(h["strength"], 4), -h["risk_difference"]))
    for i, h in enumerate(hyps, 1):
        h["rank"] = i
    shown = hyps[: max(top_n, 1) + 2]  # keep the symptoms visible next to the candidate drivers

    # --- alternative explanations -------------------------------------------------------------
    alts = []
    by_prod = df.groupby("product")["sentiment"].agg(lambda s: [(s == "negative").sum(), (s != "negative").sum()])
    if len(by_prod) >= 2:
        chi = chi_square_independence([list(map(int, v)) for v in by_prod.values])
        sizes = {k: int(sum(v)) for k, v in by_prod.items()}
        rates = {k: v[0] / max(1, sum(v)) for k, v in by_prod.items() if sum(v) >= MIN_SUPPORT} or {k: v[0] / max(1, sum(v)) for k, v in by_prod.items()}
        worst = max(rates, key=rates.get)
        alts.append({"alternative": "Product mix", "test": "Chi-square: negative rate by product",
                     "p_value": chi["p_value"], "valid": chi["valid"],
                     "finding": f"Among products with at least {MIN_SUPPORT} conversations, the negative rate is highest for {worst} "
                                f"({rates[worst]:.0%} of {sizes[worst]}); "
                                + ("differences across products are unlikely to be chance." if chi["p_value"] is not None and chi["p_value"] < 0.05
                                   else "product differences are within chance, so product mix is not a strong alternative explanation.")})
    if n_neg:
        agent_share = df.loc[neg, "agent_id"].value_counts(normalize=True)
        top_agent, share = agent_share.index[0], float(agent_share.iloc[0])
        concentrated = share >= 0.3 and n_neg >= 10
        alts.append({"alternative": "Agent concentration", "test": "Largest single-agent share of the topic's negative conversations",
                     "p_value": None, "valid": True,
                     "finding": f"{top_agent} handled {share:.0%} of the negative conversations; "
                                + ("negativity is concentrated in one agent, which could explain the pattern." if concentrated
                                   else "negativity is spread across agents, so one agent does not explain it.")})
    allscope = topic_sentiment_table(db, scope.model_copy(update={"topics": [], "sentiments": []}))
    if not allscope.empty:
        rest = allscope[allscope["key"] != topic]
        rn, rc = int(rest["negative"].sum()), int(rest["conversations"].sum())
        t2 = two_proportion_test(n_neg, n, rn, rc)
        sig = t2["p_value"] is not None and t2["p_value"] < 0.05
        higher = n_neg / n > rn / max(rc, 1)
        verdict = (" — distinctly more negative than other topics, so something topic-specific is plausible." if sig and higher else
                   " — less negative than other topics; it ranks high on volume, not on rate, so drivers may be shared across topics." if sig else
                   " — not clearly different, so drivers may be shared across topics rather than topic-specific.")
        alts.append({"alternative": "Topic baseline", "test": "Topic negative rate vs all other topics in scope", "p_value": t2["p_value"], "valid": True,
                     "finding": f"{label}: {n_neg / n:.0%} negative vs {rn / max(rc, 1):.0%} for other topics" + verdict})

    drivers = [h for h in hyps if h["role"] != "customer_reaction" and h["strength"] in ("strong association", "moderate association")]
    top = drivers[0] if drivers else None
    unc = ["Associational, not causal: these factors co-occur with negative outcomes in this dataset; the data cannot show that they cause them.",
           "Unmeasured factors (wait times, customer history, channel, policy) are not in the data and may explain the pattern.",
           f"{len(hyps)} factors were tested at α=0.05, so about {len(hyps) * 0.05:.1f} could look significant by chance; prefer factors with large differences and small p-values."]
    if n < 60:
        unc.insert(0, f"Only {n} conversations in this topic and window: intervals are wide.")
    unc.append("Customer reactions (escalation, urgency) are expressions of negativity, so they are reported as symptoms, not drivers.")
    return AnalysisResult(
        operation="root_cause_investigation", params=params, scope=tscope,
        metrics=[
            Metric(id="topic", label="Topic investigated", value=label),
            Metric(id="conversations", label="Conversations", value=n, unit="count"),
            Metric(id="negative_conversations", label="Negative conversations", value=n_neg, unit="count"),
            Metric(id="negative_rate", label="Negative rate", value=round(n_neg / n, 4), unit="percent", numerator=n_neg, denominator=n),
            Metric(id="factors_tested", label="Factors tested", value=len(hyps), unit="count"),
            Metric(id="supported_drivers", label="Associated agent/context factors", value=len(drivers), unit="count"),
            Metric(id="top_factor", label="Strongest associated factor", value=top["description"] if top else "None clearly associated"),
        ],
        table=Table(columns=list(shown[0].keys()), rows=shown),
        series={"alternatives": Table(columns=["alternative", "test", "p_value", "valid", "finding"], rows=alts),
                "all_factors": Table(columns=list(hyps[0].keys()), rows=hyps)},
        evidence_refs=(top["evidence"][:3] if top else []) + [i for h in hyps if h["role"] == "customer_reaction" for i in h["evidence"][:1]],
        method_notes=notes + ([f"Not observed in this topic, so not testable: {'; '.join(unobserved)}."] if unobserved else []) + [
            "For each factor: negative rate with vs without it (Wilson 95% CI), risk difference, relative risk, two-proportion z-test.",
            f"A factor needs at least {MIN_SUPPORT} conversations on each side to be tested.",
            "Precedence: share of negative conversations with the behaviour where it occurs before the customer's last negative message.",
            "Strength: strong = p<0.01 and ≥15 points higher; moderate = p<0.05; otherwise weak.",
        ],
        uncertainty_notes=unc,
        coverage={"topic": topic, "conversations": n},
    )

