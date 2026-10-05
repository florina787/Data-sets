"""SDLC views: Copilot, Requirements, Policy Evidence, Impact, Architecture, Development Plan, QA & Tests."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.models.domain import PERSONAS
from frontend.components import ui
from frontend.components.session import EXAMPLES, need, platform, run_sdlc


# --------------------------------------------------------------------------- shared
def clarification_panel(state: dict) -> None:
    req = state.get("requirement")
    if req is None or not req.blocking_ambiguities:
        return
    st.error("🧑‍⚖️ **HUMAN REVIEW REQUIRED** — the Requirement Agent will not invent a business rule.")
    choices = {}
    for amb in req.blocking_ambiguities:
        st.markdown(f"**{amb.ambiguity_id}** ({amb.severity.value}): {amb.question}")
        if amb.options:
            choices[amb.ambiguity_id] = st.radio("Clarification", list(amb.options), key=f"clar-{amb.ambiguity_id}",
                                                 format_func=lambda k, a=amb: a.options[k])
        else:
            st.caption("No predefined options — rewrite the request with a specific benefit and rule change.")
    if choices and st.button("Apply clarification and continue", type="primary"):
        st.session_state.clarifications = {**st.session_state.clarifications, **choices}
        run_sdlc(st.session_state.get("last_stop", "ambiguity_check"))
        st.rerun()


# --------------------------------------------------------------------------- Copilot
def copilot() -> None:
    ss = st.session_state
    st.title("ClaimForge Copilot")
    st.subheader("Agentic SDLC & Production Intelligence for Health Insurance")
    st.markdown("*“From insurance requirement to production intelligence.”*")
    ui.synthetic_banner()

    c1, c2 = st.columns([3, 1])
    with c2:
        ex = st.selectbox("Example prompts", list(EXAMPLES))
        if st.button("Use example"):
            ss.request_text = EXAMPLES[ex]
            ss.clarifications = {}
            ss.sdlc = None
            st.rerun()
        ss.n_claims = st.selectbox("Synthetic claims", [1_000, 10_000, 50_000, 100_000],
                                   index=[1_000, 10_000, 50_000, 100_000].index(ss.n_claims), format_func=lambda n: f"{n:,}")
    with c1:
        text = st.text_area("Business requirement", ss.request_text, height=110, max_chars=4000)
        if text != ss.request_text:
            ss.request_text, ss.clarifications, ss.sdlc = text, {}, None

    buttons = [("ANALYZE REQUIREMENT", "ambiguity_check"), ("VIEW POLICY", "policy"), ("RUN IMPACT ANALYSIS", "impact"),
               ("GENERATE TESTS", "qa"), ("RUN CLAIM SIMULATION", "simulation"), ("ASSESS RELEASE", "human_approval")]
    cols = st.columns(len(buttons))
    for col, (lbl, stage) in zip(cols, buttons):
        if col.button(lbl, width="stretch"):
            ss.last_stop = stage
            run_sdlc(stage)
            st.rerun()

    state = ss.sdlc
    st.markdown("#### SDLC progress")
    ui.progress(state)
    if not state:
        st.info("Enter a requirement and press **ANALYZE REQUIREMENT**. One Copilot — specialist agents work behind it.")
        return
    clarification_panel(state)
    summary = state.get("summary", {})
    st.markdown(f"#### Copilot response — *{ss.persona}* view")
    st.caption(f"Narrative source: **{summary.get('source')}** · status **{state.get('status')}**")
    st.markdown(summary.get("text", ""))
    obs = state.get("observability", {})
    with st.expander("Agents invoked (trace)"):
        st.write(" → ".join(obs.get("node_order", [])))
        st.caption(f"request_id {obs.get('request_id')} · {obs.get('total_latency_ms')} ms · paid LLM calls: {obs.get('paid_llm_calls')}")
    if state.get("status") == "AWAITING_APPROVAL":
        st.warning("Release assessment complete — go to **Release Center** for the human approval gate.")


# --------------------------------------------------------------------------- Requirements
def requirements() -> None:
    st.title("Requirements")
    ui.label("DETERMINISTIC parser + templates (LLM may only rephrase narrative in live mode)")
    s = need("requirement", "ambiguity_check", "ANALYZE REQUIREMENT")
    if not s:
        return
    req = s["requirement"]
    ui.cards([("Requirement", req.requirement_id, req.title), ("Facets", str(len(req.facets)), ", ".join(req.facets)),
              ("Acceptance criteria", str(len(req.acceptance_criteria)), "Given / When / Then"),
              ("Blocking ambiguities", str(len(req.blocking_ambiguities)), "human clarification gate")])
    clarification_panel(s)
    t1, t2, t3, t4 = st.tabs(["User stories & rules", "Acceptance criteria", "Ambiguities & assumptions", "Parameters"])
    with t1:
        for us in req.user_stories:
            st.markdown(f"- {us}")
        st.dataframe(pd.DataFrame([r.model_dump() for r in req.business_rules]), width="stretch", hide_index=True)
    with t2:
        st.dataframe(pd.DataFrame([a.model_dump() for a in req.acceptance_criteria]), width="stretch", hide_index=True)
    with t3:
        st.dataframe(pd.DataFrame([{"id": a.ambiguity_id, "severity": a.severity.value, "blocking": a.blocking,
                                    "question": a.question, "resolution": a.resolution or "UNRESOLVED",
                                    "resolved_by": a.resolved_by} for a in req.ambiguities]),
                     width="stretch", hide_index=True)
        st.markdown("**Assumptions**")
        for a in req.assumptions:
            st.markdown(f"- {a}")
        st.markdown("**Missing information**")
        for m in req.missing_information:
            st.markdown(f"- {m}")
        st.markdown("**Dependencies**")
        for d in req.dependencies:
            st.markdown(f"- {d}")
    with t4:
        ui.json_block(req.parameters)


# --------------------------------------------------------------------------- Policy
def policy() -> None:
    st.title("Policy Evidence")
    ui.label("RETRIEVAL — local BM25 over synthetic policy documents, with citations. Never fabricates clauses.")
    q = st.text_input("Search policy knowledge base", "cancelled visits authorization threshold")
    if q:
        res = platform().search_policy(q)
        if res["status"] != "EVIDENCE_FOUND":
            st.error(res["message"])
        for e in res.get("evidence", []):
            with st.container(border=True):
                st.markdown(f"**{e['citation']} — {e['title']}** · score {e['score']}")
                st.write(e["text"])
    st.divider()
    st.subheader("Evidence for the current requirement")
    s = need("policy", "policy", "VIEW POLICY")
    if s:
        p = s["policy"]
        if p["status"] != "EVIDENCE_FOUND":
            st.error(p["message"])
        for f in p.get("findings", []):
            st.markdown(f"- **{f['type']}** — {f['statement']}")
        st.dataframe(pd.DataFrame(p.get("evidence", []))[["citation", "title", "score", "text"]] if p.get("evidence") else pd.DataFrame(),
                     width="stretch", hide_index=True)
    st.divider()
    st.subheader("Upload a policy document (untrusted)")
    st.caption(".md / .txt only, size-limited; instruction-like lines are quarantined (prompt-injection defence).")
    up = st.file_uploader("Policy file", type=["md", "txt"])
    if up is not None and st.button("Index uploaded document"):
        try:
            rep = platform().upload_policy(up.name, up.getvalue())
            st.success(f"Indexed {rep['doc_id']} ({rep['sections']} sections).")
            if rep["quarantined_lines"]:
                st.warning("Quarantined lines (not indexed): " + " | ".join(rep["quarantined_lines"]))
        except ValueError as exc:
            st.error(str(exc))


# --------------------------------------------------------------------------- Impact
def impact() -> None:
    st.title("Impact Analysis")
    ui.label("DETERMINISTIC facet matching over the synthetic architecture catalog + dependency propagation")
    s = need("impact", "impact", "RUN IMPACT ANALYSIS")
    if not s:
        return
    imp = s["impact"]
    sm = imp["summary"]
    ui.cards([("Microservices affected", str(sm["microservices_affected"]), "Claims · Benefits · Authorization"),
              ("APIs affected", str(sm["apis_affected"]), ""), ("Business rules affected", str(sm["business_rules_affected"]), ""),
              ("Tables affected", str(sm["database_tables_affected"]), ""), ("Test suites affected", str(sm["tests_affected"]), ""),
              ("Monitoring affected", str(sm["monitoring_affected"]), ""), ("Docs / comms", str(sm["documentation_affected"]), ""),
              ("Critical components", str(sm["critical_components_changed"]), "changed")])
    df = pd.DataFrame([i.model_dump() for i in imp["impacts"]])
    df["action"] = df["action"].map(lambda a: a.value if hasattr(a, "value") else a)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Requirement impact map**")
        st.code(imp["tree"], language="text")
    with c2:
        fig = px.treemap(df, path=[px.Constant(s["requirement"].requirement_id), "component_type", "component_name"],
                         color="action", color_discrete_map={**ui.ACTION_COLORS, "(?)": "#cccccc"},
                         hover_data={"reason": True})
        fig.update_traces(marker=dict(line=dict(width=2, color="rgba(255,255,255,0.9)")))
        st.plotly_chart(ui.style_fig(fig, 420), width="stretch")
    st.dataframe(df[["component_name", "component_type", "criticality", "action", "impact_kind", "reason"]],
                 width="stretch", hide_index=True)


# --------------------------------------------------------------------------- Architecture
def architecture() -> None:
    st.title("Architecture")
    ui.label("DETERMINISTIC TEMPLATE + guardrail: never replaces deterministic claims engines with LLM agents")
    s = need("architecture", "architecture", "RECOMMEND ARCHITECTURE")
    if not s:
        return
    arch = s["architecture"]
    for p in arch["principles"]:
        st.markdown(f"- {p}")
    t1, t2, t3, t4 = st.tabs(["Recommendations", "Current architecture", "Target (ClaimForge, additive)", "FHIR awareness"])
    with t1:
        st.dataframe(pd.DataFrame(arch["recommendations"]), width="stretch", hide_index=True)
        if arch.get("human_review_required"):
            st.warning("Architecture changes (ADD/REPLACE) require human review before implementation.")
    with t2:
        ui.mermaid(arch["current_architecture_mermaid"], 460)
    with t3:
        ui.mermaid(arch["target_architecture_mermaid"], 620)
    with t4:
        st.caption("Mapping only — FHIR resources are NOT implemented in V1.")
        st.dataframe(pd.DataFrame(arch["fhir_mapping"]), width="stretch", hide_index=True)


# --------------------------------------------------------------------------- Development
def development() -> None:
    st.title("Development Plan")
    ui.label("DETERMINISTIC TEMPLATE for synthetic repositories — proposals are never merged or deployed")
    s = need("development_plan", "developer", "GENERATE DEVELOPMENT PLAN")
    if not s:
        return
    d = s["development_plan"]
    st.dataframe(pd.DataFrame(d["steps"]), width="stretch", hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Pseudocode**")
        st.code(d["pseudocode"], language="python")
        st.markdown("**API changes**")
        for a in d["api_changes"]:
            st.markdown(f"- `{a}`")
    with c2:
        if d["code_patch"]:
            st.markdown("**Proposed code patch (synthetic repo)**")
            st.code(d["code_patch"], language="diff")
        st.markdown("**Schema changes**")
        st.code("\n".join(d["schema_changes"]), language="sql")
    st.markdown("**Migration considerations**")
    for m in d["migration_considerations"]:
        st.markdown(f"- {m}")
    st.caption(d["technical_documentation"])


# --------------------------------------------------------------------------- QA
def qa() -> None:
    st.title("QA & Tests")
    ui.label("DETERMINISTIC generation; executable cases RUN against the rules engine")
    s = need("tests", "qa", "GENERATE TESTS")
    if not s:
        return
    t = s["tests"]
    sm = t["summary"]
    ui.cards([("Generated tests", str(len(t["cases"])), ", ".join(f"{k}: {v}" for k, v in t["by_category"].items())),
              ("Executed", str(sm["total"]), f"against {t['ruleset']}"), ("Passed", str(sm["passed"]), ""),
              ("Failed", str(sm["failed"]), f"critical: {sm['critical_failed']}")])
    cases = pd.DataFrame([c.model_dump() for c in t["cases"]])
    st.dataframe(cases[["test_id", "category", "title", "rule_id", "critical", "executable", "given", "expected"]],
                 width="stretch", hide_index=True)
    st.subheader("Execute the generated suite against another ruleset")
    rs = st.selectbox("Ruleset", ["RULESET_V2", "RULESET_V1", "RULESET_V2_DEFECTIVE", "RULESET_V2_1"])
    if st.button("RUN TEST SUITE"):
        from app.qa.test_generator import run_test_cases, summarize
        from app.claims.rulesets import get_ruleset
        res = run_test_cases(t["cases"], get_ruleset(rs))
        st.write(summarize(res))
        st.dataframe(pd.DataFrame([{"test_id": r.test_id, "passed": r.passed, "critical": r.critical, "title": r.title,
                                    "expected": r.expected, "actual": r.actual} for r in res]),
                     width="stretch", hide_index=True)


VIEWS = {"Copilot": copilot, "Requirements": requirements, "Policy Evidence": policy, "Impact Analysis": impact,
         "Architecture": architecture, "Development Plan": development, "QA & Tests": qa}
__all__ = ["VIEWS", "PERSONAS"]
