// Optional, privacy-friendly analytics. OFF by default: nothing loads unless
// CONFIG.ANALYTICS.enabled is true. Even when enabled, it respects Do Not Track
// and Global Privacy Control. See README → "Analytics (optional)".
const PROVIDERS = {
  plausible: (cfg) => ({ src: 'https://plausible.io/js/script.js', attrs: { 'data-domain': cfg.domain } }),
  goatcounter: (cfg) => ({ src: 'https://gc.zgo.at/count.js', attrs: { 'data-goatcounter': cfg.domain } }),
  umami: (cfg) => ({ src: cfg.scriptSrc, attrs: { 'data-website-id': cfg.websiteId } }),
};

export function initAnalytics(cfg) {
  if (!cfg || cfg.enabled !== true) return false;
  const optedOut = navigator.doNotTrack === '1' || window.doNotTrack === '1' || navigator.globalPrivacyControl === true;
  if (optedOut) return false;
  const make = PROVIDERS[cfg.provider];
  if (!make) return false;
  const { src, attrs } = make(cfg);
  if (!src || Object.values(attrs).some((v) => !v)) {
    console.warn('[analytics] enabled but not fully configured; skipping.');
    return false;
  }
  const s = document.createElement('script');
  s.defer = true;
  s.src = src;
  Object.entries(attrs).forEach(([k, v]) => s.setAttribute(k, v));
  document.head.append(s);
  return true;
}
