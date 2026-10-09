"""Requirement → component impact analysis (DETERMINISTIC, data-driven).

Uses the synthetic enterprise architecture catalog: each component declares which
requirement *facets* it handles and the recommended action (KEEP / ENHANCE / ADD /
REPLACE) with a reason. Dependency propagation marks dependants as INDIRECT impacts
(KEEP + regression only). New components are added from facet templates.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.config.settings import SYNTHETIC_DATA_DIR
from app.models.domain import Component, Impact, ImpactAction, Requirement

_ACTION_RANK = {ImpactAction.KEEP: 0, ImpactAction.ENHANCE: 1, ImpactAction.REPLACE: 2, ImpactAction.ADD: 3}


@lru_cache(maxsize=1)
def load_architecture() -> dict:
    return json.loads((SYNTHETIC_DATA_DIR / "architecture" / "current_architecture.json").read_text(encoding="utf-8"))


def components() -> list[Component]:
    out = []
    for c in load_architecture()["components"]:
        out.append(Component(**{k: v for k, v in c.items() if k != "facet_actions"}))
    return out


def analyze_impact(req: Requirement) -> dict:
    arch = load_architecture()
    facets = set(req.facets)
    impacts: dict[str, Impact] = {}
    for c in arch["components"]:
        hits = {f: fa for f, fa in c["facet_actions"].items() if f in facets}
        if not hits:
            continue
        best = max(hits.values(), key=lambda fa: _ACTION_RANK[ImpactAction(fa["action"])])
        impacts[c["component_id"]] = Impact(
            component_id=c["component_id"], component_name=c["name"], component_type=c["type"],
            criticality=c["criticality"], action=ImpactAction(best["action"]), impact_kind="DIRECT",
            reason=" ".join(fa["reason"] for fa in hits.values()), facets=sorted(hits),
        )
    for facet in sorted(facets):
        for new in arch.get("additions", {}).get(facet, []):
            impacts[new["component_id"]] = Impact(
                component_id=new["component_id"], component_name=new["name"], component_type=new["type"],
                criticality=new["criticality"], action=ImpactAction.ADD, impact_kind="NEW",
                reason=new["reason"], facets=[facet],
            )
    # One-hop dependency propagation (indirect impact → KEEP + regression test).
    direct_changed = {cid for cid, imp in impacts.items() if imp.action is not ImpactAction.KEEP}
    for c in arch["components"]:
        if c["component_id"] in impacts:
            continue
        deps = [d for d in c.get("depends_on", []) if d in direct_changed]
        if deps:
            impacts[c["component_id"]] = Impact(
                component_id=c["component_id"], component_name=c["name"], component_type=c["type"],
                criticality=c["criticality"], action=ImpactAction.KEEP, impact_kind="INDIRECT",
                reason=f"Depends on changed component(s) {', '.join(deps)}; no change — include in regression scope.",
                facets=[],
            )
    items = sorted(impacts.values(), key=lambda i: (i.component_type, i.component_id))
    changed = [i for i in items if i.action is not ImpactAction.KEEP]

    def count(t: str) -> int:
        return sum(1 for i in changed if i.component_type == t)

    summary = {
        "components_total": len(items),
        "components_changed": len(changed),
        "microservices_affected": count("service"),
        "apis_affected": count("api"),
        "database_tables_affected": count("database_table"),
        "events_affected": count("event"),
        "business_rules_affected": count("rule"),
        "tests_affected": count("test_suite"),
        "monitoring_affected": count("monitoring"),
        "documentation_affected": count("documentation") + count("communication"),
        "critical_components_changed": sum(1 for i in changed if i.criticality == "critical"),
        "by_action": {a.value: sum(1 for i in items if i.action is a) for a in ImpactAction},
    }
    return {"requirement_id": req.requirement_id, "impacts": items, "summary": summary,
            "method": "DETERMINISTIC: facet matching over synthetic architecture catalog + dependency propagation"}


def impact_tree(req_id: str, impacts: list[Impact]) -> str:
    """ASCII impact map, e.g. 'Requirement BR-391 ├── Claims Service [ENHANCE]'."""
    lines = [f"Requirement {req_id}"]
    for n, imp in enumerate(impacts):
        branch = "└──" if n == len(impacts) - 1 else "├──"
        lines.append(f"{branch} {imp.component_name} [{imp.action.value}] ({imp.component_type})")
    return "\n".join(lines)
