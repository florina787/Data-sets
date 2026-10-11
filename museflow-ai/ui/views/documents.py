"""📚 Document Wonderland — deterministic extraction with traceable evidence."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services import scenario_loader as fixtures
from services.validation import ValidationError, validate_upload
from ui.components import page_run, render_run, section, start_run
from ui.session import ctx


def render() -> None:
    engine = ctx().engine
    section("📚", "Document Wonderland", "Athena extracts fields, an extractive summary and line-numbered evidence — classic text processing, no model.")
    st.caption("What Athena can do: split sentences, score them by term frequency, read `Label: value` lines, find dates / amounts / "
               "percentages, list headings and action items. She does **not** understand meaning beyond that.")
    docs = fixtures.list_documents()
    tab_lib, tab_upload = st.tabs(["📚 Sample library", "📄 Local upload (.txt / .md)"])
    with tab_lib:
        c1, c2, c3 = st.columns([3, 1, 1])
        doc = c1.selectbox("Synthetic document", docs, format_func=lambda d: f"{d.emoji} {d.title} — {d.type}")
        c2.write("")
        if c2.button("🔍 Analyze", type="primary", width="stretch"):
            page_run("documents", start_run("document_analysis", {"document_id": doc.id}))
        c3.write("")
        if c3.button("🖋️ Propose redline", width="stretch"):
            page_run("documents", start_run("document_edit", {"document_id": doc.id, "edit": "add_summary_header"}))
    with tab_upload:
        st.caption("Processed locally in this session only, never sent anywhere. Max 100 KB, UTF-8 .txt or .md.")
        upload = st.file_uploader("Upload a text document", type=["txt", "md"], accept_multiple_files=False)
        if upload is not None and st.button("🔍 Analyze upload", type="primary"):
            try:
                text = validate_upload(upload.name, upload.getvalue())
                page_run("documents", start_run("document_analysis", {"document_id": "upload", "upload_name": upload.name, "upload_text": text}))
            except ValidationError as exc:
                st.error(str(exc))

    run = page_run("documents")
    if run is None:
        st.info("📖 Pick a document and press Analyze.")
        return
    out = run.outputs.get("document", {})
    if out:
        meta = out["meta"]
        st.subheader(f"{meta['emoji']} {meta['title']}")
        stats = out["stats"]
        cols = st.columns(4)
        cols[0].metric("Words", stats["words"])
        cols[1].metric("Lines", stats["lines"])
        cols[2].metric("Reading time", f"{stats['reading_minutes']} min")
        cols[3].metric("Evidence snippets", len(out["evidence"]))
        st.caption(f"Type: {meta['type']} · id: {meta['id']} · synthetic sample — not a real document.")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📝 Extractive summary** (top-scoring sentences, original order)")
            for s in out["summary"]:
                st.markdown(f"- {s['sentence']} `line {s['line']}`")
            if out.get("fields"):
                st.markdown("**🔑 Key information**")
                st.dataframe(pd.DataFrame(out["fields"]), hide_index=True, width="stretch")
        with c2:
            ents = out["entities"]
            st.markdown("**📅 Dates / 💰 amounts / ％ percentages**")
            st.write({k: [x["value"] for x in v] for k, v in ents.items()})
            if out.get("action_items"):
                st.markdown("**✅ Decisions & action items**")
                for item in out["action_items"]:
                    st.markdown(f"- **{item['kind']}:** {item['text']} `line {item['line']}`")
            st.markdown("**🏷️ Top keywords:** " + ", ".join(f"{w} ({n})" for w, n in out["keywords"]))
        with st.expander("🧾 Evidence snippets (traceability: every claim → a line)", expanded=True):
            st.dataframe(pd.DataFrame(out["evidence"]), hide_index=True, width="stretch")
        glossary = run.outputs.get("research", {}).get("evidence")
        if glossary:
            with st.expander("🧚 Aurora's glossary for terms in this document"):
                st.dataframe(pd.DataFrame(glossary), hide_index=True, width="stretch")
        if out.get("diff"):
            with st.expander("🖋️ Proposed redline (unified diff)", expanded=True):
                st.code("\n".join(out["diff"]), language="diff")
        with st.expander("📄 Extracted text with line numbers"):
            st.code("\n".join(f"{i:>3} │ {line}" for i, line in enumerate(out["full_text"].splitlines(), 1)), language=None)
    render_run(run, key="docs")
    if engine.stores.document_edits:
        st.caption("Approved redlines are applied to this session's copy only: " + ", ".join(engine.stores.document_edits))
