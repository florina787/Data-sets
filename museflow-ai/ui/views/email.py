"""💌 Email Boutique — drafting studio. Sending is ALWAYS simulated."""
from __future__ import annotations

import streamlit as st

from services import scenario_loader as fixtures
from services.validation import ValidationError
from ui.components import e, html, no_autolink, page_run, render_run, section, start_run
from ui.session import ctx, flash


def _decide(run_id: str, decision: str) -> None:
    try:
        run = ctx().engine.resume(run_id, decision, "via Email Boutique")
        flash("Email marked as sent — in simulation only. 💌" if run.status == "completed" else f"Draft {decision}.", "💌")
    except (ValidationError, KeyError) as exc:
        flash(str(exc), "⚠️")


def render() -> None:
    engine = ctx().engine
    fx = fixtures.email_fixture()
    section("💌", "Email Boutique", "Rosie drafts from templates, Pearl checks policy, you approve — then we *simulate* the send.")
    st.info("📭 MuseFlow never connects to Gmail, Outlook, SMTP or any email service. Recipients are synthetic (@example.com).")
    with st.form("email_form"):
        c1, c2, c3 = st.columns(3)
        scenario = c1.selectbox("Email scenario", list(fx["scenarios"]), format_func=lambda k: fx["scenarios"][k]["title"])
        role = c2.selectbox("Recipient role", list(fx["recipients"]),
                            format_func=lambda k: f"{fx['recipients'][k]['role']} — {fx['recipients'][k]['name']}")
        tone = c3.selectbox("Tone", list(fx["tones"]), format_func=str.title)
        if st.form_submit_button("✍️ Generate draft", type="primary"):
            page_run("email", start_run("email_followup", {"email_scenario": scenario, "recipient_role": role, "tone": tone}))

    run = page_run("email")
    if run is None:
        html('<div class="mf-card"><h4>💌 Your draft will bloom here</h4><p>Choose a scenario, a recipient and a tone.</p></div>')
    else:
        draft = run.outputs.get("email", {}).get("draft")
        if draft:
            with st.container(border=True):
                html(f"<strong>To:</strong> {e(draft['to_name'])} &lt;{no_autolink(draft['to'])}&gt; · <strong>From:</strong> {no_autolink(draft['from'])}<br>"
                     f"<strong>Subject:</strong> {e(draft['subject'])} · <em>{e(draft['tone'])} tone</em>")
                if run.status == "awaiting_approval":
                    edited = st.text_area("Edit the draft", draft["body"], height=240, key=f"body_{run.run_id}", max_chars=2000)
                    c1, c2, c3 = st.columns(3)
                    c1.button("📨 Simulate Send", type="primary", key=f"send_{run.run_id}", on_click=_decide,
                              args=(run.run_id, "approved"), width="stretch")
                    c2.button("✋ Discard draft", key=f"discard_{run.run_id}", on_click=_decide, args=(run.run_id, "rejected"), width="stretch")
                    if c3.button("🔁 Apply my edits", key=f"edit_{run.run_id}", width="stretch", disabled=edited == draft["body"]):
                        engine.resume(run.run_id, "cancelled", "superseded by edited draft")
                        page_run("email", start_run("email_followup", {"email_scenario": draft["scenario"], "recipient_role": run.values["params"]["recipient_role"],
                                                                       "tone": draft["tone"], "custom_body": edited}))
                        st.rerun()
                    st.caption("Applying edits cancels this pending run and starts a new one, so the approved text is exactly what Pearl checked.")
                else:
                    st.text(draft["body"])
        render_run(run, key="email", show_response=run.status != "awaiting_approval")

    st.subheader("📤 Simulated outbox")
    if not engine.stores.outbox:
        st.caption("Nothing “sent” yet. Approved sends appear here — they never leave this app.")
    for mail in reversed(engine.stores.outbox):
        with st.expander(f"✅ {mail['subject']} → {mail['to']} · {mail['confirmation']} (simulated)"):
            st.text(mail["body"])
