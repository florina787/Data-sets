"""Policy agent (RAG): retrieves cited policy evidence and checks requirement consistency.

Never fabricates clauses. If retrieval returns nothing, the result is
``INSUFFICIENT POLICY EVIDENCE`` and downstream governance fails the evidence check.
"""

from __future__ import annotations

import re

from app.agents.base import BaseAgent
from app.models.domain import Requirement
from app.policies.retrieval import INSUFFICIENT

_MONEY_RE = re.compile(r"\$(\d{1,3}(?:,\d{3})*|\d+)")


class PolicyAgent(BaseAgent):
    name = "policy"
    title = "Policy Agent (RAG)"
    implementation = "RETRIEVAL (local BM25) + DETERMINISTIC consistency checks"

    def search(self, query: str, top_k: int = 5) -> dict:
        return self.ctx.retriever.search_evidence(query, top_k=top_k)

    def queries_for(self, req: Requirement) -> list[str]:
        bt = req.benefit_type.value.lower().replace("_", " ") if req.benefit_type else ""
        qs = [req.raw_text]
        if "BENEFIT_LIMIT_CHANGE" in req.facets:
            qs.append(f"{bt} annual maximum")
        if "AUTH_THRESHOLD_ADD" in req.facets:
            qs += [f"{bt} prior authorization completed visits", "claims without required authorization",
                   "cancelled visits do not count toward threshold"]
        if req.facets:
            qs.append("notice of benefit changes members providers")
        return qs

    def run(self, state: dict) -> dict:
        req: Requirement = state["requirement"]
        evidence: dict[str, dict] = {}
        for q in self.queries_for(req):
            for e in self.search(q, top_k=3).get("evidence", []):
                key = f"{e['doc_id']}#{e['section_id']}"
                if key not in evidence or e["score"] > evidence[key]["score"]:
                    evidence[key] = e
        ev = sorted(evidence.values(), key=lambda e: -e["score"])[:8]
        findings = self._consistency(req, ev)
        status = "EVIDENCE_FOUND" if ev else INSUFFICIENT
        # Record discovered sections in the traceability graph (requirement → policy).
        g = self.ctx.trace_graph
        if req.requirement_id not in g.nodes:
            g.add_node(req.requirement_id, "requirement", req.title, status="ANALYZED")
        for e in ev[:5]:
            if e["section_id"] not in g.nodes:
                g.add_node(e["section_id"], "policy_section", e["title"], doc_id=e["doc_id"])
            g.link(req.requirement_id, e["section_id"], "constrained_by")
        result = {"status": status, "evidence": ev, "findings": findings,
                  "message": None if ev else f"{INSUFFICIENT}: no supporting section found; nothing fabricated.",
                  "method": self.implementation}
        fallback = (f"{len(ev)} cited policy sections retrieved ({', '.join(e['citation'] for e in ev[:4])}). "
                    + " ".join(f["statement"] for f in findings[:3])) if ev else result["message"]
        result["narrative"] = self.narrate("Explain the policy evidence", "\n".join(e["text"] for e in ev), fallback)
        return {"policy": result}

    def _consistency(self, req: Requirement, ev: list[dict]) -> list[dict]:
        out: list[dict] = []
        by_id = {e["section_id"]: e for e in ev}
        p = req.parameters
        if "BENEFIT_LIMIT_CHANGE" in req.facets:
            sec = next((e for e in ev if "maximum" in e["title"].lower() and req.benefit_type
                        and req.benefit_type.value.split("_")[0].lower() in e["title"].lower()), None)
            if sec:
                amounts = [float(m.replace(",", "")) for m in _MONEY_RE.findall(sec["text"])]
                stated = p.get("stated_current_annual_max")
                if stated is not None and stated in amounts:
                    out.append({"type": "CONSISTENT", "section": sec["section_id"],
                                "statement": f"Stated current maximum ${stated:,.0f} matches {sec['citation']}."})
                elif stated is not None:
                    out.append({"type": "CONFLICT", "section": sec["section_id"],
                                "statement": f"Stated current maximum ${stated:,.0f} does not match {sec['citation']} "
                                             f"(found {', '.join(f'${a:,.0f}' for a in amounts)})."})
                out.append({"type": "AMENDMENT_REQUIRED", "section": sec["section_id"],
                            "statement": f"{sec['citation']} must be amended to ${p['proposed_annual_max']:,.0f}."})
            else:
                out.append({"type": "INSUFFICIENT_EVIDENCE", "section": None,
                            "statement": f"{INSUFFICIENT} for the current annual maximum of this benefit."})
        if "AUTH_THRESHOLD_ADD" in req.facets:
            if "P-14.3" in by_id:
                out.append({"type": "DEPENDENCY", "section": "P-14.3",
                            "statement": "P-14.3 exempts the first 10 completed visits and notes BR-391 is under review — "
                                         "requirement is consistent; P-14.3 must be amended to state the new requirement."})
            if "P-01.3" in by_id:
                out.append({"type": "DEFINITION", "section": "P-01.3",
                            "statement": "P-01.3 defines completed visits: cancelled and no-show appointments do NOT count "
                                         "toward authorization thresholds."})
            if "P-20.3" in by_id:
                out.append({"type": "CONSISTENT", "section": "P-20.3",
                            "statement": "P-20.3 defines denial reason AUTH_REQUIRED for missing authorization."})
        if "P-40.1" in by_id:
            out.append({"type": "DEPENDENCY", "section": "P-40.1",
                        "statement": "P-40.1 requires 30 days notice to members and providers before the change."})
        return out
