"""FastAPI routes. Every matter-scoped endpoint resolves access deterministically before doing work."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Query

from app.access.matter_access import build_access_scope, check_ethical_wall, check_matter_access, matter_visibility
from app.access.rbac import has_permission
from app.agents.registry import catalogue as agent_catalogue
from app.api.deps import current_user
from app.assurance import pipeline
from app.audit import service as audit
from app.changeops import service as changeops
from app.citations import verifier
from app.config import get_settings
from app.copilot.intent import classify
from app.documents import analysis
from app.documents.access import permitted_document, permitted_documents
from app.evaluation import lab
from app.governance import control_tower, review
from app.governance.use_cases import catalogue as use_case_catalogue
from app.graph.builder import run_copilot
from app.inventory.service import inventory
from app.matterguard import guard as matterguard
from app.models import api as m
from app.models.domain import User, sensitivity_rank
from app.playbooks import guard as playbookguard
from app.privilege import guard as privilegeguard
from app.providers.llm import paid_llm_calls
from app.rag import retriever
from app.routing import router as ai_router
from app.routing import suitability
from app.security.uploads import validate_upload
from app.services.data_store import get_store
from app.valueiq import service as valueiq

api = APIRouter()


def _require(user: User, permission: str) -> None:
    if not has_permission(user, permission):
        raise HTTPException(status_code=403, detail=f"Role {user.role.value} lacks permission '{permission}'.")


def _matter_scope(user: User, matter_id: str, endpoint: str):
    """Deterministic access + ethical wall check; denials are audited. Returns (matter, scope)."""
    store = get_store()
    matter = store.matters.get(matter_id)
    acc = check_matter_access(store, user, matter)
    wall = check_ethical_wall(store, user, matter_id) if matter else None
    if not acc.allowed or (wall and wall.blocked):
        reason = wall.reason if (wall and wall.blocked) else acc.reason
        audit.record("SECURITY_ETHICAL_WALL_BLOCK" if (wall and wall.blocked) else "SECURITY_ACCESS_DENIED",
                     request_id=None, user_id=user.user_id, client_id=matter.client_id if matter else None,
                     matter_id=matter_id, payload={"endpoint": endpoint, "reason": reason, "retrieval_performed": False},
                     severity="CRITICAL")
        raise HTTPException(status_code=403, detail={"code": "ETHICAL_WALL" if (wall and wall.blocked) else acc.code,
                                                     "message": reason})
    return matter, build_access_scope(store, user, matter_id)


# ------------------------------------------------------------------------------------- reference
@api.get("/health")
def health():
    s = get_settings()
    store = get_store()
    return {"status": "ok", "service": "lexguard-backend", "demo_mode": s.demo_mode, "paid_llm_calls": paid_llm_calls(),
            "data": {"matters": len(store.matters), "documents": len(store.documents), "knowledge": len(store.knowledge)},
            "synthetic_data": True}


@api.get("/config")
def config():
    return get_settings().public_view()


@api.get("/users")
def users():
    store = get_store()
    return [dict(u.model_dump(mode="json"), practice=store.practices.get(u.practice_id) if u.practice_id else None)
            for u in store.users.values()]


@api.get("/me")
def me(user: User = Depends(current_user)):
    return {**user.model_dump(mode="json"), "permissions": sorted(p for p in (
        "view_matter_content", "use_copilot", "request_external_provider", "approve_internal", "approve_external",
        "approve_escalation", "run_evaluation", "analyze_policy_change", "approve_policy_change", "promote_version",
        "view_all_audit", "view_governance") if has_permission(user, p))}


@api.get("/clients")
def clients(user: User = Depends(current_user)):
    store = get_store()
    return [{"client_id": c.client_id, "name": c.name, "sector": c.sector,
             "ai_policy": c.ai_policy.model_dump(exclude={"evidence"})} for c in store.clients.values()]


@api.get("/matters")
def matters(user: User = Depends(current_user)):
    store = get_store()
    out = []
    for mt in store.matters.values():
        vis = matter_visibility(store, user, mt)
        if vis["permitted"]:
            c = store.clients[mt.client_id]
            out.append({"matter_id": mt.matter_id, "name": mt.name, "matter_number": mt.matter_number,
                        "client": c.name, "practice": store.practices[mt.practice_id], "risk_level": mt.risk_level,
                        "access": vis, "ai_status": ("AI PROHIBITED" if not c.ai_policy.ai_allowed else
                                                     "INTERNAL AI ONLY" if not c.ai_policy.external_ai_allowed else
                                                     "PERMITTED WITH CONTROLS")})
        else:
            out.append({"matter_id": mt.matter_id, "name": f"Restricted matter {mt.matter_number}",
                        "matter_number": mt.matter_number, "client": "Restricted", "practice": "Restricted",
                        "risk_level": None, "access": vis, "ai_status": None})
    return out


@api.get("/matters/{matter_id}")
def matter_detail(matter_id: str, user: User = Depends(current_user)):
    store = get_store()
    mt, scope = _matter_scope(user, matter_id, "GET /matters/{id}")
    c = store.clients[mt.client_id]
    mg = matterguard.evaluate(store, user_id=user.user_id, matter_id=matter_id, intent="contract_review")
    docs = [d for d in store.matter_documents(matter_id) if sensitivity_rank(d.sensitivity) <= sensitivity_rank(scope.max_sensitivity)]
    walls = store.walls_for(matter_id)
    partner = store.users[mt.responsible_partner]
    permitted_systems = [p.name for p in store.providers.values()
                         if matterguard.evaluate(store, user_id=user.user_id, matter_id=matter_id,
                                                 provider_id=p.provider_id).provider_permitted]
    return {
        "matter_id": mt.matter_id, "name": mt.name, "matter_number": mt.matter_number, "description": mt.description,
        "client": {"client_id": c.client_id, "name": c.name, "sector": c.sector},
        "practice": store.practices[mt.practice_id], "practice_id": mt.practice_id, "jurisdiction": mt.jurisdiction,
        "responsible_partner": partner.name, "current_user": user.name, "role": user.role.value,
        "confidentiality": mt.confidentiality, "risk_level": mt.risk_level, "status": mt.status,
        "ethical_wall": {"exists": bool(walls), "user_screened": False,
                         "status": "Wall in place - you are not screened" if walls else "No ethical wall"},
        "access_via": check_matter_access(store, user, mt).via,
        "ai_status": mg.decision, "ai_status_label": ("AI Prohibited" if not c.ai_policy.ai_allowed else
                                                       "Internal AI only" if not c.ai_policy.external_ai_allowed else
                                                       "Permitted with Controls"),
        "client_ai_policy": c.ai_policy.policy_summary, "permitted_ai_systems": permitted_systems,
        "human_review": "Required" if c.ai_policy.human_review_required else "Risk-based",
        "human_review_level": mg.human_review_label,
        "documents": {"total": len(docs), "active": sum(1 for d in docs if d.status == "active"),
                      "duplicates": sum(1 for d in docs if d.status == "duplicate"),
                      "unreadable": sum(1 for d in docs if d.status == "unreadable")},
        "team": [store.users[u].name for u in mt.authorized_users if u in store.users],
    }


@api.get("/providers")
def providers(user: User = Depends(current_user)):
    return [p.model_dump() for p in get_store().providers.values()]


@api.get("/playbooks")
def playbooks(user: User = Depends(current_user)):
    store = get_store()
    out = []
    for p in store.playbooks.values():
        src = store.knowledge.get(p.source_doc_id)
        out.append({**p.model_dump(), "practice": store.practices.get(p.practice_id),
                    "source_sections": [s.model_dump() for s in src.sections] if src else []})
    return out


@api.get("/knowledge/documents")
def knowledge_documents(matter_id: str | None = Query(default=None), user: User = Depends(current_user)):
    store = get_store()
    if matter_id:
        _matter_scope(user, matter_id, "GET /knowledge/documents")
    scope = build_access_scope(store, user, matter_id)
    return [{"doc_id": k.doc_id, "kind": k.kind, "title": k.title, "access_label": k.access_label, "sensitivity": k.sensitivity,
             "sections": len(k.sections)} for k in store.knowledge.values()
            if k.access_label in scope.permitted_labels and (k.matter_id is None or k.matter_id in scope.permitted_matter_ids)
            and sensitivity_rank(k.sensitivity) <= sensitivity_rank(scope.max_sensitivity)]


@api.get("/agents")
def agents():
    return agent_catalogue()


# ------------------------------------------------------------------------------------- copilot
@api.post("/copilot/chat", response_model=m.CopilotResponse)
def copilot_chat(req: m.ChatRequest, user: User = Depends(current_user)):
    # Access, ethical walls and policy are enforced inside the graph before any retrieval.
    return run_copilot(user_id=user.user_id, matter_id=req.matter_id, message=req.message,
                       selected_finding_id=req.selected_finding_id, destination=req.destination)


@api.post("/matterguard/evaluate")
def matterguard_evaluate(req: m.MatterGuardRequest, user: User = Depends(current_user)):
    res = matterguard.evaluate(get_store(), user_id=user.user_id, matter_id=req.matter_id, provider_id=req.provider_id,
                               destination=req.destination, intent=req.intent, doc_ids=req.doc_ids)
    store = get_store()
    mt = store.matters.get(req.matter_id)
    audit.record("POLICY_DECISION", request_id=None, user_id=user.user_id, client_id=mt.client_id if mt else None,
                 matter_id=req.matter_id, payload={"endpoint": "matterguard", "decision": res.decision,
                                                   "provider_id": req.provider_id},
                 severity="INFO" if res.decision != "PROHIBITED" else "WARNING")
    return res


@api.post("/routing/recommend")
def routing_recommend(req: m.RoutingRequest, user: User = Depends(current_user)):
    store = get_store()
    mt, scope = _matter_scope(user, req.matter_id, "POST /routing/recommend")
    intent = classify(store, req.task, req.matter_id)
    dest = req.destination or intent.destination
    mg = matterguard.evaluate(store, user_id=user.user_id, matter_id=req.matter_id, provider_id=intent.requested_provider,
                              destination=dest, intent=intent.intent)
    c = store.clients[mt.client_id]
    docs = [d for d in store.matter_documents(req.matter_id) if d.status == "active"]
    priv = sum(1 for d in docs if d.sensitivity == "privileged") / (len(docs) or 1)
    prov = store.providers.get(intent.requested_provider or "")
    s = suitability.score(intent=intent.intent, doc_count=len(docs), doc_sensitivities=[d.sensitivity for d in docs],
                          privileged_share=priv, client_ai_allowed=c.ai_policy.ai_allowed,
                          client_external_allowed=c.ai_policy.external_ai_allowed, external_destination=dest.startswith("external"),
                          external_provider=bool(prov and prov.external), human_review_level=mg.human_review_level)
    dec = ai_router.recommend(intent=intent.intent, mg=mg, suit=s, doc_count=len(docs), requested_provider=intent.requested_provider)
    return {"intent": intent.model_dump(), "matterguard": mg.model_dump(), "suitability": s.model_dump(), "routing": dec.model_dump()}


@api.post("/knowledge/search")
def knowledge_search(req: m.KnowledgeSearchRequest, user: User = Depends(current_user)):
    _, scope = _matter_scope(user, req.matter_id, "POST /knowledge/search")
    mg = matterguard.evaluate(get_store(), user_id=user.user_id, matter_id=req.matter_id, intent="search")
    results = retriever.search(scope, req.query, top_k=req.top_k)
    return {"query": req.query, "scope": {"matter_id": scope.matter_id, "partitions": sorted(scope.permitted_labels),
                                          "max_sensitivity": scope.max_sensitivity},
            "ai_status": mg.decision, "results": [r.model_dump() for r in results],
            "note": "Security filters were applied before retrieval; unauthorised partitions were never read."}


@api.post("/documents/analyze")
def documents_analyze(req: m.AnalyzeRequest, user: User = Depends(current_user)):
    store = get_store()
    _, scope = _matter_scope(user, req.matter_id, "POST /documents/analyze")
    mg = matterguard.evaluate(store, user_id=user.user_id, matter_id=req.matter_id, intent="contract_review")
    if not mg.ai_allowed_for_matter:
        raise HTTPException(status_code=403, detail={"code": "AI_PROHIBITED", "message": " ".join(mg.reasons)})
    docs = permitted_documents(store, scope, req.matter_id)
    targets = [permitted_document(store, scope, d) for d in req.doc_ids]
    if any(t is None for t in targets):
        raise HTTPException(status_code=404, detail="Document not found in this matter.")
    t = req.analysis_type
    if t == "change_of_control":
        r = analysis.review_change_of_control(req.matter_id, docs)
        return {"documents_in_scope": r.documents_in_scope, "documents_processed": r.documents_processed,
                "excluded": r.excluded, "clauses": len(r.findings), "findings": [f.model_dump() for f in r.findings],
                "injection_flags": r.injection_flags}
    if not targets:
        targets = [d for d in docs if d.status == "active"][:1]
    if t == "summary":
        return analysis.summarize(targets[0])
    if t == "obligations":
        return {"doc_id": targets[0].doc_id, "obligations": analysis.extract_obligations(targets[0])}
    if t == "timeline":
        return {"events": analysis.extract_timeline(targets or [d for d in docs if d.status == "active"])}
    if t == "entities":
        return analysis.extract_entities(targets[0])
    if len(targets) < 2:
        raise HTTPException(status_code=422, detail="Comparison requires two doc_ids.")
    return analysis.compare_documents(targets[0], targets[1])


@api.post("/documents/validate-upload")
def documents_validate_upload(req: m.UploadValidateRequest, user: User = Depends(current_user)):
    try:
        content = base64.b64decode(req.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="content_base64 is not valid base64.")
    return validate_upload(req.filename, content)


@api.post("/playbook/check")
def playbook_check(req: m.PlaybookCheckRequest, user: User = Depends(current_user)):
    pb = get_store().playbooks.get(req.playbook_id)
    if pb is None:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    return {"playbook_id": pb.playbook_id, "version": pb.version, "results": [
        (playbookguard.classify_clause if i.kind == "clause" else playbookguard.check_recommendation)(pb, i.id, i.text).model_dump()
        for i in req.items]}


@api.post("/citations/verify")
def citations_verify(req: m.CitationVerifyRequest, user: User = Depends(current_user)):
    _, scope = _matter_scope(user, req.matter_id, "POST /citations/verify")
    res = [verifier.verify(get_store(), scope, p.pid, p.claim, p.citation.model_dump() if p.citation else None)
           for p in req.propositions]
    return {"results": [r.model_dump() for r in res], "summary": verifier.summarize_results(res)}


@api.post("/assurance/evaluate")
def assurance_evaluate(req: m.AssuranceRequest, user: User = Depends(current_user)):
    store = get_store()
    mt, scope = _matter_scope(user, req.matter_id, "POST /assurance/evaluate")
    props = [p.model_dump() for p in req.propositions]
    if req.work_product_id:
        pre = store.pregenerated.get(req.work_product_id)
        if pre is None or pre["matter_id"] != req.matter_id:
            raise HTTPException(status_code=404, detail="Work product not found in this matter.")
        props = [dict(p, material=True) for p in pre.get("propositions", [])]
    vers = [verifier.verify(store, scope, p["pid"], p["claim"], p.get("citation")).model_dump() for p in props if p.get("material", True)]
    sources = []
    for p in props:
        c = p.get("citation") or {}
        doc = verifier.resolve_source(store, scope, c.get("doc_id", "")) if c.get("doc_id") else None
        if doc:
            sec = doc.section(c.get("section_id") or "")
            sources.append({"doc_id": doc.doc_id, "title": doc.title, "sensitivity": doc.sensitivity,
                            "matter_id": getattr(doc, "matter_id", None), "client_id": getattr(doc, "client_id", None),
                            "text": sec.text if sec else ""})
    flags = [f.model_dump() for f in privilegeguard.evaluate(active_matter_id=req.matter_id, active_client_id=mt.client_id,
                                                              destination=req.destination, sources=sources)]
    mg = matterguard.evaluate(store, user_id=user.user_id, matter_id=req.matter_id, destination=req.destination,
                              intent="citation_verify")
    res = pipeline.evaluate(propositions=props, verifications=vers, playbook_results=[], policy_decision=mg.decision,
                            privilege_flags=flags, destination=req.destination)
    return {"assurance": res.model_dump(), "verifications": vers, "privilege_flags": flags}


@api.post("/privilege/evaluate")
def privilege_evaluate(req: m.PrivilegeRequest, user: User = Depends(current_user)):
    store = get_store()
    mt, scope = _matter_scope(user, req.matter_id, "POST /privilege/evaluate")
    docs = [permitted_document(store, scope, d) for d in req.doc_ids] if req.doc_ids else \
        [d for d in permitted_documents(store, scope, req.matter_id) if d.status == "active"]
    sources = [{"doc_id": d.doc_id, "title": d.title, "sensitivity": d.sensitivity, "matter_id": d.matter_id,
                "client_id": d.client_id, "text": " ".join(s.text for s in d.sections)} for d in docs if d is not None]
    flags = privilegeguard.evaluate(active_matter_id=req.matter_id, active_client_id=mt.client_id,
                                    destination=req.destination, sources=sources)
    return {"documents_reviewed": len(sources), "flags": [f.model_dump() for f in flags],
            "note": "Flags indicate POTENTIAL privilege or confidentiality risk only. Lawyer review is required."}


@api.post("/draft/generate", response_model=m.CopilotResponse)
def draft_generate(req: m.DraftRequest, user: User = Depends(current_user)):
    msg = {"memo": "Draft a due diligence summary using only verified findings.",
           "due_diligence_report": "Draft a due diligence report using only verified findings.",
           "client_communication": "Prepare a client-ready draft."}[req.draft_type]
    return run_copilot(user_id=user.user_id, matter_id=req.matter_id, message=msg, destination=req.destination)


# ------------------------------------------------------------------------------------- review
def _review(req: m.ReviewRequest, user: User, decision: str):
    try:
        return review.decide(get_store(), work_product_id=req.work_product_id, reviewer_id=user.user_id, decision=decision,
                             destination=req.destination, comment=req.comment)
    except review.ReviewError as e:
        raise HTTPException(status_code=e.http_status, detail={"code": e.code, "message": e.message})


@api.post("/review/approve")
def review_approve(req: m.ReviewRequest, user: User = Depends(current_user)):
    return _review(req, user, "APPROVE")


@api.post("/review/reject")
def review_reject(req: m.ReviewRequest, user: User = Depends(current_user)):
    return _review(req, user, "REJECT")


@api.get("/review/work-products")
def review_list(matter_id: str | None = Query(default=None), user: User = Depends(current_user)):
    store = get_store()
    items = review.list_work_products(matter_id)
    out = []
    for i in items:
        acc = check_matter_access(store, user, store.matters.get(i["matter_id"]))
        if acc.allowed and not check_ethical_wall(store, user, i["matter_id"]).blocked:
            out.append(i)
    return out


@api.get("/review/work-products/{work_product_id}")
def review_get(work_product_id: str, user: User = Depends(current_user)):
    wp = review.get_work_product(work_product_id)
    if wp is None:
        raise HTTPException(status_code=404, detail="Work product not found.")
    _matter_scope(user, wp["matter_id"], "GET /review/work-products/{id}")
    return wp


# ------------------------------------------------------------------------------------- operations
@api.get("/control-tower/metrics")
def control_tower_metrics(user: User = Depends(current_user)):
    return control_tower.metrics(get_store())


@api.get("/value/metrics")
def value_metrics(user: User = Depends(current_user)):
    return valueiq.metrics(get_store())


@api.post("/changeops/analyze")
def changeops_analyze(req: m.ChangeOpsRequest, user: User = Depends(current_user)):
    _require(user, "analyze_policy_change")
    return changeops.analyze(get_store(), req.policy_text)


@api.post("/changeops/approve")
def changeops_approve(req: m.ChangeApproveRequest, user: User = Depends(current_user)):
    _require(user, "approve_policy_change")
    try:
        res = changeops.approve(get_store(), req.change_id, req.policy_text, user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    audit.record("POLICY_CHANGE_APPROVED", request_id=None, user_id=user.user_id, client_id=None, matter_id=None,
                 payload={"change_id": req.change_id, "gates": res["approval_gates"]})
    return res


@api.post("/evaluation/run")
def evaluation_run(req: m.EvaluationRequest, user: User = Depends(current_user)):
    _require(user, "run_evaluation")
    try:
        res = lab.compare(get_store(), req.target)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown evaluation target.")
    audit.record("EVALUATION_RUN", request_id=None, user_id=user.user_id, client_id=None, matter_id=None,
                 payload={"run_id": res["run_id"], "target": req.target, "gates_passed": res["gates_passed"]})
    return res


@api.post("/evaluation/promote")
def evaluation_promote(req: m.PromoteRequest, user: User = Depends(current_user)):
    _require(user, "promote_version")
    try:
        res = lab.promote(req.target, req.run_id, user.user_id)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=409, detail=str(e))
    audit.record("VERSION_PROMOTED", request_id=None, user_id=user.user_id, client_id=None, matter_id=None, payload=res)
    return res


@api.get("/evaluation/versions")
def evaluation_versions(user: User = Depends(current_user)):
    return lab.versions()


@api.get("/inventory")
def inventory_view(user: User = Depends(current_user)):
    return inventory(get_store())


@api.get("/use-cases")
def use_cases():
    cat = use_case_catalogue()
    return {"use_cases": cat, "counts": {s: sum(1 for u in cat if u["status"] == s) for s in ("IMPLEMENTED", "PARTIAL", "PLANNED")}}


# ------------------------------------------------------------------------------------- audit
@api.get("/audit/verify")
def audit_verify(user: User = Depends(current_user)):
    return audit.verify_chain()


@api.get("/audit/security")
def audit_security(user: User = Depends(current_user)):
    _require(user, "view_all_audit")
    return [e for e in audit.recent_events(limit=300) if e["severity"] in ("WARNING", "CRITICAL")]


@api.get("/audit/trace/{request_id}")
def audit_trace(request_id: str, user: User = Depends(current_user)):
    events = audit.trace_chain(request_id)
    if not events:
        raise HTTPException(status_code=404, detail="No audit events for this request.")
    mid = next((e["matter_id"] for e in events if e["matter_id"]), None)
    if not has_permission(user, "view_all_audit") and events[0]["user_id"] != user.user_id:
        if mid:
            _matter_scope(user, mid, "GET /audit/trace")
    return {"request_id": request_id, "chain": events}


@api.get("/audit/work-product/{work_product_id}")
def audit_work_product(work_product_id: str, user: User = Depends(current_user)):
    wp = review.get_work_product(work_product_id)
    if wp is None:
        raise HTTPException(status_code=404, detail="Work product not found.")
    _matter_scope(user, wp["matter_id"], "GET /audit/work-product")
    chain = audit.trace_chain(wp["request_id"]) if wp["request_id"] else []
    post = [e for e in audit.events_for_matter(wp["matter_id"]) if e["payload"].get("work_product_id") == work_product_id
            and e["request_id"] == wp["request_id"] and e not in chain]
    return {"work_product_id": work_product_id, "request_id": wp["request_id"], "chain": chain + post}


@api.get("/audit/{matter_id}")
def audit_matter(matter_id: str, user: User = Depends(current_user)):
    store = get_store()
    if matter_id not in store.matters:
        raise HTTPException(status_code=404, detail="Matter not found.")
    if not has_permission(user, "view_all_audit"):
        _matter_scope(user, matter_id, "GET /audit/{matter_id}")
    return {"matter_id": matter_id, "events": audit.events_for_matter(matter_id), "chain_integrity": audit.verify_chain()}
