// Checks the built website in a real browser.
//   node site/tools/site_check.mjs <built-site-dir> [screenshot-dir]
// Needs `playwright` and `axe-core` resolvable (CI installs both with --no-save).
// Fails on: horizontal scrolling, serious/critical accessibility issues (axe),
// broken enabled download links, page errors, or a feedback form that does
// not behave as configured.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(path.join(process.cwd(), "noop.js"));
const { chromium } = require("playwright");
const AXE = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");

const root = path.resolve(process.argv[2] || "_site");
const shots = process.argv[3];
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".jpg": "image/jpeg",
  ".gif": "image/gif", ".mp4": "video/mp4", ".webm": "video/webm", ".woff2": "font/woff2" };
const server = createServer(async (req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const file = path.join(root, path.normalize(p));
  if (!file.startsWith(root)) { res.writeHead(403).end(); return; }
  try { const body = await readFile(file); res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" }).end(body); }
  catch { res.writeHead(404).end("not found"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

const PAGES = ["index.html", "features.html", "feedback.html", "privacy.html", "pricing.html"];
const VIEWPORTS = [{ name: "mobile", width: 390, height: 844 }, { name: "tablet", width: 820, height: 1180 }, { name: "desktop", width: 1440, height: 900 }];
const failures = [];
const fail = (m) => { failures.push(m); console.log("FAIL", m); };
const browser = await chromium.launch();

for (const vp of VIEWPORTS) {
  for (const pageName of PAGES) {
    const page = await browser.newPage({ viewport: vp });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    // Privacy: only this site and GitHub's release API may be contacted by default.
    page.on("request", (r) => {
      const h = new URL(r.url()).host;
      if (!r.url().startsWith("data:") && h !== new URL(base).host && h !== "api.github.com") fail(`${pageName}: unexpected third-party request to ${h}`);
    });
    await page.goto(`${base}/${pageName}`, { waitUntil: "load" });
    await page.waitForTimeout(1500);
    if (errors.length) fail(`${pageName} @${vp.name}: page error ${errors.join("; ")}`);
    if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)) fail(`${pageName} @${vp.name}: horizontal scroll`);
    if (shots) {
      // Reveal everything for a complete full-page picture.
      await page.evaluate(() => document.querySelectorAll(".reveal").forEach((e) => e.classList.add("in")));
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(shots, `${pageName.replace(".html", "")}-${vp.name}.png`), fullPage: true });
    }
    if (vp.name === "desktop" || vp.name === "mobile") {
      await page.evaluate(() => document.querySelectorAll(".reveal").forEach((e) => e.classList.add("in")));
      await page.waitForTimeout(800);
      await page.addScriptTag({ content: AXE });
      const res = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations
        .map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes[0]?.target?.join(" ") })));
      for (const v of res) {
        const line = `${pageName} @${vp.name}: axe ${v.impact} ${v.id} (${v.n}) e.g. ${v.sample}`;
        if (v.impact === "serious" || v.impact === "critical") fail(line); else console.log("note", line);
      }
    }
    if (pageName === "index.html") {
      // Any enabled download link must point at a file that exists.
      const hrefs = await page.$$eval("#dl-button:not([aria-disabled]), #dl-others a", (as) => as.map((a) => a.href).filter((h) => h.includes("/releases/download/")));
      for (const h of hrefs) {
        const r = await fetch(h, { method: "HEAD", redirect: "follow" });
        if (!r.ok) fail(`download link broken: ${h} -> ${r.status}`); else console.log("download OK", h);
      }
      const label = await page.textContent("#dl-title");
      console.log(`download panel @${vp.name}: ${label}`);
    }
    await page.close();
  }
}

// Feedback page, as configured now: without a server the form is disabled and says so (no fake "sent").
{
  const page = await browser.newPage();
  await page.goto(`${base}/feedback.html`);
  const cfg = await page.evaluate(() => window.VEENA_CONFIG);
  const disabled = await page.$eval("#fb-fields", (f) => f.disabled);
  const pending = await page.isVisible("#fb-pending");
  if (!cfg.insightsUrl && !(disabled && pending)) fail("feedback form is active without a configured server");
  if (!cfg.discussionsEnabled && (await page.$$("[data-community]")).length) fail("community link shown while Discussions is not enabled");
  console.log(`feedback page as configured: ${disabled ? "not connected (shows the email address)" : "active"}`);
  await page.close();
}

