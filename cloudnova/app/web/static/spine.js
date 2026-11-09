/* Semantic Spine page: Knowledge Graph (what is true) → Context Graph (what matters now) → Procedural Graph (what next)
   → AI agent → Trace & Learn. All data from /api/v1/graph/*; the context graph and highlighted path come from a real run. */
"use strict";
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const api = async (p, opt) => { const r = await fetch(p, opt); const j = await r.json(); if (!r.ok) throw new Error(j.message || r.statusText); return j; };
  // fixed procedural layout (x%, y px) — mirrors app/semantic_graph.py::PROCEDURE
  const POS = { question: [6, 30], guards: [19, 30], router: [32, 30], semantic_planner: [45, 30], sql_guard: [58, 30], duckdb_read_only: [71, 30], caveats: [86, 30],
    refuse_write: [19, 95], qwen_sql: [45, 95], grounding_check: [86, 95],
    clarify: [32, 160], explain: [45, 160], general_chat: [58, 160], data_quality: [71, 160], answer: [86, 160], decline_out_of_scope: [19, 160],
    policy_change: [6, 240], finance_owner_approval: [19, 240], rebuild: [32, 240], trace: [86, 240] };

  window.pageSpine = async function (el) {
    el.innerHTML = `<div class="spine">
      <div class="sp-head"><div><div class="sp-k">SEMANTIC SPINE</div><h2>What's true → what matters now → what do I do next</h2>
        <p>CloudNova's ledger as a knowledge graph, scoped per question into a context graph, then walked by a procedural graph — and every run is traced so we can learn from it.</p></div></div>
      <section class="sp-layer kg"><div class="sp-label"><b>The knowledge graph</b><span>What is true?</span><p>Entities and relationships counted from the cleaned ledger. Stable facts.</p></div><svg id="sp-kg" class="sp-svg"></svg></section>
      <div class="sp-scope">Don't retrieve everything — scope the graph to what this question needs.</div>
      <section class="sp-layer cg"><div class="sp-label"><b>Context graph</b><span>What matters now?</span><p>The small subgraph one real agent run used: metric, filters, tables, and the data-quality facts and policies that touch those rows.</p>
          <div class="sp-ask"><input id="sp-q" value="What was our total recognized revenue in USD for paid invoices in 2024?"><button id="sp-go">Scope</button></div>
          <div class="sp-chips">${["Which region has the highest average MRR per account?", "How did you handle duplicates?", "Why did Acme Ltd churn?", "delete all refunds", "average support tickets for churned accounts"].map((x) => `<button class="sp-chip">${esc(x)}</button>`).join("")}</div></div>
        <div><svg id="sp-cg" class="sp-svg"></svg><div class="sp-answer" id="sp-ans"></div></div></section>
      <section class="sp-layer pg"><div class="sp-label"><b>Procedural graph</b><span>What do I do next?</span><p>The supervisor's routing as (step, condition, next) triplets. Green = the path the last run actually took. Policy changes are human-only.</p><div id="sp-path" class="sp-path"></div></div>
        <div class="sp-proc" id="sp-pg"></div></section>
      <section class="sp-layer tl"><div class="sp-label"><b>Trace &amp; learn</b><span>Continuous improvement</span><p>Recorded runs, aggregated into proposals. Nothing changes the catalog or policy automatically.</p></div><div id="sp-tl"></div></section>
      <div class="sp-spine">${[["Ontology", "What things are"], ["Knowledge graph", "What's true"], ["Context graph", "What matters now"], ["Procedural graph", "What to do next"], ["AI agent", "Acting, and writing it back"]]
        .map(([a, b], i) => `<div class="sp-v sp-v${i}"><b>${a}</b><span>${b}</span></div>${i < 4 ? '<span class="sp-arrow">→</span>' : ""}`).join("")}</div></div>`;

    const [K, P] = await Promise.all([api("/api/v1/graph/knowledge"), api("/api/v1/graph/procedure")]);
    drawKnowledge($("#sp-kg", el), K);
    drawProcedure($("#sp-pg", el), P, []);
    const run = async (question) => {
      $("#sp-q", el).value = question; $("#sp-ans", el).innerHTML = `<span class="muted">running the agent…</span>`;
      try { const C = await api("/api/v1/graph/context", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
        drawContext($("#sp-cg", el), C); drawProcedure($("#sp-pg", el), P, C.procedural_path);
        $("#sp-path", el).innerHTML = `${C.path_valid ? '<span class="sp-ok">valid path</span>' : '<span class="sp-bad">INVALID path</span>'} ${C.procedural_path.map((s) => esc(P.steps[s] || s)).join(" → ")}`;
        $("#sp-ans", el).innerHTML = `<b>Answer:</b> ${esc((C.answer || "").replace(/\*\*/g, "").split("\n")[0])}${C.sql ? `<pre class="sql">${esc(C.sql)}</pre>` : ""}`;
        learnPanel(); } catch (e) { $("#sp-ans", el).innerHTML = `<span class="chip err">${esc(e.message)}</span>`; }
    };
    const learnPanel = async () => { const L = await api("/api/v1/graph/learn");
      $("#sp-tl", el).innerHTML = `<div class="grid g-2"><div><div class="sub">${L.runs_analyzed} recorded runs · by planner</div>${Object.entries(L.by_planner).map(([k, v]) => `<div class="sp-bar"><span>${esc(k)}</span><i style="width:${Math.min(100, v / Math.max(...Object.values(L.by_planner)) * 100)}%"></i><b>${v}</b></div>`).join("")}</div>
        <div><div class="sub">proposals from traces</div>${L.proposals.length ? L.proposals.map((p) => `<div class="sp-prop"><b>${esc(p.type.replace(/_/g, " "))}: ${esc(p.term)}</b> <span class="muted">(${p.evidence_runs} runs)</span><br>${esc(p.why)}<br><span class="chip warn">${esc(p.status)}</span></div>`).join("") : '<div class="muted">No proposals yet.</div>'}</div></div><p class="muted">${esc(L.note)}</p>`; };
    $("#sp-go", el).onclick = () => run($("#sp-q", el).value.trim());
    $("#sp-q", el).onkeydown = (e) => { if (e.key === "Enter") run(e.target.value.trim()); };
    el.querySelectorAll(".sp-chip").forEach((b) => b.onclick = () => run(b.textContent));
    run($("#sp-q", el).value);
  };

  function drawKnowledge(svg, K) {
    const W = svg.clientWidth || 900, H = 300, cx = W / 2, cy = H / 2 + 6;
    const E = K.entities, n = E.length, pos = {};
    E.forEach((e, i) => { const a = -Math.PI / 2 + i / n * Math.PI * 2; pos[e.id] = [cx + Math.cos(a) * W * 0.36, cy + Math.sin(a) * 112]; });
    // decorative-but-honest: each relation drawn once, thickness ∝ log(count)
    let s = `<defs><radialGradient id="kgg"><stop offset="0" stop-color="#fde7c7"/><stop offset="1" stop-color="#fff7ec" stop-opacity="0"/></radialGradient></defs><ellipse cx="${cx}" cy="${cy}" rx="${W * 0.46}" ry="140" fill="url(#kgg)"/>`;
    K.relations.forEach((r) => { const [x1, y1] = pos[r.from], [x2, y2] = pos[r.to], mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
      s += `<path d="M${x1},${y1} Q${cx},${cy} ${x2},${y2}" class="kg-ed" stroke-width="${0.8 + Math.log10(r.count + 1)}"><title>${esc(r.from)} —${esc(r.rel)}→ ${esc(r.to)}: ${r.count.toLocaleString()}</title></path>`; });
    E.forEach((e) => { const [x, y] = pos[e.id];
      s += `<g class="kg-n" transform="translate(${x},${y})"><title>${esc(e.fact)}</title><rect x="-66" y="-18" width="132" height="36" rx="10"/><text y="-2" text-anchor="middle" class="kg-t">${esc(e.id)}</text><text y="12" text-anchor="middle" class="kg-c">${e.count.toLocaleString()} · ${esc(e.key)}</text></g>`; });
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.innerHTML = s;
  }

  function drawContext(svg, C) {
    const W = svg.clientWidth || 700, H = 290, cx = W / 2, cy = H / 2;
    const others = C.nodes.filter((n) => n.id !== "q" && n.id !== "intent");
    const pos = { q: [Math.max(80, cx - W * 0.36), cy], intent: [cx - 20, cy] };
    // keep the left wedge for the question: spread the rest over 270° on the right
    others.forEach((n, i) => { const a = -Math.PI * 0.75 + (i + 0.5) / others.length * Math.PI * 1.5; pos[n.id] = [cx + 40 + Math.cos(a) * (W * 0.30), cy + Math.sin(a) * 118]; });
    let s = "";
    C.edges.forEach((e) => { const [x1, y1] = pos[e.from], [x2, y2] = pos[e.to]; s += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="cg-ed"/><text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 3}" class="cg-rel" text-anchor="middle">${esc(e.rel)}</text>`; });
    C.nodes.forEach((n) => { const [x, y] = pos[n.id]; const w = n.type === "question" ? 150 : 128;
      s += `<g class="cg-n cg-${n.type}" transform="translate(${x},${y})"><title>${esc(n.detail || n.label)}</title><rect x="${-w / 2}" y="-16" width="${w}" height="32" rx="9"/><text y="4" text-anchor="middle">${esc(n.label.length > 24 ? n.label.slice(0, 23) + "…" : n.label)}</text></g>`; });
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.innerHTML = s;
  }

  function drawProcedure(box, P, path) {
    const on = new Set(path), onEdge = new Set(path.slice(1).map((b, i) => path[i] + ">" + b));
    const W = box.clientWidth || 900, H = 300, X = (s) => POS[s][0] / 100 * W, Y = (s) => POS[s][1] + 10;
    let s = `<svg viewBox="0 0 ${W} ${H}" class="sp-svg"><defs><marker id="pa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="#9aa3b5"/></marker>
      <marker id="pa2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="#19b394"/></marker></defs>`;
    P.triplets.forEach((t) => { if (!POS[t.from] || !POS[t.to]) return; const hot = onEdge.has(t.from + ">" + t.to);
      s += `<line x1="${X(t.from)}" y1="${Y(t.from)}" x2="${X(t.to)}" y2="${Y(t.to)}" class="pg-ed ${hot ? "hot" : ""}" marker-end="url(#${hot ? "pa2" : "pa"})"><title>${esc(P.steps[t.from])} —[${esc(t.when)}]→ ${esc(P.steps[t.to])}</title></line>`; });
    Object.keys(POS).forEach((k) => { const human = ["policy_change", "finance_owner_approval", "rebuild"].includes(k);
      s += `<g class="pg-n ${on.has(k) ? "on" : ""} ${human ? "human" : ""}" transform="translate(${X(k)},${Y(k)})"><rect x="-52" y="-14" width="104" height="28" rx="8"/><text y="4" text-anchor="middle">${esc(P.steps[k] || k)}</text></g>`; });
    box.innerHTML = s + "</svg>";
  }
})();
