"""Claims Simulation, Security & Governance and Release Center views."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.claims.rulesets import RULESETS
from frontend.components import ui
from frontend.components.session import need, platform, run_sdlc


def simulation() -> None:
    ss = st.session_state
    st.title("Claims Simulation Lab")
    ui.label("SIMULATED — deterministic rules engine over seeded synthetic claims (no LLM in claim loops)")
    st.caption("Run the SAME synthetic claims through CURRENT and PROPOSED rulesets and compare outcomes.")
    c1, c2, c3, c4 = st.columns(4)
    current = c1.selectbox("CURRENT rule", list(RULESETS), index=0)
    proposed = c2.selectbox("PROPOSED rule", ["(derived from requirement)"] + list(RULESETS), index=0,
                            help="RULESET_V2_DEFECTIVE = the controlled synthetic defect build")
    n = c3.selectbox("Claims", [1_000, 10_000, 50_000, 100_000], index=1, format_func=lambda x: f"{x:,}")
    seed = int(c4.number_input("Seed", value=platform().settings.random_seed, step=1, min_value=0))
    if st.button("RUN SIMULATION", type="primary"):
        try:
            with st.spinner(f"Adjudicating {n:,} synthetic claims twice…"):
                run = platform().run_simulation(ss.request_text, ss.clarifications or None, current_ruleset_id=current,
                                                proposed_ruleset_id=None if proposed.startswith("(") else proposed,
                                                n_claims=n, seed=seed)
            ss.sim_run = run
        except ValueError as exc:
            st.error(f"{exc} — resolve requirement ambiguity on the Copilot page or pick an explicit ruleset.")
    run = ss.get("sim_run")
    if run is None:
        st.info("Press RUN SIMULATION. (The demo requirement needs the threshold clarification; it defaults to "
                "'visit 11 onward' here only if you clarified it — otherwise pick an explicit ruleset.)")
        return
    r = run.result
    from app.qa.test_generator import generate_test_cases, run_test_cases, summarize
    from app.requirements.analyzer import DEMO_CLARIFICATIONS, analyze_requirement_text
    req = analyze_requirement_text(ss.request_text, ss.clarifications or DEMO_CLARIFICATIONS)
    reg = summarize(run_test_cases(generate_test_cases(req), RULESETS.get(r.proposed_ruleset) or RULESETS["RULESET_V2"])) if req.facets else {"failed": 0}
    rr = (ss.sdlc or {}).get("release_risk")
    ui.cards([
        ("Claims simulated", f"{r.claims_simulated:,}", f"seed {r.seed} · {r.runtime_ms:.0f} ms"),
        ("Outcomes changed", f"{r.outcomes_changed:,}", f"{r.approved_to_denied} approved→denied · {r.denied_to_approved} denied→approved"),
        ("Approval change", f"{(r.approval_rate_proposed - r.approval_rate_current) * 100:+.2f} pp", f"{r.approval_rate_current:.1%} → {r.approval_rate_proposed:.1%}"),
        ("Denial change", f"{(r.denial_rate_proposed - r.denial_rate_current) * 100:+.2f} pp", f"{r.denial_rate_current:.1%} → {r.denial_rate_proposed:.1%}"),
        ("Authorization change", f"{r.auth_required_proposed - r.auth_required_current:+,}", "AUTH_REQUIRED denials"),
        ("Financial impact", f"${r.financial.projected_annual_impact:,.0f}/yr", f"simulated diff ${r.financial.difference:,.0f} · {r.financial.disclaimer}"),
        ("Regression failures", f"{r.unexpected_changes + reg['failed']}", f"{r.unexpected_changes} unexpected outcomes · {reg['failed']} failed tests"),
        ("Release risk", f"{rr.level.value} ({rr.score})" if rr is not None else "run ASSESS RELEASE", rr.decision.value if rr is not None else ""),
    ])
    if r.unexpected_changes:
        st.error(f"⚠ {r.unexpected_changes} UNEXPECTED outcome changes — behaviour not explained by the requirement.")
    c1, c2 = st.columns(2)
    with c1:
        bb = pd.DataFrame(r.by_benefit)
        fig = go.Figure([go.Bar(name=f"Current ({r.current_ruleset})", x=bb.benefit_type, y=bb.denial_rate_current, marker_color=ui.SERIES[0]),
                         go.Bar(name=f"Proposed ({r.proposed_ruleset})", x=bb.benefit_type, y=bb.denial_rate_proposed, marker_color=ui.SERIES[1])])
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, yaxis_tickformat=".0%")
        fig.update_traces(hovertemplate="%{x}: %{y:.1%}<extra>%{fullData.name}</extra>")
        st.plotly_chart(ui.style_fig(fig, 340, "Denial rate by benefit"), width="stretch")
    with c2:
        rd = pd.DataFrame(r.reason_distribution)
        rd = rd[rd.reason_code.isin(["PAID", "PAID_CAPPED"]) == False]  # noqa: E712
        fig = go.Figure([go.Bar(name="Current", y=rd.reason_code, x=rd.current, orientation="h", marker_color=ui.SERIES[0]),
                         go.Bar(name="Proposed", y=rd.reason_code, x=rd.proposed, orientation="h", marker_color=ui.SERIES[1])])
        fig.update_layout(barmode="group", bargap=0.3)
        fig.update_layout(hovermode="y unified")
        st.plotly_chart(ui.style_fig(fig, 340, "Denial reasons (count)"), width="stretch")
    ex = {**r.expected_changes, "UNEXPECTED": r.unexpected_changes}
    st.markdown("**Change classification (expected-vs-actual)**")
    st.dataframe(pd.DataFrame([{"class": k, "claims": v} for k, v in ex.items()]), hide_index=True)
    st.dataframe(pd.DataFrame(r.by_benefit), width="stretch", hide_index=True)
    if r.unexpected_samples:
        st.markdown("**Unexpected outcome samples**")
        st.dataframe(pd.DataFrame(r.unexpected_samples), width="stretch", hide_index=True)


def security_governance() -> None:
    st.title("Security & Governance")
    ui.label("ADVISORY, DETERMINISTIC rule-based review — not a formal compliance assessment")
    s = need("governance", "governance", "RUN SECURITY & GOVERNANCE REVIEW")
    if not s:
        return
    sec, gov = s["security"], s["governance"]
    st.subheader("Security / privacy findings")
    st.caption(sec["disclaimer"])
    st.dataframe(pd.DataFrame(sec["findings"]), width="stretch", hide_index=True)
    st.dataframe(pd.DataFrame([{"check": c["check"], "status": ui.status_badge(c["status"])} for c in sec["checks"]]),
                 width="stretch", hide_index=True)
    st.subheader("Governance checklist")
    st.caption(gov["disclaimer"])
    ui.cards([("Pass", str(gov["pass"]), ""), ("Warn", str(gov["warn"]), ""), ("Fail", str(gov["fail"]), "")], per_row=3)
    st.dataframe(pd.DataFrame([{**i, "status": ui.status_badge(i["status"])} for i in gov["items"]]),
                 width="stretch", hide_index=True)
    scr = s.get("request_screen", {})
    if scr.get("flagged"):
        st.warning(f"Prompt-injection screen flagged the request: {scr['matches']} — treated as data only.")


def release_center() -> None:
    ss = st.session_state
    st.title("Release Center")
    ui.label("DETERMINISTIC risk engine · HUMAN approval gate · SIMULATED deployment")
    s = need("release_risk", "human_approval", "ASSESS RELEASE")
    if not s:
        return
    rr, ra = s["release_risk"], s["release_assessment"]
    ui.cards([("Decision", rr.decision.value, ""), ("Risk level", rr.level.value, f"score {rr.score}/100"),
              ("Blockers", str(len(rr.blockers)), "; ".join(rr.blockers)),
              ("Required approvals", str(len(rr.required_approvals)), ", ".join(rr.required_approvals))])
    c1, c2 = st.columns([1, 1])
    with c1:
        comp = pd.Series(rr.component_scores).sort_values()
        fig = go.Figure(go.Bar(x=comp.values, y=comp.index, orientation="h", marker_color=ui.SERIES[0],
                               hovertemplate="%{y}: %{x}<extra></extra>"))
        fig.update_layout(hovermode="closest")
        st.plotly_chart(ui.style_fig(fig, 330, "Risk score components"), width="stretch")
    with c2:
        st.markdown("**Evidence**")
        for e in ra["evidence"]:
            st.markdown(f"- {e}")
        st.markdown("**Reasons**")
        for r in rr.reasons:
            st.markdown(f"- {r}")
    with st.expander("Release notes (template)"):
        st.code(ra["release_notes"], language="text")
    with st.expander("Rollback plan"):
        for r in ra["rollback_plan"]:
            st.markdown(f"- {r}")
    st.divider()
    st.subheader("🧑‍⚖️ Human approval gate")
    if rr.decision.value in ("BLOCKED", "NOT READY"):
        st.error(f"Release is **{rr.decision.value}** — approval is disabled. Evidence returned above.")
        return
    rel = s.get("release", {})
    if rel.get("status", "").startswith("DEPLOYED"):
        st.success(f"Release {rel.get('version')} {rel['status']} — approved by {rel.get('approved_by')}. {rel.get('note', '')}")
        st.info("Open **ClaimIQ** to monitor production.")
    with st.form("approval"):
        approver = st.text_input("Approver name", "Demo Release Manager")
        role = st.selectbox("Role", ["Release Manager", "Claims Operations Manager", "Compliance Reviewer"])
        decision = st.radio("Decision", ["APPROVED", "REJECTED"], horizontal=True)
        comment = st.text_input("Comment", "Reviewed simulation, tests and governance evidence.")
        inject = st.checkbox("Inject CONTROLLED SYNTHETIC DEFECT at deployment (ClaimIQ demo: cancelled visits counted)", value=True)
        submitted = st.form_submit_button("SUBMIT DECISION & SIMULATE DEPLOYMENT", type="primary")
    if submitted:
        try:
            approval = {"approver": approver, "role": role, "decision": decision, "comment": comment}
            from app.models.domain import Approval
            Approval(**approval)
        except Exception as exc:  # validation error shown to user
            st.error(f"Invalid approval: {exc}")
            return
        st.session_state.last_stop = "anomaly_check"
        run_sdlc("anomaly_check", approval=approval, inject_defect=inject)
        st.rerun()


VIEWS = {"Claims Simulation": simulation, "Security & Governance": security_governance, "Release Center": release_center}