// Feedback delivery end to end: the form posts to the REAL Insights Worker code (SQLite), and the
// dashboard summary then shows exactly that submission. Phone and desktop sizes.
{
  const { DatabaseSync } = await import("node:sqlite");
  const insightsDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../../cloud/insights");
  const html = await readFile(path.join(insightsDir, "src/dashboard.html"), "utf8");
  const bundle = (await readFile(path.join(insightsDir, "src/worker.js"), "utf8")).replace('import DASHBOARD_HTML from "./dashboard.html";', `const DASHBOARD_HTML = ${JSON.stringify(html)};`);
  const { writeFile, mkdtemp } = await import("node:fs/promises");
  const tmp = await mkdtemp(path.join((await import("node:os")).tmpdir(), "veena-insights-"));
  await writeFile(path.join(tmp, "worker.mjs"), bundle);
  const W = await import("file://" + path.join(tmp, "worker.mjs"));
  for (const vp of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
    const db = new DatabaseSync(":memory:");
    db.exec(await readFile(path.join(insightsDir, "schema.sql"), "utf8"));
    const norm = (q) => q.replace(/\?(\d+)/g, "?");
    const expand = (q, a) => { const o = [...q.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1); return o.length ? o.map((i) => a[i]) : a; };
    const prep = (q) => { const st = { args: [], bind(...a) { return { ...st, args: a }; },
      async all() { return { results: db.prepare(norm(q)).all(...expand(q, this.args)) }; },
      async first() { return db.prepare(norm(q)).get(...expand(q, this.args)) ?? null; },
      async run() { const r = db.prepare(norm(q)).run(...expand(q, this.args)); return { meta: { changes: Number(r.changes) } }; } }; return st; };
    const env = { DB: { prepare: prep, async batch(l) { for (const x of l) await x.run(); } }, ALLOWED_ORIGINS: base, DASHBOARD_TOKEN: "t".repeat(40), RATE_SALT: "s" };
    const page = await browser.newPage({ viewport: vp });
    await page.route("**/config.js", (r) => r.fulfill({ contentType: "text/javascript", body: 'window.VEENA_CONFIG={insightsUrl:"https://insights.test",discussionsEnabled:false,plansLive:false};' }));
    await page.route("https://insights.test/**", async (route) => {
      const q = route.request();
      const res = await W.default.fetch(new Request(q.url(), { method: q.method(), headers: { ...q.headers(), "cf-connecting-ip": "192.0.2.1" }, body: q.method() === "POST" ? q.postData() : undefined }), env);
      await route.fulfill({ status: res.status, headers: Object.fromEntries(res.headers), body: await res.text() });
    });
    await page.goto(`${base}/feedback.html`);
    await page.click("#fb-submit");
    if (!(await page.isVisible("#fb-error"))) fail("feedback: empty form was not stopped");
    await page.check("input[name=rating][value='4']");
    await page.selectOption("#fb-feature", "documents");
    await page.fill("#fb-worked", "Citations are <b>great</b> & fast.");
    await page.fill("#fb-next", "Import a whole folder");
    await page.fill("#fb-email", "tester@example.com");
    await page.check("#fb-contact");
    await page.waitForTimeout(3100);
    await page.click("#fb-submit");
    await page.waitForSelector("text=Thank you.", { timeout: 5000 }).catch(() => fail(`feedback @${vp.width}: no confirmation`));
    const sum = await W.summary(env, { days: 7, test: false });
    const row = db.prepare("SELECT * FROM feedback").get();
    if (!(sum.feedback.total === 1 && sum.feedback.avg_rating === 4 && row && row.feature === "documents" && row.worked === "Citations are <b>great</b> & fast." && row.contact_ok === 1))
      fail(`feedback @${vp.width}: not delivered correctly ${JSON.stringify(row)}`);
    else console.log(`feedback delivered @${vp.width}px: stored and counted in the dashboard summary`);
    await page.goto(`${base}/feedback.html?type=bug`);
    if (!(await page.isVisible("text=Report a")) || (await page.isVisible("#fb-rating-group"))) fail("bug report mode not shown");
    await page.close();
  }
}

// Wording must match the downloadable app: while plansLive is false, no paid-plan claims are visible.
{
  const page = await browser.newPage();
  await page.goto(`${base}/index.html`);
  const live = await page.evaluate(() => window.VEENA_CONFIG.plansLive === true);
  const body = await page.evaluate(() => document.body.innerText);
  if (!live && /three uses|Try free|See pricing/.test(body)) fail("index: paid-plan wording visible while plansLive is false");
  if (!live && await page.isVisible('nav[aria-label="Main"] a[href="pricing.html"]')) fail("index: Pricing link visible while plansLive is false");
  if (!live && !/Free\. No account\. No subscription\./.test(body)) fail("index: free wording missing while plansLive is false");
  console.log(`wording matches release (plansLive=${live})`);
  await page.close();
}

// Pricing: keyboard tabs, plan selection updates the total, buttons never pretend to charge.
{
  const page = await browser.newPage();
  await page.goto(`${base}/pricing.html`);
  const btn = () => page.textContent('[data-buy="unlimited"]');
  if ((await btn()) !== "Get Unlimited — $74.95/month") fail("pricing: default monthly button wrong: " + (await btn()));
  await page.click('[data-plan="unlimited_annual"]');
  if ((await btn()) !== "Get Unlimited — $299.95/year") fail("pricing: annual selection did not update the total");
  await page.focus("#t-unl"); await page.keyboard.press("ArrowRight");
  if (!(await page.isVisible("#p-cr")) || (await page.isVisible("#p-unl"))) fail("pricing: arrow key did not switch to Credits");
  await page.keyboard.press("End");
  if (!(await page.isVisible("#p-cu"))) fail("pricing: End key did not switch to Custom");
  await page.click("#t-cr"); await page.click('[data-plan="credits_15"]');
  if ((await page.textContent('[data-buy="credits"]')) !== "Buy 15 Credits — $88.50") fail("pricing: credit pack total wrong");
  await page.click('[data-buy="credits"]');
  if (!/not open yet/.test(await page.textContent("#buy-status"))) fail("pricing: with no billing server the button must say payments are not open");
  await page.goto(`${base}/pricing.html?checkout=success`);
  if (/confirmed/i.test(await page.textContent("body"))) fail("pricing: success URL alone must not show a confirmed payment");
  console.log("pricing interactions OK");
  await page.close();
}

await browser.close();
server.close();
if (failures.length) { console.log(`\n${failures.length} problem(s)`); process.exit(1); }
console.log("\nsite checks passed");
