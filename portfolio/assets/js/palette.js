// Ctrl/Cmd + K command palette: accessible combobox + listbox with fuzzy filtering.
import { contactLinks } from './config.js';
import { esc, toast } from './util.js';

export function initPalette(ctx) {
  const backdrop = document.getElementById('kbar');
  const input = document.getElementById('kbar-input');
  const list = document.getElementById('kbar-list');
  if (!backdrop || !input || !list) return;

  const external = (key, label) => () => {
    const c = contactLinks()[key];
    if (!c.href) { toast(`${label} not configured yet: set it in assets/js/config.js`); return; }
    if (c.href.startsWith('mailto:')) window.location.href = c.href;
    else window.open(c.href, '_blank', 'noopener,noreferrer');
  };

  const COMMANDS = [
    { label: 'Go to Projects', group: 'Navigate', icon: '→', run: () => ctx.navigate('projects') },
    { label: 'Open Agentic AI Lab', group: 'Demo', icon: '◆', run: () => ctx.navigate('agent-lab') },
    { label: 'Open RAG Explorer', group: 'Demo', icon: '◆', run: () => ctx.navigate('rag') },
    { label: 'Open MCP Tool Lab', group: 'Demo', icon: '◆', run: () => ctx.navigate('mcp') },
    { label: 'View Architecture', group: 'Navigate', icon: '→', keywords: 'system design case study copilot', run: () => ctx.navigate('case-study') },
    { label: 'View Tech Stack', group: 'Navigate', icon: '→', keywords: 'skills map', run: () => ctx.navigate('skills') },
    { label: 'View Experience', group: 'Navigate', icon: '→', run: () => ctx.navigate('experience') },
    { label: 'View Observability Dashboard', group: 'Navigate', icon: '→', keywords: 'metrics telemetry', run: () => ctx.navigate('observability') },
    { label: 'View Security Design', group: 'Navigate', icon: '→', run: () => ctx.navigate('security') },
    { label: 'View Architecture Decisions', group: 'Navigate', icon: '→', keywords: 'trade-offs adr', run: () => ctx.navigate('decisions') },
    { label: 'View GitHub', group: 'Link', icon: '↗', run: external('github', 'GitHub') },
    { label: 'View LinkedIn', group: 'Link', icon: '↗', run: external('linkedin', 'LinkedIn') },
    { label: 'Contact Florina', group: 'Link', icon: '@', keywords: 'email hire', run: () => ctx.navigate('contact') },
    { label: 'Open Terminal', group: 'Tool', icon: '$', run: () => { ctx.navigate('top'); setTimeout(() => document.getElementById('term-input')?.focus(), 350); } },
    { label: 'Switch to Recruiter Mode', group: 'View', icon: '◐', run: () => ctx.setView('recruiter', { announce: true }), when: () => ctx.getView() !== 'recruiter' },
    { label: 'Switch to Engineer Mode', group: 'View', icon: '◑', run: () => ctx.setView('engineer', { announce: true }), when: () => ctx.getView() !== 'engineer' },
  ];

  let results = [];
  let active = 0;
  let lastFocus = null;

  // Subsequence fuzzy score: rewards consecutive matches and word starts.
  function score(cmd, q) {
    if (!q) return 1;
    const hay = `${cmd.label} ${cmd.keywords || ''} ${cmd.group}`.toLowerCase();
    if (hay.includes(q)) return 100 - hay.indexOf(q);
    let s = 0; let hi = 0; let streak = 0;
    for (const ch of q) {
      const idx = hay.indexOf(ch, hi);
      if (idx === -1) return 0;
      streak = idx === hi ? streak + 1 : 0;
      s += 1 + streak * 2 + (idx === 0 || hay[idx - 1] === ' ' ? 3 : 0);
      hi = idx + 1;
    }
    return s;
  }

  function render() {
    const q = input.value.trim().toLowerCase();
    results = COMMANDS.filter((c) => !c.when || c.when())
      .map((c) => ({ c, s: score(c, q) }))
      .filter((r) => r.s > 0)
      .sort((a, b) => b.s - a.s)
      .map((r) => r.c);
    active = Math.min(active, Math.max(0, results.length - 1));
    if (!results.length) {
      list.innerHTML = '<li class="empty" role="option" aria-disabled="true" aria-selected="false">No matching commands</li>';
      input.removeAttribute('aria-activedescendant');
      return;
    }
    list.innerHTML = results
      .map((c, i) => `<li id="kbar-opt-${i}" role="option" aria-selected="${i === active}" data-i="${i}"><span class="ico" aria-hidden="true">${esc(c.icon)}</span>${esc(c.label)}<span class="grp">${esc(c.group)}</span></li>`)
      .join('');
    input.setAttribute('aria-activedescendant', `kbar-opt-${active}`);
    list.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }

  function open() {
    lastFocus = document.activeElement;
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
    input.value = '';
    active = 0;
    render();
    input.focus();
  }
  function close({ restore = true } = {}) {
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden', 'true');
    if (restore && lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }
  function run(i) {
    const cmd = results[i];
    if (!cmd) return;
    close({ restore: false });
    cmd.run();
  }

  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (backdrop.classList.contains('open')) close(); else open();
    }
  });
  document.querySelectorAll('[data-open-palette]').forEach((b) => b.addEventListener('click', open));

  input.addEventListener('input', () => { active = 0; render(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % Math.max(results.length, 1); render(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + results.length) % Math.max(results.length, 1); render(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(active); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'Tab') { e.preventDefault(); } // focus stays in the dialog
  });
  list.addEventListener('mousemove', (e) => {
    const li = e.target.closest('[data-i]');
    if (li && Number(li.dataset.i) !== active) { active = Number(li.dataset.i); render(); }
  });
  list.addEventListener('click', (e) => { const li = e.target.closest('[data-i]'); if (li) run(Number(li.dataset.i)); });
  backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop) close(); });
}
