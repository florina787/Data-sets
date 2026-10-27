"""Analytical Evidence Challenger.

Runs inside the QA node, after the explanation is written and before anything is
shown. It argues against the answer, checking things the numeric grounding check
cannot:

  excerpt_fidelity      every quoted excerpt is re-read from the database and must match its source message
  evidence_coverage     each top-ranked claim has at least one supporting conversation attached
  evidence_relevance    evidence for a "negative" claim is mostly negative conversations
  sample_size           small groups and denominators are named, and the caveat is attached
  counter_evidence      how much of the claimed group does *not* fit the claim
  causal_language       causal wording ("driven by", "causes", "leads to") is rewritten as association
  claim_consistency     a root-cause explanation may only name factors the analysis supports

A model explanation that names unsupported factors is replaced by the deterministic
narrative. The challenger never changes a number.
"""

from __future__ import annotations

import re

from app.analytics.db import AnalyticsDB

SMALL_N = 30
CAUSAL = re.compile(r"\b(caus(?:e|es|ed|ing)|driven by|drives|driving|leads? to|led to|results? in|resulted in|due to|because of|"
                    r"responsible for|is the reason|are the reason|triggers?|triggered by)\b", re.I)
NEGATION = re.compile(r"\b(not|cannot|can't|doesn't|does not|do not|no|never|without)\b[^.]{0,30}$", re.I)
NOUN_CONTEXT = re.compile(r"\b(root[- ]?|upstream|underlying|possible|likely|potential|the|its|their|a|of|investigate|review)\s*$", re.I)
REWRITE = [
    (re.compile(r"\bis (primarily |mainly |largely )?driven by\b", re.I), lambda m: f"is {m.group(1) or ''}associated with"),
    (re.compile(r"\bare (primarily |mainly |largely )?driven by\b", re.I), lambda m: f"are {m.group(1) or ''}associated with"),
    (re.compile(r"\bdriven by\b", re.I), lambda m: "associated with"),
    (re.compile(r"\b(caused by|due to|because of)\b", re.I), lambda m: "associated with"),
    (re.compile(r"\b(leads|led|lead) to\b", re.I), lambda m: "co-occurs with"),
    (re.compile(r"\b(results|resulted|result) in\b", re.I), lambda m: "co-occurs with"),
    (re.compile(r"\bcauses\b", re.I), lambda m: "is associated with"),
    (re.compile(r"\bdrives\b", re.I), lambda m: "is associated with"),
    (re.compile(r"\bcause\b", re.I), lambda m: "are associated with"),
    (re.compile(r"\b(causing|driving)\b", re.I), lambda m: "associated with"),
    (re.compile(r"\b(triggers|triggered by)\b", re.I), lambda m: "co-occurs with"),
    (re.compile(r"\b(is|are) the reason\b", re.I), lambda m: f"{m.group(1)} associated with the pattern"),
    (re.compile(r"\bresponsible for\b", re.I), lambda m: "associated with"),
]
SUPPORTED = ("strong association", "moderate association")
FACTOR_WORDS = {"low_empathy": r"empath|acknowledg", "scripted_repeats": r"script|repeat(ed)? (the same )?repl", "no_resolution": r"no resolution",
                "resolution_mismatch": r"closing action|resolution mismatch|mismatch", "hinglish_agent": r"hinglish",
                "long_conversation": r"long(er)? conversation", "escalation": r"escalat", "urgency": r"urgen"}


def _check(name: str, status: str, detail: str, items: list | None = None) -> dict:
    return {"check": name, "status": status, "detail": detail, "items": items or []}


def _causal_hits(text: str) -> list[str]:
    hits = []
    for m in CAUSAL.finditer(text):
        before = text[max(0, m.start() - 40): m.start()]
        if NEGATION.search(before):
            continue  # "cannot show that they cause", "not proof of cause"
        if m.group(0).lower() in ("cause", "causes") and NOUN_CONTEXT.search(before):
            continue  # "a root-cause review", "investigate upstream causes": the noun, not a claim
        hits.append(m.group(0))
    return hits


def qualify(text: str) -> str:
    for pat, repl in REWRITE:
        text = pat.sub(repl, text)
    return text


