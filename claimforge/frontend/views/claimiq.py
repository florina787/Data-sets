"""ClaimIQ (production intelligence) and Root Cause views."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from frontend.components.session import platform, run_investigation


def claimiq() -> None:
    st.title("ClaimIQ — Production Intelligence")
    ui.label("SIMULATED production · STATISTICAL anomaly detection (no LLM decides whether an anomaly exists)")
    p = platform()
    if p.current_production is None:
        st.info("No release deployed in this session — showing the pre-seeded SIMULATED release-2.4 history. "
                "Approve a release in the **Release Center** to deploy your own.")
    m = p.claimiq_metrics()
    k = m["kpis"]
    st.caption(m["label"])
    ui.cards([("Claims processed", f"{k['claims']:,}", "since release"), ("Approval rate", f"{k['approval_rate']:.1%}", ""),
              ("Denial rate", f"{k['denial_rate']:.1%}", ""), ("Authorization failures", f"{k['auth_failures']:,}", "AUTH_REQUIRED"),
              ("Avg reimbursement", f"${k['avg_reimbursement']:.2f}", ""), ("Rule exceptions", str(k["rule_exceptions"]), ""),
              ("Latency p95", f"{k['latency_p95_ms']} ms", f"p50 {k['latency_p50_ms']} ms"),
              ("Current release", k["current_release"], k["deployed_ruleset"])])

    c1, c2, c3 = st.columns(3)
    rel = c1.slider("Relative-change threshold", 0.05, 1.0, float(p.settings.anomaly_relative_threshold), 0.05)
    z = c2.slider("z-score threshold", 1.0, 6.0, float(p.settings.anomaly_z_threshold), 0.5)
    mode = c3.selectbox("Baseline", ["RELEASE_PROJECTION", "HISTORICAL"],
                        help="RELEASE_PROJECTION = shadow replay of the same claims with the APPROVED spec")
    det = p.detect_anomaly(rel, z, mode)
    primary = det["primary"]
    if primary:
        st.error(f"🚨 **ANOMALY DETECTED** — {primary.summary}")
        if st.button("INVESTIGATE", type="primary"):
            run_investigation("release_correlation")
            st.session_state.nav = "Root Cause"
            st.rerun()
    else:
        st.success("✅ No anomaly at the configured thresholds — HEALTHY.")
    if mode == "HISTORICAL":
        st.caption("Note: a historical baseline also flags the *intended* new authorization denials — this is why "
                   "ClaimIQ defaults to the release-aware projection.")

    trend = pd.DataFrame(m["denial_trend_physiotherapy"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=trend.week, y=trend.denial_rate, name="Actual (deployed build)", mode="lines+markers",
                             line=dict(color=ui.SERIES[0], width=2), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=trend.week, y=trend.expected_denial_rate, name="Expected (approved spec, shadow replay)",
                             mode="lines", line=dict(color=ui.SERIES[1], width=2, dash="dash")))
    fig.add_vline(x=k["release_date"], line_width=1, line_dash="dot", line_color="rgba(128,128,128,.8)")
    fig.add_annotation(x=k["release_date"], y=1, yref="paper", text=f"Release {k['current_release']}", showarrow=False, xanchor="left")
    fig.update_layout(yaxis_tickformat=".0%")
    fig.update_traces(hovertemplate="%{y:.1%}")
    st.plotly_chart(ui.style_fig(fig, 360, "Physiotherapy denial rate by week"), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        tr = pd.DataFrame(m["top_denial_reasons"]).sort_values("count")
        f2 = go.Figure(go.Bar(x=tr["count"], y=tr.reason_code, orientation="h", marker_color=ui.SERIES[0],
                              hovertemplate="%{y}: %{x}<extra></extra>"))
        f2.update_layout(hovermode="closest")
        st.plotly_chart(ui.style_fig(f2, 320, "Top denial reasons (since release)"), width="stretch")
    with c2:
        seg = st.selectbox("Segment by", list(m["segments"]))
        st.dataframe(pd.DataFrame(m["segments"][seg]), width="stretch", hide_index=True, height=300)
    st.markdown("**Anomaly evaluations**")
    st.dataframe(pd.DataFrame([{"detected": a.detected, "metric": a.metric, "segment": a.segment["benefit_type"],
                                "baseline": a.baseline_value, "observed": a.observed_value,
                                "relative_change": a.relative_change, "z": a.z_score, "volume": a.observed_volume}
                               for a in det["anomalies"]]), width="stretch", hide_index=True)


def root_cause() -> None:
    st.title("Root Cause")
    ui.label("Bounded AGENT loop over DETERMINISTIC investigation tools · confidence from evidence weights")
    s = st.session_state.get("ciq")
    if not s:
        st.info("No investigation yet.")
        if st.button("INVESTIGATE", type="primary"):
            run_investigation("release_correlation")
            st.rerun()
        return
    rc = s.get("root_cause")
    if rc is None:
        st.success("No anomaly — nothing to investigate.")
        return
    a = s["anomaly"]["primary"]
    ui.cards([("Status", rc.status, f"{rc.iterations} iterations · {rc.tool_calls} tool calls"),
              ("Confidence", rc.confidence, f"evidence score {rc.confidence_score}"),
              ("Affected claims", f"{rc.affected_claims:,}", f"${rc.wrongly_denied_amount:,.2f} wrongly denied (simulated)"),
              ("Correlated release", rc.correlated_release or "-", rc.changed_rule or "")])
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Investigation trace**")
        ev = {e.kind: e.statement for e in rc.evidence}
        ui.flow([("Anomaly", a.summary if a else "-"),
                 ("Denial reason", ev.get("denial_reason_shift", "-")),
                 ("Release", ev.get("correlate_release", "-")),
                 ("Rule", rc.changed_rule or "-"),
                 ("Requirement", ev.get("trace_rule_to_requirement", "-")),
                 ("Evidence", ev.get("inspect_affected_claims", "-") + " " + ev.get("run_regression_suite", "")),
                 ("Root cause", rc.likely_defect or "INCONCLUSIVE")])
    with c2:
        st.markdown("**Hypotheses**")
        st.dataframe(pd.DataFrame(rc.hypotheses), width="stretch", hide_index=True)
        st.markdown("**Evidence (weights → confidence)**")
        st.dataframe(pd.DataFrame([{"step": e.kind, "weight": e.weight, "statement": e.statement} for e in rc.evidence]),
                     width="stretch", hide_index=True)
        if rc.sample_claims:
            st.markdown("**Affected synthetic claims (sample)**")
            st.dataframe(pd.DataFrame(rc.sample_claims), width="stretch", hide_index=True)
    corr = s.get("release_correlation")
    if corr:
        st.markdown(f"**Release correlation** ({'consistent ✅' if corr['consistent'] else 'inconsistent ❌'}): "
                    + " → ".join(corr["chain"]))
    st.divider()
    st.subheader("Recommended remediation")
    st.markdown("- **Count COMPLETED visits only** in AUTH_RULE_184 (hotfix 2.4.1) — requires human approval; "
                "production is never modified by an agent.")
    b1, b2, b3 = st.columns(3)
    if b1.button("GENERATE REGRESSION TEST", width="stretch"):
        run_investigation("qa_regression")
        st.rerun()
    if b2.button("CREATE DEFECT", width="stretch"):
        run_investigation(None)
        st.rerun()
    if b3.button("VIEW TRACEABILITY", width="stretch"):
        st.session_state.trace_focus = s["defect"].key if s.get("defect") is not None else "AUTH_RULE_184"
        st.session_state.nav = "Traceability"
        st.rerun()
    rem = s.get("remediation")
    if rem is not None:
        with st.container(border=True):
            st.markdown(f"**{rem.recommended_change}** · status {rem.status} · human approval required: {rem.requires_human_approval}")
            st.markdown(f"Claims to reprocess (after approval): **{rem.claims_to_reprocess}** · Rollback: {rem.rollback_option}")
            st.dataframe(pd.DataFrame(rem.verification["attempts"]), width="stretch", hide_index=True)
            for v in rem.additional_validation:
                st.markdown(f"- {v}")
    reg = s.get("regression")
    if reg:
        st.markdown(f"**Regression test {reg['test'].test_id}** — passes on fix: {reg['passes_on_fix']} · "
                    f"fails on deployed build: {reg['fails_on_deployed_build']}")
        st.code(reg["code"], language="python")
    d = s.get("defect")
    if d is not None:
        st.subheader(f"Defect {d.key} (MOCKED tracker)")
        st.markdown(f"**{d.title}** · Severity **{d.severity.value}** · {d.priority} · {d.status}")
        st.markdown(f"**Description:** {d.description}")
        st.markdown(f"**Expected:** {d.expected}  \n**Actual:** {d.actual}")
        st.markdown("**Reproduction:**\n" + "\n".join(f"1. {r}" for r in d.reproduction))
        st.markdown(f"**Source requirement:** {d.source_requirement} · **Introduced:** {d.introduced_in_release} · "
                    f"**Rule:** {d.rule_id} · **Policy:** {d.policy_section}")
    fb = s.get("feedback")
    if fb:
        st.subheader("SDLC feedback loop")
        st.dataframe(pd.DataFrame(fb["backlog_items"]), width="stretch", hide_index=True)
        for l in fb["lessons"]:
            st.markdown(f"- {l}")


VIEWS = {"ClaimIQ": claimiq, "Root Cause": root_cause}
