// Architecture decisions: accessible tabs (roving tabindex, arrow keys, Home/End).
import { $, esc } from './util.js';

const DECISIONS = [
  {
    t: 'RAG vs Fine-Tuning',
    use: ['Knowledge changes often or must be cited', 'Access control differs per user/document', 'You need answers traceable to sources'],
    avoid: ['The gap is behaviour or format, not knowledge', 'Latency budget cannot afford retrieval', 'The corpus is tiny and static (put it in the prompt)'],
    trade: ['RAG: fresh, auditable, permission-aware, but retrieval quality caps answer quality', 'Fine-tuning: consistent style and format and shorter prompts, but stale knowledge and a training pipeline to own'],
    verdict: 'Default: RAG for knowledge, fine-tuning for behaviour. Combine them when a small tuned model has to follow a strict output format over retrieved context.',
  },
  {
    t: 'LangChain vs LangGraph',
    use: ['LangChain: linear chains, integrations, quick composition', 'LangGraph: stateful agents, branching, loops, human-in-the-loop, checkpoints'],
    avoid: ['LangChain alone when control flow has cycles or needs resumption', 'LangGraph for a single prompt → parse step'],
    trade: ['Graphs make routing explicit and testable at the cost of more upfront modelling', 'Either way, keep business logic in plain functions so the framework stays replaceable'],
    verdict: 'Default: LangGraph for anything agentic in production. Use LangChain components inside the nodes.',
  },
  {
    t: 'Single Agent vs Multi-Agent',
    use: ['Single: one domain, fewer than ~10 tools, tight latency', 'Multi: distinct skills with different tools, prompts or permissions'],
    avoid: ['Multi-agent "because it\'s cool": every hop adds latency, cost and failure surface', 'A single agent with 40 tools and a prompt that tries to do everything'],
    trade: ['Specialization improves tool selection and testability', 'Coordination overhead, harder debugging, and more tokens'],
    verdict: 'Default: start with a single agent and a good tool design. Split it when evaluation shows tool-selection errors or the agents need different permissions.',
  },
  {
    t: 'Vector Search vs Hybrid Search',
    use: ['Vector: paraphrase-heavy natural language queries', 'Hybrid: IDs, codes, product names, acronyms and mixed queries (most enterprise data)'],
    avoid: ['Vector-only over ticket keys, error codes or SKUs', 'Hybrid without score normalization or rank fusion'],
    trade: ['Hybrid improves recall on exact terms but adds an index and fusion tuning', 'Rerankers recover precision at extra latency'],
    verdict: 'Default: hybrid (BM25 + dense) with reciprocal rank fusion, then a reranker on the top candidates.',
  },
  {
    t: 'REST vs MCP',
    use: ['REST: service-to-service integration with fixed callers', 'MCP: exposing tools to LLM agents with discoverable schemas across many clients'],
    avoid: ['MCP as a replacement for your service APIs', 'Hand-writing a bespoke tool adapter per agent when an MCP server could be shared'],
    trade: ['MCP standardizes discovery and invocation for agents, but adds a server to secure and operate', 'REST is mature and universal but has no agent-facing contract'],
    verdict: 'Default: keep REST for systems and put an MCP server in front for agents, with auth, scopes and audit at that layer.',
  },
  {
    t: 'Serverless vs Containers',
    use: ['Serverless: spiky, event-driven, short tasks (ingestion triggers, webhooks)', 'Containers: long-lived streaming, GPU or model hosting, steady load'],
    avoid: ['Serverless for long LLM streams hitting timeouts or cold starts', 'Containers for a nightly 2-minute job'],
    trade: ['Serverless: no ops, scales to zero, but limits on duration, memory and connections', 'Containers: control and predictability, but you own scaling and patching'],
    verdict: 'Default: containers for the API and agents, serverless for ingestion and event glue.',
  },
  {
    t: 'FAISS vs Managed Vector DB',
    use: ['FAISS: embedded, read-heavy, single-tenant, rebuildable indexes', 'Managed: multi-tenant, frequent upserts, metadata filtering, HA'],
    avoid: ['FAISS when you need per-document ACL filters and live updates', 'Managed DB for a 50k-chunk prototype'],
    trade: ['FAISS: fast and free, but persistence, filtering and replication are on you', 'Managed: operational features and cost or lock-in'],
    verdict: 'Default: FAISS or Chroma to prototype. In production, a managed or self-hosted DB with native metadata filtering for permissions.',
  },
  {
    t: 'Synchronous vs Asynchronous',
    use: ['Sync + streaming: interactive chat with a p95 under ~10s', 'Async (queue + callback): long agent tasks, batch enrichment, document ingestion'],
    avoid: ['Holding HTTP connections open for multi-minute agent runs', 'Async for simple Q&A where users expect immediate tokens'],
    trade: ['Async improves resilience and throughput but needs job state, retries and notifications', 'Sync is simpler but couples user latency to the slowest dependency'],
    verdict: 'Default: stream synchronous answers. Move anything long-running to a queue with status polling or webhooks.',
  },
];

export function initDecisions() {
  const tabs = $('#dec-tabs');
  const panel = $('#dec-panel');
  if (!tabs || !panel) return;
  tabs.innerHTML = DECISIONS.map((d, i) => `<button type="button" role="tab" id="dec-tab-${i}" aria-controls="dec-panel" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">${esc(d.t)}</button>`).join('');
  const list = (items) => `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;

  function select(i, focus = false) {
    const btns = tabs.querySelectorAll('[role="tab"]');
    btns.forEach((b, j) => { b.setAttribute('aria-selected', String(j === i)); b.tabIndex = j === i ? 0 : -1; });
    if (focus) { btns[i].focus(); btns[i].scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    const d = DECISIONS[i];
    panel.setAttribute('aria-labelledby', `dec-tab-${i}`);
    panel.querySelector('.panel-body').innerHTML = `
      <h3>${esc(d.t)}</h3>
      <div class="dec-cols">
        <div class="card use"><span class="k">Use when</span>${list(d.use)}</div>
        <div class="card avoid"><span class="k">Avoid when</span>${list(d.avoid)}</div>
        <div class="card trade"><span class="k">Trade-offs</span>${list(d.trade)}</div>
      </div>
      <p class="verdict">${esc(d.verdict)}</p>`;
  }

  tabs.addEventListener('click', (e) => {
    const b = e.target.closest('[role="tab"]');
    if (b) select(Number(b.id.split('-').pop()));
  });
  tabs.addEventListener('keydown', (e) => {
    const cur = Number(document.activeElement?.id?.split('-').pop() || 0);
    const n = DECISIONS.length;
    const map = { ArrowDown: cur + 1, ArrowRight: cur + 1, ArrowUp: cur - 1, ArrowLeft: cur - 1, Home: 0, End: n - 1 };
    if (e.key in map) { e.preventDefault(); select((map[e.key] + n) % n, true); }
  });
  select(0);
}
