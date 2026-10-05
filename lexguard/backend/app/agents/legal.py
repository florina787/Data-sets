"""Work agents: Legal Knowledge, Document Analysis, Legal Research, Drafting, Policy explainer,
Value Analysis, traditional search and work-product intake.

All document and knowledge access goes through the sealed AccessScope and the ToolGateway.
"""

from __future__ import annotations

import re

from app.audit import service as audit_service
from app.citations import verifier
from app.documents import analysis
from app.documents.access import permitted_document, permitted_documents
from app.drafting import drafter
from app.graph.context import RunContext
from app.matterguard import guard as matterguard
from app.playbooks import guard as playbookguard
from app.privilege import guard as privilegeguard
from app.rag import retriever
from app.rag.index import tokenize
from app.valueiq import service as valueiq

COC_INTENTS = {"contract_review", "playbook_compare", "escalation_query", "show_evidence", "draft_memo", "client_draft",
               "external_provider_request"}
KNOWLEDGE_KINDS = {"firm_policy", "client_instruction", "outside_counsel_guideline", "playbook", "precedent", "template",
                   "research_note", "institutional"}


def _wp_id(prefix: str, ctx: RunContext) -> str:
    return f"{prefix}-{ctx.request_id[-10:].upper()}"


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", text.strip())[0]


def _source_points(sources: list[retriever.RetrievedSource]) -> list[dict]:
    pts = []
    for s in sources:
        sent = _first_sentence(s.text)
        pts.append({"text": sent, "citation": {"doc_id": s.doc_id, "section_id": s.section_id, "quote": sent},
                    "title": s.title, "heading": s.heading})
    return pts


def _sources_json(sources) -> list[dict]:
    return [s.model_dump() for s in sources]


# --------------------------------------------------------------------------------------------
def legal_knowledge(state: dict, ctx: RunContext) -> dict:
    query = state["task"]
    if state["intent"] == "playbook_compare":
        query = "playbook change of control consent veto termination escalation"
    top_k = int(ctx.cfg.get("top_k", 5))
    srcs = ctx.tools.call("legal_knowledge", "knowledge_search", retriever.search, ctx.scope, query, top_k=top_k,
                          kinds=KNOWLEDGE_KINDS)
    ctx.audit("RETRIEVAL", {"agent": "legal_knowledge", "source_ids": [s.source_id for s in srcs],
                            "partitions": sorted(ctx.scope.permitted_labels)})
    out = {"retrieved_sources": state.get("retrieved_sources", []) + _sources_json(srcs),
           "agent_trace": [{"label": f"{len(srcs)} knowledge sources retrieved (permission-aware)", "agent": "legal_knowledge",
                            "status": "ok" if srcs else "warn", "detail": ", ".join(sorted({s.doc_id for s in srcs})) or "No sources"}],
           "agents_invoked": ["legal_knowledge"]}
    if state["intent"] == "knowledge_question":
        points = _source_points(srcs)
        out["work_product"] = {"work_product_id": _wp_id("WP-KQA", ctx), "kind": "knowledge_answer",
                               "title": "Knowledge answer", "destination": state.get("destination", "internal"),
                               "points": points,
                               "propositions": [{"pid": f"P{i + 1}", "claim": p["text"], "citation": p["citation"], "material": True}
                                                for i, p in enumerate(points)]}
    return out


# --------------------------------------------------------------------------------------------
def _coc_findings_from_review(review: analysis.CoCReview) -> list[dict]:
    return [f.model_dump() for f in review.findings]


