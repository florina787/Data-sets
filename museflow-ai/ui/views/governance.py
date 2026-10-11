"""🛡️ Trust & Governance — the security posture of the public demo, checked live where possible."""
from __future__ import annotations

import importlib.util

import pandas as pd
import streamlit as st

from agents.governance import evaluate
from ui.components import badge, html, section
from ui.session import ctx

LLM_SDKS = ("anthropic", "openai", "google.generativeai", "google.genai", "langchain_openai", "langchain_anthropic", "cohere", "mistralai")
PLAYGROUND = {
    "Simulated email to a synthetic recipient": {"tool": "email.simulate_send", "args": {"to": "sam.rivera@example.com", "subject": "Hi", "body": "Hello!"}},
    "Email to a real-looking domain": {"tool": "email.simulate_send", "args": {"to": "someone@gmail.com", "subject": "Hi", "body": "Hello!"}},
    "Run a shell command": {"tool": "shell.exec", "args": {"cmd": "rm -rf /"}},
    "Call a paid LLM API": {"tool": "llm.chat_completion", "args": {"prompt": "hi"}},
    "Read-only research lookup": {"tool": "research.lookup_fixture", "args": {"topic": "ai_frameworks"}},
}


def render() -> None:
    engine = ctx().engine
    section("🛡️", "Trust & Governance", "What this demo can and cannot do — checked live where possible.")
    installed = [name for name in LLM_SDKS if _spec(name)]
    rows = [
        ("Execution mode", "Demo-only · deterministic simulation", True),
        ("API credentials", "None required, none read (no key prompts, no secrets in code)", True),
        ("LLM SDKs installed (live check)", ", ".join(installed) if installed else "none of " + ", ".join(LLM_SDKS), not installed),
        ("External integrations", "None — no email, calendar, browser, OAuth or MCP connectors", True),
        ("Consequential actions", "Require Governance + human approval; executed only as session-scoped simulations", True),
        ("Session isolation", f"Session {engine.session_id[:8]}… · own stores, audit log and InMemorySaver ({len(engine.checkpoints.threads())} thread(s))", True),
        ("Data retention", "In memory for this session only; nothing persisted to disk or a shared database", True),
        ("Audit chain integrity (live)", f"{len(engine.audit)} entries · verified={engine.audit.verify()}", engine.audit.verify()),
    ]
    for label, value, ok in rows:
        html(f'<div class="mf-card" style="padding:.6rem 1rem">{badge("✅ OK" if ok else "⚠️ CHECK", "ok" if ok else "warn")} '
             f"&nbsp;<strong>{label}</strong><p>{value}</p></div>")

    st.subheader("🧰 Tool allowlist")
    st.dataframe(pd.DataFrame([{"Tool": s.name, "Agent": s.agent, "Consequential → approval": "yes" if s.consequential else "no",
                                "Description": s.description} for s in engine.tools.specs.values()]), hide_index=True, width="stretch")

    st.subheader("🧪 Policy playground")
    st.caption("Evaluate a hypothetical action against Pearl's policies (evaluation only — nothing is executed).")
    choice = st.selectbox("Hypothetical action", list(PLAYGROUND))
    decisions = evaluate(PLAYGROUND[choice], engine.context())
    st.dataframe(pd.DataFrame(decisions), hide_index=True, width="stretch")

    st.subheader("📋 Policy decisions in this session")
    recorded = [{"Run": r.run_id, "Workflow": r.title, **d} for r in engine.history() for d in r.outputs.get("governance", {}).get("decisions", [])]
    st.dataframe(pd.DataFrame(recorded), hide_index=True, width="stretch") if recorded else st.caption("No governed workflows yet.")

    st.subheader("✨ Audit log (hash-chained)")
    entries = engine.audit.entries()
    if entries:
        st.dataframe(pd.DataFrame([{"#": x["seq"], "Run": x["run_id"], "Event": x["kind"], "Hash": x["hash"][:16] + "…",
                                    "Prev": x["prev_hash"][:10] + "…", "At": x["at"]} for x in reversed(entries)]), hide_index=True, width="stretch")
    else:
        st.caption("The audit log is empty — run a workflow.")


def _spec(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False
