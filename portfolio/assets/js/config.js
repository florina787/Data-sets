/**
 * SITE CONFIGURATION — the single place to edit personal values.
 *
 * Everything that links to you (header, contact section, terminal, command
 * palette, JSON-LD, OpenGraph/canonical tags) is generated from this file.
 * Values still equal to their placeholder are rendered as inert, clearly
 * labelled placeholders so a half-configured site never ships broken links.
 *
 * After editing, run `node scripts/build.mjs` (the GitHub Pages workflow does
 * this automatically) to sync the static <head> metadata used by crawlers.
 *
 * Never put secrets here: this file is public.
 */
export const CONFIG = {
  name: 'Florina Regius',
  title: 'Lead AI Engineer',
  roles: ['Agentic AI', 'Generative AI', 'Forward Deployed AI Engineer', 'AI Architect'],
  tagline: 'I design, build and productionize enterprise AI systems.',
  subTagline: 'From prototype → architecture → agents → integration → deployment → observability → scale.',
  description:
    'Florina Regius — Lead AI Engineer focused on agentic AI, RAG and production-grade enterprise AI systems: architecture, orchestration, security, evaluation and observability.',

  // ── Replace these three placeholders ─────────────────────────────────────
  GITHUB_USERNAME: 'GITHUB_USERNAME', // e.g. 'octocat'
  LINKEDIN_URL: 'LINKEDIN_URL', // e.g. 'https://www.linkedin.com/in/your-handle'
  EMAIL_ADDRESS: 'EMAIL_ADDRESS', // e.g. 'you@example.com'

  // Public URL of the deployed site, with trailing slash.
  // GitHub Pages project site: 'https://<user>.github.io/<repo>/'
  SITE_URL: 'https://GITHUB_USERNAME.github.io/Data-sets/',

  // Repository that hosts the featured Enterprise Agentic AI Copilot project.
  PROJECT_REPO: 'Data-sets',
  PROJECT_BRANCH: 'master',

  // Optional, privacy-friendly analytics. Disabled by default — see README.
  ANALYTICS: {
    enabled: false,
    provider: 'plausible', // 'plausible' | 'goatcounter' | 'umami'
    domain: '', // plausible: your site domain · goatcounter: https://<code>.goatcounter.com/count
    scriptSrc: '', // umami: https://<your-umami-host>/script.js
    websiteId: '', // umami only
  },
};

const PLACEHOLDERS = new Set(['GITHUB_USERNAME', 'LINKEDIN_URL', 'EMAIL_ADDRESS', '']);

export const isPlaceholder = (value) =>
  value == null || PLACEHOLDERS.has(String(value).trim()) || String(value).includes('GITHUB_USERNAME');

/** Resolved contact links. `href` is null while the value is a placeholder. */
export function contactLinks(cfg = CONFIG) {
  const gh = isPlaceholder(cfg.GITHUB_USERNAME) ? null : `https://github.com/${cfg.GITHUB_USERNAME}`;
  const li = isPlaceholder(cfg.LINKEDIN_URL) ? null : cfg.LINKEDIN_URL;
  const em = isPlaceholder(cfg.EMAIL_ADDRESS) ? null : `mailto:${cfg.EMAIL_ADDRESS}`;
  return {
    github: { label: 'GitHub', href: gh, display: gh ? `github.com/${cfg.GITHUB_USERNAME}` : 'GITHUB_USERNAME' },
    linkedin: { label: 'LinkedIn', href: li, display: li ? li.replace(/^https?:\/\/(www\.)?/, '') : 'LINKEDIN_URL' },
    email: { label: 'Email', href: em, display: em ? cfg.EMAIL_ADDRESS : 'EMAIL_ADDRESS' },
  };
}

/** Link to a path inside the project repository, or null while unconfigured. */
export function repoLink(path = '', cfg = CONFIG) {
  if (isPlaceholder(cfg.GITHUB_USERNAME)) return null;
  const base = `https://github.com/${cfg.GITHUB_USERNAME}/${cfg.PROJECT_REPO}`;
  return path ? `${base}/tree/${cfg.PROJECT_BRANCH}/${path}` : base;
}

export function blobLink(path, cfg = CONFIG) {
  if (isPlaceholder(cfg.GITHUB_USERNAME)) return null;
  return `https://github.com/${cfg.GITHUB_USERNAME}/${cfg.PROJECT_REPO}/blob/${cfg.PROJECT_BRANCH}/${encodeURI(path)}`;
}
