// Agentic AI Lab: a deterministic simulation of a supervisor-style multi-agent workflow.
import { $, $$, esc, sleep } from './util.js';

const AGENTS = {
  orchestrator: {
    name: 'Orchestrator',
    purpose: 'Classifies intent, plans which agents run (and in what order), enforces budgets and decides when the task is complete.',
    input: 'User question, conversation state, user identity and roles.',
    output: 'An execution plan (ordered/parallel agent calls) and the shared state passed between agents.',
    tools: ['intent classifier', 'planner', 'state checkpointer', 'budget tracker'],
    failure: 'Max-iteration and token ceilings stop loops; low-confidence intent falls back to a safe default route; a step that fails twice escalates to a human or returns a partial answer.',
  },
  retrieval: {
    name: 'Retrieval Agent',
    purpose: 'Finds the evidence: hybrid search over permitted documents, reranked and packed into a context budget.',
    input: 'Rewritten query, user ACL principals, metadata filters (source, date).',
    output: 'Ranked chunks with doc_id, chunk_id, source URL and relevance scores.',
    tools: ['BM25 index', 'vector store', 'cross-encoder reranker', 'ACL filter'],
    failure: 'Vector store timeout → degrade to keyword-only search; empty results → query rewrite once, then report "no evidence" rather than guess.',
  },
  reasoning: {
    name: 'Reasoning Agent',
    purpose: 'Synthesizes evidence and tool results into findings: compares, summarizes, identifies risks and actions.',
    input: 'Retrieved chunks, tool results, the question and the plan.',
    output: 'Structured findings, each linked to the evidence IDs that support it.',
    tools: ['LLM (structured output)', 'calculator', 'schema validator'],
    failure: 'Malformed output → re-ask with the validation error (once); LLM timeout → fallback model; contradictory evidence is surfaced, not resolved silently.',
  },
  tool: {
    name: 'Tool Agent',
    purpose: 'Calls enterprise systems (Jira, GitHub, databases) through MCP/REST with typed, validated arguments.',
    input: 'Tool intents from the plan, user-scoped credentials (on-behalf-of token).',
    output: 'Normalized tool results with status, latency and provenance.',
    tools: ['MCP client', 'Jira', 'GitHub', 'SQL (read-only)', 'REST APIs'],
    failure: 'Retry with exponential backoff + jitter on transient errors, circuit breaker per tool, idempotency keys for writes, and human confirmation before any side effect.',
  },
  validator: {
    name: 'Validator',
    purpose: 'Final gate: verifies citations, checks grounding, redacts PII and scores confidence before anything reaches the user.',
    input: 'Draft answer, the exact context and tool results that were available.',
    output: 'Approved answer with citations, or a safe "insufficient evidence" response.',
    tools: ['citation checker', 'groundedness scorer', 'PII redactor', 'policy filter'],
    failure: 'Unsupported claims are removed or the answer is downgraded; citation to unseen sources fails validation; repeated failure routes to human review.',
  },
};

const SCENARIOS = [
  {
    id: 'release',
    label: 'Which open issues block the October release, and what does the runbook say about P1s?',
    intent: 'issue_lookup + policy',
    plan: ['retrieval', 'tool', 'reasoning'],
    retrieval: '3 chunks from "Incident Severity & On-call Runbook" (score 0.82 / 0.77 / 0.64)',
    tool: 'jira.search_issues(jql="fixVersion = 2026.10 AND status != Done AND priority = P1") → 2 issues',
    reasoning: '2 blocking P1 issues; runbook requires 15-min acknowledgement and an incident commander',
    response: 'Answer with 3 citations + 2 Jira links',
  },
  {
    id: 'policy',
    label: 'Summarize the remote-access policy for contractors.',
    intent: 'summarization',
    plan: ['retrieval', 'reasoning'],
    retrieval: '4 chunks from "Remote Access & VPN Policy" (score 0.88 / 0.81 / 0.73 / 0.58)',
    reasoning: '5 key rules extracted; contractor-specific clause highlighted',
    response: 'Summary with 4 citations',
  },
  {
    id: 'prs',
    label: 'List PRs waiting on review in the payments service.',
    intent: 'tool_query',
    plan: ['tool', 'reasoning'],
    tool: 'github.list_pull_requests(repo="payments-service", state="open", review="required") → 3 PRs',
    reasoning: 'Grouped by age; oldest waiting 4 days',
    response: 'Table of 3 PRs with links',
  },
];

