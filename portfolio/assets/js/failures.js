// "When AI fails": failure modes mapped to resilience patterns, filterable by pattern.
import { $, esc } from './util.js';

const PATTERNS = ['Retry', 'Exponential backoff', 'Circuit breaker', 'Fallback model', 'Caching', 'Validation', 'Max agent iterations', 'Human escalation'];

const FAILURES = [
  { name: 'LLM timeout', what: 'Provider latency spikes or the request hangs past the stage budget.', fix: ['Retry', 'Exponential backoff', 'Fallback model', 'Caching'] },
  { name: 'API failure', what: '5xx or network errors from the model provider or an internal service.', fix: ['Retry', 'Exponential backoff', 'Circuit breaker', 'Fallback model'] },
  { name: 'Tool failure', what: 'An enterprise system (Jira, DB) errors out or rejects the call.', fix: ['Retry', 'Circuit breaker', 'Validation', 'Human escalation'] },
  { name: 'Retrieval failure', what: 'Vector store unavailable or slow. Search returns errors.', fix: ['Retry', 'Circuit breaker', 'Caching', 'Fallback model'] },
  { name: 'Empty context', what: 'Nothing relevant was retrieved, so the model would have to guess.', fix: ['Validation', 'Human escalation'] },
  { name: 'Hallucination', what: 'Fluent claims not supported by the provided evidence.', fix: ['Validation', 'Human escalation'] },
  { name: 'Rate limiting', what: '429s from the provider under burst load or tenant spikes.', fix: ['Exponential backoff', 'Caching', 'Fallback model', 'Circuit breaker'] },
  { name: 'Token overflow', what: 'Prompt + context + history exceed the context window or budget.', fix: ['Validation', 'Fallback model'] },
  { name: 'Agent loop', what: 'The agent repeats tool calls or replans without converging.', fix: ['Max agent iterations', 'Human escalation', 'Validation'] },
  { name: 'Malformed tool response', what: 'The tool returns an unexpected schema, or the LLM emits invalid tool arguments.', fix: ['Validation', 'Retry', 'Human escalation'] },
];

const DETAIL = {
  'Empty context': 'Detect low retrieval scores → rewrite query once → otherwise answer "not found" with closest sources.',
  Hallucination: 'Groundedness check + citation verification; unsupported claims removed or answer downgraded.',
  'Token overflow': 'Count tokens before calling; trim lowest-ranked chunks, summarize history, or route to a long-context model.',
  'Agent loop': 'Hard iteration and token ceilings; detect repeated (tool, args) pairs; hand off to a human with the trace.',
};

export function initFailures() {
  const grid = $('#fail-grid');
  const bar = $('#fail-patterns');
  if (!grid || !bar) return;
  bar.innerHTML = ['All', ...PATTERNS].map((p, i) => `<button type="button" data-p="${esc(p)}" aria-pressed="${i === 0}">${esc(p)}</button>`).join('');
  grid.innerHTML = FAILURES.map((f) => `
    <article class="fail" data-fix="${esc(f.fix.join('|'))}">
      <h3>${esc(f.name)}</h3>
      <p>${esc(f.what)}${DETAIL[f.name] ? `<br><span class="muted">${esc(DETAIL[f.name])}</span>` : ''}</p>
      <div class="fix">${f.fix.map((x) => `<span class="tag acc">${esc(x)}</span>`).join('')}</div>
    </article>`).join('');

  bar.addEventListener('click', (e) => {
    const b = e.target.closest('[data-p]');
    if (!b) return;
    const p = b.dataset.p;
    bar.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    grid.querySelectorAll('.fail').forEach((card) => {
      const has = p === 'All' || card.dataset.fix.split('|').includes(p);
      card.classList.toggle('dim', !has);
      card.classList.toggle('hit', has && p !== 'All');
    });
  });
}
