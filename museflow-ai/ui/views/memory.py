"""🧠🌸 Memory Garden — session-scoped memories shown as flowers."""
from __future__ import annotations

import streamlit as st

from services.memory_store import CATEGORY_FLOWERS, MEMORY_CATEGORIES
from services.validation import ValidationError
from ui.components import e, html, page_run, render_run, section, start_run
from ui.session import ctx, flash


def _delete(memory_id: str) -> None:
    ctx().engine.stores.memory.delete(memory_id)
    flash("Memory removed from your garden.", "🍂")


def render() -> None:
    engine = ctx().engine
    store = engine.stores.memory
    section("🧠", "Memory Garden", "Every memory is a flower that lives only in this browser session.")
    st.info("🌱 Memory is **session-scoped**: it is kept in your Streamlit session only, never written to a shared file or "
            "database, and may disappear after refresh, session expiry or a server restart. Please don't add sensitive "
            "personal information — the demo rejects emails, phone numbers, IDs and credentials.")

    with st.form("add_memory", clear_on_submit=True):
        st.markdown("**🌷 Plant a memory** (runs the *Personal Memory* workflow: Supervisor → Memory → Audit)")
        c1, c2 = st.columns([1, 3])
        category = c1.selectbox("Category", MEMORY_CATEGORIES)
        text = c2.text_input("Memory", placeholder="I prefer deep-work blocks in the morning.", max_chars=280)
        if st.form_submit_button("🌸 Plant it", type="primary"):
            run = start_run("personal_memory", {"operation": "add", "category": category, "text": text})
            if run is not None:
                page_run("memory", run)

    last = page_run("memory")
    if last is not None:
        render_run(last, key="mem")

    c1, c2 = st.columns([3, 1])
    query = c1.text_input("🔎 Search memories", placeholder="morning, goals, project…", max_chars=100)
    category_filter = c2.selectbox("Filter", ["All", *MEMORY_CATEGORIES])
    items = store.search(query, None if category_filter == "All" else category_filter)

    if not items:
        html('<div class="mf-card" style="text-align:center"><div class="mf-flower">🌱</div>'
             "<p>Your garden is waiting for its first flower. Plant a memory above — or tell Lumi “remember that …”.</p></div>")
    cols = st.columns(3)
    for index, item in enumerate(items):
        with cols[index % 3]:
            with st.container(border=True):
                html(f'<div class="mf-flower">{CATEGORY_FLOWERS[item.category]}</div>'
                     f"<strong>{e(item.category)}</strong><p>{e(item.text)}</p>"
                     f'<small style="color:var(--mf-muted)">{e(item.id)} · {e(item.updated_at)} · via {e(item.source)}</small>')
                with st.popover("✏️ Edit"):
                    new_cat = st.selectbox("Category", MEMORY_CATEGORIES, index=MEMORY_CATEGORIES.index(item.category), key=f"cat_{item.id}")
                    new_text = st.text_area("Text", item.text, key=f"txt_{item.id}", max_chars=280)
                    if st.button("Save", key=f"save_{item.id}"):
                        try:
                            store.update(item.id, new_cat, new_text)
                            flash("Memory updated.", "🌸")
                            st.rerun()
                        except ValidationError as exc:
                            st.error(str(exc))
                st.button("🗑️ Delete", key=f"del_{item.id}", on_click=_delete, args=(item.id,))

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🌸 Ask Iris what she remembers"):
        if page_run("memory", start_run("memory_recall", {"operation": "search", "query": query})):
            st.rerun()
    if c2.button("🧹 Clear my demo memories"):
        store.clear()
        flash("Your memory garden was cleared.", "🧹")
        st.rerun()
