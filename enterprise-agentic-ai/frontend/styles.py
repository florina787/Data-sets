"""CSS and small HTML helpers for the Streamlit UI."""

from __future__ import annotations

import html

CSS = """
<style>
:root {
  --ink: #0f172a; --muted: #64748b; --line: #e2e8f0; --card: #ffffff;
  --brand: #4f46e5; --brand-2: #0ea5e9; --ok: #059669; --warn: #d97706; --bad: #dc2626;
}
.block-container { padding-top: 3rem; max-width: 1400px; }
.hero {
  background: linear-gradient(120deg, #1e1b4b 0%, #4338ca 55%, #0ea5e9 100%);
  border-radius: 18px; padding: 26px 30px; color: #fff; margin-bottom: 18px;
  box-shadow: 0 10px 30px rgba(67, 56, 202, .25);
}
.hero h1 { font-size: 2.05rem; margin: 0; color: #fff; letter-spacing: -.02em; }
.hero p { margin: 6px 0 0; font-size: 1.08rem; opacity: .92; font-style: italic; }
.hero .badges { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.35); color: #fff;
}
.badge.demo { background: #fef3c7; color: #92400e; border-color: #fcd34d; }
.badge.live { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
.route { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 4px 0 12px; }
.route .node {
  padding: 6px 12px; border-radius: 10px; font-weight: 600; font-size: .86rem;
  background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe;
}
.route .node.guard { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }
.route .arrow { color: var(--muted); font-weight: 700; }
.kpi {
  border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; background: var(--card);
}
.kpi .label { color: var(--muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; }
.kpi .value { font-size: 1.45rem; font-weight: 700; color: var(--ink); }
.kpi .sub { color: var(--muted); font-size: .75rem; }
.src {
  border: 1px solid var(--line); border-left: 4px solid var(--brand); border-radius: 10px;
  padding: 10px 12px; margin-bottom: 8px; background: #fafbff;
}
.src.tool { border-left-color: var(--brand-2); background: #f5fbff; }
.src .meta { font-size: .78rem; color: var(--muted); }
.src .label { font-weight: 700; color: var(--brand); margin-right: 6px; }
.small-muted { color: var(--muted); font-size: .8rem; }
</style>
"""


def hero(title: str, motto: str, mode: str, model: str | None, embedding: str | None) -> str:
    mode_badge = (
        '<span class="badge live">LIVE AI MODE · Claude</span>'
        if mode == "live"
        else '<span class="badge demo">DEMO MODE · no API key · zero LLM cost</span>'
    )
    extra = []
    if model:
        extra.append(f'<span class="badge">Model: {html.escape(model)}</span>')
    if embedding:
        extra.append(f'<span class="badge">Embeddings: {html.escape(embedding)}</span>')
    extra.append('<span class="badge">LangGraph · RAG · Tools · Guardrails</span>')
    return (
        f'<div class="hero"><h1>{html.escape(title)}</h1><p>{html.escape(motto)}</p>'
        f'<div class="badges">{mode_badge}{"".join(extra)}</div></div>'
    )


def route(nodes: list[str]) -> str:
    parts = []
    for i, node in enumerate(nodes):
        cls = "node guard" if node == "Guardrail" else "node"
        parts.append(f'<span class="{cls}">{html.escape(node)}</span>')
        if i < len(nodes) - 1:
            parts.append('<span class="arrow">→</span>')
    return f'<div class="route">{"".join(parts)}</div>'


def kpi(label: str, value: str, sub: str = "") -> str:
    return (
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div><div class="sub">{html.escape(sub)}</div></div>'
    )


def source_card(citation: dict) -> str:
    label = html.escape(citation["label"])
    if citation["source_type"] == "tool":
        return (
            f'<div class="src tool"><span class="label">[{label}]</span><b>Enterprise tool</b>'
            f'<div class="meta"><code>{html.escape(citation.get("snippet") or "")}</code></div></div>'
        )
    score = citation.get("score")
    score_txt = f" · similarity {score:.2f}" if isinstance(score, (int, float)) else ""
    return (
        f'<div class="src"><span class="label">[{label}]</span><b>{html.escape(citation.get("filename") or "")}</b>'
        f' › {html.escape(citation.get("section") or "")}'
        f'<div class="meta">document_id <code>{html.escape(citation.get("document_id") or "")}</code> · '
        f'chunk_id <code>{html.escape(citation.get("chunk_id") or "")}</code>{score_txt}</div>'
        f'<div style="margin-top:6px">{html.escape(citation.get("snippet") or "")}</div></div>'
    )
