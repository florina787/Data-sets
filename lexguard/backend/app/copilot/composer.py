"""Composes the typed Copilot response from graph state. The frontend never parses agent prose."""

from __future__ import annotations

STATUS_PRIORITY = ["ACCESS_DENIED", "BLOCKED", "HALTED", "ERROR", "HUMAN_DECISION_REQUIRED", "NEEDS_INPUT",
                   "REVIEW_REQUIRED", "COMPLETED"]


def _metric(label: str, value, tone: str | None = None, hint: str | None = None) -> dict:
    return {"label": label, "value": value, "tone": tone, "hint": hint}


def _action(aid: str, label: str, kind: str, **payload) -> dict:
    return {"id": aid, "label": label, "kind": kind, "payload": payload}


def _evidence_for(f: dict, citations_by_f: dict, store, playbook_text: dict) -> dict:
    vers = citations_by_f.get(f["finding_id"], [])
    return {
        "finding_id": f["finding_id"], "doc_id": f["doc_id"], "doc_title": f["doc_title"], "section_id": f["section_id"],
        "heading": f["heading"], "text": f["clause_text"],
        "highlight": (f["propositions"][0].get("citation") or {}).get("quote"),
        "playbook": {"result": f.get("playbook_result"), "rule_id": f.get("rule_id"), "topic": f.get("playbook_topic"),
                     "standard_position": f.get("standard_position"),
                     "playbook_source": playbook_text.get(f.get("playbook_section_id"))},
        "verification": [{"pid": v["pid"], "claim": v["claim"], "status": v["status"], "reasons": v["reasons"],
                          "doc_id": v["doc_id"], "section_id": v["section_id"]} for v in vers],
        "evidence_status": ("VERIFIED" if vers and all(v["status"] == "SUPPORTED" for v in vers) else "NEEDS_REVIEW"),
    }


