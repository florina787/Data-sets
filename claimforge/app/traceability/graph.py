"""Traceability graph (DETERMINISTIC).

Requirement → Policy → Business Rule → Architecture Component → Implementation → Test →
Release → Production Metric → Incident/Anomaly → Defect (→ feedback to Requirement).

Supports forward (downstream) and reverse (upstream) tracing and shortest paths.
"""

from __future__ import annotations

from collections import deque

from app.models.domain import TraceabilityLink


class TraceabilityGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[TraceabilityLink] = []

    # ------------------------------------------------------------------ build
    def add_node(self, node_id: str, node_type: str, label: str = "", **attrs) -> None:
        self.nodes[node_id] = {"id": node_id, "type": node_type, "label": label or node_id, **attrs}

    def link(self, source: str, target: str, relation: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError(f"unknown node in link {source} -> {target}")
        if any(e.source_id == source and e.target_id == target and e.relation == relation for e in self.edges):
            return
        self.edges.append(TraceabilityLink(source_id=source, source_type=self.nodes[source]["type"],
                                           target_id=target, target_type=self.nodes[target]["type"],
                                           relation=relation))

    # ------------------------------------------------------------------ query
    FEEDBACK_RELATIONS = frozenset({"feeds_back_to"})

    def _bfs(self, start: str, forward: bool, include_feedback: bool = False) -> list[dict]:
        """Breadth-first trace. Feedback edges (defect → requirement) are excluded by default
        so upstream/downstream stay acyclic; they are reported via :meth:`feedback_links`."""
        if start not in self.nodes:
            raise KeyError(start)
        seen, out, q = {start}, [], deque([start])
        while q:
            cur = q.popleft()
            for e in self.edges:
                if not include_feedback and e.relation in self.FEEDBACK_RELATIONS:
                    continue
                nxt = e.target_id if forward and e.source_id == cur else (e.source_id if not forward and e.target_id == cur else None)
                if nxt and nxt not in seen:
                    seen.add(nxt)
                    out.append(self.nodes[nxt])
                    q.append(nxt)
        return out

    def downstream(self, node_id: str) -> list[dict]:
        return self._bfs(node_id, True)

    def upstream(self, node_id: str) -> list[dict]:
        return self._bfs(node_id, False)

    def path(self, source: str, target: str, undirected: bool = False) -> list[str]:
        prev: dict[str, str | None] = {source: None}
        q = deque([source])
        while q:
            cur = q.popleft()
            if cur == target:
                break
            for e in self.edges:
                if e.relation in self.FEEDBACK_RELATIONS:
                    continue
                for a, b in ((e.source_id, e.target_id),) + (((e.target_id, e.source_id),) if undirected else ()):
                    if a == cur and b not in prev:
                        prev[b] = cur
                        q.append(b)
        if target not in prev:
            return []
        out, cur = [], target
        while cur is not None:
            out.append(cur)
            cur = prev[cur]
        return list(reversed(out))

    def trace(self, node_id: str) -> dict:
        node = self.nodes[node_id]
        links = [e.model_dump() for e in self.edges if node_id in (e.source_id, e.target_id)]
        return {"node": node, "upstream": self.upstream(node_id), "downstream": self.downstream(node_id),
                "direct_links": links, "feedback_links": self.feedback_links()}

    def feedback_links(self) -> list[dict]:
        return [e.model_dump() for e in self.edges if e.relation in self.FEEDBACK_RELATIONS]

    def to_mermaid(self, focus: str | None = None) -> str:
        keep = set(self.nodes)
        if focus and focus in self.nodes:
            keep = {focus} | {n["id"] for n in self.upstream(focus)} | {n["id"] for n in self.downstream(focus)}
        safe = {nid: f"N{i}" for i, nid in enumerate(self.nodes)}
        lines = ["flowchart LR"]
        for nid in keep:
            n = self.nodes[nid]
            lines.append(f'    {safe[nid]}["{n["type"]}<br/>{nid}"]')
        for e in self.edges:
            if e.source_id in keep and e.target_id in keep:
                lines.append(f"    {safe[e.source_id]} -->|{e.relation}| {safe[e.target_id]}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"nodes": list(self.nodes.values()), "edges": [e.model_dump() for e in self.edges]}


def build_base_graph(requirements: list[dict], releases: dict, kb) -> TraceabilityGraph:
    """Seed the graph from synthetic catalogs (requirements, policy, rules, components, releases)."""
    g = TraceabilityGraph()
    for r in requirements:
        g.add_node(r["requirement_id"], "requirement", r["title"], status=r["status"])
        for sec in r.get("policy_sections", []):
            s = kb.get_section(sec)
            if s:
                g.add_node(sec, "policy_section", s.title, doc_id=s.doc_id)
                g.link(r["requirement_id"], sec, "constrained_by")
    # BR-391 specific chain (rules, components, implementation, tests, release, metric)
    g.add_node("BEN_RULE_090", "business_rule", "Annual benefit maximum")
    g.add_node("AUTH_RULE_184", "business_rule", "Physiotherapy prior-authorization threshold")
    for sec, rule in (("P-14.2", "BEN_RULE_090"), ("P-14.3", "AUTH_RULE_184"), ("P-01.3", "AUTH_RULE_184")):
        if sec in g.nodes:
            g.link(sec, rule, "implemented_as")
    for comp, label, rule in (("SVC-BENEFITS", "Benefits Service", "BEN_RULE_090"),
                              ("SVC-AUTH", "Authorization Service", "AUTH_RULE_184"),
                              ("SVC-CLAIMS", "Claims Service", "AUTH_RULE_184")):
        g.add_node(comp, "component", label)
        g.link(rule, comp, "realized_in")
    for cs in releases.get("change_sets", []):
        g.add_node(cs["change_id"], "implementation", cs["summary"])
        g.link(cs["component_id"], cs["change_id"], "changed_by")
    for rel in releases["releases"]:
        g.add_node(rel["release_id"], "release", f"Release {rel['version']}", version=rel["version"])
        for cid in rel.get("change_ids", []):
            if cid in g.nodes:
                g.link(cid, rel["release_id"], "shipped_in")
    g.add_node("METRIC-PHYSIO-AUTH-DENIAL-RATE", "production_metric", "Physiotherapy AUTH_REQUIRED denial rate")
    g.add_node("METRIC-PHYSIO-DENIAL-RATE", "production_metric", "Physiotherapy denial rate")
    g.link("REL-2.4", "METRIC-PHYSIO-AUTH-DENIAL-RATE", "monitored_by")
    g.link("REL-2.4", "METRIC-PHYSIO-DENIAL-RATE", "monitored_by")
    return g
