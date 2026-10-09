"""Assurance-chain agents: Citation Verification, Playbook, Privilege/Confidentiality, WorkProduct Assurance,
and the human-review gate."""

from __future__ import annotations

from app.assurance import pipeline
from app.citations import verifier
from app.governance import review as review_service
from app.graph.context import RunContext
from app.playbooks import guard as playbookguard
from app.privilege import guard as privilegeguard


def citation_check(state: dict, ctx: RunContext) -> dict:
    wp = state["work_product"]
    strict = bool(ctx.cfg.get("strict_numbers", True))
    results = ctx.tools.call("citation_verification", "citation_verify", verifier.verify_batch, ctx.store, ctx.scope,
                             wp.get("propositions", []), strict_numbers=strict)
    summ = verifier.summarize_results([verifier.VerificationResult(**{k: r[k] for k in verifier.VerificationResult.model_fields})
                                       for r in results])
    issues = summ["issues"]
    return {"citations": results,
            "agent_trace": [{"label": "Citation verification completed", "agent": "citation_verification",
                             "status": "ok", "detail": f"{summ['SUPPORTED']}/{summ['total']} supported"}] +
                           ([{"label": f"{issues} finding(s) require evidence review", "agent": "citation_verification",
                              "status": "warn",
                              "detail": f"{summ['PARTIALLY_SUPPORTED']} partial, {summ['UNSUPPORTED']} unsupported, "
                                        f"{summ['SOURCE_NOT_FOUND']} source not found"}] if issues else []),
            "agents_invoked": ["citation_verification"]}


def playbook_check(state: dict, ctx: RunContext) -> dict:
    wp = state["work_product"]
    store = ctx.store
    matter = store.matters[ctx.matter_id]
    results: list[dict] = []
    findings = [dict(f) for f in (state.get("findings") or wp.get("findings") or [])]
    if wp.get("recommendations"):
        pb = store.playbooks.get(wp["recommendations"][0].get("playbook_id")) or store.playbook_for_practice(matter.practice_id)
        checked = ctx.tools.call("playbook", "playbook_compare",
                                 lambda: [playbookguard.check_recommendation(pb, r["rid"], r["text"]) for r in wp["recommendations"]])
        results = [r.model_dump() for r in checked]
        label = f"AI recommendations compared with {pb.title}"
    elif findings:
        pb = store.playbook_for_practice(matter.practice_id)
        if pb is None:
            return {"playbook_results": [], "agent_trace": [{"label": "No playbook for this practice", "agent": "playbook",
                                                              "status": "skipped", "detail": ""}],
                    "agents_invoked": ["playbook"]}
        classified = ctx.tools.call("playbook", "playbook_compare",
                                    lambda: [playbookguard.classify_clause(pb, f["finding_id"], f["clause_text"]) for f in findings])
        for f, res in zip(findings, classified):
            f.update(playbook_result=res.result, rule_id=res.rule_id, standard_position=res.standard_position,
                     playbook_topic=res.topic, playbook_section_id=res.source_section_id)
            results.append(res.model_dump())
        label = f"{pb.title} comparison completed"
    else:
        return {"playbook_results": [], "agent_trace": [{"label": "Playbook check not applicable", "agent": "playbook",
                                                          "status": "skipped", "detail": "No clauses or recommendations"}],
                "agents_invoked": ["playbook"]}
    dev = sum(1 for r in results if r["result"] in ("DEVIATION", "ESCALATION_REQUIRED"))
    esc = sum(1 for r in results if r["result"] == "ESCALATION_REQUIRED")
    out = {"playbook_results": results,
           "agent_trace": [{"label": label, "agent": "playbook", "status": "warn" if esc else "ok",
                            "detail": f"{dev} deviation(s), {esc} escalation(s) required"}],
           "agents_invoked": ["playbook"]}
    if findings:
        out["findings"] = findings
    return out


