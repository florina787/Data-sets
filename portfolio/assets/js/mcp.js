// MCP Tool Lab: simulates the JSON-RPC 2.0 exchange between an agent's MCP client and an
// MCP server (initialize → tools/list → tools/call). No network calls, no credentials.
import { $, $$, esc, sleep, jsonHtml } from './util.js';

const ICONS = {
  jira: '<path d="M12 3 4 11l8 8 8-8-8-8Zm0 5 3 3-3 3-3-3 3-3Z"/>',
  confluence: '<path d="M4 16c3-4 6-4 8-2s5 2 8-2M4 8c3 4 6 4 8 2s5-2 8 2"/>',
  sharepoint: '<circle cx="9" cy="9" r="5"/><circle cx="15" cy="15" r="5"/>',
  github: '<path d="M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6 0C6.8 2.8 5.8 3.1 5.8 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4.4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
  database: '<ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v14c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
  rest: '<path d="M8 7 3 12l5 5M16 7l5 5-5 5M14 4l-4 16"/>',
};

const TOOLS = [
  {
    id: 'jira', label: 'JIRA',
    ask: 'Which P1 bugs are still open for the October release?',
    tools: [
      { name: 'jira_search_issues', description: 'Search Jira issues with JQL. Read-only.', inputSchema: { type: 'object', properties: { jql: { type: 'string' }, maxResults: { type: 'integer', maximum: 50 } }, required: ['jql'] } },
      { name: 'jira_create_issue', description: 'Create a Jira issue. Requires user confirmation.', inputSchema: { type: 'object', properties: { project: { type: 'string' }, summary: { type: 'string' } }, required: ['project', 'summary'] } },
    ],
    pick: 'jira_search_issues', why: 'Read-only search matches the request; create_issue is a write action and is not needed.',
    args: { jql: 'project = NOVA AND priority = P1 AND fixVersion = "2026.10" AND status != Done', maxResults: 20 },
    result: { total: 2, issues: [{ key: 'NOVA-1412', summary: 'Checkout times out under load', status: 'In Progress' }, { key: 'NOVA-1437', summary: 'Token refresh fails for SSO users', status: 'To Do' }] },
    answer: 'Two P1 bugs are still open for the October release: NOVA-1412 (checkout timeouts, in progress) and NOVA-1437 (SSO token refresh, not started). Under the release process, both block the release unless the engineering director signs off an exception.',
  },
  {
    id: 'confluence', label: 'CONFLUENCE',
    ask: 'Find the latest on-call runbook for the payments team.',
    tools: [
      { name: 'confluence_search', description: 'CQL search across spaces the user can read.', inputSchema: { type: 'object', properties: { cql: { type: 'string' }, limit: { type: 'integer' } }, required: ['cql'] } },
      { name: 'confluence_get_page', description: 'Fetch a page body by id.', inputSchema: { type: 'object', properties: { pageId: { type: 'string' } }, required: ['pageId'] } },
    ],
    pick: 'confluence_search', why: 'There is no page id yet, so search first. The agent would call get_page next if more detail is needed.',
    args: { cql: 'space = PAY AND title ~ "on-call runbook" ORDER BY lastmodified DESC', limit: 3 },
    result: { results: [{ id: '884213', title: 'Payments On-call Runbook v4', lastModified: '2026-09-18' }, { id: '771002', title: 'Payments On-call Runbook v3 (archived)', lastModified: '2025-11-02' }] },
    answer: 'The current runbook is "Payments On-call Runbook v4" (updated 2026-09-18). v3 is archived. Do you want a summary of the escalation steps?',
  },
  {
    id: 'sharepoint', label: 'SHAREPOINT',
    ask: 'Get the current travel policy document.',
    tools: [
      { name: 'sharepoint_search_files', description: 'Search documents the user can access (permission-trimmed).', inputSchema: { type: 'object', properties: { query: { type: 'string' }, site: { type: 'string' } }, required: ['query'] } },
    ],
    pick: 'sharepoint_search_files', why: 'This is the only discovered tool that can locate documents, and its results are permission-trimmed for the user.',
    args: { query: 'travel policy', site: 'finance' },
    result: { files: [{ name: 'Expense & Travel Policy.docx', id: 'FIN-POL-003', modified: '2026-06-30', webUrl: 'https://sharepoint.example/finance/FIN-POL-003' }] },
    answer: 'The current policy is "Expense & Travel Policy" (FIN-POL-003, updated 2026-06-30). Economy class is the default for flights under six hours, and expenses are due within 30 days.',
  },
  {
    id: 'github', label: 'GITHUB',
    ask: 'Which PRs in payments-service are waiting for review?',
    tools: [
      { name: 'github_list_pull_requests', description: 'List pull requests for a repository.', inputSchema: { type: 'object', properties: { repo: { type: 'string' }, state: { enum: ['open', 'closed', 'all'] } }, required: ['repo'] } },
      { name: 'github_get_file', description: 'Read a file at a ref.', inputSchema: { type: 'object', properties: { repo: { type: 'string' }, path: { type: 'string' } }, required: ['repo', 'path'] } },
    ],
    pick: 'github_list_pull_requests', why: 'The request is about pull requests, so the file reader is irrelevant.',
    args: { repo: 'novagrid/payments-service', state: 'open' },
    result: { pull_requests: [{ number: 318, title: 'Idempotency keys for refunds', review: 'required', age_days: 4 }, { number: 322, title: 'Bump OTel SDK', review: 'required', age_days: 1 }] },
    answer: 'Two PRs are waiting for review in payments-service: #318 "Idempotency keys for refunds" (4 days old, the priority) and #322 "Bump OTel SDK" (1 day).',
  },
  {
    id: 'database', label: 'DATABASE',
    ask: 'How many support tickets were opened last week by region?',
    tools: [
      { name: 'sql_query_readonly', description: 'Run a parameterized SELECT on the analytics replica. DDL/DML rejected.', inputSchema: { type: 'object', properties: { sql: { type: 'string' }, params: { type: 'array' } }, required: ['sql'] } },
    ],
    pick: 'sql_query_readonly', why: 'Aggregation over tickets. The server enforces read-only access and parameterization.',
    args: { sql: 'SELECT region, COUNT(*) AS n FROM tickets WHERE opened_at >= $1 GROUP BY region ORDER BY n DESC', params: ['2026-09-26'] },
    result: { columns: ['region', 'n'], rows: [['EMEA', 128], ['NA', 97], ['APAC', 64]], rowCount: 3 },
    answer: 'Last week: EMEA 128, NA 97 and APAC 64 tickets (289 total). These are synthetic sample values.',
  },
  {
    id: 'rest', label: 'REST API',
    ask: 'What is the status of the order-service deployment?',
    tools: [
      { name: 'deploy_get_status', description: 'GET /v1/deployments/{service} on the internal deploy API.', inputSchema: { type: 'object', properties: { service: { type: 'string' }, env: { enum: ['staging', 'prod'] } }, required: ['service'] } },
    ],
    pick: 'deploy_get_status', why: 'The server wraps the REST endpoint as a typed tool with a narrow, read-only scope.',
    args: { service: 'order-service', env: 'prod' },
    result: { service: 'order-service', env: 'prod', version: '4.12.1', status: 'healthy', rollout: '100%', deployedAt: '2026-10-01T09:14:00Z' },
    answer: 'order-service 4.12.1 is fully rolled out (100%) in prod and healthy. It was deployed on 2026-10-01 at 09:14 UTC.',
  },
];

