// RAG Explorer: a real (small) retrieval pipeline running entirely in the browser.
// BM25 sparse retrieval + feature-hashed dense vectors, fused, reranked, packed into
// a token budget, then answered extractively, so the answer can only contain corpus text.
import { CORPUS, SUGGESTED, SYNONYMS } from './rag-corpus.js';
import { $, $$, esc, sleep } from './util.js';

const STOP = new Set('a an and are as at be by can do does for from has have how i if in is it its may me must my of on or our should so that the their them then there these this to was we what when where which who why will with you your about after any all also into not only other per same than until'.split(' '));
const DIM = 256;
const TOKEN_BUDGET = 220;
const SYSTEM_TOKENS = 48;
const MIN_RERANK = 0.3;

const stem = (w) => {
  if (w.length > 5 && w.endsWith('ing')) w = w.slice(0, -3);
  else if (w.length > 5 && w.endsWith('ion')) w = w.slice(0, -3);
  else if (w.length > 4 && w.endsWith('ed')) w = w.slice(0, -2);
  else if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) w = w.slice(0, -1);
  if (w.length > 4 && w.endsWith('e')) w = w.slice(0, -1);
  return w;
};
const tokenize = (text) =>
  text.toLowerCase().replace(/[^a-z0-9\s-]/g, ' ').split(/[\s-]+/).filter((w) => w && !STOP.has(w)).map(stem);

const SYN = Object.fromEntries(Object.entries(SYNONYMS).map(([k, v]) => [stem(k), v.map(stem)]));

// FNV-1a hash → bucket index and sign, for the hashing-trick embedding.
function fnv(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return h >>> 0;
}
function embed(tokens) {
  const v = new Float32Array(DIM);
  const add = (feat, w) => { const h = fnv(feat); v[h % DIM] += (h & 0x80000000 ? -1 : 1) * w; };
  tokens.forEach((t, i) => {
    add(`w:${t}`, 1);
    if (i > 0) add(`b:${tokens[i - 1]}_${t}`, 0.5);
    const padded = `^${t}$`;
    for (let j = 0; j < padded.length - 2; j += 1) add(`c:${padded.slice(j, j + 3)}`, 0.25);
  });
  const n = Math.hypot(...v) || 1;
  for (let i = 0; i < DIM; i += 1) v[i] /= n;
  return v;
}
const cosine = (a, b) => { let s = 0; for (let i = 0; i < DIM; i += 1) s += a[i] * b[i]; return s; };
const estTokens = (text) => Math.ceil(text.split(/\s+/).length * 1.3);

// ---- index (built once) ----
const CHUNKS = CORPUS.flatMap((doc) =>
  doc.chunks.map((c, i) => {
    const tokens = tokenize(`${doc.title} ${c.section} ${c.text}`);
    return { ...c, doc, key: `${doc.id}#${i + 1}`, tokens, tf: tokens.reduce((m, t) => m.set(t, (m.get(t) || 0) + 1), new Map()), vec: embed(tokens), titleTokens: new Set(tokenize(`${doc.title} ${c.section}`)) };
  }),
);
const AVGDL = CHUNKS.reduce((s, c) => s + c.tokens.length, 0) / CHUNKS.length;
const DF = new Map();
CHUNKS.forEach((c) => new Set(c.tokens).forEach((t) => DF.set(t, (DF.get(t) || 0) + 1)));
const idf = (t) => Math.log(1 + (CHUNKS.length - (DF.get(t) || 0) + 0.5) / ((DF.get(t) || 0) + 0.5));

function bm25(chunk, terms, k1 = 1.2, b = 0.75) {
  let s = 0;
  for (const t of terms) {
    const f = chunk.tf.get(t) || 0;
    if (!f) continue;
    s += idf(t) * ((f * (k1 + 1)) / (f + k1 * (1 - b + (b * chunk.tokens.length) / AVGDL)));
  }
  return s;
}

