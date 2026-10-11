"""💖 Human Approval Center — LangGraph interrupts awaiting a human decision."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from services.validation import ValidationError
from ui.components import approval_box, html, section
from ui.session import ctx, flash


@st.dialog("💖 Review simulated action", width="large")
def review_dialog(run_id: str) -> None:
    engine = ctx().engine
    run = engine.runs[run_id]
    pending = run.pending or {}
    st.markdown(f"**{pending.get('summary', '')}**")
    st.caption(f"Run {run.run_id} · {run.title} · tool `{pending.get('tool')}` · proposed by {fixtures.get_agent(pending.get('agent', 'supervisor')).name}")
    st.json(pending.get("args", {}))
    note = st.text_input("Note for the audit log", max_chars=200)
    c1, c2, c3 = st.columns(3)
    for col, label, decision in ((c1, "💖 Approve", "approved"), (c2, "✋ Reject", "rejected"), (c3, "🚫 Cancel", "cancelled")):
        if col.button(label, key=f"dlg_{decision}", type="primary" if decision == "approved" else "secondary", width="stretch"):
            try:
                result = engine.resume(run_id, decision, note)
                flash(f"{result.title}: {result.status}.", "💖")
            except (ValidationError, KeyError) as exc:
                flash(str(exc), "⚠️")
            st.rerun()


def render() -> None:
    engine = ctx().engine
    section("💖", "Human Approval Center", "Consequential (simulated) actions pause the graph at a LangGraph interrupt until you decide.")
    st.caption("Approve → the same checkpointed thread resumes and the action runs *in simulation*. Reject / Cancel → nothing executes; "
               "the Audit Agent records the decision. Checkpoints live in this session's private in-memory saver.")
    pending = engine.pending()
    if not pending:
        html('<div class="mf-card" style="text-align:center"><div class="mf-flower">🦄</div><h4>All caught up!</h4>'
             "<p>No approvals waiting. Try drafting an email or a simulated booking.</p></div>")
    for run in pending:
        st.markdown(f"#### {run.emoji} {run.title} · `{run.run_id}`")
        approval_box(run, key="center")
        if st.button("🔍 Open review dialog", key=f"dlg_open_{run.run_id}"):
            review_dialog(run.run_id)

    decided = [r for r in engine.history() if r.values.get("approval") or r.status in {"denied"}]
    st.subheader("📜 Decision history")
    if decided:
        rows = []
        for run in decided:
            appr = run.values.get("approval") or {}
            rows.append({"Run": run.run_id, "Workflow": run.title, "Action": (run.values.get("action") or {}).get("tool", ""),
                         "Decision": appr.get("decision", "—"), "Final status": run.status, "Note": appr.get("note", ""),
                         "Decided at": appr.get("decided_at", "")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("No decisions yet.")
    st.markdown("**Approval states:** ⏳ Pending · 💖 Approved · ✋ Rejected · 🚫 Cancelled · ✅ Completed")
