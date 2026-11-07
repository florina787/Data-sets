/* CloudNova UI — vanilla JS, no build step. Every chart is drawn from API data (never mock values). */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const usd = (v, d = 0) => v == null ? "—" : (v < 0 ? "-" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const compact = (v) => v == null ? "—" : (v < 0 ? "-" : "") + "$" + Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(Math.abs(v));
const pct = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const num = (v) => v == null ? "—" : Number(v).toLocaleString("en-US");
const C = { indigo: "#5b5bd6", sky: "#4f8ff7", teal: "#19b394", amber: "#f2a93b", rose: "#e5566b", violet: "#9b7bf0", slate: "#9a9db8" };
const PALETTE = [C.indigo, C.sky, C.teal, C.amber, C.violet, C.rose, C.slate];
const charts = [];
let state = { session: localStorage.getItem("cn_session") || null, cache: {} };

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.message || r.statusText), { code: body.code || r.status });
  return body;
}
async function cached(path) { return state.cache[path] ??= await api(path); }
function md(text) {
  return esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^(\d+)\. /gm, "<span class='muted'>$1.</span> ").replace(/^- /gm, "• ").replace(/\n/g, "<br>");
}
function toast(msg) { const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.append(t); setTimeout(() => t.remove(), 3500); }
function killCharts() { while (charts.length) charts.pop().destroy(); }
function chart(canvas, cfg) {
  if (!window.Chart) { canvas.parentElement.innerHTML = "<div class='empty'>Chart library failed to load.</div>"; return; }
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily; Chart.defaults.color = "#5f6385";
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true } } } }, cfg.options || {});
  const c = new Chart(canvas, cfg); charts.push(c); return c;
}
const moneyAxis = { ticks: { callback: (v) => compact(v) }, grid: { color: "#f0eff8" } };
const card = (title, sub, body, extra = "") => `<div class="card ${extra}"><div class="card-head"><h3>${esc(title)}</h3></div><div class="sub">${sub}</div>${body}</div>`;
const table = (cols, rows, fmt = {}) => `<div class="table-wrap"><table><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) =>
  `<tr>${r.map((v, i) => { const f = fmt[cols[i]]; const out = f ? f(v, r) : esc(v ?? "—"); return `<td class="${typeof v === "number" ? "num" : ""}">${out}</td>`; }).join("")}</tr>`).join("")}</tbody></table></div>`;