export function initMcp() {
  const toolsEl = $('#mcp-tools');
  if (!toolsEl) return;
  const log = $('#mcp-log');
  const phases = $$('#mcp-phases li');
  const title = $('#mcp-title-run');
  const replay = $('#mcp-replay');
  let runId = 0;
  let current = null;

  toolsEl.innerHTML = TOOLS.map((t) => `
    <button type="button" class="tool" data-tool="${t.id}" aria-pressed="false">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[t.id]}</svg>
      ${t.label}
    </button>`).join('');

  const layers = (active) => $$('#mcp-stack .layer').forEach((l) => l.classList.toggle('active', active.includes(l.dataset.layer)));
  const phase = (i) => phases.forEach((li, j) => { li.classList.toggle('active', j === i); li.classList.toggle('done', j < i); });
  const msg = (from, to, label, body) => {
    const li = document.createElement('li');
    li.innerHTML = `<div class="dir"><span><b>${esc(from)}</b> → ${esc(to)}</span><span>${esc(label)}</span></div>${body}`;
    log.append(li);
    log.scrollTop = log.scrollHeight;
  };
  const rpc = (obj) => `<pre>${jsonHtml(obj)}</pre>`;
  const say = (text) => `<div class="say">${esc(text)}</div>`;

  async function simulate(t) {
    const my = ++runId;
    const alive = () => my === runId;
    current = t;
    replay.disabled = false;
    $$('.tool', toolsEl).forEach((b) => { b.setAttribute('aria-pressed', String(b.dataset.tool === t.id)); b.classList.remove('active'); });
    title.textContent = `${t.label} · simulated tool call`;
    log.innerHTML = '';
    let id = 1;

    msg('user', 'agent', 'request', say(t.ask));
    layers(['agent']);
    phase(0);
    await sleep(500); if (!alive()) return;
    layers(['client', 'server']);
    msg('mcp client', 'mcp server', 'initialize', rpc({ jsonrpc: '2.0', id: id++, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'copilot-agent', version: '1.0.0' } } }));
    await sleep(500); if (!alive()) return;
    msg('mcp client', 'mcp server', 'tools/list', rpc({ jsonrpc: '2.0', id: id, method: 'tools/list' }));
    await sleep(550); if (!alive()) return;
    msg('mcp server', 'mcp client', 'result', rpc({ jsonrpc: '2.0', id: id++, result: { tools: t.tools } }));
    await sleep(600); if (!alive()) return;

    phase(1);
    layers(['llm', 'agent']);
    msg('llm', 'agent', 'tool selection', say(`Selected ${t.pick}. ${t.why}`));
    await sleep(800); if (!alive()) return;

    phase(2);
    layers(['client', 'server']);
    $(`.tool[data-tool="${t.id}"]`, toolsEl).classList.add('active');
    msg('mcp client', 'mcp server', 'tools/call', rpc({ jsonrpc: '2.0', id: id, method: 'tools/call', params: { name: t.pick, arguments: t.args } }));
    await sleep(900); if (!alive()) return;

    phase(3);
    msg('mcp server', 'mcp client', 'result · simulated data', rpc({ jsonrpc: '2.0', id: id, result: { content: [{ type: 'text', text: JSON.stringify(t.result) }], structuredContent: t.result, isError: false } }));
    $(`.tool[data-tool="${t.id}"]`, toolsEl).classList.remove('active');
    await sleep(700); if (!alive()) return;

    phase(4);
    layers(['llm', 'agent']);
    msg('agent', 'user', 'response', say(t.answer));
    await sleep(400); if (!alive()) return;
    layers([]);
    phase(5);
  }

  toolsEl.addEventListener('click', (e) => {
    const b = e.target.closest('[data-tool]');
    if (b) simulate(TOOLS.find((t) => t.id === b.dataset.tool));
  });
  replay.addEventListener('click', () => current && simulate(current));
}