def document_analysis(state: dict, ctx: RunContext) -> dict:
    intent = state["intent"]
    store = ctx.store
    route = (state.get("routing_decision") or {}).get("route")
    docs = ctx.tools.call("document_analysis", "matter_document_search", permitted_documents, store, ctx.scope, ctx.matter_id)
    trace: list[dict] = []
    out: dict = {"agents_invoked": ["document_analysis"]}

    if intent in COC_INTENTS:
        if route == "EXTERNAL_LEGAL_AI":
            excluded = set(ctx.mg.excluded_doc_sensitivities)
            payload = [{"doc_id": d.doc_id, "title": d.title,
                        "sections": [s.model_dump() for s in d.sections]} for d in docs
                       if d.status == "active" and d.sensitivity not in excluded]
            result = ctx.tools.call("document_analysis", "external_provider_call", ctx.providers.invoke,
                                    state["provider"], "analyze_documents", payload,
                                    "Identify change-of-control provisions.")
            trace.append({"label": f"External provider analysed {len(payload)} documents (simulated, no network call)",
                          "agent": "document_analysis", "status": "ok",
                          "detail": f"Provider {state['provider']}; output returned to LexGuard assurance"})
            findings = []
            by_id = {d.doc_id: d for d in docs}
            for item in result.get("clauses", []):
                d = by_id[item["doc_id"]]
                fid = f"F-{d.doc_id}-{item['section_id']}"
                findings.append({"finding_id": fid, "doc_id": d.doc_id, "doc_title": d.title, "counterparty": d.counterparty,
                                 "doc_type": d.doc_type, "section_id": item["section_id"], "heading": item["heading"],
                                 "clause_text": item["clause_text"], "provider_output": True,
                                 "propositions": [{"pid": f"{fid}-P1", "material": True,
                                                   "claim": f"{d.title} contains a change-of-control provision in {item['heading']}.",
                                                   "citation": {"doc_id": d.doc_id, "section_id": item["section_id"],
                                                                "quote": item.get("quote")}}]})
            review_summary = {"documents_in_matter": len(docs), "documents_in_scope": len(payload),
                              "documents_processed": len(payload), "duplicates": 0, "unreadable": 0,
                              "excluded_total": len(docs) - len(payload), "clauses": len(findings), "injection_flags": [],
                              "provider_id": state["provider"]}
        else:
            review = ctx.tools.call("document_analysis", "clause_extraction", analysis.review_change_of_control,
                                    ctx.matter_id, docs)
            findings = _coc_findings_from_review(review)
            dup, unread = len(review.excluded["duplicate"]), len(review.excluded["unreadable"])
            review_summary = {"documents_in_matter": review.documents_in_scope,
                              "documents_in_scope": review.documents_in_scope - dup,
                              "documents_processed": review.documents_processed, "duplicates": dup, "unreadable": unread,
                              "excluded": review.excluded, "excluded_total": dup + unread, "clauses": len(findings),
                              "injection_flags": review.injection_flags,
                              "non_coc_control_mentions": review.non_coc_control_mentions}
            trace.append({"label": f"{review.documents_processed} documents retrieved and analysed",
                          "agent": "document_analysis", "status": "ok",
                          "detail": f"{review.documents_in_scope} in matter; {dup} duplicates and {unread} unreadable scans excluded"})
            trace.append({"label": f"Contract analysis completed - {len(findings)} change-of-control clauses",
                          "agent": "document_analysis", "status": "ok",
                          "detail": f"{review.non_coc_control_mentions} other 'control' mentions (e.g. quality/export control) ignored"})
            if review.injection_flags:
                for f in review.injection_flags:
                    ctx.audit("PROMPT_INJECTION_DETECTED", {"source": f["doc_id"], "section_id": f["section_id"],
                                                            "patterns": f["patterns"]}, "WARNING")
                trace.append({"label": f"{len(review.injection_flags)} document(s) contain embedded instructions - treated as data",
                              "agent": "document_analysis", "status": "warn",
                              "detail": "No instruction executed; scope, RBAC and ethical walls unchanged."})
                out["injection_flags"] = state.get("injection_flags", []) + review.injection_flags
        ctx.audit("RETRIEVAL", {"agent": "document_analysis", "documents_processed": review_summary["documents_processed"],
                                "finding_source_ids": sorted({f["doc_id"] for f in findings}),
                                "matter_partition": f"matter:{ctx.matter_id}"})
        out["review"] = review_summary
        out["findings"] = findings
        out["work_product"] = {
            "work_product_id": _wp_id("WP-COC", ctx), "kind": "coc_review",
            "title": f"Change-of-control review - {store.matters[ctx.matter_id].name}",
            "destination": state.get("destination", "internal"), "findings": findings,
            "propositions": [dict(p, finding_id=f["finding_id"]) for f in findings for p in f["propositions"]],
            "documents_in_scope": review_summary["documents_in_scope"],
            "documents_processed": review_summary["documents_processed"],
            "provider_id": state.get("provider"),
        }
        out["agent_trace"] = trace
        return out

    doc_ids = (state.get("intent_detail") or {}).get("doc_ids", [])
    target = None
    for did in doc_ids:
        target = permitted_document(store, ctx.scope, did)
        if target:
            break
    active = [d for d in docs if d.status == "active"]
    if doc_ids and target is None:
        out.update(status="NEEDS_INPUT",
                   answer="The referenced document is not available in this matter for your access level.",
                   agent_trace=[{"label": "Document not available in permitted scope", "agent": "document_analysis",
                                 "status": "warn", "detail": "Only documents in the active matter can be analysed."}])
        return out
    target = target or (active[0] if active else None)
    if target is None:
        out.update(status="NEEDS_INPUT", answer="No readable documents are available in this matter.",
                   agent_trace=[{"label": "No documents available", "agent": "document_analysis", "status": "warn", "detail": ""}])
        return out

    if intent == "summarize":
        summ = ctx.tools.call("document_analysis", "summarize", analysis.summarize, target)
        points = [{"text": p["text"], "citation": dict(p["citation"], quote=p["text"])} for p in summ["points"]]
        out["analysis"] = {"type": "summary", **summ}
        label = f"Summarised {target.doc_id} ({len(points)} sections)"
    elif intent == "extract_obligations":
        obs = ctx.tools.call("document_analysis", "obligation_extract", analysis.extract_obligations, target)
        points = [{"text": o["obligation"], "citation": dict(o["citation"], quote=o["obligation"])} for o in obs]
        out["analysis"] = {"type": "obligations", "doc_id": target.doc_id, "title": target.title, "items": obs}
        label = f"Extracted {len(obs)} obligations from {target.doc_id}"
    elif intent == "extract_timeline":
        pool = [target] if doc_ids else active[:50]
        events = ctx.tools.call("document_analysis", "timeline_extract", analysis.extract_timeline, pool)
        points = [{"text": e["event"], "citation": {"doc_id": e["doc_id"], "section_id": e["section_id"], "quote": e["event"]}}
                  for e in events[:25]]
        out["analysis"] = {"type": "timeline", "items": events[:25]}
        label = f"Extracted {len(events)} dated events"
    elif intent == "extract_entities":
        ents = ctx.tools.call("document_analysis", "entity_extract", analysis.extract_entities, target)
        out["analysis"] = {"type": "entities", "doc_id": target.doc_id, "title": target.title, **ents}
        out["agent_trace"] = [{"label": f"Entities extracted from {target.doc_id}", "agent": "document_analysis",
                               "status": "ok", "detail": f"{sum(len(v) for v in ents.values())} entities"}]
        return out
    elif intent == "compare_documents":
        b = permitted_document(store, ctx.scope, doc_ids[1]) if len(doc_ids) > 1 else None
        if b is None:
            out.update(status="NEEDS_INPUT", answer="The second document is not available in this matter.",
                       agent_trace=[{"label": "Second document not in permitted scope", "agent": "document_analysis",
                                     "status": "warn", "detail": ""}])
            return out
        cmp_ = ctx.tools.call("document_analysis", "document_compare", analysis.compare_documents, target, b)
        out["analysis"] = {"type": "comparison", **cmp_}
        out["agent_trace"] = [{"label": f"Compared {target.doc_id} with {b.doc_id}", "agent": "document_analysis", "status": "ok",
                               "detail": f"{sum(1 for r in cmp_['sections'] if r['status'] != 'IDENTICAL')} differing sections"}]
        return out
    else:
        points, label = [], "No analysis performed"
    out["work_product"] = {"work_product_id": _wp_id("WP-DOC", ctx), "kind": intent, "title": f"{label}",
                           "destination": state.get("destination", "internal"), "points": points,
                           "propositions": [{"pid": f"P{i + 1}", "claim": p["text"], "citation": p["citation"], "material": True}
                                            for i, p in enumerate(points)]}
    out["agent_trace"] = [{"label": label, "agent": "document_analysis", "status": "ok", "detail": target.title}]
    return out