/* ------------------------------------------------------------ hero: glowing cloud raining data */
function heroCloud(canvas) {
  const ctx = canvas.getContext("2d"); let w, h, raf; const drops = []; const dpr = window.devicePixelRatio || 1;
  const blobs = [[-0.22, 0.02, 0.17], [0, -0.06, 0.24], [0.2, 0.0, 0.18], [-0.08, 0.08, 0.16], [0.1, 0.09, 0.15]];
  function size() { w = canvas.clientWidth; h = canvas.clientHeight; canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); }
  size(); window.addEventListener("resize", size);
  function frame(t) {
    if (!canvas.isConnected) { cancelAnimationFrame(raf); return; }
    ctx.clearRect(0, 0, w, h);
    const cx = w * 0.52, cy = h * 0.34, s = Math.min(w, h * 1.4), bob = Math.sin(t / 1400) * 4;
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    blobs.forEach(([dx, dy, r], i) => {
      const x = cx + dx * s, y = cy + dy * s + bob, R = r * s * (1 + 0.03 * Math.sin(t / 900 + i));
      const g = ctx.createRadialGradient(x - R * 0.3, y - R * 0.3, R * 0.1, x, y, R);
      g.addColorStop(0, i % 2 ? "rgba(255,170,120,.55)" : "rgba(140,180,255,.6)");
      g.addColorStop(0.6, i % 2 ? "rgba(214,92,140,.28)" : "rgba(90,110,240,.3)"); g.addColorStop(1, "rgba(40,40,120,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fill();
    });
    if (drops.length < 90 && Math.random() < 0.6) drops.push({ x: cx + (Math.random() - 0.5) * s * 0.5, y: cy + s * 0.1, v: 0.6 + Math.random() * 1.4, hue: Math.random() < 0.5 ? 210 : 28 });
    for (let i = drops.length - 1; i >= 0; i--) {
      const d = drops[i]; d.y += d.v;
      ctx.strokeStyle = `hsla(${d.hue},95%,72%,.18)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(d.x, d.y - 26); ctx.lineTo(d.x, d.y); ctx.stroke();
      ctx.fillStyle = `hsla(${d.hue},100%,75%,.95)`; ctx.beginPath(); ctx.arc(d.x, d.y, 1.6, 0, Math.PI * 2); ctx.fill();
      if (d.y > h + 10) drops.splice(i, 1);
    }
    ctx.restore(); raf = requestAnimationFrame(frame);
  }
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) raf = requestAnimationFrame(frame); else frame(0);
}

/* ------------------------------------------------------------ pages */
async function pageHome(el) {
  const [k, d] = await Promise.all([cached("/api/v1/kpis"), cached("/api/v1/dashboard")]);
  const kpi = (icon, bg, label, value, def) => `<div class="card kpi"><div class="label"><i style="background:${bg}">${icon}</i>${label}</div><div class="value">${value}</div><div class="def">${esc(def)}</div></div>`;
  el.innerHTML = `
  <div class="grid g-hero">
    <div class="card hero"><canvas id="heroCanvas"></canvas><div class="copy">
      <span class="tag">☁ Track B · spec-driven · local Qwen</span>
      <h1>Revenue answers you can <em>actually trust</em>, in plain English.</h1>
      <p>${num(k.invoices)} cleaned invoices from three disagreeing systems. Every number below comes from an approved SQL metric — and every answer shows its query.</p>
      <button class="btn" onclick="location.hash='#/ask'">Ask CloudNova AI →</button>
      <button class="btn ghost" onclick="location.hash='#/quality'">See the cleaning</button></div></div>
    <div class="card health"><div class="card-head"><h3>Data health</h3><span class="pill ok"><span class="dot"></span>built</span></div>
      <div class="sub">raw ${num(k.manifest.raw_rows)} rows → ${num(k.manifest.clean_invoices)} invoices</div>
      <div class="meter"><i style="width:${(k.manifest.clean_invoices / k.manifest.raw_rows * 100).toFixed(1)}%"></i></div>
      ${Object.entries(k.manifest.rejected_by_reason).map(([r, n], i) => `<div class="legend-row"><span><span class="swatch" style="background:${PALETTE[i]}"></span>${esc(r.replace(/_/g, " "))}</span><b>${num(n)}</b></div>`).join("")}
      <div class="legend-row"><span><span class="swatch" style="background:${C.slate}"></span>status conflicts (audited)</span><b>${num(k.manifest.dedup_conflicts)}</b></div>
      <div class="legend-row"><span>FX rule</span><b>${esc(k.manifest.fx_direction)}</b></div>
      <div class="legend-row"><span>Built</span><b>${esc(k.manifest.built_at.replace("T", " ").slice(0, 16))}</b></div>
    </div>
  </div>
  <div class="section-title">Executive Command Center</div>
  <div class="grid g-4">
    ${kpi("$", "#ecebff", "Paid revenue", compact(k.paid_revenue), k.definitions.paid_revenue)}
    ${kpi("≈", "#e6f0ff", "Net revenue", compact(k.net_revenue), k.definitions.net_revenue)}
    ${kpi("↻", "#e3f7f1", "MRR (active)", compact(k.mrr), k.definitions.mrr)}
    ${kpi("↓", "#fde9ec", "Refunds", compact(k.refunds), k.definitions.refunds)}
    ${kpi("⏳", "#fff4e0", "Pending + failed", compact(k.exposure), `${num(k.exposure_count)} invoices · ${k.definitions.exposure}`)}
    ${kpi("✕", "#fde9ec", "Churn rate", pct(k.churn_rate), k.definitions.churn_rate)}
    ${kpi("◎", "#ecebff", "Active accounts", num(k.active_accounts), `of ${num(k.accounts)} account_ids (latest-invoice snapshot)`)}
    ${kpi("★", "#e3f7f1", "Avg CSAT", k.avg_csat?.toFixed(2), "accounts with a score; blanks never imputed")}
  </div>
  <div class="grid g-21" style="margin-top:14px">
    ${card("Monthly recognized revenue", "paid vs net of refunds · USD · invoices up to today", `<div class="chart-box"><canvas id="cMonthly"></canvas></div>`)}
    ${card("Invoice status mix", "after normalization of 25 raw spellings", `<div class="chart-box"><canvas id="cStatus"></canvas></div>`)}
  </div>`;
  heroCloud($("#heroCanvas"));
  const m = d.monthly.rows;
  chart($("#cMonthly"), { type: "line", data: { labels: m.map((r) => r[0]), datasets: [
    { label: "Paid", data: m.map((r) => r[1]), borderColor: C.indigo, backgroundColor: "rgba(91,91,214,.10)", fill: true, tension: .35, pointRadius: 0 },
    { label: "Net of refunds", data: m.map((r) => r[3]), borderColor: C.teal, tension: .35, pointRadius: 0 }] }, options: { scales: { y: moneyAxis, x: { grid: { display: false } } } } });
  const s = d.status_mix.rows;
  chart($("#cStatus"), { type: "doughnut", data: { labels: s.map((r) => r[0]), datasets: [{ data: s.map((r) => r[1]), backgroundColor: [C.indigo, C.amber, C.rose, C.slate, C.violet], borderWidth: 0 }] }, options: { cutout: "68%" } });
}

async function pageRevenue(el) {
  const d = await cached("/api/v1/dashboard");
  el.innerHTML = `<div class="section-title">Revenue Intelligence</div>
  <div class="grid g-2">
    ${card("Net revenue by region", "paid + refunded (negative), USD", `<div class="chart-box"><canvas id="cRegion"></canvas></div>`)}
    ${card("Net revenue by plan", "Enterprise $299 · Pro $99 · Starter $49 per seat/month", `<div class="chart-box"><canvas id="cPlan"></canvas></div>`)}
    ${card("Refunds & exposure by month", "refunds (negative) vs pending+failed exposure", `<div class="chart-box"><canvas id="cRefund"></canvas></div>`)}
    ${card("Discount tiers on paid invoices", "invoice count and paid revenue per discount %", `<div class="chart-box"><canvas id="cDisc"></canvas></div>`)}
  </div>`;
  const r = d.by_region.rows, p = d.by_plan.rows, m = d.monthly.rows, ds = d.discount.rows;
  chart($("#cRegion"), { type: "bar", data: { labels: r.map((x) => x[0]), datasets: [{ label: "Net revenue", data: r.map((x) => x[1]), backgroundColor: C.indigo, borderRadius: 8 }] }, options: { scales: { y: moneyAxis } } });
  chart($("#cPlan"), { type: "doughnut", data: { labels: p.map((x) => x[0]), datasets: [{ data: p.map((x) => x[1]), backgroundColor: [C.indigo, C.sky, C.teal], borderWidth: 0 }] }, options: { cutout: "62%", plugins: { tooltip: { callbacks: { label: (c) => `${c.label}: ${usd(c.raw)}` } } } } });
  chart($("#cRefund"), { type: "bar", data: { labels: m.map((x) => x[0]), datasets: [
    { label: "Refunds", data: m.map((x) => x[2]), backgroundColor: C.rose, borderRadius: 4 }, { label: "Exposure", data: m.map((x) => x[4]), backgroundColor: C.amber, borderRadius: 4 }] }, options: { scales: { y: moneyAxis, x: { stacked: false } } } });
  chart($("#cDisc"), { type: "bar", data: { labels: ds.map((x) => x[0] + "%"), datasets: [
    { label: "Paid revenue", data: ds.map((x) => x[2]), backgroundColor: C.teal, borderRadius: 8, yAxisID: "y" },
    { label: "Invoices", data: ds.map((x) => x[1]), type: "line", borderColor: C.indigo, yAxisID: "y1", tension: .3 }] }, options: { scales: { y: moneyAxis, y1: { position: "right", grid: { display: false } } } } });
}

async function pageCustomers(el) {
  const d = await cached("/api/v1/dashboard");
  const t = d.top_accounts;
  el.innerHTML = `<div class="section-title">Customer Intelligence</div>
  ${card("Top 10 accounts by net revenue", "ranked by account_id · CSAT ≤ 2 flagged · blank CSAT shown as unknown, never as low",
    table(["Account", "Name", "Region", "Plan", "Net revenue", "CSAT"], t.rows.map((r) => [r[0], r[1], r[2], r[3], r[4], r[5]]),
      { "Net revenue": (v) => usd(v, 2), CSAT: (v) => v == null ? "<span class='muted'>unknown</span>" : v <= 2 ? `<span class="flag">⚠ ${v}</span>` : v }))}
  <div class="grid g-3" style="margin-top:14px">
    ${card("Churn rate by plan", "latest-invoice snapshot; no churn dates exist", `<div class="chart-box"><canvas id="cChurn"></canvas></div>`)}
    ${card("Average MRR by region", "active accounts · list × seats × (1 − discount)", `<div class="chart-box"><canvas id="cMrr"></canvas></div>`)}
    ${card("CSAT vs churn", "accounts per CSAT score and their churn rate", `<div class="chart-box"><canvas id="cCsat"></canvas></div>`)}
  </div>`;
  const ch = d.churn_by_plan.rows, mr = d.mrr_by_region.rows, cs = d.csat_dist.rows;
  chart($("#cChurn"), { type: "bar", data: { labels: ch.map((x) => x[0]), datasets: [{ label: "Churn rate", data: ch.map((x) => x[1]), backgroundColor: [C.rose, C.amber, C.sky], borderRadius: 8 }] }, options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (v) => pct(v) } } } } });
  chart($("#cMrr"), { type: "bar", data: { labels: mr.map((x) => x[0]), datasets: [{ label: "Avg MRR", data: mr.map((x) => x[1]), backgroundColor: C.indigo, borderRadius: 8 }] }, options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: moneyAxis } } });
  chart($("#cCsat"), { type: "bar", data: { labels: cs.map((x) => x[0]), datasets: [{ label: "Accounts", data: cs.map((x) => x[1]), backgroundColor: C.sky, borderRadius: 6, yAxisID: "y" },
    { label: "Churn rate", data: cs.map((x) => x[2]), type: "line", borderColor: C.rose, yAxisID: "y1" }] }, options: { scales: { y1: { position: "right", ticks: { callback: (v) => pct(v) }, grid: { display: false } } } } });
}

async function pageQuality(el) {
  const [q, rc] = await Promise.all([cached("/api/v1/data-quality"), cached("/api/v1/reconciliation")]);
  const m = q.manifest, im = rc.impact;
  const colors = { "Raw export rows": C.indigo, "exact duplicate": C.rose, "synonym duplicate": C.amber, "lost conflict": C.violet, "Clean invoices": C.teal };
  let run = 0; const bars = rc.waterfall.map((s) => { if (s.kind === "total") { run = s.rows; return [0, s.rows]; } const a = run; run += s.rows; return [run, a]; });
  el.innerHTML = `<div class="section-title">Reconciliation · where did ${num(rc.raw_rows)} rows go?</div>
  <div class="grid g-21">
    ${card(`${num(rc.raw_rows)} raw rows → ${num(rc.clean_invoices)} invoices + ${num(rc.rejected_rows)} audited`, "click a bar to see why those rows were removed and what keeping them would have done to revenue",
      `<div class="chart-box"><canvas id="cWaterfall"></canvas></div><div id="wfInfo" class="sub" style="margin-top:10px;min-height:36px">Every raw row lands in exactly one place: <code>invoices</code> or <code>rejected_rows</code> (with its full raw record). Nothing is silently dropped.</div>`)}
    ${card("Financial impact of deduplication", "same normalized rows summed without dedup (naive) vs one row per invoice (clean)",
      table(["Metric", "Naive", "Clean", "Avoided"], [
        ["Paid revenue", im.paid_revenue.naive_no_dedup, im.paid_revenue.clean, im.paid_revenue.overstatement_avoided],
        ["Net revenue", im.net_revenue.naive_no_dedup, im.net_revenue.clean, im.net_revenue.overstatement_avoided],
        ["Pending + failed exposure", im.exposure.naive_no_dedup, im.exposure.clean, im.exposure.overstatement_avoided]],
        { Naive: (v) => usd(v), Clean: (v) => usd(v), Avoided: (v) => `<b>${usd(v)}</b>` }) +
      `<p class="sub" style="margin-top:12px">Status conflicts: if every losing record had won instead, net revenue would move by <b>${usd(rc.conflicts.net_revenue_swing_if_all_losers_won)}</b> across ${rc.conflicts.count} invoices — the size of the decision the billing owner must confirm.</p>`)}
  </div>
  <div style="margin-top:14px">${card("Status conflicts — which record won, and what if the other one was right", "precedence refunded > paid > failed > void > pending (data contract §3)",
    table(["Invoice", "Raw statuses", "Winner", "Loser", "Amount (USD)", "Δ net revenue if loser won"], rc.conflicts.rows.map((r) => [r.invoice_id, r.raw_statuses, r.winner, r.loser, r.amount_usd, r.net_revenue_delta_if_loser_won]),
      { "Amount (USD)": (v) => usd(v, 2), "Δ net revenue if loser won": (v) => v ? `<span class="flag">${usd(v, 2)}</span>` : "<span class='muted'>no change</span>" }))}</div>
  <div class="section-title">Data Quality Studio</div>
  <div class="grid g-21">
    ${card("Issues found and what we did", "every flag is stored on the row (<code>dq_flags</code>); nothing is imputed", table(q.issues.columns, q.issues.rows))}
    ${card("Open question: FX direction", "paid invoices · documented rule (× rate) vs inverse (÷ rate)",
      table(["Currency", "Invoices", "Local", "USD (documented)", "USD (inverse)"], q.fx.rows, { Local: (v) => num(Math.round(v)), "USD (documented)": (v) => usd(v), "USD (inverse)": (v) => usd(v) }) +
      `<p class="sub" style="margin-top:10px">Every EUR/GBP amount equals the USD list price × the rate, so the documented conversion may apply FX twice. Kept the documented rule; flagged for the finance lead. Raw file sha256 ${esc(m.raw_sha256.slice(0, 12))}…</p>`)}
  </div>`;
  const byReason = Object.fromEntries(rc.by_reason.map((r) => [r.reason.replace(/_/g, " "), r]));
  chart($("#cWaterfall"), { type: "bar", data: { labels: rc.waterfall.map((s) => s.label), datasets: [{ data: bars, backgroundColor: rc.waterfall.map((s) => colors[s.label] || C.slate), borderRadius: 8, borderSkipped: false }] },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${num(rc.waterfall[c.dataIndex].rows)} rows` } } },
      scales: { y: { min: 4800, title: { display: true, text: "rows (axis starts at 4,800)" } } },
      onClick: (_, els) => { if (!els.length) return; const s = rc.waterfall[els[0].index], r = byReason[s.label];
        $("#wfInfo").innerHTML = r ? `<b>${num(r.rows)} ${esc(s.label)} rows</b> (${num(r.invoice_ids)} invoice ids) — ${esc(r.explanation)} Keeping them would have added <b>${usd(r.paid_usd)}</b> paid revenue, ${usd(r.refunded_usd)} refunds and ${usd(r.exposure_usd)} pending/failed exposure.`
          : `<b>${esc(s.label)}: ${num(s.rows)}</b>`; } } });
}

