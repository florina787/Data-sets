// AI observability dashboard. ALL VALUES ARE DEMO TELEMETRY generated locally by a
// seeded PRNG. They are not measurements of any real system.
import { $, esc, rng, prefersReducedMotion } from './util.js';

const N = 30;
const METRICS = [
  { id: 'req', label: 'Requests', unit: '/min', base: 420, vol: 0.06, min: 250, max: 650, fmt: (v) => Math.round(v), good: 'neutral' },
  { id: 'lat', label: 'Latency p95', unit: 'ms', base: 1850, vol: 0.05, min: 1200, max: 2900, fmt: (v) => Math.round(v), good: 'down' },
  { id: 'tok', label: 'Token usage', unit: 'k/min', base: 1480, vol: 0.07, min: 900, max: 2300, fmt: (v) => Math.round(v), good: 'down' },
  { id: 'ret', label: 'Retrieval quality', unit: 'nDCG', base: 0.81, vol: 0.015, min: 0.7, max: 0.92, fmt: (v) => v.toFixed(2), good: 'up' },
  { id: 'agt', label: 'Agent success rate', unit: '%', base: 94.5, vol: 0.006, min: 89, max: 98.5, fmt: (v) => v.toFixed(1), good: 'up' },
  { id: 'tool', label: 'Tool call success', unit: '%', base: 98.1, vol: 0.004, min: 94, max: 99.8, fmt: (v) => v.toFixed(1), good: 'up' },
  { id: 'cache', label: 'Cache hit rate', unit: '%', base: 31, vol: 0.05, min: 18, max: 46, fmt: (v) => v.toFixed(1), good: 'up' },
  { id: 'cost', label: 'Cost / request', unit: 'USD', base: 0.0124, vol: 0.05, min: 0.008, max: 0.019, fmt: (v) => `$${v.toFixed(4)}`, good: 'down' },
];

const SPANS = [
  { name: 'gateway + auth', base: 14, cls: 'sec' },
  { name: 'input guardrail', base: 32, cls: 'sec' },
  { name: 'hybrid retrieval', base: 140, cls: '' },
  { name: 'rerank', base: 85, cls: '' },
  { name: 'context build', base: 12, cls: '' },
  { name: 'llm generate', base: 1180, cls: 'llm' },
  { name: 'output validation', base: 70, cls: 'sec' },
];

export function initObservability() {
  const grid = $('#obs-kpis');
  if (!grid) return;
  const rand = rng(20261003);
  const series = Object.fromEntries(METRICS.map((m) => [m.id, []]));
  const step = (m, prev) => Math.min(m.max, Math.max(m.min, prev + (rand() - 0.5) * 2 * m.vol * m.base + (m.base - prev) * 0.08));
  METRICS.forEach((m) => { let v = m.base; for (let i = 0; i < N; i += 1) { v = step(m, v); series[m.id].push(v); } });

  grid.innerHTML = METRICS.map((m) => `
    <div class="kpi" data-kpi="${m.id}">
      <div class="lbl">${esc(m.label)}</div>
      <div class="val"><span data-val></span><small>${esc(m.unit === 'USD' ? '' : m.unit)}</small></div>
      <div class="delta" data-delta></div>
      <svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" role="img" aria-label="${esc(m.label)} trend, simulated">
        <path data-area fill="var(--accent-soft)" stroke="none"></path>
        <path data-line fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"></path>
        <line data-x y1="0" y2="34" stroke="var(--ink-2)" stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"></line>
      </svg>
      <span class="hover-read" data-read></span>
    </div>`).join('');

  const geom = (vals) => {
    const lo = Math.min(...vals); const hi = Math.max(...vals); const span = hi - lo || 1;
    const pts = vals.map((v, i) => [(i / (vals.length - 1)) * 100, 31 - ((v - lo) / span) * 28]);
    const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join('');
    return { line, area: `${line}L100,34L0,34Z` };
  };

  function render() {
    METRICS.forEach((m) => {
      const el = grid.querySelector(`[data-kpi="${m.id}"]`);
      const vals = series[m.id];
      const last = vals[vals.length - 1];
      const prev = vals.slice(-11, -1).reduce((a, b) => a + b, 0) / 10;
      const d = ((last - prev) / prev) * 100;
      el.querySelector('[data-val]').textContent = m.fmt(last);
      const arrow = d >= 0 ? '▲' : '▼';
      el.querySelector('[data-delta]').textContent = `${arrow} ${Math.abs(d).toFixed(1)}% vs prev 10 · demo`;
      const g = geom(vals);
      el.querySelector('[data-line]').setAttribute('d', g.line);
      el.querySelector('[data-area]').setAttribute('d', g.area);
    });
    const traceRand = rng(Math.floor(rand() * 1e9));
    let t = 0;
    const spans = SPANS.map((s) => { const dur = s.base * (0.7 + traceRand() * 0.6); const out = { ...s, start: t, dur }; t += dur; return out; });
    $('#obs-waterfall').innerHTML = spans.map((s) => `
      <li><span>${esc(s.name)}</span><span class="track"><span class="span ${s.cls}" style="left:${((s.start / t) * 100).toFixed(2)}%;width:${Math.max(0.6, (s.dur / t) * 100).toFixed(2)}%"></span></span><span class="ms">${Math.round(s.dur)}ms</span></li>`).join('');
    $('#obs-trace-id').textContent = `trace ${Math.floor(traceRand() * 0xffffffff).toString(16).padStart(8, '0')} · ${Math.round(t)}ms · demo`;
    $('#obs-updated').textContent = `generated ${new Date().toLocaleTimeString()}`;
  }

  // Hover crosshair + value readout on each sparkline.
  grid.addEventListener('pointermove', (e) => {
    const svg = e.target.closest('svg.spark');
    grid.querySelectorAll('.kpi.hovering').forEach((k) => { if (!svg || !k.contains(svg)) { k.classList.remove('hovering'); k.querySelector('[data-x]').setAttribute('visibility', 'hidden'); } });
    if (!svg) return;
    const kpi = svg.closest('.kpi');
    const m = METRICS.find((x) => x.id === kpi.dataset.kpi);
    const r = svg.getBoundingClientRect();
    const i = Math.round(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * (N - 1));
    const x = (i / (N - 1)) * 100;
    const line = kpi.querySelector('[data-x]');
    line.setAttribute('x1', x); line.setAttribute('x2', x); line.setAttribute('visibility', 'visible');
    kpi.classList.add('hovering');
    kpi.querySelector('[data-read]').textContent = `t-${N - 1 - i}: ${m.fmt(series[m.id][i])}`;
  });
  grid.addEventListener('pointerleave', () => grid.querySelectorAll('.kpi').forEach((k) => { k.classList.remove('hovering'); k.querySelector('[data-x]').setAttribute('visibility', 'hidden'); }));

  render();

  const toggle = $('#obs-toggle');
  let paused = prefersReducedMotion();
  let visible = false;
  const sync = () => { toggle.textContent = paused ? 'Resume' : 'Pause'; toggle.setAttribute('aria-pressed', String(paused)); };
  sync();
  toggle.addEventListener('click', () => { paused = !paused; sync(); });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(grid);
  setInterval(() => {
    if (paused || !visible || document.hidden) return;
    METRICS.forEach((m) => { const s = series[m.id]; s.push(step(m, s[s.length - 1])); s.shift(); });
    render();
  }, 2500);
}