def claim_constraints(tool_results: dict, evidence: list[dict]) -> dict:
    """Pre-generation review: what a narrative may and may not claim, decided from the compact results before any model runs.

    The same rules are checked again on the generated text by challenge(); handing them to the writer first means the
    model is told which factors it may name instead of being rejected afterwards for naming the wrong ones.
    """
    rules = ["Describe associations, never causes: avoid 'caused by', 'driven by', 'due to', 'leads to', 'because of'.",
             "Quote only the evidence excerpts given; do not paraphrase them as new findings."]
    may, must_not = [], []
    rc = tool_results.get("root_cause_investigation")
    if rc and rc.get("status") == "ok":
        rows = rc["series"]["all_factors"]["rows"]
        may = [h["description"] for h in rows if h["strength"] in SUPPORTED and h["role"] != "customer_reaction"]
        must_not = [h["description"] for h in rows if h["strength"] not in SUPPORTED and h["role"] != "customer_reaction"]
        rules.append("Name ONLY the factors in MAY_NAME as associated with the outcome, in the headline and the answer. "
                     "Do not name any factor in MUST_NOT_NAME as a driver or association; you may say it was tested and not supported.")
        if not may:
            rules.append("No agent or context factor was supported: say so plainly rather than offering a likely reason.")
    ready = bool(tool_results) and all(r.get("status") in ("ok", "insufficient_data") for r in tool_results.values())
    return {"ready": ready, "may_name": may, "must_not_name": must_not, "rules": rules, "evidence_conversations": len(evidence)}


