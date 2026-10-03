// Small shared helpers. No dependencies.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Promise-based delay that collapses to ~0 when the user prefers reduced motion. */
export const sleep = (ms) => new Promise((r) => setTimeout(r, prefersReducedMotion() ? Math.min(ms, 30) : ms));

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

let toastTimer;
export function toast(msg) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
}

/** Deterministic PRNG (mulberry32) so simulations are reproducible. */
export function rng(seed = 42) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Syntax-highlight a JSON value for display (input is escaped first). */
export function jsonHtml(value) {
  const text = esc(JSON.stringify(value, null, 2));
  return text.replace(
    /(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?)/g,
    (m, str, colon, bool, num) => {
      if (str) return colon ? `<span class="json-k">${str}</span>${colon}` : `<span class="json-s">${str}</span>`;
      if (bool) return `<span class="json-b">${bool}</span>`;
      if (num) return `<span class="json-n">${num}</span>`;
      return m;
    },
  );
}

/** Smoothly scroll to a section id and move focus there for keyboard/screen-reader users. */
export function goTo(id) {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
  const heading = el.querySelector('h1, h2');
  if (heading) {
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
  }
  history.replaceState(null, '', `#${id}`);
  return true;
}