def compose(state: dict, ctx, status: str, value: dict | None) -> dict:
    store = ctx.store
    intent = state.get("intent", "unknown")
    mg = state.get("ai_policy") or {}
    matter = store.matters.get(ctx.matter_id) if ctx.matter_id else None
    cards: list[dict] = []
    actions: list[dict] = []
    findings_out: list[dict] = []
    evidence: list[dict] = []
    deviations: list[dict] = []
    answer = state.get("answer") or ""
    citations = state.get("citations", [])
    citations_by_f: dict[str, list] = {}
    for c in citations:
        if c.get("finding_id"):
            citations_by_f.setdefault(c["finding_id"], []).append(c)
    assurance = state.get("assurance_result")
    review = state.get("review") or {}
    findings = state.get("findings") or (state.get("work_product") or {}).get("findings") or []

    # ------------------------------------------------------------------ blocked / denied states
    if status == "ACCESS_DENIED":
        acc = state.get("ethical_wall_status") if (state.get("ethical_wall_status") or {}).get("blocked") else state.get("matter_access")
        wall = bool((state.get("ethical_wall_status") or {}).get("blocked"))
        answer = ("Access denied. " + (acc or {}).get("reason", "") +
                  " No documents were retrieved and the attempt has been logged as a security event.")
        cards.append({"type": "ACCESS_DENIED", "title": "Ethical wall enforced" if wall else "Matter access denied",
                      "severity": "CRITICAL", "body": (acc or {}).get("reason"),
                      "metrics": [_metric("Documents retrieved", 0, "good"), _metric("Security event", "Logged", "warn"),
                                  _metric("Control", "Ethical wall" if wall else "RBAC / matter team")],
                      "items": [], "actions": []})
    elif status == "BLOCKED" and intent != "cross_matter_request":
        ev = [e for e in mg.get("policy_evidence", []) if e["effect"] == "PROHIBIT"]
        answer = ("Blocked. " + " ".join(mg.get("reasons", [])) +
                  (" Permitted alternative: " + mg["alternatives"][0] if mg.get("alternatives") else ""))
        cards.append({"type": "POLICY_BLOCK", "title": "External legal-AI request blocked", "severity": "HIGH",
                      "body": mg.get("client_policy_summary"),
                      "metrics": [_metric("Decision", mg.get("decision"), "bad"), _metric("Risk", mg.get("risk")),
                                  _metric("Data sent externally", "None", "good")],
                      "items": [{"rule_id": e["rule_id"], "text": e["description"], "source": e.get("source_doc_id"),
                                 "section": e.get("source_section_id")} for e in ev],
                      "actions": []})
        cards.append({"type": "NEXT_ACTION", "title": "Allowed alternatives", "severity": None, "body": None, "metrics": [],
                      "items": [{"text": a} for a in mg.get("alternatives", [])], "actions": []})
        actions.append(_action("use-internal", "Analyse with Internal RAG", "copilot",
                               message="Review the contracts in this matter for change-of-control clauses."))
        actions.append(_action("why-blocked", "Why was this blocked?", "copilot", message="Why was this workflow blocked?"))
        actions.append(_action("open-audit", "Open audit event", "navigate", href=f"/audit?matter={ctx.matter_id}"))
    elif status == "HUMAN_ROUTE":
        answer = ("AI is not permitted on this matter. " + " ".join(mg.get("reasons", [])[:1]) +
                  " The request has been routed to the matter team; traditional (non-generative) search remains available.")
        cards.append({"type": "POLICY_BLOCK", "title": "Level 0 - AI prohibited", "severity": "HIGH",
                      "body": mg.get("client_policy_summary"),
                      "metrics": [_metric("Route", "Human lawyer"), _metric("AI tools", "Blocked", "bad")],
                      "items": [{"text": a} for a in mg.get("alternatives", [])], "actions": []})
        status = "BLOCKED"

    # ------------------------------------------------------------------ change-of-control family
    elif state.get("work_product", {}).get("kind") in ("coc_review", "draft") or intent in (
            "contract_review", "playbook_compare", "escalation_query", "show_evidence", "draft_memo", "client_draft"):
        pb = store.playbook_for_practice(matter.practice_id) if matter else None
        pb_doc = store.knowledge.get(pb.source_doc_id) if pb else None
        pb_text = {s.section_id: {"doc_id": pb_doc.doc_id, "section_id": s.section_id, "heading": s.heading, "text": s.text}
                   for s in pb_doc.sections} if pb_doc else {}
        evid_all = [_evidence_for(f, citations_by_f, store, pb_text) for f in findings]
        issues = [e for e in evid_all if e["evidence_status"] != "VERIFIED"]
        devs = [e for e in evid_all if e["playbook"]["result"] in ("DEVIATION", "ESCALATION_REQUIRED")]
        escs = [e for e in devs if e["playbook"]["result"] == "ESCALATION_REQUIRED"]
        for e in evid_all:
            findings_out.append({"finding_id": e["finding_id"], "doc_id": e["doc_id"], "doc_title": e["doc_title"],
                                 "heading": e["heading"], "playbook_result": e["playbook"]["result"],
                                 "rule_id": e["playbook"]["rule_id"], "topic": e["playbook"]["topic"],
                                 "evidence_status": e["evidence_status"], "summary": e["text"][:220]})
        deviations = [{"finding_id": e["finding_id"], "doc_id": e["doc_id"], "doc_title": e["doc_title"],
                       "result": e["playbook"]["result"], "rule_id": e["playbook"]["rule_id"], "topic": e["playbook"]["topic"],
                       "standard_position": e["playbook"]["standard_position"], "clause": e["text"]} for e in devs]
        sel = state.get("selected_finding_id")
        if intent == "show_evidence":
            evidence = [e for e in evid_all if e["finding_id"] == sel] if sel else (escs + issues)
        elif intent == "escalation_query":
            evidence = escs
        else:
            evidence = sorted(devs + [i for i in issues if i not in devs], key=lambda e: (
                {"ESCALATION_REQUIRED": 0, "DEVIATION": 1}.get(e["playbook"]["result"], 2), e["doc_id"]))
        n_proc = review.get("documents_processed", 0)
        if intent in ("draft_memo", "client_draft") and state.get("draft"):
            d = state["draft"]
            answer = (f"{d['title']} prepared from verified findings only. "
                      f"{len(d['excluded_pending_review'])} finding(s) with unverified evidence were excluded and listed for lawyer review. "
                      + ("External delivery requires assurance PASS and Senior Associate/Partner approval."
                         if d["client_facing"] else "Lawyer review required before use."))
            cards.append({"type": "DRAFT", "title": d["title"], "severity": None, "body": d["disclaimer"],
                          "metrics": [_metric("Paragraphs", len(d["paragraphs"])),
                                      _metric("Excluded (unverified)", len(d["excluded_pending_review"]),
                                              "warn" if d["excluded_pending_review"] else "good"),
                                      _metric("Destination", d["destination"].replace("_", " "))],
                          "items": d["paragraphs"], "actions": []})
        elif intent == "escalation_query":
            answer = (f"{len(escs)} provision(s) require partner escalation under the "
                      f"{pb.title if pb else 'practice playbook'}: " +
                      "; ".join(f"{e['doc_title']} ({e['playbook']['topic']})" for e in escs) + ".")
        elif intent == "show_evidence":
            answer = (f"Showing source evidence for {len(evidence)} finding(s)" +
                      (" (selected finding)." if sel else ": escalations and findings that need evidence review."))
        else:
            answer = (f"Change-of-control review of {matter.name if matter else ''}: {n_proc} of "
                      f"{review.get('documents_in_matter', n_proc)} documents processed; {len(findings)} change-of-control clauses "
                      f"identified; {len(devs)} deviate from the M&A playbook ({len(escs)} require partner escalation); "
                      f"{len(issues)} finding(s) require evidence review." +
                      (f" Assurance {assurance['score_pct']}% ({assurance['status'].replace('_', ' ')})." if assurance else "") +
                      " Lawyer approval is required before use.")
        cards.insert(0, {"type": "ANALYSIS_SUMMARY", "title": "Change-of-control review", "severity": None,
                         "body": f"Playbook: {pb.title} v{pb.version}" if pb else None,
                         "metrics": [_metric("Contracts analysed", n_proc, hint=f"{review.get('documents_in_matter', n_proc)} in matter; "
                                             f"{review.get('duplicates', 0)} duplicates, {review.get('unreadable', 0)} unreadable excluded"),
                                     _metric("Clauses identified", len(findings)),
                                     _metric("Playbook deviations", len(devs), "warn" if devs else "good"),
                                     _metric("Escalation candidates", len(escs), "bad" if escs else "good"),
                                     _metric("Evidence issues", len(issues), "warn" if issues else "good")],
                         "items": [], "actions": []})
        if devs and intent not in ("show_evidence",):
            cards.append({"type": "PLAYBOOK_DEVIATION", "title": "Playbook deviations", "severity": "MEDIUM",
                          "body": "Classified deterministically against the practice playbook.", "metrics": [],
                          "items": deviations, "actions": []})
        if issues and intent not in ("show_evidence", "escalation_query"):
            cards.append({"type": "FINDING", "title": "Findings that require evidence review", "severity": "MEDIUM",
                          "body": "Do not rely on these findings until a lawyer resolves the evidence issue.", "metrics": [],
                          "items": [{"finding_id": i["finding_id"], "doc_id": i["doc_id"], "doc_title": i["doc_title"],
                                     "issues": [v for v in i["verification"] if v["status"] != "SUPPORTED"]} for i in issues],
                          "actions": []})
        if review.get("injection_flags"):
            cards.append({"type": "SECURITY", "title": "Embedded instructions detected in documents", "severity": "HIGH",
                          "body": "Treated as data. No instruction was executed and permissions were not changed.",
                          "metrics": [], "items": review["injection_flags"], "actions": []})
        actions += [
            _action("view-evidence", "View Evidence", "panel", tab="evidence"),
            _action("review-exceptions", "Review Exceptions", "copilot", message="Show me the evidence for the findings that need review."),
            _action("compare-playbook", "Compare Playbook", "panel", tab="playbook"),
            _action("draft-memo", "Draft Memo", "copilot", message="Draft a due diligence summary using only verified findings."),
            _action("send-review", "Send for Review", "panel", tab="approval"),
        ]

    # ------------------------------------------------------------------ other intents
    elif intent == "legal_judgment" or status == "HUMAN_DECISION_REQUIRED":
        status = "HUMAN_DECISION_REQUIRED"
        rd = state.get("routing_decision") or {}
        answer = ("This is a consequential legal judgment and is reserved to the responsible lawyer and the client. "
                  "LexGuard will not recommend whether to accept or reject. AI can support the decision with: "
                  + "; ".join(rd.get("ai_support_permitted", [])) + ". A cited decision-support pack is attached.")
        cards.append({"type": "HUMAN_JUDGMENT", "title": "Lawyer decision required", "severity": "HIGH",
                      "body": "Route: Human lawyer. AI support is limited to research, evidence synthesis and non-decisional scenario framing.",
                      "metrics": [_metric("Legal-judgment risk", (state.get("ai_suitability") or {}).get("legal_judgment_risk"), "bad"),
                                  _metric("Autonomy risk", (state.get("ai_suitability") or {}).get("autonomy_risk"), "bad"),
                                  _metric("Route", "HUMAN LAWYER")],
                      "items": [{"text": s} for s in rd.get("ai_support_permitted", [])], "actions": []})
        wp = state.get("work_product") or {}
        if wp.get("scenarios"):
            cards.append({"type": "ANALYSIS", "title": "Scenario framing (non-decisional)", "severity": None,
                          "body": "Structure for the lawyer's analysis. Contains no recommendation.", "metrics": [],
                          "items": wp["scenarios"], "actions": []})
    elif intent in ("citation_verify",):
        cs = (assurance or {}).get("citation_summary", {})
        answer = (f"Citation verification of '{(state.get('work_product') or {}).get('title', '')}': "
                  f"{cs.get('SUPPORTED', 0)} supported, {cs.get('PARTIALLY_SUPPORTED', 0)} partially supported, "
                  f"{cs.get('UNSUPPORTED', 0)} unsupported, {cs.get('SOURCE_NOT_FOUND', 0)} source not found. "
                  "Unsupported propositions must not be relied on; lawyer review required.")
    elif intent == "recommendation_check":
        res = state.get("playbook_results", [])
        answer = ("Playbook check of the AI recommendations: " +
                  "; ".join(f"{r['subject_id']} {r['result'].replace('_', ' ')}" for r in res) +
                  ". Recommendations that conflict with the playbook require escalation before use.")
        deviations = [{"finding_id": r["subject_id"], "doc_id": None, "doc_title": "AI recommendation", "result": r["result"],
                       "rule_id": r["rule_id"], "topic": r["topic"], "standard_position": r["standard_position"],
                       "clause": r["subject_text"]} for r in res]
        cards.append({"type": "PLAYBOOK_DEVIATION", "title": "AI recommendation vs playbook", "severity": "HIGH",
                      "body": "PlaybookGuard compares AI recommendations with the firm's standard positions.", "metrics": [],
                      "items": deviations, "actions": []})
    elif intent in ("policy_question", "explain_block", "cross_matter_request"):
        extra = state.get("response_extras") or {}
        if extra.get("provider_matrix"):
            cards.append({"type": "PROVIDER_MATRIX", "title": "Provider permissions for this matter", "severity": None,
                          "body": mg.get("client_policy_summary"), "metrics": [], "items": extra["provider_matrix"], "actions": []})
        if intent == "cross_matter_request":
            cards.append({"type": "SECURITY", "title": "Cross-matter request refused", "severity": "CRITICAL",
                          "body": "Matter boundaries are enforced by deterministic controls before retrieval.",
                          "metrics": [_metric("Documents retrieved outside matter", 0, "good")], "items": [], "actions": []})
    elif intent == "value_query":
        a = state.get("analysis") or {}
        m = a.get("matter") or {}
        answer = (f"Estimated net hours saved on this matter: {m.get('net_hours_saved', 0)} "
                  f"({m.get('productivity_improvement_pct', 0)}% vs traditional estimate). {a.get('label', '')}")
        cards.append({"type": "VALUE", "title": "ValueIQ - matter estimate", "severity": None, "body": a.get("formula"),
                      "metrics": [_metric("Traditional hours", m.get("traditional_hours")),
                                  _metric("Lawyer review hours", m.get("lawyer_review_hours")),
                                  _metric("Net hours saved", m.get("net_hours_saved"), "good"),
                                  _metric("Est. value (USD)", m.get("estimated_value_usd"))], "items": [], "actions": []})
        actions.append(_action("open-valueiq", "Open ValueIQ", "navigate", href="/valueiq"))
    elif intent == "privilege_review":
        flags = state.get("privilege_flags", [])
        answer = (f"Confidentiality review flagged {len(flags)} POTENTIAL privilege/confidentiality risk(s). "
                  "These are not privilege determinations; a lawyer must review.")
    elif state.get("analysis"):
        a = state["analysis"]
        answer = answer or {
            "summary": f"Extractive summary of {a.get('title', '')}.",
            "obligations": f"{len(a.get('items', []))} obligations extracted from {a.get('title', '')}.",
            "timeline": f"{len(a.get('items', []))} dated events extracted.",
            "entities": f"Entities extracted from {a.get('title', '')}.",
            "comparison": f"Comparison of {a.get('doc_a')} and {a.get('doc_b')}.",
            "search": f"{a.get('total', 0)} documents matched (keyword search, no generative AI).",
        }.get(a.get("type"), "Analysis complete.")
        cards.append({"type": "ANALYSIS", "title": a.get("type", "analysis").title(), "severity": None, "body": None,
                      "metrics": [], "items": a.get("items") or a.get("points") or a.get("sections") or
                      [{k: v for k, v in a.items() if k in ("parties", "amounts", "percentages", "durations", "dates")}],
                      "actions": []})
    elif state.get("work_product"):
        wp = state["work_product"]
        answer = answer or f"{wp['title']}: {len(wp.get('points', []))} cited points from permitted sources."
    if not answer:
        answer = "No result."

    # ------------------------------------------------------------------ shared cards
    flags = state.get("privilege_flags", [])
    if flags:
        cards.append({"type": "RISK", "title": "POTENTIAL PRIVILEGE / CONFIDENTIALITY RISK", "severity": "HIGH",
                      "body": "Flags indicate potential risk only. Lawyer review required.", "metrics": [],
                      "items": flags, "actions": []})
    if citations and intent in ("citation_verify", "research", "knowledge_question", "legal_judgment", "summarize",
                                "extract_obligations", "extract_timeline"):
        cards.append({"type": "CITATION_REPORT", "title": "Citation verification", "severity": None,
                      "body": "Each material proposition checked against permitted sources.", "metrics": [],
                      "items": [{"pid": c["pid"], "claim": c["claim"], "status": c["status"], "doc_id": c["doc_id"],
                                 "section_id": c["section_id"], "source_title": c["source_title"], "evidence": c["evidence_text"],
                                 "reasons": c["reasons"]} for c in citations], "actions": []})
    if assurance:
        cards.append({"type": "ASSURANCE", "title": "WorkProduct assurance", "severity": None, "body": assurance["meaning"],
                      "metrics": [_metric("Assurance", f"{assurance['score_pct']}%",
                                          "good" if assurance["status"] == "PASS" else "warn"),
                                  _metric("Status", assurance["status"].replace("_", " ")),
                                  _metric("Unsupported-claim rate", f"{assurance['unsupported_claim_rate']:.1%}")],
                      "items": [{"component": k, "value": v, "weight": assurance["weights"][k]} for k, v in assurance["components"].items()],
                      "actions": []})
    hr = state.get("human_review")
    if hr:
        cards.append({"type": "APPROVAL", "title": "Lawyer approval required", "severity": None, "body": hr["reason"],
                      "metrics": [_metric("Review level", hr["label"]),
                                  _metric("Approver", " / ".join(r.replace("_", " ").title() for r in hr["required_roles"])),
                                  _metric("External delivery", "Allowed after approval" if hr["external_delivery_allowed"]
                                          else "Blocked until assurance passes", "good" if hr["external_delivery_allowed"] else "warn")],
                      "items": [], "actions": [_action("approve", "Approve", "review", work_product_id=hr["work_product_id"]),
                                               _action("reject", "Reject", "review", work_product_id=hr["work_product_id"])]})
    if actions:
        cards.append({"type": "NEXT_ACTION", "title": "Recommended actions", "severity": None, "body": None, "metrics": [],
                      "items": [], "actions": actions})

    if status == "COMPLETED" and hr:
        status = "REVIEW_REQUIRED"
    sources = state.get("retrieved_sources", [])
    return {
        "answer": answer, "status": status, "risk": state.get("risk") or mg.get("risk") or "HIGH", "intent": intent,
        "findings": findings_out, "evidence": evidence, "citations": citations, "playbook_deviations": deviations,
        "actions": actions, "cards": cards, "approval_required": bool(hr),
        "approval": hr, "matterguard": mg or None, "routing": state.get("routing_decision"),
        "suitability": state.get("ai_suitability"), "assurance": assurance, "privilege_flags": flags,
        "sources": [{k: s.get(k) for k in ("doc_id", "section_id", "title", "heading", "text", "kind", "score",
                                            "untrusted_instruction_detected")} for s in sources][:25],
        "draft": state.get("draft"), "work_product_id": (hr or {}).get("work_product_id"),
        "analysis": state.get("analysis"), "review_summary": review or None, "value_estimate": value,
        "injection_flags": state.get("injection_flags", []),
    }