def challenge(db: AnalyticsDB, plan: dict, tool_results: dict, evidence: list[dict], explanation: dict, explanation_source: str) -> tuple[dict, dict]:
    """Return (review, explanation); the explanation is only changed to qualify causal wording or drop unsupported claims."""
    checks: list[dict] = []
    challenges: list[str] = []

    # 1. excerpt fidelity --------------------------------------------------------------------
    quoted = {x["message_id"]: x["text"] for e in evidence for x in e.get("excerpts", [])}
    if quoted:
        ids = list(quoted)
        src = db.query(f"SELECT message_id, masked_text FROM messages WHERE message_id IN ({','.join('?' * len(ids))})", ids)
        truth = dict(zip(src["message_id"], src["masked_text"]))
        bad = [m for m, t in quoted.items() if truth.get(m) != t]
        checks.append(_check("excerpt_fidelity", "fail" if bad else "pass",
                             f"{len(quoted) - len(bad)}/{len(quoted)} quoted excerpts match their source message word for word", bad))
    else:
        checks.append(_check("excerpt_fidelity", "pass", "No excerpts quoted"))

    # 2. coverage of top-ranked claims ------------------------------------------------------------
    rank = next((tool_results[o] for o in ("leadership_priorities", "rank_negative_topics") if tool_results.get(o, {}).get("table")), None)
    ev_topics = {e.get("topic") for e in evidence}
    if rank and rank["status"] == "ok":
        top = [r["name"] for r in rank["table"]["rows"][:3]]
        covered = [t for t in top if t in ev_topics]
        missing = [t for t in top if t not in ev_topics]
        status = "pass" if len(covered) == len(top) else "warn" if covered else "fail"
        checks.append(_check("evidence_coverage", status, f"{len(covered)}/{len(top)} top-ranked groups have a supporting conversation attached", missing))
        if missing:
            challenges.append(f"No example conversation is attached for: {', '.join(missing)}. Open the Explorer before quoting these.")
    rc = tool_results.get("root_cause_investigation")
    if rc and rc["status"] == "ok":
        top_driver = next((h for h in rc["table"]["rows"] if h["role"] != "customer_reaction" and h["strength"] in SUPPORTED), None)
        has = top_driver is not None and bool(set(top_driver["evidence"]) & {e["conversation_id"] for e in evidence})
        checks.append(_check("evidence_coverage", "pass" if has or top_driver is None else "warn",
                             "Example conversations for the strongest factor are attached" if has else
                             "No supported factor to illustrate" if top_driver is None else "The strongest factor has no example attached"))

    # 3. relevance -------------------------------------------------------------------------------
    if plan.get("category") in ("negative_topics", "leadership_priorities", "root_cause", "agent_coaching") and evidence:
        neg = sum(e.get("sentiment") == "negative" for e in evidence)
        share = neg / len(evidence)
        checks.append(_check("evidence_relevance", "pass" if share >= 0.5 else "warn",
                             f"{neg}/{len(evidence)} evidence conversations are negative, matching a claim about negative sentiment"))

    # 4. sample size -----------------------------------------------------------------------------
    small = []
    for op, r in tool_results.items():
        for m in r.get("metrics", []):
            if m.get("denominator") is not None and 0 < m["denominator"] < SMALL_N:
                small.append(f"{m['label']} (n={int(m['denominator'])})")
        for row in ((r.get("table") or {}).get("rows") or [])[:10]:
            n = row.get("conversations") or row.get("with_factor")
            if isinstance(n, (int, float)) and 0 < n < SMALL_N:
                small.append(f"{row.get('name') or row.get('factor') or row.get('agent_id')} (n={int(n)})")
    small = list(dict.fromkeys(small))
    disclosed = any(re.search(r"small|few|wide|sample|minimum", n, re.I) for r in tool_results.values() for n in r.get("uncertainty_notes", []))
    checks.append(_check("sample_size", "pass" if not small else "warn" if not disclosed else "pass",
                         "No group below 30 conversations" if not small else
                         f"{len(small)} group(s) below {SMALL_N} conversations" + (" — caveat attached" if disclosed else " — added a caveat"), small[:8]))
    added_notes = [] if not small or disclosed else [f"Some figures rest on fewer than {SMALL_N} conversations ({', '.join(small[:4])}); treat them as indicative."]

    # 5. counter-evidence ------------------------------------------------------------------------
    counter = []
    if rank and rank["status"] == "ok" and rank["table"]["rows"]:
        first = rank["table"]["rows"][0]
        if first.get("negative_rate") is not None:
            counter.append(f"{1 - first['negative_rate']:.0%} of {first['name']} conversations were not negative.")
    if rc and rc["status"] == "ok":
        h = next((h for h in rc["table"]["rows"] if h["role"] != "customer_reaction" and h["strength"] in SUPPORTED), None)
        if h:
            counter.append(f"{1 - h['negative_rate_with']:.0%} of conversations with '{h['factor'].replace('_', ' ')}' were not negative, "
                           f"and {h['negative_rate_without']:.0%} without it were negative anyway.")
    traj = tool_results.get("sentiment_trajectory")
    if traj and traj["status"] == "ok":
        ups = [t for t in traj["series"]["turning_points"]["rows"] if t["direction"] == "improved"]
        if ups:
            counter.append(f"Sentiment also improved at turn(s) {', '.join(str(t['turn_index']) for t in ups[:4])}; the arc is not uniformly negative.")
    checks.append(_check("counter_evidence", "pass", "Counter-evidence stated alongside the claim" if counter else "No counter-evidence applicable", counter))

    # 6. causal language -------------------------------------------------------------------------
    text = " ".join([explanation.get("headline", ""), explanation.get("answer", "")] + explanation.get("key_points", []))
    hits = _causal_hits(text)
    if hits:
        explanation = {**explanation, "headline": qualify(explanation.get("headline", "")), "answer": qualify(explanation.get("answer", "")),
                       "key_points": [qualify(k) for k in explanation.get("key_points", [])]}
        challenges.append("Causal wording was rewritten as association: this observational data cannot establish cause.")
    checks.append(_check("causal_language", "warn" if hits else "pass",
                         f"Rewrote causal wording as association: {sorted(set(h.lower() for h in hits))}" if hits else "No unqualified causal claims", hits))

    # 7. claim consistency (root cause) ------------------------------------------------------------
    replaced = False
    if rc and rc["status"] == "ok":
        supported = {h["factor"] for h in rc["series"]["all_factors"]["rows"] if h["strength"] in SUPPORTED and h["role"] != "customer_reaction"}
        lead = explanation.get("headline", "")
        named = {f for f, pat in FACTOR_WORDS.items() if re.search(pat, lead, re.I)}
        unsupported = sorted(named - supported - {"escalation", "urgency"})
        status = "fail" if unsupported else "pass"
        checks.append(_check("claim_consistency", status,
                             f"Headline names factors the analysis does not support: {unsupported}" if unsupported
                             else "Factors named in the headline are supported by the tests", unsupported))
        if unsupported:
            challenges.append(f"The explanation named {', '.join(u.replace('_', ' ') for u in unsupported)} as a driver, but the tests do not support it.")
            replaced = explanation_source == "llm"

    # 8. statement provenance (top statements) ---------------------------------------------------
    st = tool_results.get("top_statements")
    if st and st.get("status") == "ok":
        pol = st["params"]["polarity"]
        claimed = {mid: r["statement"] for r in st["table"]["rows"] for mid in r["example_message_ids"]}
        src = db.query(f"""SELECT m.message_id, m.masked_text, m.speaker_role, l.sentiment FROM messages m JOIN message_labels l USING (message_id)
                           WHERE m.message_id IN ({','.join('?' * len(claimed))})""", list(claimed))
        ok = {r.message_id for r in src.itertuples() if r.masked_text == claimed[r.message_id] and r.speaker_role == "customer" and r.sentiment == pol}
        bad = sorted(set(claimed) - ok)
        checks.append(_check("statement_provenance", "fail" if bad else "pass",
                             f"{len(ok)}/{len(claimed)} example messages re-read: customer-authored, labelled {pol}, text matches" if not bad
                             else f"{len(bad)} example message(s) do not match the claimed statement, speaker or polarity", bad))

    statuses = [c["status"] for c in checks]
    verdict = "challenged" if "fail" in statuses else "partially supported" if statuses.count("warn") >= 2 else "supported"
    review = {"verdict": verdict, "checks": checks, "challenges": challenges, "counter_evidence": counter, "added_notes": added_notes,
              "replaced_explanation": replaced,
              "passed": statuses.count("pass"), "total": len(checks)}
    return review, explanation