async function pageTower(el) {
  const t = await api("/api/v1/traces");
  const ev = t.evals;
  el.innerHTML = `<div class="section-title">Agent Control Tower</div>
  <div class="grid g-4">
    <div class="card kpi"><div class="label">Local model</div><div class="value" style="font-size:16px">${esc(t.llm.model || "none")}</div><div class="def">${t.llm.reachable ? "<span class='pill ok'><span class='dot'></span>reachable</span>" : "<span class='pill off'><span class='dot'></span>offline — analytics still work</span>"} ${esc(t.llm.base_url || "")}</div></div>
    <div class="card kpi"><div class="label">Requests (recent)</div><div class="value">${num(t.summary.requests)}</div><div class="def">${num(t.summary.ok)} ok · ${num(t.summary.failed)} failed · avg ${t.summary.avg_total_ms ?? "—"} ms</div></div>
    <div class="card kpi"><div class="label">Planner mix</div><div class="value" style="font-size:16px">${Object.entries(t.summary.by_planner).map(([k, v]) => `${k} ${v}`).join(" · ")}</div><div class="def">semantic = approved metrics · llm_sql = Qwen-written SQL</div></div>
    <div class="card kpi"><div class="label">Eval suite</div><div class="value">${ev ? `${ev.counts.PASS}/${ev.counts.PASS + ev.counts.FAIL}` : "—"}</div><div class="def">${ev ? `XFAIL ${ev.counts.XFAIL} · SKIP ${ev.counts.SKIP} · ${esc(ev.run_at)}` : "run python -m evals"}</div></div>
  </div>
  <div class="grid g-2" style="margin-top:14px">
    ${card("Execution graph", "selected run · drag to pan · wheel to zoom · click a node for details", `<svg class="graph" id="graph"></svg><div id="nodeInfo" class="sub" style="margin-top:8px"></div>`)}
    ${card("Recent runs", "click a row to inspect its trace", t.runs.length ? `<div class="table-wrap"><table><thead><tr><th>Question</th><th>Intent</th><th>Planner</th><th>Status</th><th>ms</th></tr></thead><tbody>${t.runs.map((r, i) =>
      `<tr data-i="${i}" style="cursor:pointer"><td>${esc(r.question.slice(0, 60))}</td><td>${esc(r.intent)}</td><td>${esc(r.planner)}</td><td>${r.status === "ok" ? "ok" : `<span class="flag">${esc(r.status)}</span>`}</td><td class="num">${Math.round(r.total_ms)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">No runs yet — ask a question.</div>`)}
  </div>
  ${ev ? `<div style="margin-top:14px">${card("Latest evaluation results", "python -m evals · expected answers from an independent oracle", table(["Case", "Category", "Result", "ms", "Detail"], ev.results.map((r) => [r.id, r.category, r.status, r.ms, r.detail.slice(0, 140)]),
    { Result: (v) => v === "PASS" ? `<span class="chip">PASS</span>` : v === "XFAIL" ? `<span class="chip warn">XFAIL</span>` : v === "SKIP" ? `<span class="chip">SKIP</span>` : `<span class="chip err">${v}</span>` }))}</div>` : ""}`;
  const draw = (run) => drawGraph($("#graph"), run);
  if (t.runs.length) draw(t.runs[0]);
  el.querySelectorAll("tr[data-i]").forEach((tr) => tr.onclick = () => draw(t.runs[+tr.dataset.i]));
}

function drawGraph(svg, run) {
  if (!run) return;
  const steps = [{ step: "question", detail: run.question, status: "ok", ms: 0 }, ...run.trace, { step: "answer", detail: `${run.intent} · ${run.planner}`, status: run.status === "ok" ? "ok" : "error", ms: run.total_ms }];
  const W = 190, H = 54, gapX = 40, perRow = 3;
  const nodes = steps.map((s, i) => { const row = Math.floor(i / perRow), col = row % 2 ? perRow - 1 - (i % perRow) : i % perRow; return { ...s, x: 20 + col * (W + gapX), y: 20 + row * (H + 46) }; });
  const color = (s) => s.status === "error" ? C.rose : s.status === "flagged" || s.status === "denied" ? C.amber : s.step === "tool" ? C.indigo : s.step === "route" ? C.sky : C.teal;
  const label = (s) => s.step === "tool" ? s.tool : s.step;
  let edges = "";
  for (let i = 1; i < nodes.length; i++) { const a = nodes[i - 1], b = nodes[i]; edges += `<path d="M${a.x + W / 2},${a.y + H / 2} L${b.x + W / 2},${b.y + H / 2}" stroke="#c9c7ee" stroke-width="2" marker-end="url(#arr)"/>`; }
  svg.innerHTML = `<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="#b9b6ec"/></marker></defs><g id="vp">${edges}${nodes.map((n, i) =>
    `<g class="node" data-i="${i}" style="cursor:pointer"><rect x="${n.x}" y="${n.y}" width="${W}" height="${H}" rx="12" fill="#fff" stroke="${color(n)}" stroke-width="2"/>
     <circle cx="${n.x + 16}" cy="${n.y + 18}" r="5" fill="${color(n)}"/><text x="${n.x + 28}" y="${n.y + 22}" font-weight="700" fill="#171a33">${esc(label(n))}</text>
     <text x="${n.x + 12}" y="${n.y + 41}" fill="#5f6385">${esc((n.agent ? n.agent + " · " : "") + (n.ms ? Math.round(n.ms) + " ms" : n.status))}</text></g>`).join("")}</g>`;
  const rows = Math.ceil(nodes.length / perRow);
  let vb = { x: 0, y: 0, w: perRow * (W + gapX) + 20, h: rows * (H + 46) + 20 };
  const apply = () => svg.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); apply();
  svg.onwheel = (e) => { e.preventDefault(); const k = e.deltaY > 0 ? 1.1 : 0.9; vb = { ...vb, w: vb.w * k, h: vb.h * k }; apply(); };
  let drag = null;
  svg.onmousedown = (e) => drag = { x: e.clientX, y: e.clientY, vb: { ...vb } };
  window.onmouseup = () => drag = null;
  svg.onmousemove = (e) => { if (!drag) return; const s = vb.w / svg.clientWidth; vb.x = drag.vb.x - (e.clientX - drag.x) * s; vb.y = drag.vb.y - (e.clientY - drag.y) * s; apply(); };
  svg.querySelectorAll(".node").forEach((g) => g.onclick = () => { const n = nodes[+g.dataset.i]; $("#nodeInfo").innerHTML = `<b>${esc(label(n))}</b> — ${esc(n.detail || "")}`; });
}

/* ------------------------------------------------------------ chat */
async function pageAsk(el, initial) {
  el.innerHTML = `<div class="chat">
    <div class="card thread"><div class="msgs" id="msgs"></div>
      <form class="composer" id="composer"><textarea id="q" placeholder="Ask anything — “Which region has the highest average MRR per account?”, “only Enterprise”, “explain the calculation”…"></textarea>
      <button class="btn">Ask</button></form></div>
    <aside class="card"><div class="card-head"><h3>Conversation</h3><button class="btn sm light" id="newChat">New</button></div>
      <div class="sub" id="sid"></div>
      <div class="section-title" style="margin-top:8px">Stakeholder questions</div>
      ${["What was our total recognized revenue in USD for paid invoices in 2024?", "Which region has the highest average MRR per account?", "How much have we given back in refunds?",
        "What's the churn rate among Enterprise accounts vs Starter?", "List the top 5 accounts by revenue, and flag any with CSAT ≤ 2.", "How many invoices are stuck in pending/failed and what's the exposed $?"]
        .map((q) => `<div class="history-item" data-q="${esc(q)}">${esc(q)}</div>`).join("")}
      <div class="section-title">This conversation</div><div id="hist"></div></aside></div>`;
  const msgs = $("#msgs");
  const renderSid = () => $("#sid").textContent = state.session ? `session ${state.session}` : "new session";
  renderSid();
  async function loadHistory() {
    if (!state.session) { msgs.innerHTML = `<div class="empty">Ask a question about CloudNova's revenue, MRR, churn, refunds or data quality.<br>Answers come from SQL over the cleaned data — the query is always shown.</div>`; $("#hist").innerHTML = ""; return; }
    const h = await api(`/api/v1/sessions/${state.session}`);
    $("#hist").innerHTML = h.turns.map((t) => `<div class="history-item" data-q="${esc(t.question)}">${esc(t.question)}</div>`).join("") || "<div class='muted'>—</div>";
  }
  await loadHistory();
  if (!state.session) msgs.innerHTML = msgs.innerHTML;
  el.querySelectorAll("aside").forEach((a) => a.onclick = (e) => { const q = e.target.closest("[data-q]"); if (q) send(q.dataset.q); });
  $("#newChat").onclick = async () => { if (state.session) await api(`/api/v1/sessions/${state.session}`, { method: "DELETE" }).catch(() => {}); state.session = null; localStorage.removeItem("cn_session"); msgs.innerHTML = ""; renderSid(); loadHistory(); };
  const form = $("#composer"), ta = $("#q");
  ta.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } };
  form.onsubmit = (e) => { e.preventDefault(); const q = ta.value.trim(); if (q) { ta.value = ""; send(q); } };
  async function send(q) {
    if (msgs.querySelector(".empty")) msgs.innerHTML = "";
    msgs.insertAdjacentHTML("beforeend", `<div class="msg user"><div class="bubble">${esc(q)}</div></div>`);
    const pending = document.createElement("div"); pending.className = "msg bot";
    pending.innerHTML = `<div class="bubble"><span class="typing"><i></i><i></i><i></i></span> <span class="muted">thinking — Qwen-backed steps can take ~10–30 s on CPU</span></div>`;
    msgs.append(pending); msgs.scrollTop = msgs.scrollHeight;
    try {
      const r = await api("/api/v1/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q, session_id: state.session }) });
      state.session = r.session_id; localStorage.setItem("cn_session", r.session_id); renderSid();
      pending.innerHTML = renderAnswer(r); bindAnswer(pending, r, send); loadHistory();
    } catch (err) {
      pending.innerHTML = `<div class="bubble"><span class="chip err">${esc(err.code)}</span> ${esc(err.message)}</div>`;
    }
    msgs.scrollTop = msgs.scrollHeight;
  }
  if (initial) send(initial);
}

