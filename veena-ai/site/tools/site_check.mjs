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

// Feedback page, as configured now: a pending form is disabled, and no community link appears unverified.
{
  const page = await browser.newPage();
  await page.goto(`${base}/feedback.html`);
  const cfg = await page.evaluate(() => window.VEENA_CONFIG);
  const disabled = await page.$eval("#fb-fields", (f) => f.disabled);
  const pending = await page.isVisible("#fb-pending");
  if (!cfg.feedback?.formUrl && !(disabled && pending)) fail("feedback form is active without a configured Google Form");
  if (!cfg.discussionsEnabled && (await page.$$("[data-community]")).length) fail("community link shown while Discussions is not enabled");
  console.log(`feedback page as configured: ${disabled ? "pending (form not set up)" : "active"}`);
  await page.close();
}

// Feedback page with an example configuration: the pre-filled Google Forms link carries the answers.
{
  const page = await browser.newPage();
  await page.route("**/config.js", (r) => r.fulfill({ contentType: "text/javascript", body:
    'window.VEENA_CONFIG={feedback:{formUrl:"https://docs.google.com/forms/d/e/EXAMPLE_FORM_ID_FOR_TESTS_ONLY/viewform",' +
    'entries:{experience:"entry.1",type:"entry.2",message:"entry.3",email:"entry.4",page:null}},discussionsEnabled:false,cloudflareToken:null};' }));
  await page.route("https://docs.google.com/**", (r) => r.fulfill({ body: "stub" }));
  await page.goto(`${base}/feedback.html?utm_campaign=test`);
  await page.click("#fb-submit");
  if (!(await page.isVisible("#fb-error"))) fail("feedback: empty form was not stopped");
  await page.check("input[value=Good]");
  await page.check("input[value=\"Feature request\"]");
  await page.fill("#fb-message", "Please add <b>dark mode</b> & more.");
  const [popup] = await Promise.all([page.waitForEvent("popup"), page.click("#fb-submit")]);
  const u = new URL(popup.url());
  const ok = u.origin === "https://docs.google.com" && u.searchParams.get("usp") === "pp_url" && u.searchParams.get("entry.1") === "Good" &&
    u.searchParams.get("entry.2") === "Feature request" && u.searchParams.get("entry.3") === "Please add <b>dark mode</b> & more." && !u.searchParams.has("entry.4");
  if (!ok) fail(`feedback: wrong pre-filled link ${popup.url()}`); else console.log("feedback pre-filled link OK");
  if (!(await page.isVisible("text=Thank you."))) fail("feedback: no confirmation shown");
  await page.close();
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
