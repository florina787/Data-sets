"""AI Inventory - applications, agents, models, providers, prompts, RAG pipelines and workflows."""

from __future__ import annotations

from app.agents.registry import catalogue
from app.changeops.service import gate_overlay
from app.config import get_settings
from app.evaluation.lab import versions
from app.services.data_store import DataStore


def inventory(store: DataStore) -> dict:
    settings = get_settings()
    vers = {v["target"]: v for v in versions()}
    overlay = gate_overlay()

    def owner(uid: str) -> str:
        u = store.users.get(uid)
        return u.name if u else uid

    items: list[dict] = []
    items.append({"id": "APP-LEXGUARD", "type": "AI application", "name": "LexGuard Copilot", "owner": owner("U-007"),
                  "version": "1.0.0", "risk": "HIGH", "approval_status": "APPROVED", "last_evaluation": None,
                  "deployment_status": "DEMO" if settings.demo_mode else "LIVE"})
    items.append({"id": "APP-ENT-COPILOT", "type": "AI application", "name": "Firm Enterprise Copilot", "owner": owner("U-007"),
                  "version": "2026.3", "risk": "MEDIUM", "approval_status": "APPROVED", "last_evaluation": None,
                  "deployment_status": "PRODUCTION"})
    for a in catalogue():
        items.append({"id": f"AGENT-{a['agent_id']}", "type": "Agent", "name": a["name"], "owner": owner("U-007"),
                      "version": a["version"], "risk": "HIGH" if a["agent_id"] in ("drafting", "document_analysis", "legal_research") else "MEDIUM",
                      "approval_status": "APPROVED", "last_evaluation": (vers.get("DUE_DILIGENCE_AGENT") or {}).get("last_evaluation")
                      if a["agent_id"] == "document_analysis" else None, "deployment_status": "PRODUCTION",
                      "tools": a["tools"]})
    items.append({"id": "MODEL-DETERMINISTIC", "type": "Model", "name": "Deterministic engines (rules, BM25, verifier)",
                  "owner": owner("U-007"), "version": "1.0", "risk": "LOW", "approval_status": "APPROVED",
                  "last_evaluation": None, "deployment_status": "ACTIVE"})
    items.append({"id": "MODEL-CLAUDE-LIVE", "type": "Model", "name": f"Anthropic Claude ({settings.llm_model}) - narration only",
                  "owner": owner("U-007"), "version": settings.llm_model, "risk": "MEDIUM", "approval_status": "CONDITIONAL",
                  "last_evaluation": None, "deployment_status": "ENABLED" if settings.live_llm_enabled else "DISABLED (DEMO_MODE)"})
    for p in store.providers.values():
        items.append({"id": p.provider_id, "type": "Provider", "name": p.name, "owner": owner(p.owner), "version": "-",
                      "risk": "HIGH" if p.external else "MEDIUM", "approval_status": p.approval_status,
                      "last_evaluation": None, "deployment_status": p.status, "external": p.external,
                      "allowed_classifications": p.allowed_classifications, "notes": p.notes})
    for pr in store.prompts:
        v = vers.get(pr["prompt_id"])
        items.append({"id": pr["prompt_id"], "type": "Prompt", "name": pr["name"], "owner": owner(pr["owner"]),
                      "version": (v or {}).get("production") or pr["production_version"],
                      "candidate_version": (v or {}).get("candidate") if v else pr["candidate_version"],
                      "risk": "MEDIUM", "approval_status": "APPROVED", "last_evaluation": (v or {}).get("last_evaluation"),
                      "deployment_status": "PRODUCTION"})
    rag = vers["RAG_PIPELINE"]
    items.append({"id": "RAG-INTERNAL", "type": "RAG pipeline", "name": "Permission-aware internal RAG", "owner": owner("U-007"),
                  "version": rag["production"], "candidate_version": rag["candidate"], "risk": "HIGH", "approval_status": "APPROVED",
                  "last_evaluation": rag["last_evaluation"], "deployment_status": "PRODUCTION"})
    for w in store.workflows.values():
        items.append({"id": w.workflow_id, "type": "Workflow", "name": w.name, "owner": owner("U-006"), "version": "1.0",
                      "risk": "HIGH" if any(d.startswith("external") for d in w.destinations) else "MEDIUM",
                      "approval_status": "APPROVED" if w.status == "PRODUCTION" else "PILOT", "last_evaluation": None,
                      "deployment_status": w.status, "gates": sorted(set(w.gates) | set(overlay.get(w.workflow_id, []))),
                      "hitl_level": w.hitl_level})
    return {"items": items, "versioned_components": list(vers.values()),
            "counts": {t: sum(1 for i in items if i["type"] == t) for t in sorted({i["type"] for i in items})}}