export function retrieve(question) {
  const base = tokenize(question);
  const expanded = [...new Set(base.flatMap((t) => [t, ...(SYN[t] || [])]))];
  const added = expanded.filter((t) => !base.includes(t));
  const qvec = embed(expanded);

  const scored = CHUNKS.map((c) => ({ c, sparse: bm25(c, expanded), dense: Math.max(0, cosine(qvec, c.vec)) }));
  const maxSparse = Math.max(...scored.map((s) => s.sparse), 1e-9);
  const maxDense = Math.max(...scored.map((s) => s.dense), 1e-9);
  scored.forEach((s) => {
    s.sparseN = s.sparse / maxSparse;
    s.denseN = s.dense / maxDense;
    // Confidence-weighted fusion: keep absolute dense similarity in play so weak matches stay weak.
    s.hybrid = 0.5 * s.sparseN * Math.min(1, maxSparse / 4) + 0.5 * Math.min(1, s.dense * 2.2);
  });
  const candidates = scored.sort((a, b) => b.hybrid - a.hybrid).slice(0, 6);

  // "Cross-encoder" rerank simulation: coverage of original query terms, title match, phrase match.
  const bigrams = base.slice(1).map((t, i) => `${base[i]} ${t}`);
  candidates.forEach((s) => {
    const cover = base.length ? base.filter((t) => s.c.tf.has(t) || (SYN[t] || []).some((x) => s.c.tf.has(x))).length / base.length : 0;
    const title = base.some((t) => s.c.titleTokens.has(t)) ? 1 : 0;
    const joined = s.c.tokens.join(' ');
    const phrase = bigrams.length ? bigrams.filter((bg) => joined.includes(bg)).length / bigrams.length : 0;
    s.rerank = Math.min(1, 0.45 * s.hybrid + 0.35 * cover + 0.1 * title + 0.1 * phrase);
  });
  candidates.sort((a, b) => b.rerank - a.rerank);

  // Context builder: greedy pack by rerank score within the token budget.
  let used = SYSTEM_TOKENS;
  const selected = [];
  for (const s of candidates) {
    const t = estTokens(s.c.text);
    if (s.rerank < MIN_RERANK || used + t > TOKEN_BUDGET || selected.length >= 3) continue;
    selected.push(s);
    s.tokens = t;
    used += t;
  }

  // Extractive "LLM": only sentences from selected chunks, ranked by query-term overlap.
  const sentences = selected.flatMap((s, i) =>
    s.c.text.split(/(?<=\.)\s+/).map((text) => {
      const toks = new Set(tokenize(text));
      const hits = expanded.filter((t) => toks.has(t)).length + base.filter((t) => toks.has(t)).length;
      return { text, cite: i + 1, hits };
    }),
  );
  const top = Math.max(0, ...sentences.map((x) => x.hits));
  const best = sentences.filter((x) => x.hits >= Math.max(2, top * 0.5)).sort((a, b) => b.hits - a.hits || a.cite - b.cite).slice(0, 3);
  best.sort((a, b) => a.cite - b.cite);
  const grounded = best.length > 0;
  return { base, expanded, added, qvec, candidates, selected, used, answer: best, grounded };
}

const heat = (x) => {
  const a = Math.min(1, Math.abs(x) * 4);
  return x >= 0 ? `rgba(31,78,245,${0.1 + a * 0.9})` : `rgba(27,29,33,${0.06 + a * 0.6})`;
};
const pct = (x) => `${Math.round(x * 100)}%`;

