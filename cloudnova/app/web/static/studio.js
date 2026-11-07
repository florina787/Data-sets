/* Financial Investigation Studio — Revenue Constellation · Investigation Replay · Decision Butterfly.
   One experience: click an invoice → its replay; click a policy → its impact. All data from /api/v1/studio/*. */
"use strict";
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const usd = (v, d = 2) => v == null ? "—" : (v < 0 ? "-" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const STATUS_COLOR = { paid: "#a3e635", refunded: "#f472b6", pending: "#f2c14e", failed: "#fb7185", void: "#64748b" };
  const api = async (p) => { const r = await fetch(p); const j = await r.json(); if (!r.ok) throw new Error(j.message || r.statusText); return j; };

  window.pageStudio = async function (el, initial) {
    const st = { view: "constellation", filters: { q: "", region: "", plan: "", flag: "", accounts: 12 }, graph: null, sel: null };
    el.innerHTML = `<div class="studio">
      <div class="st-head"><div><div class="st-kicker">FINANCIAL INVESTIGATION STUDIO</div><h2>Follow any number back to the rows and rules that produced it</h2>
        <p>Accounts, invoices, discrepancy checks and policy decisions from the cleaned ledger. Every link is a database fact; proposed policies are never shown as approved.</p></div>
        <div class="st-tabs" role="tablist">${[["constellation", "Revenue Constellation"], ["replay", "Investigation Replay"], ["butterfly", "Decision Butterfly"]]
          .map(([k, l]) => `<button role="tab" data-v="${k}">${l}</button>`).join("")}</div></div>
      <div class="st-body"><div class="st-main" id="st-main"></div><aside class="st-evidence" id="st-ev"><div class="st-kicker">EVIDENCE</div><p class="st-muted">Select a node, step or metric.</p></aside></div></div>`;
    const main = $("#st-main", el), ev = $("#st-ev", el);
    el.querySelectorAll(".st-tabs button").forEach((b) => b.onclick = () => { if (b.dataset.v === "constellation") showGraph(); else if (b.dataset.v === "replay") showReplay(st.sel?.invoice || "INV-102104"); else showButterfly(st.sel?.policy || "fx_direction"); });
    const setTab = (v) => { st.view = v; el.querySelectorAll(".st-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.v === v)); };
    const evidence = (title, html) => { ev.innerHTML = `<div class="st-kicker">EVIDENCE</div><h3>${esc(title)}</h3>${html}`; };

    /* ---------------- 1. Revenue Constellation */
    async function showGraph() {
      setTab("constellation");
      main.innerHTML = `<div class="st-filters">
          <input id="sf-q" placeholder="Search account, name or invoice id…" value="${esc(st.filters.q)}">
          <select id="sf-region"><option value="">All regions</option>${["NA", "EMEA", "APAC", "LATAM"].map((r) => `<option ${st.filters.region === r ? "selected" : ""}>${r}</option>`).join("")}</select>
          <select id="sf-plan"><option value="">All plans</option>${["Starter", "Pro", "Enterprise"].map((r) => `<option ${st.filters.plan === r ? "selected" : ""}>${r}</option>`).join("")}</select>
          <select id="sf-flag"><option value="">Any discrepancy</option>${[["status_conflict", "Status conflict"], ["refund_without_payment", "Refund w/o payment"], ["refund_before_first_payment", "Refund before payment"], ["future_dated_paid", "Future-dated paid"], ["aged_receivable", "Aged receivable"], ["ambiguous_date", "Ambiguous date"]].map(([v, l]) => `<option value="${v}" ${st.filters.flag === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          <label>accounts <input id="sf-n" type="range" min="4" max="40" value="${st.filters.accounts}"><b id="sf-nv">${st.filters.accounts}</b></label></div>
        <div class="st-canvas"><svg id="st-svg"></svg><div class="st-tip" id="st-tip"></div>
          <div class="st-legend"><span><i class="lg acc"></i>account</span><span><i class="lg inv"></i>invoice (colour = status)</span><span><i class="lg disc"></i>discrepancy check</span><span><i class="lg pol"></i>policy / open decision</span><span class="st-muted">drag to pan · wheel to zoom · click for evidence</span></div></div>`;
      let t; const reload = () => { clearTimeout(t); t = setTimeout(loadGraph, 250); };
      $("#sf-q", el).oninput = (e) => { st.filters.q = e.target.value; reload(); };
      ["region", "plan", "flag"].forEach((k) => $(`#sf-${k}`, el).onchange = (e) => { st.filters[k] = e.target.value; loadGraph(); });
      $("#sf-n", el).oninput = (e) => { st.filters.accounts = +e.target.value; $("#sf-nv", el).textContent = e.target.value; reload(); };
      await loadGraph();
    }

    async function loadGraph() {
      const f = st.filters, svg = $("#st-svg", el);
      if (!svg) return;
      try { st.graph = await api(`/api/v1/studio/graph?q=${encodeURIComponent(f.q)}&region=${f.region}&plan=${f.plan}&flag=${f.flag}&accounts=${f.accounts}`); }
      catch (e) { svg.innerHTML = ""; evidence("Error", `<p>${esc(e.message)}</p>`); return; }
      const g = st.graph;
      if (!g.nodes.length) { svg.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="#8f93c9">No accounts match these filters.</text>`; return; }
      const W = svg.clientWidth || 900, H = svg.clientHeight || 560, cx = W / 2, cy = H / 2;
      const N = g.nodes.map((n, i) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0 })), idx = Object.fromEntries(N.map((n, i) => [n.id, i]));
      const accs = N.filter((n) => n.type === "account"), pols = N.filter((n) => n.type === "policy"), discs = N.filter((n) => n.type === "discrepancy");
      accs.forEach((n, i) => { const a = i / accs.length * Math.PI * 2; n.x = cx + Math.cos(a) * W * 0.30; n.y = cy + Math.sin(a) * H * 0.32; });
      [...pols, ...discs].forEach((n, i, arr) => { const a = i / arr.length * Math.PI * 2 + 0.4; n.x = cx + Math.cos(a) * 60; n.y = cy + Math.sin(a) * 60; });
      const E = g.edges.map((e) => ({ ...e, a: idx[e.from], b: idx[e.to] }));
      E.filter((e) => e.type === "billed").forEach((e) => { N[e.b].x = N[e.a].x + (Math.random() - .5) * 40; N[e.b].y = N[e.a].y + (Math.random() - .5) * 40; });
      for (let it = 0; it < 260; it++) {  // small deterministic-enough force layout (repulsion + springs + centre)
        for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
          const dx = N[j].x - N[i].x, dy = N[j].y - N[i].y, d2 = dx * dx + dy * dy + 0.01, f = Math.min(260 / d2, 2);
          N[i].vx -= dx * f; N[i].vy -= dy * f; N[j].vx += dx * f; N[j].vy += dy * f; }
        for (const e of E) { const A = N[e.a], B = N[e.b], dx = B.x - A.x, dy = B.y - A.y, d = Math.sqrt(dx * dx + dy * dy) + .01;
          const L = e.type === "billed" ? 38 : 170, k = (d - L) * (e.type === "billed" ? 0.05 : 0.004); A.vx += dx / d * k; A.vy += dy / d * k; B.vx -= dx / d * k; B.vy -= dy / d * k; }
        for (const n of N) { n.vx += (cx - n.x) * 0.004; n.vy += (cy - n.y) * 0.004; n.x += n.vx * .5; n.y += n.vy * .5; n.vx *= .6; n.vy *= .6;
          n.x = Math.max(60, Math.min(W - 60, n.x)); n.y = Math.max(40, Math.min(H - 40, n.y)); } }
      const maxRev = Math.max(...accs.map((a) => a.net_revenue_usd || 1));
      const shape = (n) => {
        if (n.type === "account") { const r = 9 + 14 * Math.sqrt(Math.max(n.net_revenue_usd, 0) / maxRev); return `<circle r="${r}" class="nd-acc"/>`; }
        if (n.type === "invoice") return `<circle r="5" fill="${STATUS_COLOR[n.status] || "#94a3b8"}" class="nd-inv"/>`;
        if (n.type === "discrepancy") return `<rect x="-9" y="-9" width="18" height="18" transform="rotate(45)" class="nd-disc"/>`;
        return `<rect x="-14" y="-10" width="28" height="20" rx="5" class="nd-pol"/>`; };
      svg.innerHTML = `<g id="vp">${E.map((e) => `<line class="ed ed-${e.type}" data-a="${e.a}" data-b="${e.b}" x1="${N[e.a].x}" y1="${N[e.a].y}" x2="${N[e.b].x}" y2="${N[e.b].y}"/>`).join("")}
        ${N.map((n, i) => `<g class="nd nd-t-${n.type}" data-i="${i}" transform="translate(${n.x},${n.y})" tabindex="0">${shape(n)}${n.type !== "invoice" ? `<text y="${n.type === "account" ? -14 - 14 * Math.sqrt(Math.max(n.net_revenue_usd || 0, 0) / maxRev) + 8 : -16}" text-anchor="middle">${esc(n.type === "account" ? n.label : n.label)}</text>` : ""}</g>`).join("")}</g>`;
      // pan/zoom
      let vb = { x: 0, y: 0, w: W, h: H }, drag = null; const apply = () => svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); apply();
      svg.onwheel = (e) => { e.preventDefault(); const k = e.deltaY > 0 ? 1.12 : 0.89; const mx = vb.x + e.offsetX / svg.clientWidth * vb.w, my = vb.y + e.offsetY / svg.clientHeight * vb.h;
        vb = { x: mx - (mx - vb.x) * k, y: my - (my - vb.y) * k, w: vb.w * k, h: vb.h * k }; apply(); };
      svg.onmousedown = (e) => { if (!e.target.closest(".nd")) drag = { x: e.clientX, y: e.clientY, vb: { ...vb } }; };
      window.onmouseup = () => { drag = null; };
      svg.onmousemove = (e) => { if (drag) { const s = vb.w / svg.clientWidth; vb.x = drag.vb.x - (e.clientX - drag.x) * s; vb.y = drag.vb.y - (e.clientY - drag.y) * s; apply(); } };
      const tip = $("#st-tip", el);
      const describe = (n) => n.type === "account" ? `<b>${esc(n.label)}</b> · ${esc(n.ref)}<br>${esc(n.region)} · ${esc(n.plan)} · ${n.invoices} invoice(s)<br>net revenue ${usd(n.net_revenue_usd, 0)} · MRR ${usd(n.mrr_usd, 0)}`
        : n.type === "invoice" ? `<b>${esc(n.ref)}</b> · ${esc(n.status)}<br>${usd(n.amount_usd)} USD (${esc(n.currency)}) · ${esc(n.invoice_date)}<br><span class="st-muted">click → investigation replay</span>`
        : n.type === "discrepancy" ? `<b>${esc(n.label)}</b><br>${n.ledger_total.toLocaleString()} invoices in the whole ledger`
        : `<b>${esc(n.label)}</b><br>active: ${esc(n.active_value)}<br><span class="st-muted">${esc(n.status)}</span>`;
      svg.querySelectorAll(".nd").forEach((gEl) => {
        const n = N[+gEl.dataset.i];
        gEl.onmouseenter = (e) => { tip.innerHTML = describe(n); tip.style.display = "block";
          svg.querySelectorAll(".ed").forEach((l) => l.classList.toggle("hot", +l.dataset.a === +gEl.dataset.i || +l.dataset.b === +gEl.dataset.i)); };
        gEl.onmousemove = (e) => { const r = svg.getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 14) + "px"; tip.style.top = (e.clientY - r.top + 10) + "px"; };
        gEl.onmouseleave = () => { tip.style.display = "none"; svg.querySelectorAll(".ed.hot").forEach((l) => l.classList.remove("hot")); };
        gEl.onclick = () => select(n, E.filter((e) => e.a === +gEl.dataset.i || e.b === +gEl.dataset.i).map((e) => ({ ...e, other: N[e.a === +gEl.dataset.i ? e.b : e.a] })));
      });
      evidence("Constellation", `<p>${g.counts.accounts} accounts · ${g.counts.invoices} invoices · ${g.counts.edges} evidence-backed links.</p>
        <table class="st-tbl">${Object.entries(g.legend.edges).map(([k, v]) => `<tr><td><span class="ed-key ed-${k}"></span>${k}</td><td>${esc(v)}</td></tr>`).join("")}</table>
        <p class="st-muted">Account size = net revenue. Ordered like Q5 (net revenue, then account_id).</p>`);
    }

    function select(n, links) {
      const rows = links.map((l) => `<tr><td>${esc(l.type)}</td><td>${esc(l.other.label)}</td><td class="st-muted">${esc(l.evidence)}</td></tr>`).join("");
      if (n.type === "invoice") { st.sel = { invoice: n.ref }; evidence(n.ref, `<p>${esc(n.status)} · ${usd(n.amount_usd)} · ${esc(n.invoice_date)}</p><button class="st-btn" id="go-replay">Open investigation replay →</button><table class="st-tbl">${rows}</table>`);
        $("#go-replay", el).onclick = () => showReplay(n.ref); }
      else if (n.type === "policy") { st.sel = { policy: n.policy_key }; evidence(n.label, `<p>Active: <b>${esc(n.active_value)}</b><br><span class="st-muted">${esc(n.status)}</span></p>
          ${n.policy_key ? `<button class="st-btn" id="go-bf">Open decision impact →</button>` : `<a class="st-btn" href="#/quality">Open reconciliation →</a>`}<table class="st-tbl">${rows}</table>`);
        if (n.policy_key) $("#go-bf", el).onclick = () => showButterfly(n.policy_key); }
      else evidence(n.label, `<p>${n.type === "account" ? `${esc(n.ref)} · ${esc(n.region)} · ${esc(n.plan)} · net ${usd(n.net_revenue_usd, 0)}` : `${(n.ledger_total || 0).toLocaleString()} invoices ledger-wide`}</p><table class="st-tbl">${rows}</table>`);
    }

    /* ---------------- 2. Investigation Replay */
    async function showReplay(id) {
      setTab("replay"); st.sel = { invoice: id };
      main.innerHTML = `<div class="st-filters"><input id="rp-id" value="${esc(id)}" placeholder="INV-100010"><button class="st-btn" id="rp-go">Replay</button>
        <span class="st-muted">try INV-102104 (conflict) · INV-100012 (EUR) · INV-100105 (ambiguous date) · INV-100033 (refund)</span></div><div id="rp-body" class="st-replay"></div>`;
      $("#rp-go", el).onclick = () => showReplay($("#rp-id", el).value.trim());
      $("#rp-id", el).onkeydown = (e) => { if (e.key === "Enter") showReplay(e.target.value.trim()); };
      let r; try { r = await api(`/api/v1/studio/invoices/${encodeURIComponent(id)}/replay`); }
      catch (e) { $("#rp-body", el).innerHTML = `<div class="st-err">${esc(e.message)}</div>`; return; }
      const body = $("#rp-body", el);
      body.innerHTML = `<div class="st-timeline">${r.steps.map((s, i) => `<button class="st-step" data-i="${i}" style="animation-delay:${i * 180}ms"><span class="n">${i + 1}</span><b>${esc(s.step)}</b><small>${esc(s.summary)}</small></button>`).join("")}</div>
        <div class="st-stepdetail" id="rp-detail"></div>
        <div class="st-muted" style="margin-top:10px">evidence hash <code>${r.evidence_hash.slice(0, 16)}…</code> · <a href="#" id="rp-export">export evidence (JSON)</a></div>`;
      const showStep = (i) => { body.querySelectorAll(".st-step").forEach((b, k) => b.classList.toggle("on", k === i)); const s = r.steps[i]; $("#rp-detail", el).innerHTML = renderStep(s); evidence(`${r.invoice_id} · ${s.step}`, `<pre class="st-pre">${esc(JSON.stringify(s.evidence, null, 2))}</pre>`); };
      body.querySelectorAll(".st-step").forEach((b) => b.onclick = () => showStep(+b.dataset.i));
      $("#rp-export", el).onclick = (e) => { e.preventDefault(); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: "application/json" })); a.download = `${r.invoice_id}-evidence.json`; a.click(); };
      for (let i = 0; i < r.steps.length; i++) { showStep(i); if (!el.isConnected || st.view !== "replay") return; await new Promise((res) => setTimeout(res, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 650)); }
      showStep(2);
    }

    function renderStep(s) {
      const e = s.evidence;
      if (s.step === "Imported") return `<table class="st-tbl"><tr><th>raw row</th><th>plan</th><th>amount</th><th>status</th><th>date</th></tr>${e.raw_rows.map((r) => `<tr><td>${r.raw_row_number}</td><td>${esc(r.plan)}</td><td>${esc(r.amount)}</td><td>${esc(r.status)}</td><td>${esc(r.invoice_date)}</td></tr>`).join("")}</table><p class="st-muted">${esc(e.file)} · sha256 ${esc(e.sha256.slice(0, 16))}…</p>`;
      if (s.step === "Normalized") return `<table class="st-tbl"><tr><th>field</th><th>raw</th><th></th><th>clean</th><th>rule</th><th>reproduced</th></tr>${e.map((n) => `<tr><td>${n.field}</td><td class="st-raw">${esc(JSON.stringify(n.raw))}</td><td>→</td><td class="st-clean">${esc(n.clean)}</td><td class="st-muted">${esc(n.rule)}</td><td>${n.reproduced ? "✓" : "✗"}</td></tr>`).join("")}</table>`;
      if (s.step === "Reconciled") return `<p><b>${esc(e.dedup_rule)}</b> · kept raw row ${e.kept_raw_row}</p>${e.conflict ? `<p>Systems said <b>${esc(e.conflict.raw_statuses)}</b> → winner <b>${esc(e.conflict.winner)}</b> by precedence · ${usd(e.conflict.usd_at_stake)} at stake</p>` : ""}
        ${e.rejected.length ? `<table class="st-tbl"><tr><th>rejected raw row</th><th>reason</th><th>status</th></tr>${e.rejected.map((r) => `<tr><td>${r.raw_row_number}</td><td>${esc(r.reason)}</td><td>${esc(r.status)}</td></tr>`).join("")}</table>` : `<p class="st-muted">No duplicate records.</p>`}`;
      if (s.step === "Calculated") return `<p class="st-calc">${esc(e.price_book)}</p><p class="st-calc">MRR ${esc(e.mrr)}</p>
        <table class="st-tbl"><tr><th>FX rule</th><th>USD</th><th>matches price book</th></tr><tr><td>documented (× ${e.fx.rate}) ${e.fx.active_rule === "documented" ? "· active" : ""}</td><td>${usd(e.fx.documented)}</td><td>${e.matches_price_book.documented ? "✓" : "✗"}</td></tr>
        <tr><td>inverse (÷ ${e.fx.rate}) ${e.fx.active_rule === "inverse" ? "· active" : "· proposed, not approved"}</td><td>${usd(e.fx.inverse)}</td><td>${e.matches_price_book.inverse ? "✓" : "✗"}</td></tr></table><p>Counts toward: <b>${e.counts_toward.join(", ")}</b></p>`;
      return `<p>Flags: ${e.dq_flags.length ? e.dq_flags.map((f) => `<span class="st-chip">${esc(f)}</span>`).join(" ") : "none"}</p><p>Discrepancy checks: ${e.discrepancies.length ? e.discrepancies.map((f) => `<span class="st-chip gold">${esc(f)}</span>`).join(" ") : "none"}</p>
        <p>Independent oracle: ${e.oracle ? (e.oracle.agrees ? `<b class="ok">agrees</b> (status ${esc(e.oracle.status)}, ${usd(e.oracle.amount_usd_documented)})` : "<b class='bad'>disagrees</b>") : "n/a"}</p>
        <p>Account snapshot invoice: ${e.is_account_snapshot_invoice ? "yes — this invoice defines the account's plan/region/churn" : "no"} · policy v${esc(e.policy_version)}</p>`;
    }

    /* ---------------- 3. Decision Butterfly */
    async function showButterfly(key) {
      setTab("butterfly"); st.sel = { policy: key };
      main.innerHTML = `<div class="st-filters"><select id="bf-k"><option value="fx_direction">PDR-001 · FX direction</option><option value="account_identity">PDR-002 · Account identity</option></select>
        <a class="st-btn ghost" href="#/decisions">Go to Finance Decisions →</a></div><div id="bf-body"></div>`;
      $("#bf-k", el).value = key; $("#bf-k", el).onchange = (e) => showButterfly(e.target.value);
      let b; try { b = await api(`/api/v1/studio/policies/${key}/impact`); } catch (e) { $("#bf-body", el).innerHTML = `<div class="st-err">${esc(e.message)}</div>`; return; }
      const [L, Rt] = [b.interpretations.find((i) => i.value === b.active_value), b.interpretations.find((i) => i.value !== b.active_value)];
      const fmt = (m, v) => /churn/i.test(m) ? (v * 100).toFixed(2) + "%" : /Accounts/.test(m) ? Math.round(v).toLocaleString() : usd(v, 0);
      const W = 1000, rowH = 46, H = Math.max(L.metrics.length * rowH + 80, 360), cy = H / 2;
      const ys = L.metrics.map((_, i) => 60 + i * rowH);
      const wing = (side, interp) => { const x0 = side < 0 ? 330 : 670, xm = side < 0 ? 170 : 830;
        return interp.metrics.map((m, i) => `<path class="bf-link ${side < 0 ? "cur" : "alt"}" d="M${W / 2},${cy} C${(W / 2 + x0) / 2},${cy} ${x0},${ys[i]} ${xm + (side < 0 ? 110 : -110)},${ys[i]}"/>
          <g class="bf-m" data-side="${side}" data-i="${i}" transform="translate(${xm},${ys[i]})"><rect x="-150" y="-17" width="300" height="34" rx="9" class="${side < 0 ? "cur" : "alt"} ${Math.abs(m.delta) > 1e-6 ? "chg" : ""}"/>
          <text x="-138" y="-1" class="bf-name">${esc(m.metric)}</text><text x="138" y="-1" text-anchor="end" class="bf-val">${fmt(m.metric, m.value)}</text>
          ${side > 0 ? `<text x="138" y="12" text-anchor="end" class="bf-delta">${Math.abs(m.delta) < 1e-6 ? "no change" : (m.delta > 0 ? "+" : "") + fmt(m.metric, m.delta)}</text>` : ""}</g>`).join(""); };
      $("#bf-body", el).innerHTML = `<div class="st-bf-head"><div><span class="st-chip lime">ACTIVE</span> <b>${esc(L.value)}</b><br><span class="st-muted">${esc(L.status)}</span></div>
          <div style="text-align:right"><span class="st-chip gold">${Rt.status.startsWith("proposed — blocked") ? "BLOCKED" : "PROPOSED"}</span> <b>${esc(Rt.value)}</b><br><span class="st-muted">${esc(Rt.status.slice(0, 120))}</span></div></div>
        <svg viewBox="0 0 ${W} ${H}" class="bf-svg"><g transform="translate(${W / 2},${cy})"><circle r="58" class="bf-core"/><text y="-6" text-anchor="middle" class="bf-core-t">${esc(b.record.split("/").pop().slice(0, 7))}</text><text y="14" text-anchor="middle" class="bf-core-s">${esc(key.replace("_", " "))}</text></g>
          ${wing(-1, L)}${wing(1, Rt)}</svg>
        <div class="grid g-2" style="margin-top:8px"><div class="st-card"><b>Top-5 accounts</b> — ${Rt.top5_changed ? "<span class='bad'>changes</span>" : "unchanged"}<div class="st-two"><ol>${L.top5.map((x) => `<li>${esc(x)}</li>`).join("")}</ol><ol>${Rt.top5.map((x) => `<li class="${L.top5.includes(x) ? "" : "new"}">${esc(x)}</li>`).join("")}</ol></div></div>
          <div class="st-card"><b>Not affected</b><ul>${b.unaffected.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>${Rt.top_region ? `<p class="st-muted">Top-MRR region: ${esc(L.top_region)} → ${esc(Rt.top_region)}</p>` : ""}</div></div>`;
      el.querySelectorAll(".bf-m").forEach((g) => g.onclick = () => { const it = (+g.dataset.side < 0 ? L : Rt).metrics[+g.dataset.i];
        evidence(it.metric, `<p>${esc(+g.dataset.side < 0 ? L.value : Rt.value)}: <b>${fmt(it.metric, it.value)}</b></p><p>baseline (${esc(L.value)}): ${fmt(it.metric, it.baseline)}<br>Δ ${fmt(it.metric, it.delta)}</p><p class="st-muted">Computed deterministically in DuckDB from the same cleaned rows (stored ${key === "fx_direction" ? "amount_usd vs amount_usd_alt" : "account_id vs account_name snapshot"}). Policy v${esc(b.policy_version)} remains active until a finance owner approves a change.</p>`); });
      evidence("Decision impact", `<p>${esc(b.record)}</p><p>Left wing: the active interpretation. Right wing: the alternative, with its change against today's numbers. Gold = proposed, never applied from here.</p>`);
    }

    const start = (initial || "").split("=");
    if (start[0] === "invoice") showReplay(start[1]); else if (start[0] === "policy") showButterfly(start[1]); else showGraph();
  };
})();