function renderAnswer(r) {
  const res = r.result;
  const chips = [`<span class="chip">${esc(r.intent)}</span>`, r.planner !== "none" ? `<span class="chip">${r.planner === "semantic" ? "approved metric" : "Qwen SQL"}</span>` : "",
    r.llm.used ? `<span class="chip qwen">${esc(r.llm.model)} · ${Math.round(r.llm.latency_ms)} ms</span>` : "", `<span class="chip">${Math.round(r.latency_ms)} ms</span>`].join("");
  return `<div class="bubble">${md(r.answer)}
    ${r.chart && res && res.rows.length > 1 ? `<div class="chart-box" style="height:220px;margin-top:12px"><canvas></canvas></div>` : ""}
    ${(r.caveats || []).map((c) => `<div class="caveat">⚠ ${esc(c)}</div>`).join("")}
    <div class="meta">${chips}</div>
    ${r.sql ? `<details open><summary>Generated SQL (executed read-only)</summary><pre class="sql">${esc(r.sql)}</pre></details>` : ""}
    ${res && res.rows.length ? `<details><summary>Result rows (${res.row_count}${res.truncated ? "+, truncated" : ""})</summary>${table(res.columns, res.rows.slice(0, 50), {})}</details>` : ""}
    ${r.metric_definitions?.length ? `<details><summary>Metric definitions</summary>${r.metric_definitions.map((d) => `<p><b>${esc(d.label)}</b> — ${esc(d.definition)}<br><code>${esc(d.sql)}</code></p>`).join("")}</details>` : ""}
    <details><summary>Agent trace (${r.trace.length} steps)</summary>${r.trace.map((t) => `<div class="sub" style="margin:4px 0">${t.status !== "ok" ? `<span class="chip ${t.status === "error" ? "err" : "warn"}">${esc(t.status)}</span> ` : ""}<b>${esc(t.tool || t.step)}</b> ${esc(t.detail)} ${t.ms ? `· ${t.ms} ms` : ""}</div>`).join("")}</details>
    ${r.suggestions?.length ? `<div class="suggest">${r.suggestions.map((s) => `<button data-s="${esc(s)}">${esc(s)}</button>`).join("")}</div>` : ""}</div>`;
}