# --------------------------------------------------------------------------------------------
def legal_research(state: dict, ctx: RunContext) -> dict:
    top_k = int(ctx.cfg.get("top_k", 5))
    support_mode = state["intent"] == "legal_judgment"
    query = state["task"]
    if support_mode:
        k_src = ctx.tools.call("legal_research", "knowledge_search", retriever.search, ctx.scope,
                               "settlement evaluation factors litigation risk quantum", top_k=2, kinds=KNOWLEDGE_KINDS)
        m_src = ctx.tools.call("legal_research", "matter_document_search", retriever.search, ctx.scope, query + " offer damages quantum risk",
                               top_k=4, kinds={"matter_document"})
        srcs = k_src + m_src
    else:
        srcs = ctx.tools.call("legal_research", "knowledge_search", retriever.search, ctx.scope, query, top_k=top_k)
    ctx.audit("RETRIEVAL", {"agent": "legal_research", "source_ids": [s.source_id for s in srcs]})
    points = _source_points(srcs)
    title = "Decision-support pack (not a recommendation)" if support_mode else "Research summary"
    wp = {"work_product_id": _wp_id("WP-RES", ctx), "kind": "decision_support" if support_mode else "research_summary",
          "title": title, "destination": state.get("destination", "internal"), "points": points,
          "propositions": [{"pid": f"P{i + 1}", "claim": p["text"], "citation": p["citation"], "material": True}
                           for i, p in enumerate(points)]}
    if support_mode:
        wp["scenarios"] = [
            {"scenario": "Accept", "considerations": "Certainty of outcome and timing; release terms; confidentiality conditions."},
            {"scenario": "Reject / counter", "considerations": "Quantum range and limitation-of-liability risk; costs; time to trial."},
            {"scenario": "Defer", "considerations": "Offer expiry date; further evidence or mediation steps."},
        ]
    return {"retrieved_sources": state.get("retrieved_sources", []) + _sources_json(srcs), "work_product": wp,
            "agent_trace": [{"label": f"{len(srcs)} sources retrieved for {'decision support' if support_mode else 'research'}",
                             "agent": "legal_research", "status": "ok" if srcs else "warn",
                             "detail": ", ".join(sorted({s.doc_id for s in srcs}))}],
            "agents_invoked": ["legal_research"]}