def privilege_check(state: dict, ctx: RunContext) -> dict:
    wp = state["work_product"]
    store = ctx.store
    sources: dict[str, dict] = {}
    for p in wp.get("propositions", []):
        c = p.get("citation") or {}
        doc = verifier.resolve_source(store, ctx.scope, c.get("doc_id", "")) if c.get("doc_id") else None
        if doc is None:
            continue
        sec = doc.section(c.get("section_id", "")) if c.get("section_id") else None
        sources[doc.doc_id] = {"doc_id": doc.doc_id, "title": doc.title, "sensitivity": doc.sensitivity,
                               "matter_id": getattr(doc, "matter_id", None), "client_id": getattr(doc, "client_id", None),
                               "text": sec.text if sec else ""}
    flags = privilegeguard.evaluate(active_matter_id=ctx.matter_id, active_client_id=ctx.client_id,
                                    destination=wp.get("destination", "internal"), sources=list(sources.values()))
    flags_d = [f.model_dump() for f in ctx.tools.call("privilege", "privilege_scan", lambda: flags)]
    return {"privilege_flags": flags_d,
            "agent_trace": [{"label": "Confidentiality review completed", "agent": "privilege",
                             "status": "warn" if flags_d else "ok",
                             "detail": f"{len(flags_d)} potential privilege/confidentiality flag(s)" if flags_d else "No potential risks flagged"}],
            "agents_invoked": ["privilege"]}


def assurance(state: dict, ctx: RunContext) -> dict:
    wp = state["work_product"]
    res = pipeline.evaluate(
        propositions=wp.get("propositions", []), verifications=state.get("citations", []),
        playbook_results=state.get("playbook_results", []), policy_decision=ctx.mg.decision,
        privilege_flags=state.get("privilege_flags", []), documents_in_scope=wp.get("documents_in_scope"),
        documents_processed=wp.get("documents_processed"), destination=wp.get("destination", "internal"),
        recommendations_checked=bool(wp.get("recommendations")))
    ctx.audit("ASSURANCE_RESULT", {"work_product_id": wp["work_product_id"], "score": res.score, "status": res.status,
                                   "citation_summary": res.citation_summary, "blocking_issues": res.blocking_issues})
    return {"assurance_result": res.model_dump(),
            "agent_trace": [{"label": f"Assurance {res.score_pct}% - {res.status.replace('_', ' ')}", "agent": "workproduct_assurance",
                             "status": "ok" if res.status == "PASS" else "warn",
                             "detail": "Traceability/verification score - not a measure of legal correctness"}],
            "agents_invoked": ["workproduct_assurance"]}


def human_review(state: dict, ctx: RunContext) -> dict:
    wp = state["work_product"]
    esc = any(r["result"] == "ESCALATION_REQUIRED" for r in state.get("playbook_results", []))
    required = ["PARTNER"] if esc else []
    content = {k: v for k, v in wp.items() if k not in ("propositions",)}
    content["findings"] = state.get("findings") or wp.get("findings") or []
    content["citations"] = state.get("citations", [])
    content["playbook_results"] = state.get("playbook_results", [])
    content["privilege_flags"] = state.get("privilege_flags", [])
    if ctx.persist:
        review_service.save_work_product(work_product_id=wp["work_product_id"], request_id=ctx.request_id,
                                         matter_id=ctx.matter_id, kind=wp["kind"], title=wp["title"], content=content,
                                         assurance=state.get("assurance_result", {}), destination=wp.get("destination", "internal"),
                                         required_roles=required, created_by=ctx.user_id)
    ctx.audit("WORK_PRODUCT_CREATED", {"work_product_id": wp["work_product_id"], "kind": wp["kind"],
                                       "provider_id": wp.get("provider_id") or state.get("provider")})
    ctx.audit("HUMAN_REVIEW_PENDING", {"work_product_id": wp["work_product_id"], "required_roles": required or
                                       ["PARTNER", "SENIOR_ASSOCIATE", "ASSOCIATE"], "destination": wp.get("destination")})
    hr = {"required": True, "level": ctx.mg.human_review_level, "label": ctx.mg.human_review_label,
          "required_roles": required or ["PARTNER", "SENIOR_ASSOCIATE", "ASSOCIATE"],
          "reason": "Playbook escalation requires Partner approval." if esc else "AI-assisted work product requires lawyer review.",
          "external_delivery_allowed": state.get("assurance_result", {}).get("external_delivery_allowed", False),
          "work_product_id": wp["work_product_id"]}
    return {"human_review": hr, "approval_status": "PENDING",
            "agent_trace": [{"label": "Lawyer approval pending", "agent": "supervisor", "status": "pending",
                             "detail": hr["reason"]}]}
