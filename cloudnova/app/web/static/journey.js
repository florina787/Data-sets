/* Nova's Guided Journey + Decisions page. Loaded before app.js; registers window.pageJourney / window.pageDecisions.
   Nova only reflects what the engine recorded: narration comes from /api/v1/journey, scene 5 moves on real /ask trace
   events, scene 6 waits for a real decision. She never blocks a click (pointer-events: none). */
"use strict";
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const usd = (v, d = 2) => v == null ? "—" : (v < 0 ? "-" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const num = (v) => v == null ? "—" : Number(v).toLocaleString("en-US");
  const POSES = ["idle", "walk", "turn", "point", "think", "work", "success", "warn", "wait", "error"];
  const POSE_LABEL = { idle: "Idle", walkL: "Walking left", walkR: "Walking right", turn: "Turning", point: "Pointing", think: "Thinking", work: "Working", success: "Success", warn: "Warning", wait: "Waiting for approval", error: "Error" };

  /* ---------- Nova: one SVG rig (jointed shoulders + hips), poses are CSS states — identity cannot drift between scenes */
  function novaSVG() {
    return `<svg viewBox="0 0 80 160" aria-hidden="true">
      <ellipse cx="40" cy="155" rx="20" ry="3.5" fill="rgba(23,26,51,.15)"/>
      <g class="g-leg l"><rect x="31" y="104" width="7" height="44" rx="3" fill="#2b2f6b"/><rect x="28" y="145" width="11" height="6" rx="3" fill="#171a33"/></g>
      <g class="g-leg r"><rect x="42" y="104" width="7" height="44" rx="3" fill="#2b2f6b"/><rect x="41" y="145" width="11" height="6" rx="3" fill="#171a33"/></g>
      <path d="M29 22 C16 30 18 70 22 86 L58 86 C62 70 64 30 51 22 Z" fill="#2a1d1a"/>
      <path d="M27 60 L53 60 L60 110 L20 110 Z" fill="#5b5bd6"/>
      <path d="M27 60 L53 60 L54 70 L26 70 Z" fill="#4949c4"/>
      <g transform="translate(34 78)"><circle cx="4" cy="6" r="3.2" fill="#cfe0ff"/><circle cx="8" cy="4" r="4" fill="#e4eeff"/><circle cx="12" cy="6.5" r="3" fill="#cfe0ff"/></g>
      <g class="g-arm l"><rect x="22" y="61" width="7" height="34" rx="3.5" fill="#f2c7a5"/><rect x="21" y="60" width="9" height="12" rx="4" fill="#5b5bd6"/></g>
      <g class="g-arm r"><rect x="51" y="61" width="7" height="34" rx="3.5" fill="#f2c7a5"/><rect x="50" y="60" width="9" height="12" rx="4" fill="#5b5bd6"/></g>
      <rect x="36" y="49" width="8" height="12" rx="3" fill="#f2c7a5"/>
      <g class="g-head"><circle cx="40" cy="36" r="15" fill="#f6d0b1"/>
        <path d="M24 37 C22 20 34 16 41 17 C52 17 58 25 56 37 C52 28 44 25 36 27 C31 28 27 31 24 37 Z" fill="#2a1d1a"/>
        <circle cx="34.5" cy="38" r="1.7" fill="#171a33"/><circle cx="45.5" cy="38" r="1.7" fill="#171a33"/>
        <path d="M36 44 Q40 47 44 44" stroke="#b3524a" stroke-width="1.6" fill="none" stroke-linecap="round"/>
        <circle cx="31.5" cy="42" r="2" fill="#f4a9a0" opacity=".6"/><circle cx="48.5" cy="42" r="2" fill="#f4a9a0" opacity=".6"/></g>
      <g class="g-prop p-laptop"><rect x="26" y="84" width="28" height="16" rx="2" fill="#262a52"/><rect x="28" y="86" width="24" height="11" fill="#19b394"/></g>
      <g class="g-prop p-clip"><rect x="30" y="78" width="20" height="24" rx="2" fill="#fff" stroke="#9a9db8"/><line x1="33" y1="85" x2="47" y2="85" stroke="#9a9db8"/><line x1="33" y1="90" x2="45" y2="90" stroke="#9a9db8"/></g>
      <g class="g-prop p-hour"><circle cx="62" cy="14" r="7" fill="#0f8f75"/><path d="M59 10 h6 l-3 4 3 4 h-6 l3 -4 z" fill="#fff"/></g>
      <g class="g-prop p-warn"><circle cx="62" cy="14" r="7" fill="#f2a93b"/><rect x="61" y="9" width="2" height="6" fill="#fff"/><rect x="61" y="16.5" width="2" height="2" fill="#fff"/></g>
      <g class="g-prop p-err"><circle cx="62" cy="14" r="7" fill="#e5566b"/><path d="M59 11 l6 6 M65 11 l-6 6" stroke="#fff" stroke-width="2"/></g>
      <g class="g-prop p-think"><circle cx="60" cy="14" r="5" fill="#fff" stroke="#c9c7ee"/><circle cx="55" cy="22" r="2" fill="#fff" stroke="#c9c7ee"/></g>
      <g class="g-prop p-spark"><path d="M12 22 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 z" fill="#f2a93b"/><path d="M66 14 l1.5 3.5 3.5 1.5 -3.5 1.5 -1.5 3.5 -1.5 -3.5 -3.5 -1.5 3.5 -1.5 z" fill="#19b394"/></g>
    </svg>`;
  }
  window.novaSVG = novaSVG;

  function makeGuide(wrap, getState) {
    const g = document.createElement("div");
    g.className = "guide"; g.dataset.pose = "idle"; g.setAttribute("aria-hidden", "true");
    g.innerHTML = novaSVG() + `<div class="bubble"></div>`;
    wrap.appendChild(g);
    let x = 20, y = 60;
    return {
      el: g,
      pose(p) { g.dataset.pose = p; },
      say(t) { g.querySelector(".bubble").textContent = t || ""; },
      async moveToEl(target) {
        if (!target) return;
        target.scrollIntoView({ block: "center", behavior: getState().reduced ? "auto" : "smooth" });
        await new Promise((r) => setTimeout(r, 250));
        const wr = wrap.getBoundingClientRect(), tr = target.getBoundingClientRect();
        // stand just right of the target (or left if there is no room), feet level with the target's lower edge
        let nx = tr.right - wr.left + 6;
        if (nx > wr.width - 80) nx = tr.left - wr.left - 80;
        nx = Math.max(6, Math.min(wr.width - 80, nx));
        const ny = Math.max(60, Math.min(wr.height - 155, tr.bottom - wr.top - 150));
        const st = getState();
        const dist = Math.hypot(nx - x, ny - y);
        g.classList.toggle("flip", nx < x);
        g.classList.toggle("bubble-left", nx > wr.width - 330);
        if (st.reduced || st.skip || dist < 4) { g.style.transitionDuration = "0s"; g.style.left = nx + "px"; g.style.top = ny + "px"; x = nx; y = ny; return; }
        const ms = Math.min(2600, dist / (220 * st.speed) * 1000);
        g.dataset.pose = "walk"; g.style.transitionDuration = ms + "ms"; g.style.left = nx + "px"; g.style.top = ny + "px"; x = nx; y = ny;
        await st.sleep(ms);
        g.dataset.pose = "turn"; await st.sleep(140); g.classList.remove("flip");
      },
    };
  }

  /* ---------- scene renderers (all figures from the API) */
  const R = {
    messy: (d) => `<div class="grid g-3">
        <div class="card kpi"><div class="label">Raw rows</div><div class="value">${num(d.raw_rows)}</div><div class="def">three source systems, one CSV</div></div>
        <div class="card kpi"><div class="label">Plan spellings</div><div class="value">${num(d.variants.plan)}</div><div class="def">for 3 real plans</div></div>
        <div class="card kpi"><div class="label">Status spellings</div><div class="value">${num(d.variants.status)}</div><div class="def">for 5 canonical statuses</div></div></div>
      <div class="card j-target" id="raw-card" style="margin-top:12px"><h3>Before → after (real invoices)</h3><div class="sub">left: raw export · right: row in <code>invoices</code> after <code>rules.py</code></div>
        <div class="j-examples">${d.examples.map((x) => `<div class="j-ex"><div class="lbl">${esc(x.issue)}<br><span class="muted" style="font-weight:500">${esc(x.invoice_id)}</span></div>
          <div class="r">plan <b>${esc(JSON.stringify(x.raw.plan))}</b> · amount <b>${esc(x.raw.amount)}</b><br>status <b>${esc(x.raw.status)}</b> · date <b>${esc(x.raw.date)}</b><br><b>${esc(x.raw.email || "''")}</b></div>
          <div style="color:var(--indigo);font-size:18px">→</div>
          <div class="c">plan <b>${esc(x.clean.plan)}</b> · <b>${usd(x.clean.amount_usd)}</b> USD<br>status <b>${esc(x.clean.status)}</b> · date <b>${esc(x.clean.date)}</b><br><b>${esc(x.clean.email || "NULL (not imputed)")}</b></div></div>`).join("")}</div></div>`,
    reconcile: (d) => {
      const steps = [{ id: "raw", label: "Raw rows", rows: d.raw_rows }, ...d.by_reason.map((r) => ({ id: r.reason, label: r.reason.replace(/_/g, " "), rows: r.rows, paid: r.paid_usd })), { id: "clean", label: "Clean invoices", rows: d.clean_invoices }];
      const max = d.raw_rows, min = 4800;
      let run = d.raw_rows;
      return `<div class="grid g-21"><div class="card"><h3>${num(d.raw_rows)} → ${num(d.clean_invoices)} + ${num(d.rejected_rows)} audited</h3><div class="sub">bars on a 4,800–5,125 axis</div>
        <div style="display:flex;gap:14px;align-items:flex-end;height:230px;padding:10px 6px 0">${steps.map((s) => {
          let lo, hi; if (s.id === "raw" || s.id === "clean") { lo = min; hi = s.rows; } else { hi = run; lo = run - s.rows; run = lo; }
          const h = (hi - lo) / (max - min) * 200, b = (lo - min) / (max - min) * 200;
          const color = s.id === "raw" ? "var(--indigo)" : s.id === "clean" ? "var(--teal)" : s.id === "exact_duplicate" ? "var(--rose)" : s.id === "synonym_duplicate" ? "var(--amber)" : "#9b7bf0";
          return `<div style="flex:1;text-align:center;font-size:11px"><div style="height:210px;position:relative"><div class="j-target" id="bar-${s.id}" style="position:absolute;left:8%;right:8%;bottom:${b}px;height:${Math.max(h, 4)}px;background:${color};border-radius:8px"></div></div>
            <b>${s.id === "raw" || s.id === "clean" ? num(s.rows) : "−" + num(s.rows)}</b><br><span class="muted">${esc(s.label)}</span></div>`; }).join("")}</div></div>
        <div class="card"><h3>Revenue impact</h3><div class="sub">naive (no dedup) vs clean</div><table><thead><tr><th></th><th>Naive</th><th>Clean</th></tr></thead><tbody>
        ${[["Paid", d.impact.paid_revenue], ["Net", d.impact.net_revenue], ["Exposure", d.impact.exposure]].map(([l, v]) => `<tr><td>${l}</td><td class="num">${usd(v.naive_no_dedup, 0)}</td><td class="num">${usd(v.clean, 0)}</td></tr>`).join("")}
        </tbody></table><p class="sub" style="margin-top:10px">Overstatement avoided: <b>${usd(d.impact.paid_revenue.overstatement_avoided)}</b> paid revenue.</p></div></div>`;
    },
    revenue: (d) => `<div class="grid g-4">${[["kpi-paid", "Paid revenue 2024", d.q1_paid_2024, "status = paid · 2024"], ["kpi-net", "Net revenue (all time)", d.net, "paid + refunds"], ["kpi-refunds", "Refunds", d.refunds, "status = refunded (negative)"], ["kpi-exposure", "Pending + failed", d.exposure, num(d.exposure_count) + " invoices"]]
      .map(([id, l, v, def]) => `<div class="card kpi j-target" id="${id}"><div class="label">${l}</div><div class="value">${usd(v, 0)}</div><div class="def">${def}</div></div>`).join("")}</div>`,
    mrr: (d) => { const max = Math.max(...d.mrr_by_region.map((r) => r[1]));
      return `<div class="grid g-2"><div class="card"><h3>Average MRR per active account</h3><div class="sub">list × seats × (1 − discount), latest-invoice snapshot</div>
        ${d.mrr_by_region.map((r, i) => `<div style="display:grid;grid-template-columns:60px 1fr 90px;gap:8px;align-items:center;margin:9px 0;font-size:12.5px"><b>${esc(r[0])}</b>
          <div class="${i === 0 ? "j-target" : ""}" ${i === 0 ? 'id="mrr-top"' : ""} style="height:18px;width:${r[1] / max * 100}%;background:${i === 0 ? "var(--indigo)" : "#c9c7ee"};border-radius:6px"></div><span class="num">${usd(r[1])}</span></div>`).join("")}</div>
        <div class="card"><h3>Churn: Enterprise vs Starter</h3><div class="sub">share of accounts whose latest snapshot is churned</div><div class="grid g-2">
        ${["Enterprise", "Starter"].map((p) => `<div class="card kpi j-target" id="churn-${p}"><div class="label">${p}</div><div class="value">${(d.churn[p].rate * 100).toFixed(2)}%</div><div class="def">${num(d.churn[p].churned)} of ${num(d.churn[p].accounts)} accounts</div></div>`).join("")}</div></div></div>`; },
    harness: (d) => `<div class="card"><div class="sub">question sent live to <code>POST /api/v1/ask</code>: <b>${esc(d.question)}</b></div>
      <div class="j-graph" id="graph">${[["question", "Question", "user", 9, 50], ["guard", "Guards", "injection · write · scope", 24, 22], ["router", "Router", "intent", 37, 50], ["planner", "Semantic planner", "metric × dim × filter", 52, 22],
        ["sqlguard", "SQL guard", "sqlglot allow-list", 63, 78], ["duckdb", "DuckDB (read-only)", "execute", 76, 50], ["caveats", "Caveats", "data-quality facts", 87, 22], ["answer", "Answer + SQL", "grounded", 92, 78]]
        .map(([id, l, s, x, y]) => `<div class="j-node j-target" id="node-${id}" style="left:${x}%;top:${y}%">${l}<small>${s}</small></div>`).join("")}</div>
      <div class="sub" id="harness-result" style="margin-top:10px"></div></div>`,
    approval: (d) => { const p = d.proposal, im = p.impact;
      return `<div class="j-desk"><div class="j-deskart j-target" id="desk"><div style="text-align:center">
          <svg width="220" height="150" viewBox="0 0 220 150"><rect x="20" y="92" width="180" height="8" rx="3" fill="#8a6a4b"/><rect x="34" y="100" width="6" height="40" fill="#8a6a4b"/><rect x="180" y="100" width="6" height="40" fill="#8a6a4b"/>
          <rect x="120" y="62" width="44" height="30" rx="3" fill="#262a52"/><rect x="138" y="92" width="8" height="4" fill="#262a52"/><circle cx="82" cy="48" r="13" fill="#e2b48f"/><path d="M62 92 C62 70 102 70 102 92 Z" fill="#5f6385"/><rect x="40" y="80" width="14" height="12" fill="#19b394" opacity=".6"/></svg>
          <div>Finance owner's desk — the journey is paused here</div><div id="desk-state" style="margin-top:6px"></div></div></div>
        <div class="card"><div style="display:flex;gap:8px;align-items:center"><span class="chip">POLICY</span><span class="chip warn">PENDING</span><b>${esc(p.record.split("/").pop())}</b></div>
          <h3 style="margin-top:8px">FX direction: ${esc(p.current)} → recommended ${esc(p.recommended)}</h3>
          <table><thead><tr><th></th><th>documented (current)</th><th>inverse</th></tr></thead><tbody>
            <tr><td>Non-USD invoices matching price book</td><td class="num">${num(im.price_book_matches.documented)} / ${num(im.non_usd_invoices_checked)}</td><td class="num">${num(im.price_book_matches.inverse)} / ${num(im.non_usd_invoices_checked)}</td></tr>
            <tr><td>Q1 paid revenue 2024</td><td class="num">${usd(im.answers.documented.q1_paid_2024)}</td><td class="num">${usd(im.answers.inverse.q1_paid_2024)}</td></tr>
            <tr><td>Refunds</td><td class="num">${usd(im.answers.documented.refunds)}</td><td class="num">${usd(im.answers.inverse.refunds)}</td></tr></tbody></table>
          <div class="j-form" id="approve-form">${d.approvals_enabled ? "" : `<div class="caveat">Approvals are disabled on this server (FINANCE_APPROVER_PIN not set). The decision stays open — that is the safe default.</div>`}
            <label>Decision</label><div class="opts">${Object.keys(p.options).map((o) => `<label style="margin:0"><input type="radio" name="opt" value="${o}" ${o === p.recommended ? "checked" : ""}> ${o}</label>`).join("")}</div>
            <label>Approver (finance owner)</label><input id="ap-name" placeholder="Name">
            <label>Rationale (min 20 characters)</label><textarea id="ap-why" rows="2"></textarea>
            <label>Approval PIN</label><input id="ap-pin" type="password" autocomplete="off">
            <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><button class="btn sm" id="ap-go" ${d.approvals_enabled ? "" : "disabled"}>✓ Approve decision</button>
              <button class="btn light sm" id="ap-skip">Continue without deciding</button></div>
            <div class="sub" style="margin-top:8px">Impact hash ${esc(im.impact_hash)} is sent with the approval. Approving records the decision; the rebuild is a separate step on the Decisions page.</div>
            <div id="ap-msg"></div></div></div></div>`; },
    summary: (d) => { const ev = d.evals;
      return `<div class="grid g-3">${ev ? `<div class="card kpi j-target" id="summary-evals"><div class="label">Stakeholder answers verified</div><div class="value">${ev.stakeholder.filter((r) => r.status === "PASS").length} / ${ev.stakeholder.length}</div><div class="def">independent oracle · ${esc(ev.run_at)}</div></div>
          <div class="card kpi"><div class="label">Eval suite</div><div class="value">${ev.counts.PASS} pass · ${ev.counts.FAIL} fail</div><div class="def">${ev.counts.XFAIL} documented expected failures · ${ev.counts.SKIP} skipped</div></div>` : `<div class="card j-target" id="summary-evals">No eval artifact — run <code>python -m evals</code>.</div>`}
        <div class="card kpi"><div class="label">Hybrid vs Qwen-only</div><div class="value">${d.modes ? `${d.modes.hybrid.correct}/${d.modes.hybrid.total} vs ${d.modes.llm.correct}/${d.modes.llm.total}` : "—"}</div><div class="def">${d.modes ? `median ${num(d.modes.hybrid.median_ms)} ms vs ${num(d.modes.llm.median_ms)} ms` : "run python -m evals.compare_modes"}</div></div></div>
        <div class="card j-honest" style="margin-top:12px"><h3>Where each answer could be wrong</h3><div class="sub">cited by SQL + oracle; the choices below could change the number · policy v${esc(d.policy.version)} active</div>
        <table><thead><tr><th>Question</th><th>Confidence</th><th>Could be wrong because…</th></tr></thead><tbody>
        ${d.honesty.map((h) => `<tr><td><b>${esc(h.q)}</b></td><td>${esc(h.confidence)}</td><td><ul>${h.could_be_wrong.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></td></tr>`).join("")}</tbody></table></div>`; },
  };

  /* ---------- the journey page */
  window.pageJourney = async function (el) {
    const J = await (await fetch("/api/v1/journey")).json();
    const S = J.scenes;
    const st = { i: 0, playing: true, speed: 1.5, muted: true, reduced: matchMedia("(prefers-reduced-motion: reduce)").matches, skip: false, token: 0, source: "live", narr: [], events: [] };
    st.sleep = (ms) => new Promise((res) => { const tok = st.token; const end = Date.now() + ms;
      (function tick() { if (tok !== st.token || !el.isConnected) return res("cancel"); if (st.skip) return res(); if (!st.playing) return setTimeout(tick, 120); if (Date.now() >= end) return res(); setTimeout(tick, 40); })(); });
    el.innerHTML = `<div class="j-head"><div class="badge"><img src="/static/brand/cloud-logo.svg" width="34"></div><div><h2>Nova's Guided Journey</h2>
        <p>Nova walks executives through CloudNova's money, the query agent and the decisions only a person can make. Charts stay interactive; the narration panel carries every message as text.</p></div></div>
      <div class="j-demo">${esc(J.labels.data)} ${esc(J.labels.character)}</div>
      <div class="card"><div class="j-controls">
        <button class="primary" id="j-play">Pause</button><button id="j-skip">⏭ Skip animation</button><button id="j-replay">↻ Replay scene</button>
        <label>Jump to <select id="j-jump">${S.map((s, i) => `<option value="${i}">${s.id}. ${esc(s.title)}</option>`).join("")}</select></label>
        <label>Speed <select id="j-speed">${[1, 1.5, 2, 3].map((v) => `<option ${v === 1.5 ? "selected" : ""}>${v}×</option>`).join("")}</select></label>
        <button id="j-mute">🔈 Unmute</button><button id="j-motion">${st.reduced ? "Motion on" : "Reduce motion"}</button>
        <div class="j-live">Events <select id="j-src"><option value="live">Live query run</option><option value="recorded">Recorded run (latest trace)</option></select>
          <span class="j-pill reading" id="j-run">—</span><span class="j-pill" id="j-llm">model…</span><span class="j-pill working" id="j-status">PLAYING</span></div></div>
        <div class="j-steps" id="j-steps">${S.map((s, i) => `<button data-i="${i}">${s.id} ${esc(s.title)}</button>`).join("")}</div></div>
      <div class="j-body"><div class="card j-stage-wrap" id="j-wrap"><div class="j-scene-head"><div><div class="k" id="j-k"></div><h3 id="j-title"></h3><p class="sub" id="j-sub"></p></div>
          <div class="j-state">Nova: <span class="j-pill" id="j-agent">—</span><br>Destination: <code id="j-dest"></code> · gesture: <span id="j-gest"></span></div></div>
          <div class="j-scene" id="j-scene"></div></div>
        <div class="card"><h3>Narration</h3><div class="sub">everything Nova says and does, as text</div><div class="j-narr" id="j-narr" aria-live="polite"></div>
          <h3 style="margin-top:14px">Execution events</h3><div class="j-events" id="j-events"></div></div></div>`;
    const wrap = $("#j-wrap", el), guide = makeGuide(wrap, () => st);
    fetch("/api/v1/health").then((r) => r.json()).then((h) => { const b = $("#j-llm", el); if (!b) return;
      b.textContent = h.llm.reachable ? `QWEN ONLINE · ${h.llm.model}` : "QWEN OFFLINE · deterministic mode"; b.className = "j-pill " + (h.llm.reachable ? "completed" : "warn"); });
    const page = el.closest(".main") || el; if (st.reduced) page.classList.add("reduced");
    window.addEventListener("hashchange", () => { st.token++; if (window.speechSynthesis) speechSynthesis.cancel(); }, { once: true });
    const setAgent = (txt, cls) => { const a = $("#j-agent", el); if (!a) return; a.textContent = txt; a.className = "j-pill " + cls; };
    const say = (sceneN, text) => { guide.say(text); st.narr.push([sceneN, text]);
      $("#j-narr", el).innerHTML = st.narr.map(([n, t], k) => `<div class="msg ${k === st.narr.length - 1 ? "now" : ""}"><b>Scene ${n}</b>${esc(t)}</div>`).join("");
      $("#j-narr", el).scrollTop = 1e9;
      if (!st.muted && window.speechSynthesis) { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.rate = Math.min(2, st.speed * 0.9); speechSynthesis.speak(u); } };
    const evt = (name, detail) => { st.events.push([name, detail]); $("#j-events", el).innerHTML = st.events.map(([n, d]) => `<div><span>${esc(n)}</span> ${esc(d)}</div>`).join(""); $("#j-events", el).scrollTop = 1e9; };
    const readTime = (t) => (1100 + t.length * 32) / st.speed;
    const hl = (id) => { el.querySelectorAll(".j-target.hl").forEach((x) => x.classList.remove("hl")); const t = id && $("#" + CSS.escape(id), el); if (t) t.classList.add("hl"); return t; };

    async function narrate(sc, lines, pose) { for (const line of lines) { guide.pose(pose); say(sc.id, line); if ((await st.sleep(readTime(line))) === "cancel") return false; } return true; }

    async function harness(sc) {
      setAgent("WORKING", "working");
      let resp;
      const node = (id, cls) => { const n = $("#node-" + id, el); if (n) { n.classList.remove("active"); if (cls) n.classList.add(cls); } return n; };
      const visit = async (id, eventName, detail, line) => { const n = hl("node-" + id); n.classList.add("active"); evt(eventName, detail); await guide.moveToEl(n); guide.pose("work"); if (line) say(sc.id, line); return st.sleep(line ? readTime(line) : 600 / st.speed); };
      await guide.moveToEl($("#node-question", el)); guide.pose("work");
      say(sc.id, sc.narration[0]); evt("RUN_PLANNED", sc.data.question);
      if (st.source === "recorded") {
        const t = await (await fetch("/api/v1/traces?limit=50")).json();
        const run = t.runs.find((r) => r.planner === "semantic" && r.status === "ok");
        if (!run) { say(sc.id, "No recorded semantic run yet — switching to a live run."); st.source = "live"; }
        else resp = { trace: run.trace, run_id: run.run_id, sql: null, answer: `(recorded run for: ${run.question})`, latency_ms: run.total_ms };
      }
      if (!resp) { try { const r = await fetch("/api/v1/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: sc.data.question }) }); resp = await r.json(); if (!r.ok) throw new Error(resp.message); }
        catch (e) { guide.pose("error"); setAgent("ERROR", "warn"); say(sc.id, "The query agent returned an error: " + e.message); return; } }
      $("#j-run", el).textContent = "RUN " + (resp.run_id || "").toUpperCase(); $("#j-run", el).className = "j-pill completed";
      for (const t of resp.trace) {
        if ((st.token, false)) break;
        if (t.step === "guard") { if ((await visit("guard", "GUARD_FLAGGED", t.detail, "Guard flagged instruction-like text; treating it as data.")) === "cancel") return; continue; }
        if (t.step === "route") { await visit("guard", "GUARDS_PASSED", "length · write-intent · out-of-scope"); node("guard", "ok");
          if ((await visit("router", "ROUTED", t.detail, `Routed: ${t.detail}.`)) === "cancel") return; node("router", "ok"); continue; }
        if (t.tool === "run_metric_query") {
          if ((await visit("planner", "TOOL_RUNNING", "run_metric_query", "The semantic planner compiles approved metric SQL — no LLM in this path.")) === "cancel") return; node("planner", "ok");
          await visit("sqlguard", "VALIDATION_STARTED", "sqlglot structural check (inside run_query)", "Validation: one SELECT, allow-listed tables and columns."); node("sqlguard", "ok");
          if ((await visit("duckdb", "TOOL_COMPLETED", `${t.detail} · ${t.ms} ms`, `DuckDB answered read-only: ${t.detail}.`)) === "cancel") return; node("duckdb", "ok"); continue; }
        if (t.tool === "scope_caveats") { if ((await visit("caveats", "TOOL_COMPLETED", `scope_caveats · ${t.detail}`, `I attached ${t.detail} that apply to these rows.`)) === "cancel") return; node("caveats", "ok"); continue; }
        if (t.tool) { await visit("planner", "TOOL_" + (t.status === "ok" ? "COMPLETED" : "FAILED"), `${t.tool} · ${t.detail}`); }
      }
      await visit("answer", "TASK_COMPLETED", `${Math.round(resp.latency_ms)} ms`); node("answer", "ok");
      $("#harness-result", el).innerHTML = `<b>Answer:</b> ${esc((resp.answer || "").replace(/\*\*/g, "").split("\n")[0])}${resp.sql ? `<pre class="sql" style="margin-top:8px">${esc(resp.sql)}</pre>` : ""}`;
      guide.pose("success"); setAgent("COMPLETED", "completed");
      say(sc.id, "Task completed and verified: the number came from DuckDB, the SQL is shown, and the caveats travel with it.");
      await st.sleep(readTime("Task completed and verified"));
    }

    async function approval(sc) {
      setAgent("AWAITING APPROVAL", "awaiting"); $("#j-status", el).textContent = "PAUSED AT APPROVAL GATE"; $("#j-status", el).className = "j-pill awaiting";
      $("#desk-state", el).innerHTML = `<span class="j-pill awaiting">WORKFLOW PAUSED</span>`;
      const tok = st.token;
      // handlers are live immediately: the approver can act while Nova is still talking
      const decided = new Promise((resolve) => {
        $("#ap-skip", el).onclick = () => { evt("APPROVAL_DEFERRED", "no decision recorded; policy unchanged"); guide.pose("idle");
          say(sc.id, "No decision recorded. The original rule stays active — I'll carry the open decision into the summary."); setAgent("OPEN", "awaiting"); resolve(); };
        $("#ap-go", el).onclick = async () => {
          const opt = (el.querySelector('input[name="opt"]:checked') || {}).value;
          const body = { key: "fx_direction", option: opt, approver: $("#ap-name", el).value, role: "finance_owner", rationale: $("#ap-why", el).value, pin: $("#ap-pin", el).value, impact_hash: sc.data.proposal.impact.impact_hash };
          const r = await fetch("/api/v1/policy/decisions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
          const j = await r.json();
          if (!r.ok) { guide.pose("error"); $("#ap-msg", el).innerHTML = `<div class="caveat">${esc(j.message || "rejected")}</div>`; evt("APPROVAL_REJECTED", j.code || r.status); say(sc.id, "That approval was not accepted: " + (j.message || "")); return; }
          $("#ap-msg", el).innerHTML = ""; evt("DECISION_RECORDED", `#${j.decision_id} ${j.status}`); guide.pose("success"); setAgent("DECIDED", "completed");
          $("#desk-state", el).innerHTML = `<span class="j-pill completed">DECISION #${j.decision_id} RECORDED</span>`;
          say(sc.id, `Decision #${j.decision_id} recorded by ${body.approver} (${j.status.replace(/_/g, " ")}). Nothing has been rebuilt — that is a separate step on the Decisions page.`); resolve(); };
        (function watch() { if (tok !== st.token) return resolve(); setTimeout(watch, 200); })();
      });
      await guide.moveToEl(hl("desk"));
      evt("APPROVAL_REQUIRED", "PDR-001 fx_direction — waiting for finance owner");
      let done = false; decided.then(() => { done = true; });
      for (const line of sc.narration) { if (done) break; guide.pose("wait"); say(sc.id, line); if ((await st.sleep(readTime(line))) === "cancel") return; }
      await decided;  // the walk does not continue until a person acts
      if (tok !== st.token) return;
      $("#j-status", el).textContent = st.playing ? "PLAYING" : "PAUSED"; $("#j-status", el).className = "j-pill working";
      await st.sleep(1800 / st.speed);
    }

    async function runScene(i) {
      if (!el.isConnected) return;
      st.token++; st.skip = false; st.i = i; const tok = st.token; const sc = S[i];
      if (window.speechSynthesis) speechSynthesis.cancel();
      $("#j-k", el).textContent = `SCENE ${sc.id} OF ${S.length}`; $("#j-title", el).textContent = sc.title; $("#j-sub", el).textContent = sc.subtitle;
      $("#j-dest", el).textContent = sc.destination; $("#j-gest", el).textContent = sc.gesture; $("#j-jump", el).value = i;
      el.querySelectorAll("#j-steps button").forEach((b, k) => { b.className = k === i ? "on" : k < i ? "done" : ""; });
      $("#j-scene", el).innerHTML = R[sc.key](sc.data); guide.say(""); setAgent("READING", "reading"); evt("SCENE_STARTED", `${sc.id} ${sc.title}`);
      await new Promise((r) => requestAnimationFrame(r));
      if (sc.key === "harness") await harness(sc);
      else if (sc.key === "approval") await approval(sc);
      else { guide.pose("think"); await st.sleep(400 / st.speed); await guide.moveToEl(hl(sc.destination)); const gest = { point: "point", work: "work", success: "success", warn: "warn", wait: "wait" }[sc.gesture] || "point";
        if ((await narrate(sc, sc.narration, gest)) === false) return; if (sc.key === "summary") { guide.pose(gest); setAgent(gest === "success" ? "COMPLETED" : "NEEDS ATTENTION", gest === "success" ? "completed" : "warn"); } }
      if (tok !== st.token || !el.isConnected) return;
      evt("SCENE_COMPLETED", `${sc.id}`);
      if (sc.key !== "summary") setAgent("DONE", "completed");
      if (i < S.length - 1) { if ((await st.sleep(1300 / st.speed)) === "cancel") return; if (tok === st.token) runScene(i + 1); }
      else { $("#j-status", el).textContent = "FINISHED"; $("#j-status", el).className = "j-pill completed"; }
    }

    $("#j-play", el).onclick = (e) => { st.playing = !st.playing; e.target.textContent = st.playing ? "Pause" : "▶ Play"; $("#j-status", el).textContent = st.playing ? "PLAYING" : "PAUSED"; if (!st.playing && window.speechSynthesis) speechSynthesis.cancel(); };
    $("#j-skip", el).onclick = () => { st.skip = true; };
    $("#j-replay", el).onclick = () => runScene(st.i);
    $("#j-jump", el).onchange = (e) => runScene(+e.target.value);
    el.querySelectorAll("#j-steps button").forEach((b) => b.onclick = () => runScene(+b.dataset.i));
    $("#j-speed", el).onchange = (e) => { st.speed = parseFloat(e.target.value); };
    $("#j-mute", el).onclick = (e) => { st.muted = !st.muted; e.target.textContent = st.muted ? "🔈 Unmute" : "🔊 Mute"; if (st.muted && window.speechSynthesis) speechSynthesis.cancel(); };
    $("#j-motion", el).onclick = (e) => { st.reduced = !st.reduced; page.classList.toggle("reduced", st.reduced); e.target.textContent = st.reduced ? "Motion on" : "Reduce motion"; };
    $("#j-src", el).onchange = (e) => { st.source = e.target.value; };
    window.__journey = st;  // test hook (read-only use in browser checks)
    runScene(0);
  };

  /* ---------- Decisions page: approval-gated policy changes */
  window.pageDecisions = async function (el) {
    const P = await (await fetch("/api/v1/policy")).json();
    const a = P.active_policy;
    el.innerHTML = `<div class="section-title">Financial policy decisions</div>
      <div class="banner">Active policy <b>v${esc(a.version)}</b> (${esc(a.status)}). Original rules (v${esc(P.original_policy_version)}) are preserved in <code>policies/financial_policy.yaml</code>.
        Changes need a finance-owner approval, then an explicit rebuild. ${P.approvals_enabled ? "" : "<b>Approvals are disabled on this server</b> (FINANCE_APPROVER_PIN not set)."} ${esc(P.note)}</div>
      ${P.proposals.map((p) => `<div class="card" style="margin-bottom:14px"><div class="card-head"><h3>${esc(p.key)}: current <code>${esc(p.current)}</code> · recommended <code>${esc(p.recommended)}</code></h3><span class="sub">${esc(p.record)}</span></div>
        <div class="grid g-2"><div><div class="sub">options</div><ul style="font-size:12.5px">${Object.entries(p.options).map(([k, v]) => `<li><b>${esc(k)}</b> — ${esc(v)}${p.blocked[k] ? `<br><span class="flag">blocked from applying:</span> ${esc(p.blocked[k])}` : ""}</li>`).join("")}</ul>
          <details open><summary>Impact evidence (hash ${esc(p.impact.impact_hash)})</summary><pre class="sql" style="max-height:220px;overflow:auto">${esc(JSON.stringify(p.impact, null, 2))}</pre></details></div>
        <div class="j-form" data-key="${esc(p.key)}" data-hash="${esc(p.impact.impact_hash)}"><label>Decision</label><div class="opts">${Object.keys(p.options).map((o) => `<label style="margin:0"><input type="radio" name="o-${esc(p.key)}" value="${esc(o)}" ${o === p.recommended ? "checked" : ""}> ${esc(o)}</label>`).join("")}</div>
          <label>Approver</label><input class="ap-name"><label>Rationale</label><textarea class="ap-why" rows="2"></textarea><label>Approval PIN</label><input class="ap-pin" type="password" autocomplete="off">
          <button class="btn sm ap-go" style="margin-top:10px" ${P.approvals_enabled ? "" : "disabled"}>Record decision</button><div class="ap-msg"></div></div></div></div>`).join("")}
      <div class="card"><h3>Decision log</h3><div class="sub">recorded decisions; only "approved pending rebuild" can be applied</div>
        ${P.decisions.length ? `<table><thead><tr><th>#</th><th>Key</th><th>From → to</th><th>Approver</th><th>Rationale</th><th>Status</th><th></th></tr></thead><tbody>${P.decisions.map((d) => `<tr><td>${d.id}</td><td>${esc(d.key)}</td><td>${esc(d.from_value)} → ${esc(d.to_value)}</td><td>${esc(d.approver)}</td><td>${esc(d.rationale)}</td><td>${esc(d.status)}${d.policy_version ? " · v" + esc(d.policy_version) : ""}</td>
          <td>${d.status === "approved_pending_rebuild" ? `<button class="btn sm ap-apply" data-id="${d.id}">Apply & rebuild</button>` : ""}</td></tr>`).join("")}</tbody></table>` : `<div class="empty">No decisions recorded yet.</div>`}</div>`;
    el.querySelectorAll(".j-form[data-key]").forEach((f) => { f.querySelector(".ap-go").onclick = async () => {
      const body = { key: f.dataset.key, option: f.querySelector("input[type=radio]:checked").value, approver: f.querySelector(".ap-name").value, role: "finance_owner",
        rationale: f.querySelector(".ap-why").value, pin: f.querySelector(".ap-pin").value, impact_hash: f.dataset.hash };
      const r = await fetch("/api/v1/policy/decisions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); const j = await r.json();
      f.querySelector(".ap-msg").innerHTML = r.ok ? `<div class="caveat" style="background:#effaf6;color:#0f8f75">Decision #${j.decision_id}: ${esc(j.status)}</div>` : `<div class="caveat">${esc(j.message || "rejected")}</div>`;
      if (r.ok) setTimeout(() => window.dispatchEvent(new HashChangeEvent("hashchange")), 900); }; });
    el.querySelectorAll(".ap-apply").forEach((b) => b.onclick = async () => { if (!confirm("Apply this decision and rebuild the database from the raw CSV?")) return;
      const r = await fetch(`/api/v1/policy/decisions/${b.dataset.id}/apply`, { method: "POST" }); const j = await r.json(); alert(r.ok ? `Applied: policy v${j.policy_version}, rebuilt.` : j.message); window.dispatchEvent(new HashChangeEvent("hashchange")); });
  };

  /* ---------- launcher: Nova on every page */
  document.addEventListener("DOMContentLoaded", () => {
    const l = document.createElement("div"); l.className = "nova-launch";
    l.innerHTML = `<div class="mini guide" data-pose="idle" style="position:relative;left:0;bottom:0;width:34px;height:68px">${novaSVG()}</div><a href="#/journey">Guided journey</a>`;
    document.body.appendChild(l);
    window.addEventListener("hashchange", () => { l.style.display = location.hash.startsWith("#/journey") ? "none" : "flex"; });
    if (location.hash.startsWith("#/journey")) l.style.display = "none";
  });
})();