# --------------------------------------------------------------------------------------------
def drafting(state: dict, ctx: RunContext) -> dict:
    wp = state.get("work_product") or {}
    if wp.get("kind") != "coc_review":
        return {"agent_trace": [{"label": "Drafting skipped - no verified analysis available", "agent": "drafting",
                                 "status": "warn", "detail": ""}], "agents_invoked": ["drafting"]}
    store = ctx.store
    matter = store.matters[ctx.matter_id]
    playbook = store.playbook_for_practice(matter.practice_id)
    findings = [dict(f) for f in wp["findings"]]
    ver_by_f: dict[str, list[dict]] = {}
    props = [dict(p, finding_id=f["finding_id"]) for f in findings for p in f["propositions"]]
    for v in ctx.tools.call("drafting", "citation_verify", verifier.verify_batch, store, ctx.scope, props,
                            strict_numbers=bool(ctx.cfg.get("strict_numbers", True))):
        ver_by_f.setdefault(v["finding_id"], []).append(v)
    if playbook:
        classified = ctx.tools.call("drafting", "playbook_compare",
                                    lambda: [playbookguard.classify_clause(playbook, f["finding_id"], f["clause_text"]) for f in findings])
        for f, r in zip(findings, classified):
            f.update(playbook_result=r.result, rule_id=r.rule_id, standard_position=r.standard_position)
    review = state.get("review", {})
    summary = {"documents_processed": review.get("documents_processed", 0), "documents_in_scope": review.get("documents_in_matter", 0),
               "excluded_total": review.get("excluded_total", 0), "clauses": len(findings),
               "deviations": sum(1 for f in findings if f.get("playbook_result") in ("DEVIATION", "ESCALATION_REQUIRED")),
               "escalations": sum(1 for f in findings if f.get("playbook_result") == "ESCALATION_REQUIRED")}
    destination = state.get("destination", "internal")
    draft_type = "due_diligence_report" if destination.startswith("external") or "due diligence" in state["task"].lower() else "memo"
    d = ctx.tools.call("drafting", "draft_generate", drafter.draft_due_diligence, matter={"name": matter.name},
                       client={"name": store.clients[matter.client_id].name}, review_summary=summary, findings=findings,
                       verification_by_finding=ver_by_f, draft_type=draft_type, destination=destination)
    included = {c["doc_id"] for p in d["paragraphs"] for c in p["citations"]}
    props = []
    for f in findings:
        if f["doc_id"] in included:
            p1 = f["propositions"][0]
            props.append(dict(p1, finding_id=f["finding_id"]))
    new_wp = {"work_product_id": _wp_id("WP-DRAFT", ctx), "kind": "draft", "title": d["title"], "destination": destination,
              "findings": [f for f in findings if f["doc_id"] in included], "propositions": props,
              "documents_in_scope": wp["documents_in_scope"], "documents_processed": wp["documents_processed"],
              "draft": d}
    return {"draft": d, "work_product": new_wp, "findings": findings,
            "agent_trace": [{"label": f"Draft prepared from {len(props)} verified findings", "agent": "drafting", "status":
                             "warn" if d["excluded_pending_review"] else "ok",
                             "detail": f"{len(d['excluded_pending_review'])} unverified finding(s) excluded (not silently included)"}],
            "agents_invoked": ["drafting"]}