function bindAnswer(node, r, send) {
  node.querySelectorAll("[data-s]").forEach((b) => b.onclick = () => send(b.dataset.s));
  const cv = node.querySelector("canvas");
  if (!cv) return;
  const cols = r.result.columns, rows = r.result.rows.slice(0, 24);
  const xi = cols.indexOf(r.chart.x) >= 0 ? cols.indexOf(r.chart.x) : 0;
  const ys = (r.chart.y || []).map((y) => cols.indexOf(y)).filter((i) => i >= 0);
  const isMoney = r.chart.unit === "usd";
  chart(cv, { type: r.chart.type === "line" ? "line" : "bar", data: { labels: rows.map((x) => x[xi] ?? "(blank)"),
    datasets: ys.map((i, k) => ({ label: cols[i], data: rows.map((x) => x[i]), backgroundColor: PALETTE[k], borderColor: PALETTE[k], borderRadius: 6, tension: .3, pointRadius: 0 })) },
    options: { indexAxis: r.chart.type === "bar_h" ? "y" : "x", scales: isMoney ? { [r.chart.type === "bar_h" ? "x" : "y"]: moneyAxis } : {} } });
}


/* ------------------------------------------------------------ enhancements */
const KIND_LABEL = { rule_violation: "rule violation", decision_required: "decision required", needs_investigation: "needs investigation", needs_policy: "needs policy", control_passed: "control passed" };
async function pageLeakage(el) {
  const d = await api("/api/v1/leakage/findings");
  el.innerHTML = `<div class="section-title">Revenue Leakage Investigator</div>
  <div class="banner">${esc(d.summary.note)}</div>
  <div class="grid g-2">${d.findings.map((f) => `
    <div class="card finding ${f.kind}">
      <div class="card-head"><h3>${esc(f.title)}</h3><span class="kind">${esc(KIND_LABEL[f.kind])}</span></div>
      <div class="sub">rule: ${esc(f.rule)}</div>
      <div style="display:flex;gap:24px;margin:6px 0 10px"><div class="money">${num(f.count)}<small>invoices</small></div>
        <div class="money">${usd(f.exposure_usd)}<small>at stake — not a confirmed loss</small></div></div>
      <div style="font-size:12.5px;line-height:1.5">${esc(f.summary)}<br><span class="muted">${esc(f.why)}</span></div>
      ${f.sample_invoice_ids.length ? `<div class="sub" style="margin-top:8px">evidence: ${f.sample_invoice_ids.map(esc).join(", ")}${f.count > f.sample_invoice_ids.length ? " …" : ""}</div>` : ""}
      ${f.evidence_extra ? `<div class="sub">${esc(JSON.stringify(f.evidence_extra))}</div>` : ""}
      <details><summary>SQL</summary><pre class="sql">${esc(f.sql)}</pre></details>
      <div style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12px">investigation
        <select data-id="${f.id}">${["open", "investigating", "resolved", "dismissed"].map((s) => `<option ${s === f.investigation.status ? "selected" : ""}>${s}</option>`).join("")}</select>
        <span class="muted">${f.investigation.note ? esc(f.investigation.note) : ""}</span></div>
    </div>`).join("")}</div>`;
  el.querySelectorAll("select[data-id]").forEach((sel) => sel.onchange = async () => {
    try { await api(`/api/v1/leakage/findings/${sel.dataset.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: sel.value, note: "" }) }); toast(`Marked ${sel.value} (ledger unchanged)`); }
    catch (e) { toast(e.message); } });
}

async function pageSimulator(el) {
  const plans = ["Starter", "Pro", "Enterprise"], base = { Starter: 49, Pro: 99, Enterprise: 299 };
  const st = { price: { ...base }, seats: 0, disc: null, churn: 0 };
  el.innerHTML = `<div class="section-title">Financial Digital Twin · What-if Simulator</div>
  <div class="banner"><b>Hypothetical.</b> Scenarios are computed in memory from the observed active-account snapshot. They are not forecasts and never change the ledger.</div>
  <div class="grid g-2">
    <div class="card"><h3>Assumptions</h3><div class="sub">observed baseline = list price × seats × (1 − discount) for active accounts</div>
      ${plans.map((p) => `<div class="slider-row"><span>${p} list price</span><input type="range" min="0" max="${base[p] * 2}" value="${base[p]}" data-price="${p}"><b id="pv-${p}">$${base[p]}</b></div>`).join("")}
      <div class="slider-row"><span>Seats (all plans)</span><input type="range" min="-50" max="100" value="0" id="seats"><b id="sv">0%</b></div>
      <div class="slider-row"><span>Discount override</span><input type="range" min="-1" max="40" value="-1" id="disc"><b id="dv">observed</b></div>
      <div class="slider-row"><span>Assumed churn</span><input type="range" min="0" max="50" value="0" id="churn"><b id="cv">0%</b></div>
      <button class="btn light sm" id="reset">Reset to observed</button></div>
    <div class="card"><h3>Observed vs hypothetical</h3><div class="sub" id="label"></div><div id="simOut"></div></div>
  </div>
  <div style="margin-top:14px">${card("MRR by plan", "observed (solid) vs hypothetical (light)", `<div class="chart-box"><canvas id="cSim"></canvas></div>`)}</div>
  <div class="sub" id="method" style="margin-top:10px"></div>`;
  let timer, ch;
  async function run() {
    const body = { list_price_usd: st.price, seat_change_pct: { all: st.seats }, assumed_churn_pct: st.churn };
    if (st.disc !== null) body.discount_pct = { all: st.disc };
    let r; try { r = await api("/api/v1/simulator/scenarios", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); } catch (e) { toast(e.message); return; }
    $("#label").textContent = r.label;
    const row = (k, l, f) => `<tr><td>${l}</td><td class="num">${f(r.observed[k])}</td><td class="num">${f(r.hypothetical[k])}</td><td class="num ${r.delta[k] < 0 ? "flag" : ""}">${r.delta[k] >= 0 ? "+" : ""}${f(r.delta[k])}</td></tr>`;
    $("#simOut").innerHTML = `<table><thead><tr><th></th><th>Observed</th><th>Hypothetical</th><th>Δ</th></tr></thead><tbody>
      ${row("mrr", "MRR", (v) => usd(v))}${row("arr", "ARR (MRR × 12)", (v) => usd(v))}${row("billings_12m", "12-mo billings (annual = 10 mo)", (v) => usd(v))}
      ${row("accounts", "Active accounts", (v) => num(Math.round(v)))}${row("seats", "Seats", (v) => num(Math.round(v)))}</tbody></table>`;
    $("#method").textContent = "Method: " + Object.entries(r.method).map(([k, v]) => `${k}: ${v}`).join(" · ");
    const data = { labels: r.by_plan.map((p) => p.plan), datasets: [
      { label: "Observed MRR", data: r.by_plan.map((p) => p.observed.mrr), backgroundColor: C.indigo, borderRadius: 6 },
      { label: "Hypothetical MRR", data: r.by_plan.map((p) => p.hypothetical.mrr), backgroundColor: "rgba(91,91,214,.3)", borderRadius: 6 }] };
    if (ch) { ch.data = data; ch.update(); } else ch = chart($("#cSim"), { type: "bar", data, options: { scales: { y: moneyAxis } } });
  }
  const later = () => { clearTimeout(timer); timer = setTimeout(run, 150); };
  el.querySelectorAll("[data-price]").forEach((i) => i.oninput = () => { st.price[i.dataset.price] = +i.value; $(`#pv-${i.dataset.price}`).textContent = "$" + i.value; later(); });
  $("#seats").oninput = (e) => { st.seats = +e.target.value; $("#sv").textContent = st.seats + "%"; later(); };
  $("#disc").oninput = (e) => { const v = +e.target.value; st.disc = v < 0 ? null : v; $("#dv").textContent = v < 0 ? "observed" : v + "%"; later(); };
  $("#churn").oninput = (e) => { st.churn = +e.target.value; $("#cv").textContent = st.churn + "%"; later(); };
  $("#reset").onclick = () => route();
  run();
}

async function pageIntegrations(el) {
  const p = await api("/api/v1/integrations/legacy-billing/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const pv = p.provenance;
  el.innerHTML = `<div class="section-title">Enterprise Integration · simulated legacy billing system</div>
  <div class="card console">
    <div class="card-head"><h3>legacy_billing_v1 → raw contract → same cleaning rules → preview</h3><span class="pill ok"><span class="dot"></span>read-only</span></div>
    <div class="sub">${esc(p.mode)} · file ${esc(pv.file)} · sha256 ${esc(pv.sha256.slice(0, 12))}… · control total ${p.control_total.matches ? "✓" : "✗"} (${p.control_total.declared_records} declared / ${p.control_total.actual_records} actual)</div>
    <div class="pipe"><div class="node"><b>SOURCE</b>${num(pv.rows_in_file)} legacy rows</div><span class="arrow">→</span>
      <div class="node"><b>MAPPING</b>${num(pv.rows_mapped)} mapped · ${num(pv.rows_rejected_at_mapping)} rejected</div><span class="arrow">→</span>
      <div class="node"><b>PIPELINE RULES</b>${num(p.cleaned.length)} clean · ${num(p.rejected_by_pipeline.length)} dedup-rejected</div><span class="arrow">→</span>
      <div class="node"><b>FLAGS</b>${Object.entries(p.flags_summary).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "none"}</div><span class="arrow">→</span>
      <div class="node"><b>LEDGER</b>not written (approval step not built)</div></div>
  </div>
  <div class="grid g-2" style="margin-top:14px">
    <div class="card console"><h3>Schema mapping</h3><div class="sub">app/sources/mappings/legacy_billing.yaml</div>
      ${table(["Raw contract", "Legacy column"], Object.entries(p.mapping.columns))}</div>
    <div class="card console"><h3>Rejected with reasons</h3><div class="sub">validation at mapping, then the ledger's own dedup rule</div>
      ${table(["Line", "Reason"], [...p.rejected_at_mapping.map((r) => [r.source_line, r.reason]), ...p.rejected_by_pipeline.map((r) => [r.source_line, `${r.invoice_id}: ${r.reason}`])])}</div>
  </div>
  <div style="margin-top:14px" class="card console"><h3>Cleaned preview with lineage</h3><div class="sub">every row keeps source system, file, line and file hash</div>
    ${table(["Invoice", "Plan", "Cycle", "Seats", "Ccy", "Amount USD", "Expected USD", "Status", "Flags", "Source line"],
      p.cleaned.map((r) => [r.invoice_id, r.plan, r.billing_cycle, r.seats, r.currency, r.amount_usd, r.expected_amount_usd, r.status, r.dq_flags || "—", r.lineage.source_line]),
      { "Amount USD": (v) => usd(v, 2), "Expected USD": (v) => usd(v, 2), Flags: (v) => v.includes("pricing_violation") ? `<span class="flag">${esc(v)}</span>` : esc(v) })}</div>`;
}

/* ------------------------------------------------------------ router + chrome */
const PAGES = { "": pageHome, ask: pageAsk, revenue: pageRevenue, customers: pageCustomers, quality: pageQuality, tower: pageTower, leakage: pageLeakage, simulator: pageSimulator, integrations: pageIntegrations };
async function route() {
  const [name, ...rest] = location.hash.replace(/^#\/?/, "").split("?");
  const key = PAGES[name] ? name : "";
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", (a.dataset.page === "home" ? "" : a.dataset.page) === key));
  killCharts();
  const el = $("#page"); el.innerHTML = `<div class="empty">Loading…</div>`;
  try { await PAGES[key](el, new URLSearchParams(rest.join("?")).get("q")); }
  catch (e) { el.innerHTML = `<div class="card"><span class="chip err">${esc(e.code || "error")}</span> ${esc(e.message)}</div>`; }
}
$("#topAsk").onsubmit = (e) => { e.preventDefault(); const q = $("#topInput").value.trim(); if (!q) return; $("#topInput").value = ""; location.hash = "#/ask?q=" + encodeURIComponent(q); };
window.addEventListener("hashchange", route);
(async function chrome() {
  const img = new Image(); img.onload = () => { const w = $("#watermark"); w.classList.add("has-image"); w.style.setProperty("--wm", "url(/static/brand/background.png)"); }; img.src = "/static/brand/background.png";
  try {
    const h = await api("/api/v1/health"); const k = await cached("/api/v1/kpis");
    $("#railBar").style.width = (k.manifest.clean_invoices / k.manifest.raw_rows * 100).toFixed(1) + "%";
    $("#railRows").textContent = `${num(k.manifest.clean_invoices)} / ${num(k.manifest.raw_rows)} rows`;
    $("#railPct").textContent = `${k.manifest.rejected_rows} audited`;
    $("#railLlm").innerHTML = h.llm.reachable ? `<span class="pill ok"><span class="dot"></span>${esc(h.llm.model)}</span>` : `<span class="pill off"><span class="dot"></span>Qwen offline</span>`;
  } catch (e) { toast("API not reachable: " + e.message); }
})();
route();
