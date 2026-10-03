// Entry point: wires shared UI and lazy-loads each interactive demo when it nears the viewport.
import { CONFIG, contactLinks, repoLink, blobLink } from './config.js';
import { initTerminal } from './terminal.js';
import { initPalette } from './palette.js';
import { initAnalytics } from './analytics.js';
import { $, $$, toast, prefersReducedMotion, goTo } from './util.js';

const VIEW_KEY = 'fr.view';

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode: ignore */ }
}

export function setView(view, { announce = false } = {}) {
  if (view !== 'engineer' && view !== 'recruiter') return;
  document.documentElement.dataset.view = view;
  $$('[data-view-btn]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.viewBtn === view)));
  storageSet(VIEW_KEY, view);
  if (announce) toast(view === 'recruiter' ? 'Recruiter mode: concise profile view' : 'Engineer mode: full technical detail');
  window.dispatchEvent(new CustomEvent('viewchange', { detail: view }));
}

export const getView = () => document.documentElement.dataset.view || 'engineer';

function initViewToggle() {
  const saved = storageGet(VIEW_KEY);
  setView(saved === 'recruiter' ? 'recruiter' : 'engineer');
  $$('[data-view-btn]').forEach((btn) =>
    btn.addEventListener('click', () => {
      setView(btn.dataset.viewBtn, { announce: true });
      if (btn.closest('#profile')) document.getElementById('approach')?.scrollIntoView();
    }),
  );
}

function initNav() {
  const toggle = $('.nav-toggle');
  const nav = $('#primary-nav');
  const close = () => { nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); };
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('open')) { close(); toggle.focus(); }
  });

  // Highlight the nav entry for the section currently in view.
  const links = new Map($$('#primary-nav a').map((a) => [a.getAttribute('href').slice(1), a]));
  const spy = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      links.forEach((a) => a.removeAttribute('aria-current'));
      links.get(entry.target.id)?.setAttribute('aria-current', 'true');
    }
  }, { rootMargin: '-45% 0px -50% 0px' });
  $$('main > section[id]').forEach((el) => spy.observe(el));
}

function linkEl(href, label) {
  if (!href) {
    const span = document.createElement('span');
    span.className = 'placeholder-link';
    span.title = 'Set GITHUB_USERNAME in assets/js/config.js';
    span.textContent = `${label}: GITHUB_USERNAME`;
    return span;
  }
  const a = document.createElement('a');
  a.className = 'btn sm ghost';
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.textContent = `${label} ↗`;
  return a;
}

function initContactLinks() {
  const links = contactLinks();
  $$('[data-contact]').forEach((el) => {
    const c = links[el.dataset.contact];
    el.querySelector('.v').textContent = c.display;
    if (c.href) {
      el.href = c.href;
      if (!c.href.startsWith('mailto:')) { el.target = '_blank'; el.rel = 'noopener noreferrer'; }
    } else {
      el.removeAttribute('href');
      el.classList.add('is-placeholder');
      el.setAttribute('aria-label', `${c.label}: placeholder, not configured yet`);
    }
  });
  $$('[data-repo-link]').forEach((el) => el.append(linkEl(repoLink(el.dataset.repoLink), el.dataset.repoLabel)));
  $$('[data-blob-link]').forEach((el) => el.append(linkEl(blobLink(el.dataset.blobLink), el.dataset.repoLabel)));
  const year = $('#year');
  if (year) year.textContent = String(new Date().getFullYear());
}

function initReveal() {
  const els = $$('.reveal');
  if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
    els.forEach((el) => el.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  els.forEach((el) => io.observe(el));
  document.documentElement.classList.add('reveal-ready');
}

function initPipeline() {
  const steps = $$('#pipeline li');
  if (!steps.length || prefersReducedMotion()) return;
  let i = 0;
  let timer = null;
  const tick = () => { steps.forEach((s, j) => s.classList.toggle('lit', j === i)); i = (i + 1) % steps.length; };
  const io = new IntersectionObserver(([e]) => {
    if (e.isIntersecting && !timer) { tick(); timer = setInterval(tick, 900); }
    else if (!e.isIntersecting && timer) { clearInterval(timer); timer = null; }
  });
  io.observe($('#pipeline'));
}

function initCaseStudy() {
  $$('#cs-flow button.box').forEach((btn) =>
    btn.addEventListener('click', () => btn.setAttribute('aria-expanded', String(btn.getAttribute('aria-expanded') !== 'true'))),
  );
}

// Each demo module is fetched only when its section approaches the viewport (or is jumped to).
const LAZY = {
  'agent-lab': () => import('./agent-lab.js').then((m) => m.initAgentLab()),
  rag: () => import('./rag.js').then((m) => m.initRag()),
  mcp: () => import('./mcp.js').then((m) => m.initMcp()),
  observability: () => import('./observability.js').then((m) => m.initObservability()),
  failures: () => import('./failures.js').then((m) => m.initFailures()),
  decisions: () => import('./decisions.js').then((m) => m.initDecisions()),
  cost: () => import('./cost.js').then((m) => m.initCost()),
};
const loaded = new Set();

export function loadDemo(name) {
  if (loaded.has(name) || !LAZY[name]) return Promise.resolve();
  loaded.add(name);
  return LAZY[name]().catch((err) => {
    loaded.delete(name);
    console.error(`Failed to load demo "${name}"`, err);
  });
}

function initLazyDemos() {
  const els = $$('[data-lazy]');
  if (!('IntersectionObserver' in window)) { els.forEach((el) => loadDemo(el.dataset.lazy)); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { loadDemo(e.target.dataset.lazy); io.unobserve(e.target); } });
  }, { rootMargin: '600px 0px' });
  els.forEach((el) => io.observe(el));
}

function injectJsonLd() {
  // Enrich the static JSON-LD with sameAs links once they are configured.
  const links = contactLinks();
  const sameAs = [links.github.href, links.linkedin.href].filter(Boolean);
  if (!sameAs.length) return;
  const node = $('script[type="application/ld+json"]');
  try {
    const data = JSON.parse(node.textContent);
    data.sameAs = sameAs;
    node.textContent = JSON.stringify(data);
  } catch { /* leave static block untouched */ }
}

/** Navigate to a section, switching view mode first if the section is hidden in the current one. */
export function navigate(id) {
  const el = document.getElementById(id);
  if (!el) return false;
  if (el.classList.contains('eng-only') && getView() === 'recruiter') setView('engineer', { announce: true });
  if (el.classList.contains('rec-only') && getView() === 'engineer') setView('recruiter', { announce: true });
  const lazy = el.querySelector('[data-lazy]');
  if (lazy) loadDemo(lazy.dataset.lazy);
  return goTo(id);
}

function init() {
  initViewToggle();
  initNav();
  initContactLinks();
  initReveal();
  initPipeline();
  initCaseStudy();
  initLazyDemos();
  const ctx = { setView, getView, loadDemo, navigate };
  initTerminal(ctx);
  initPalette(ctx);
  injectJsonLd();
  initAnalytics(CONFIG.ANALYTICS);
}

init();
