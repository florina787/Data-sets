// After `vite build`: static HTML per public page (unique metadata for crawlers and link previews),
// 404.html fallback so app routes load on refresh, sitemap.xml and robots.txt.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname;
const SITE = (process.env.FEMORA_SITE_URL ?? "https://florina787.github.io/femora/").replace(/\/?$/, "/");
const PAGES = [
  ["", "FEMORA Muse · Every woman's journey deserves to be understood", "Meet Muse, your personal AI wellness companion. Understand your menopause journey, discover meaningful connections, and feel supported through every change."],
  ["features", "Features · FEMORA Muse", "Muse AI companion, menopause journey, health intelligence, MedScan, food & lifestyle, Guardian safety, sisterhood and offline privacy. What works today and what's coming."],
  ["demo", "Interactive demo · FEMORA Muse", "Explore FEMORA Muse with synthetic sample data: Muse conversation, symptom history, health dashboard, journey timeline, nutrition and the sisterhood map. No sign-up needed."],
  ["club", "Sisterhood club · FEMORA Muse", "A women's club built on consent: verified organisations map today; moderated circles, anonymous lounge and Sister Match coming with secure accounts."],
  ["how-it-works", "How it works · FEMORA Muse", "Six steps: explore, set up a private profile, record symptoms, explore insights with Muse, discover community, and manage your data."],
  ["gallery", "Gallery · FEMORA Muse", "Short recordings of the real FEMORA Muse app: onboarding, Muse conversations, menopause journey, food, health dashboard, Guardian, sisterhood map and themes."],
  ["pricing", "Pricing & free trial · FEMORA Muse", "FEMORA Free, Plus and Circle: proposed plans, transparent entitlements and a 30-day free trial planned for paid features. No payments are active."],
  ["trust", "Science, trust & privacy · FEMORA Muse", "What FEMORA Muse can and cannot do, what stays on your device, how evidence is used, consent and deletion, community privacy and safety guidance."],
];
const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
// Content Security Policy (production only; the dev server needs inline scripts).
const CSP = `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tiles.openfreemap.org; font-src 'self' data:; connect-src 'self' https://tiles.openfreemap.org https://nominatim.openstreetmap.org http://localhost:* http://127.0.0.1:*; worker-src 'self' blob:; child-src blob:; media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self' mailto:" />`;
const base = readFileSync(join(dist, "index.html"), "utf8").replace("<meta charset=\"UTF-8\" />", "<meta charset=\"UTF-8\" />\n    " + CSP);
const meta = (html, path, title, desc) => {
  const url = SITE + (path ? path + "/" : "");
  return html
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/(<meta name="description" content=")[^"]*"/, `$1${esc(desc)}"`)
    .replace(/(<link rel="canonical" href=")[^"]*"/, `$1${url}"`)
    .replace(/(<meta property="og:url" content=")[^"]*"/, `$1${url}"`)
    .replace(/(<meta property="og:title" content=")[^"]*"/, `$1${esc(title)}"`)
    .replace(/(<meta property="og:description" content=")[^"]*"/, `$1${esc(desc)}"`)
    .replace(/(<meta name="twitter:title" content=")[^"]*"/, `$1${esc(title)}"`)
    .replace(/(<meta name="twitter:description" content=")[^"]*"/, `$1${esc(desc)}"`)
    .replaceAll("__SITE_URL__", SITE);
};
for (const [path, title, desc] of PAGES) {
  const dir = path ? join(dist, path) : dist;
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "index.html"), meta(base, path, title, desc));
}
// The app entry gets a real 200 page (not indexed); deeper app routes use the 404.html fallback.
mkdirSync(join(dist, "app"), { recursive: true });
writeFileSync(join(dist, "app", "index.html"), meta(base, "app", "FEMORA Muse app", PAGES[0][2]).replace("<head>", '<head>\n    <meta name="robots" content="noindex" />'));
// App routes (/app/...) and unknown paths: GitHub Pages serves 404.html, which boots the same app.
writeFileSync(join(dist, "404.html"), meta(base, "", "FEMORA Muse", PAGES[0][2]).replace("<head>", '<head>\n    <meta name="robots" content="noindex" />'));
const today = new Date().toISOString().slice(0, 10);
writeFileSync(join(dist, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${PAGES.map(([p]) => `  <url><loc>${SITE}${p ? p + "/" : ""}</loc><lastmod>${today}</lastmod></url>`).join("\n")}\n</urlset>\n`);
writeFileSync(join(dist, "robots.txt"), `User-agent: *\nAllow: /\nDisallow: ${new URL(SITE).pathname}app/\nSitemap: ${SITE}sitemap.xml\n`);
writeFileSync(join(dist, ".nojekyll"), "");
console.log(`postbuild: ${PAGES.length} pages, 404.html, sitemap.xml, robots.txt for ${SITE}`);