export function initRag() {
  const form = $('#rag-form');
  if (!form) return;
  const input = $('#rag-q');
  const out = $('#rag-results');
  const stages = $$('#rag-stages li');
  const suggest = $('#rag-suggest');
  $('#rag-corpus-stat').textContent = `corpus: ${CORPUS.length} docs · ${CHUNKS.length} chunks`;

  suggest.innerHTML = SUGGESTED.map((q) => `<button type="button">${esc(q)}</button>`).join('');
  suggest.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    input.value = b.textContent;
    form.requestSubmit();
  });

  let runId = 0;
  const stage = (i) => stages.forEach((li, j) => { li.classList.toggle('active', j === i); li.classList.toggle('done', j < i); });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim().slice(0, 200);
    if (!q) return;
    const my = ++runId;
    const alive = () => my === runId;
    const r = retrieve(q);
    out.innerHTML = '';

    stage(0); await sleep(250); if (!alive()) return;
    stage(1);
    const left = document.createElement('div');
    const right = document.createElement('div');
    const grid = document.createElement('div');
    grid.className = 'rag-out';
    grid.append(left, right);
    out.append(grid);
    left.innerHTML = `
      <div class="card" style="margin-bottom:12px">
        <span class="k">Query processing</span>
        <div class="qp">
          <div><b>tokens</b>${r.base.map((t) => `<span class="tag">${esc(t)}</span>`).join(' ') || '<span class="muted">none</span>'}</div>
          <div><b>expansion</b>${r.added.map((t) => `<span class="tag acc">+${esc(t)}</span>`).join(' ') || '<span class="muted">none</span>'}</div>
        </div>
      </div>`;
    await sleep(350); if (!alive()) return;

    stage(2);
    const dims = Array.from(r.qvec.slice(0, 32));
    left.insertAdjacentHTML('beforeend', `
      <div class="card" style="margin-bottom:12px">
        <span class="k">Embedding · first 32 of ${DIM} dims (hashed n-grams, L2-normalized)</span>
        <div class="emb" role="img" aria-label="Query embedding heat strip">${dims.map((d) => `<i style="background:${heat(d)}" title="${d.toFixed(3)}"></i>`).join('')}</div>
      </div>`);
    await sleep(350); if (!alive()) return;

    stage(3); await sleep(300); if (!alive()) return;
    stage(4);
    const chunkCard = document.createElement('div');
    chunkCard.className = 'card';
    chunkCard.innerHTML = `<span class="k">Retrieved candidates · top ${r.candidates.length} by hybrid score (BM25 + vector)</span>
      <ol class="chunks">${r.candidates.map((s, i) => `
        <li class="chunk" data-key="${esc(s.c.key)}">
          <div class="chunk-head"><span class="src">${esc(s.c.doc.title)} · ${esc(s.c.section)}</span><span class="tag">${esc(s.c.doc.source)} · ${esc(s.c.key)}</span></div>
          <p>${esc(s.c.text)}</p>
          <div class="bars">
            <span>vector</span><span class="bar"><i style="width:${pct(Math.min(1, s.dense * 2.2))}"></i></span><span class="v">${s.dense.toFixed(2)}</span>
            <span>bm25</span><span class="bar k"><i style="width:${pct(s.sparseN)}"></i></span><span class="v">${s.sparse.toFixed(1)}</span>
            <span>rerank</span><span class="bar r"><i style="width:0%" data-w="${pct(s.rerank)}"></i></span><span class="v" data-v="${s.rerank.toFixed(2)}">—</span>
          </div>
        </li>`).join('')}</ol>`;
    left.append(chunkCard);
    await sleep(450); if (!alive()) return;

    stage(5);
    $$('.chunk', chunkCard).forEach((li) => {
      const i = li.querySelector('[data-w]');
      i.style.width = i.dataset.w;
      const v = li.querySelector('[data-v]');
      v.textContent = v.dataset.v;
    });
    // Reorder list by rerank score.
    const ol = chunkCard.querySelector('.chunks');
    r.candidates.forEach((s) => ol.append(ol.querySelector(`[data-key="${CSS.escape(s.c.key)}"]`)));
    await sleep(450); if (!alive()) return;

    stage(6);
    const sel = new Set(r.selected.map((s) => s.c.key));
    $$('.chunk', chunkCard).forEach((li) => { li.classList.toggle('selected', sel.has(li.dataset.key)); li.classList.toggle('dropped', !sel.has(li.dataset.key)); });
    right.innerHTML = `
      <div class="card" style="margin-bottom:12px">
        <span class="k">Context builder</span>
        <div class="ctx-budget">
          <div>${r.used} / ${TOKEN_BUDGET} tokens · ${r.selected.length} chunk(s) selected · threshold rerank ≥ ${MIN_RERANK}</div>
          <div class="ctx-meter" role="img" aria-label="Context token budget usage">
            <i class="sys" style="width:${pct(SYSTEM_TOKENS / TOKEN_BUDGET)}" title="system prompt"></i>
            ${r.selected.map((s) => `<i style="width:${pct(s.tokens / TOKEN_BUDGET)}" title="${esc(s.c.key)}"></i>`).join('')}
          </div>
          <div class="muted">${r.selected.map((s, i) => `[${i + 1}] ${esc(s.c.key)} (${s.tokens} tok)`).join(' · ') || 'No chunk passed the relevance threshold.'}</div>
        </div>
      </div>`;
    await sleep(450); if (!alive()) return;

    stage(7); await sleep(500); if (!alive()) return;
    stage(8);
    const answer = document.createElement('div');
    answer.className = 'answer';
    if (r.grounded) {
      answer.innerHTML = `
        <span class="k" style="font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase">Grounded answer <span class="tag ok">cited</span> <span class="tag sim">simulated LLM</span></span>
        <p style="margin-top:8px">${r.answer.map((s) => `${esc(s.text)}<sup><a href="#rag-cite-${s.cite}" aria-label="source ${s.cite}">[${s.cite}]</a></sup>`).join(' ')}</p>
        <ol class="cites">${r.selected.map((s, i) => `<li id="rag-cite-${i + 1}">[${i + 1}] ${esc(s.c.doc.title)} · ${esc(s.c.section)} · ${esc(s.c.doc.source)} (${esc(s.c.key)})</li>`).join('')}</ol>`;
    } else {
      answer.innerHTML = `
        <span class="k" style="font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase">Response <span class="tag err">insufficient context</span></span>
        <p style="margin-top:8px">I couldn't find this in the available documents, so I won't guess. Try rephrasing, or ask about remote access, incidents, expenses, data classification, AI usage, releases, passwords or onboarding.</p>
        <p class="small muted" style="margin:0">This is the expected behaviour: a grounded system refuses rather than hallucinating when retrieval finds nothing relevant.</p>`;
    }
    right.append(answer);
    stage(9);
  });
}