const STATES = ['IDLE', 'ROUTING', 'RETRIEVING', 'REASONING', 'VALIDATING', 'COMPLETE'];

export function initAgentLab() {
  const root = $('#agent-flow');
  if (!root) return;
  const select = $('#agent-scenario');
  const runBtn = $('#agent-run');
  const resetBtn = $('#agent-reset');
  const failBox = $('#agent-fail');
  const trace = $('#agent-trace');
  const detailBody = $('#agent-detail-body');
  const detailTag = $('#agent-detail-tag');

  select.innerHTML = SCENARIOS.map((s) => `<option value="${s.id}">${esc(s.label)}</option>`).join('');

  let runId = 0;
  let clock = 0;

  const node = (k) => root.querySelector(`[data-node="${k}"]`);
  const wire = (k) => root.querySelector(`[data-wire="${k}"]`);

  function setNode(k, cls, label) {
    const n = node(k);
    if (!n) return;
    n.classList.remove('active', 'done', 'failed');
    if (cls) n.classList.add(cls);
    n.querySelector('.node-state').textContent = label;
  }
  function setWire(keys, mode) {
    keys.forEach((k) => {
      const w = wire(k);
      if (!w) return;
      w.classList.remove('on', 'flowing');
      if (mode) w.classList.add(mode);
    });
  }
  function setState(s) {
    const idx = STATES.indexOf(s);
    $$('#agent-states span').forEach((el, i) => {
      el.classList.toggle('now', i === idx);
      el.classList.toggle('past', i < idx);
    });
  }
  function log(who, msg, cls = '', dt = 0) {
    clock += dt;
    const li = document.createElement('li');
    li.innerHTML = `<span class="t">${String(Math.round(clock)).padStart(5, '0')}ms</span><span class="who">${esc(who)}</span><span class="msg ${cls}">${esc(msg)}</span>`;
    trace.append(li);
    trace.scrollTop = trace.scrollHeight;
  }

  function reset() {
    runId += 1;
    clock = 0;
    ['orchestrator', 'retrieval', 'reasoning', 'tool', 'validator'].forEach((k) => setNode(k, null, 'idle'));
    setNode('user', null, 'question');
    setNode('response', null, '—');
    $$('[data-wire]', root).forEach((w) => w.classList.remove('on', 'flowing'));
    setState('IDLE');
    trace.innerHTML = '';
    log('system', 'Ready. Choose a scenario and run the workflow.');
    runBtn.disabled = false;
  }

  async function run() {
    reset();
    const my = runId;
    const alive = () => my === runId;
    const scenario = SCENARIOS.find((s) => s.id === select.value) || SCENARIOS[0];
    const inject = failBox.checked;
    trace.innerHTML = '';
    runBtn.disabled = true;

    log('user', scenario.label);
    setNode('user', 'done', 'sent');
    setWire(['user'], 'flowing');
    await sleep(500); if (!alive()) return;
    setWire(['user'], 'on');

    setState('ROUTING');
    setNode('orchestrator', 'active', 'routing');
    log('orchestrator', `intent=${scenario.intent} · plan=[${scenario.plan.join(' → ')}] · budget=8k tokens, max_iter=6`, '', 180);
    await sleep(900); if (!alive()) return;
    setNode('orchestrator', 'done', 'plan ready');
    setWire(['orch', 'bus-down'], 'on');

    // Evidence gathering: retrieval and tool calls run in parallel.
    const gather = scenario.plan.filter((a) => a === 'retrieval' || a === 'tool');
    setState('RETRIEVING');
    gather.forEach((a) => {
      setWire([`to-${a}`], 'flowing');
      setNode(a, 'active', a === 'tool' ? 'calling tools' : 'retrieving');
    });
    await sleep(700); if (!alive()) return;

    for (const a of gather) {
      if (a === 'tool' && inject) {
        log('tool', 'jira MCP call → timeout after 3000ms', 'bad', 3000);
        setNode('tool', 'failed', 'timeout · retry 1');
        await sleep(700); if (!alive()) return;
        log('tool', 'retry 1/3 after backoff 400ms (+jitter) · circuit=closed', '', 400);
        setNode('tool', 'active', 'retrying');
        await sleep(800); if (!alive()) return;
        log('tool', scenario.tool, 'good', 640);
      } else if (a === 'retrieval' && inject && !gather.includes('tool')) {
        log('retrieval', 'vector store timeout → degrade to keyword-only (BM25) search', 'bad', 1200);
        setNode('retrieval', 'failed', 'degraded');
        await sleep(800); if (!alive()) return;
        setNode('retrieval', 'active', 'bm25 fallback');
        log('retrieval', `${scenario.retrieval.replace(/\(score[^)]*\)/, '(keyword scores)')}`, 'good', 150);
      } else {
        log(a, scenario[a], 'good', a === 'tool' ? 420 : 260);
      }
      setNode(a, 'done', a === 'tool' ? 'results ✓' : 'evidence ✓');
      setWire([`to-${a}`], 'on');
      setWire([`from-${a}`], 'on');
      await sleep(350); if (!alive()) return;
    }

    setState('REASONING');
    setWire(['to-reasoning'], 'flowing');
    setNode('reasoning', 'active', 'reasoning');
    log('reasoning', 'synthesizing findings from evidence (structured output)', '', 120);
    await sleep(1000); if (!alive()) return;
    log('reasoning', scenario.reasoning, 'good', 1350);
    setNode('reasoning', 'done', 'findings ✓');
    setWire(['to-reasoning', 'from-reasoning', 'bus-up'], 'on');
    setWire(['to-validator'], 'flowing');

    setState('VALIDATING');
    setNode('validator', 'active', 'validating');
    await sleep(800); if (!alive()) return;
    log('validator', 'citations: all referenced IDs present in context ✓', 'good', 60);
    log('validator', 'groundedness: claims supported ✓ · PII: none detected ✓', 'good', 90);
    setNode('validator', 'done', 'approved');
    setWire(['to-validator'], 'on');
    setWire(['to-response'], 'flowing');
    await sleep(500); if (!alive()) return;

    setWire(['to-response'], 'on');
    setNode('response', 'done', 'delivered');
    setState('COMPLETE');
    log('response', `${scenario.response}${inject ? ' · 1 recovered failure recorded in trace' : ''}`, 'good', 40);
    runBtn.disabled = false;
  }

  function showDetail(key) {
    const a = AGENTS[key];
    if (!a) return;
    $$('button.node', root).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.node === key)));
    detailTag.textContent = key;
    detailBody.innerHTML = `
      <h3>${esc(a.name)}</h3>
      <dl>
        <div><dt>Purpose</dt><dd>${esc(a.purpose)}</dd></div>
        <div><dt>Input</dt><dd>${esc(a.input)}</dd></div>
        <div><dt>Output</dt><dd>${esc(a.output)}</dd></div>
        <div><dt>Tools</dt><dd class="chips">${a.tools.map((t) => `<span class="tag">${esc(t)}</span>`).join('')}</dd></div>
        <div><dt>Failure handling</dt><dd>${esc(a.failure)}</dd></div>
      </dl>`;
  }

  $$('button.node', root).forEach((b) => b.addEventListener('click', () => showDetail(b.dataset.node)));
  runBtn.addEventListener('click', run);
  resetBtn.addEventListener('click', reset);
  showDetail('orchestrator');
}
