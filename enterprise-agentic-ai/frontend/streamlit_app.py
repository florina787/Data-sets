"""Streamlit UI for the Enterprise Agentic AI Copilot.

Run with:  streamlit run frontend/streamlit_app.py
Configure the backend with API_BASE_URL (default http://localhost:8000).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from api_client import APIError, CopilotAPI
from styles import CSS, hero, kpi, route, source_card

TITLE = "Enterprise Agentic AI Copilot"
MOTTO = "From scattered enterprise knowledge to trusted action."
EXAMPLES = [
    "What is the current status of Project Phoenix?",
    "What are the major delivery risks?",
    "Summarize the architecture document.",
    "Which issues are blocking the October release?",
    "Compare the project status with the delivery metrics.",
    "What actions should the engineering manager take this week?",
]
AGENT_LABELS = {
    "supervisor": "Supervisor",
    "rag_agent": "RAG Agent",
    "tool_agent": "Tool Agent",
    "analysis_agent": "Analysis Agent",
    "response_agent": "Response Agent",
    "guardrail": "Guardrail",
}

st.set_page_config(page_title=TITLE, page_icon="🧭", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def get_api() -> CopilotAPI:
    return CopilotAPI(os.getenv("API_BASE_URL", "http://localhost:8000"))


api = get_api()
state = st.session_state
state.setdefault("history", [])  # list of {"question": str, "response": dict | None, "error": str | None}
state.setdefault("pending", None)

try:
    health = api.health()
    backend_error = None
except APIError as exc:
    health, backend_error = {}, str(exc)

st.markdown(
    hero(TITLE, MOTTO, health.get("mode", "demo"), health.get("llm_model"), health.get("embedding_backend")),
    unsafe_allow_html=True,
)
if backend_error:
    st.error(f"{backend_error}\n\nStart the API with `uvicorn app.api.main:app --port 8000`.")
    st.stop()
if health.get("embedding_fallback_reason"):
    st.info(f"ℹ️ {health['embedding_fallback_reason']}")

# --- Sidebar ---------------------------------------------------------------------
with st.sidebar:
    st.subheader("💡 Example questions")
    for example in EXAMPLES:
        if st.button(example, use_container_width=True, key=f"ex-{example}"):
            state.pending = example

    st.divider()
    st.subheader("📄 Upload a document")
    upload = st.file_uploader("Markdown, text or PDF", type=["md", "txt", "pdf"], label_visibility="collapsed")
    if upload is not None and st.button("Index document", type="primary", use_container_width=True):
        try:
            result = api.upload(upload.name, upload.getvalue(), upload.type)
            action = "Re-indexed" if result["replaced_existing"] else "Indexed"
            st.success(f"{action} **{result['filename']}** · {result['chunks_indexed']} chunks")
        except APIError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("⚙️ System")
    st.caption(
        f"Mode: **{health['mode'].upper()}** · Documents: **{health['documents_indexed']}** · "
        f"Chunks: **{health['chunks_indexed']}** · Tools: **{health['tools_available']}**"
    )
    if health["mode"] == "demo":
        st.caption("Demo mode composes answers offline from retrieved evidence and tool data. No LLM API calls are made.")
    top_k = st.slider("Chunks to retrieve (top-k)", 1, 10, 5)
    with st.expander("Indexed documents"):
        try:
            for doc in api.documents():
                st.markdown(f"- `{doc['filename']}` · {doc['chunks']} chunks")
        except APIError as exc:
            st.caption(str(exc))
    if st.button("Clear conversation", use_container_width=True):
        state.history = []
        st.rerun()
    st.caption("All enterprise data in this demo is synthetic and fictional.")

# --- Main layout ------------------------------------------------------------------
chat_col, insight_col = st.columns([3, 2], gap="large")

with chat_col:
    st.subheader("💬 Ask the copilot")
    question = st.chat_input("Ask a business question about projects, risks, issues or people…")
    if state.pending:
        question, state.pending = state.pending, None

    if question:
        with st.spinner("Supervisor routing → agents working → guardrail validating…"):
            try:
                state.history.append({"question": question, "response": api.chat(question, top_k=top_k), "error": None})
            except APIError as exc:
                state.history.append({"question": question, "response": None, "error": str(exc)})

    if not state.history:
        st.markdown(
            "Ask a question or pick an example from the sidebar. Each request is routed by a "
            "**LangGraph supervisor** through specialised agents. The answer is checked by a **guardrail** "
            "and shown with its sources, route and metrics."
        )
    for turn in state.history:
        with st.chat_message("user"):
            st.markdown(turn["question"])
        with st.chat_message("assistant", avatar="🧭"):
            if turn["error"]:
                st.error(turn["error"])
                continue
            resp = turn["response"]
            st.markdown(route(resp["route"]), unsafe_allow_html=True)
            st.markdown(resp["answer"])
            conf = resp["confidence"]
            st.caption(
                f"Intent **{resp['intent']}** · confidence **{conf:.0%}** · "
                f"{resp['latency_ms']:.0f} ms · request `{resp['request_id']}`"
            )

last = next((t["response"] for t in reversed(state.history) if t["response"]), None)

with insight_col:
    tab_exec, tab_sources, tab_metrics, tab_obs = st.tabs(["🧠 Agents", "📚 Sources", "📊 Metrics", "🔭 Traces"])

    with tab_exec:
        if not last:
            st.caption("The agent route and step timings appear here after your first question.")
        else:
            st.markdown("**Agent route**")
            st.markdown(route(last["route"]), unsafe_allow_html=True)
            st.caption(last.get("intent_reasoning", ""))
            steps = pd.DataFrame(
                [
                    {
                        "step": i + 1,
                        "agent": AGENT_LABELS.get(s["agent"], s["agent"]),
                        "ms": s["duration_ms"],
                        "detail": s["detail"] + (f" ⚠️ {s['error']}" if s.get("error") else ""),
                    }
                    for i, s in enumerate(last["agent_steps"])
                ]
            )
            st.dataframe(steps, hide_index=True, use_container_width=True)
            if last["tool_calls"]:
                st.markdown("**Tools invoked**")
                for call in last["tool_calls"]:
                    icon = "✅" if call["success"] else "❌"
                    args = ", ".join(f"{k}={v}" for k, v in call["arguments"].items())
                    with st.expander(f"{icon} {call['tool_name']}({args}) · {call['duration_ms']:.1f} ms"):
                        st.json(call["result"] if call["success"] else {"error": call["error"]})
            g = last["guardrail"]
            st.markdown("**Guardrail**")
            st.markdown(
                f"{'✅ Passed' if g['passed'] else '⚠️ Flagged'} · grounding **{g['grounding_score']:.0%}** · "
                f"citation validity **{g['citation_validity']:.0%}** · redactions **{len(g['redactions'])}**"
            )
            for issue in g["issues"]:
                st.caption(f"• {issue}")
            if last["errors"]:
                st.warning("Errors during execution:\n\n" + "\n".join(f"- {e}" for e in last["errors"]))

    with tab_sources:
        if not last:
            st.caption("Cited sources with filename, document ID and chunk ID appear here.")
        else:
            if not last["citations"]:
                st.caption("No sources cited for this answer.")
            for citation in last["citations"]:
                st.markdown(source_card(citation), unsafe_allow_html=True)
            if last["retrieved_chunks"]:
                with st.expander(f"All retrieved chunks ({len(last['retrieved_chunks'])})"):
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"score": c["score"], "filename": c["filename"], "section": c["section"], "chunk_id": c["chunk_id"]}
                                for c in last["retrieved_chunks"]
                            ]
                        ),
                        hide_index=True,
                        use_container_width=True,
                    )

    with tab_metrics:
        if not last:
            st.caption("Latency, tokens, retrieval and confidence for the last request appear here.")
        else:
            usage = last["token_usage"]
            token_sub = "estimated · no LLM call" if usage["estimated"] else f"{usage['llm_calls']} Claude calls"
            c1, c2 = st.columns(2)
            c1.markdown(kpi("Latency", f"{last['latency_ms']:.0f} ms", "end-to-end graph run"), unsafe_allow_html=True)
            c2.markdown(kpi("Confidence", f"{last['confidence']:.0%}", "guardrail score"), unsafe_allow_html=True)
            c3, c4 = st.columns(2)
            c3.markdown(kpi("Retrieved chunks", str(len(last["retrieved_chunks"])), "from vector store"), unsafe_allow_html=True)
            c4.markdown(kpi("Tools invoked", str(len(last["tool_calls"])), "enterprise tools"), unsafe_allow_html=True)
            c5, c6 = st.columns(2)
            c5.markdown(kpi("Tokens", f"{usage['total_tokens']:,}", token_sub), unsafe_allow_html=True)
            c6.markdown(kpi("Sources cited", str(len(last["citations"])), "documents + tools"), unsafe_allow_html=True)
            st.markdown("")
            st.progress(min(1.0, max(0.0, last["confidence"])), text=f"Confidence {last['confidence']:.0%}")
            st.markdown("**Latency by agent (ms)**")
            per_agent: dict[str, float] = {}
            for s in last["agent_steps"]:
                label = AGENT_LABELS.get(s["agent"], s["agent"])
                per_agent[label] = per_agent.get(label, 0.0) + s["duration_ms"]
            st.bar_chart(pd.Series(per_agent, name="ms"), horizontal=True)

    with tab_obs:
        try:
            m = api.metrics()
        except APIError as exc:
            st.caption(str(exc))
            m = None
        if m:
            o1, o2, o3 = st.columns(3)
            o1.markdown(kpi("Requests", str(m["total_requests"]), f"{m['failed_requests']} failed"), unsafe_allow_html=True)
            o2.markdown(kpi("Avg latency", f"{m['avg_latency_ms']:.0f} ms", f"p95 {m['p95_latency_ms']:.0f} ms"), unsafe_allow_html=True)
            o3.markdown(kpi("Avg confidence", f"{m['avg_confidence']:.0%}", f"{m['llm_calls']} LLM calls"), unsafe_allow_html=True)
            if m["intent_counts"]:
                st.markdown("**Intents routed**")
                st.bar_chart(pd.Series(m["intent_counts"], name="requests"), horizontal=True)
            if m["recent_traces"]:
                st.markdown("**Recent traces**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "time": t["timestamp"][11:19],
                                "request_id": t["request_id"],
                                "intent": t["intent"],
                                "path": " → ".join(AGENT_LABELS.get(a, a) for a in t["agents_invoked"]),
                                "tools": len(t["tool_calls"]),
                                "chunks": t["retrieval_count"],
                                "ms": t["latency_ms"],
                                "errors": len(t["errors"]),
                            }
                            for t in m["recent_traces"]
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