# --------------------------------------------------------------------------------------------
def load_work_product(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    base_id = "WP-REC-MAPLE-002" if state["intent"] == "recommendation_check" else "WP-MEMO-MAPLE-001"
    pre = store.pregenerated.get(base_id)
    if pre is None or pre["matter_id"] != ctx.matter_id:
        return {"status": "NEEDS_INPUT", "answer": "No AI-generated work product is awaiting verification on this matter.",
                "agent_trace": [{"label": "No pending AI work product on this matter", "agent": "workproduct_assurance",
                                 "status": "warn", "detail": ""}], "agents_invoked": ["workproduct_assurance"]}
    wp = {"work_product_id": f"{base_id}-{ctx.request_id[-6:].upper()}", "source_work_product": base_id,
          "kind": pre["kind"], "title": pre["title"], "destination": pre["destination"], "provider_id": pre["provider_id"],
          "propositions": [dict(p, material=True) for p in pre.get("propositions", [])],
          "recommendations": pre.get("recommendations", [])}
    return {"work_product": wp,
            "agent_trace": [{"label": f"Loaded AI work product {base_id}", "agent": "workproduct_assurance", "status": "ok",
                             "detail": f"Generated by {store.providers[pre['provider_id']].name}"}],
            "agents_invoked": ["workproduct_assurance"]}


# --------------------------------------------------------------------------------------------
def privilege_scan(state: dict, ctx: RunContext) -> dict:
    docs = ctx.tools.call("privilege", "privilege_scan", permitted_documents, ctx.store, ctx.scope, ctx.matter_id)
    sources = [{"doc_id": d.doc_id, "matter_id": d.matter_id, "client_id": d.client_id, "sensitivity": d.sensitivity,
                "title": d.title, "text": " ".join(s.text for s in d.sections)} for d in docs if d.status == "active"]
    flags = privilegeguard.evaluate(active_matter_id=ctx.matter_id, active_client_id=ctx.client_id,
                                    destination=state.get("destination", "internal"), sources=sources)
    return {"privilege_flags": [f.model_dump() for f in flags], "analysis": {"type": "privilege_review", "documents": len(sources)},
            "agent_trace": [{"label": f"Confidentiality review completed - {len(flags)} potential risk flag(s)",
                             "agent": "privilege", "status": "warn" if flags else "ok",
                             "detail": "Potential risks only; lawyer review required."}],
            "agents_invoked": ["privilege"]}


# --------------------------------------------------------------------------------------------
def policy_explainer(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    intent = state["intent"]
    matter = store.matters[ctx.matter_id]
    client = store.clients[matter.client_id]
    trace_label = "Policy explanation prepared"
    extra: dict = {}
    if intent == "cross_matter_request":
        ctx.audit("SECURITY_CROSS_MATTER_ATTEMPT", {"referenced_matters_count": len(state["intent_detail"]["referenced_other_matters"]),
                                                     "retrieval_performed": False}, "CRITICAL")
        answer = ("LexGuard only works within the active matter. Requests that reference other matters are not executed, "
                  "and no documents outside this matter were searched. Switch matters (if you are authorised) to work on another matter.")
        trace_label = "Cross-matter request refused (no retrieval outside active matter)"
        status = "BLOCKED"
    elif intent == "explain_block":
        events = [e for e in audit_service.events_for_matter(ctx.matter_id, limit=200)
                  if e["user_id"] == ctx.user_id and e["request_id"] != ctx.request_id
                  and e["event_type"] in ("POLICY_BLOCK", "DELIVERY_BLOCKED", "SECURITY_ACCESS_DENIED",
                                          "SECURITY_ETHICAL_WALL_BLOCK", "TOOL_DENIED", "SECURITY_CROSS_MATTER_ATTEMPT")]
        if events:
            e = events[0]
            reasons = e["payload"].get("reasons") or [e["payload"].get("reason") or e["event_type"]]
            rules = e["payload"].get("rules") or [e["payload"].get("rule", "")]
            answer = (f"Your last blocked request on {matter.name} ({e['event_type'].replace('_', ' ').lower()}) was stopped by "
                      f"deterministic policy {', '.join(r for r in rules if r)}: {' '.join(reasons)}")
            alts = e["payload"].get("alternatives") or []
            if alts:
                answer += " Permitted alternative: " + alts[0]
            extra["blocked_event"] = e
        else:
            answer = f"No blocked workflow is recorded for you on {matter.name}."
        status = "COMPLETED"
    else:
        rows = []
        for p in store.providers.values():
            r = matterguard.evaluate(store, user_id=ctx.user_id, matter_id=ctx.matter_id, provider_id=p.provider_id,
                                     destination="internal", intent="policy_question")
            rows.append({"provider_id": p.provider_id, "provider": p.name, "external": p.external,
                         "decision": r.decision, "permitted": bool(r.provider_permitted),
                         "reasons": [e.description for e in r.policy_evidence if e.effect in ("PROHIBIT", "RESTRICT")][:2]})
        ext_ok = [r for r in rows if r["external"] and r["permitted"] and store.providers[r["provider_id"]].type == "EXTERNAL_LEGAL_AI"]
        if not client.ai_policy.ai_allowed:
            answer = f"No. {client.name} prohibits all AI use on its matters (POL-CLIENT-001). Work is routed to the matter team."
        elif not client.ai_policy.external_ai_allowed:
            answer = (f"No - external AI is prohibited for {client.name} (POL-CLIENT-003). "
                      f"Permitted alternative: LexGuard Internal RAG (firm-hosted) with lawyer review.")
        elif ext_ok:
            answer = (f"Yes, with controls. Approved external provider(s) for this matter: {', '.join(r['provider'] for r in ext_ok)}. "
                      f"Data up to '{client.ai_policy.max_external_classification}' only; lawyer review is mandatory.")
        else:
            answer = "No approved external provider is currently available for this matter."
        extra["provider_matrix"] = rows
        status = "COMPLETED"
    ev = client.ai_policy.evidence
    src = verifier.resolve_source(store, ctx.scope, ev["doc_id"])
    sec = src.section(ev["section_id"]) if src else None
    evidence = [{"doc_id": ev["doc_id"], "section_id": ev["section_id"], "title": src.title if src else None,
                 "text": sec.text if sec else None, "kind": "client_instruction"}] if sec else []
    return {"answer": answer, "status": status, "response_extras": extra, "retrieved_sources": evidence,
            "agent_trace": [{"label": trace_label, "agent": "ai_policy", "status": "blocked" if status == "BLOCKED" else "ok",
                             "detail": "Deterministic policy engine; no generative step."}],
            "agents_invoked": ["ai_policy"]}


# --------------------------------------------------------------------------------------------
def value_analysis(state: dict, ctx: RunContext) -> dict:
    m = ctx.tools.call("value_analysis", "value_calc", valueiq.metrics, ctx.store)
    row = next((r for r in m["by"]["matter"] if r["id"] == ctx.matter_id), None)
    return {"analysis": {"type": "value", "matter": row, "label": m["label"], "formula": m["formula"]},
            "agent_trace": [{"label": "ValueIQ estimate calculated", "agent": "value_analysis", "status": "ok",
                             "detail": m["label"]}], "agents_invoked": ["value_analysis"]}


def traditional_search(state: dict, ctx: RunContext) -> dict:
    docs = ctx.tools.call("traditional_search", "traditional_search", permitted_documents, ctx.store, ctx.scope, ctx.matter_id)
    q = set(tokenize(state["task"])) - {"find", "locate", "list", "document", "contract", "file"}
    hits = [d for d in docs if d.status == "active" and (not q or q & set(tokenize(d.title + " " + (d.doc_type or ""))))]
    return {"analysis": {"type": "search", "items": [{"doc_id": d.doc_id, "title": d.title} for d in hits[:25]],
                         "total": len(hits)},
            "agent_trace": [{"label": f"Keyword search returned {len(hits)} documents (no generative AI)",
                             "agent": "traditional_search", "status": "ok", "detail": ""}],
            "agents_invoked": ["traditional_search"]}


WORK_AGENTS = {
    "legal_knowledge": legal_knowledge, "document_analysis": document_analysis, "legal_research": legal_research,
    "drafting": drafting, "load_work_product": load_work_product, "privilege_scan": privilege_scan,
    "policy_explainer": policy_explainer, "value_analysis": value_analysis, "traditional_search": traditional_search,
}
