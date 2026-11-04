// Walking-agent acceptance test. Needs the API on :8000 and `vite preview` on :4173.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch { playwright = require("/opt/node22/lib/node_modules/playwright"); }
const { chromium } = playwright;

const BASE = process.env.BASE_URL ?? "http://localhost:4173";
const SHOTS = process.env.SHOTS ?? "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
let failures = 0, passes = 0;
async function check(name, fn) {
  try { await fn(); passes++; console.log(`  ✓ ${name}`); } catch (e) { failures++; console.log(`  ✗ ${name}\n      ${String(e.message ?? e).split("\n")[0]}`); }
}
const assert = (c, m) => { if (!c) throw new Error(m); };
const shot = async (p, n) => { if (SHOTS) await p.screenshot({ path: `${SHOTS}/${n}.png` }); };

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const walkerX = async () => (await page.locator('[data-testid="sherin-walker"]').boundingBox()).x;
const trackPoses = () => page.evaluate(() => {
  window.__poses = new Set(); window.__walked = false;
  const el = document.querySelector('[data-testid="sherin-layer"]');
  new MutationObserver(() => { window.__poses.add(el.dataset.pose); if (el.dataset.walking === "true") window.__walked = true; }).observe(el, { attributes: true });
});
const poses = () => page.evaluate(() => [...window.__poses]);

console.log("Every route");
const ROUTES = ["/", "/journey", "/chat", "/portfolio", "/guardian", "/harness", "/azure", "/python", "/tokens", "/savings", "/metrics", "/approvals", "/esg", "/reports", "/settings"];
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await check("Sherin's full-body character is present on all 15 routes and never intercepts clicks", async () => {
  for (const r of ROUTES) {
    await page.click(`nav a[href="${r}"]`);
    await page.waitForSelector('[data-testid="sherin-character"]');
    const info = await page.evaluate(() => {
      const layer = document.querySelector('[data-testid="sherin-layer"]');
      const c = document.querySelector('[data-testid="sherin-layer"] [data-testid="sherin-character"]').getBoundingClientRect();
      const hit = document.elementFromPoint(c.left + c.width / 2, c.top + c.height / 2);
      return { pe: getComputedStyle(layer).pointerEvents, blocked: !!hit?.closest('[data-testid="sherin-character"]'), asset: document.querySelector('[data-testid="sherin-layer"] [data-testid="sherin-character"]').dataset.asset };
    });
    assert(info.pe === "none" && !info.blocked, `${r}: character intercepts pointer events`);
    assert(info.asset === "sherin-fullbody-rig", `${r}: unexpected asset`);
  }
  assert(errors.length === 0, errors.join(" | "));
});
await check("Persistent layer: navigation walks or transitions instead of remounting", async () => {
  await page.click('nav a[href="/savings"]'); await page.waitForTimeout(3000);
  const id = await page.evaluate(() => { const el = document.querySelector('[data-testid="sherin-layer"]'); el.dataset.probe = "same-node"; return 1; });
  await trackPoses();
  await page.click('nav a[href="/metrics"]'); await page.waitForTimeout(3000); // nearby stop: she walks
  assert(await page.evaluate(() => document.querySelector('[data-testid="sherin-layer"]').dataset.probe) === "same-node" && id, "layer was remounted");
  assert(await page.evaluate(() => window.__walked), "did not walk between routes");
  assert(await page.locator('[data-testid="sherin-speech"]').count() === 1, "no greeting");
});

console.log("Chat → Sherin points at the evidence");
await check("'Why did AI spending increase this month?' sends Sherin to the largest cost increase", async () => {
  await page.click('nav a[href="/"]');
  await page.getByRole("textbox", { name: "Message Sherin" }).fill("Sherin, why did AI spending increase this month?");
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForSelector("#graph-d-drivers.sherin-focus", { timeout: 25000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="sherin-layer"]').dataset.pose === "point", null, { timeout: 15000 });
  const t = await page.locator('[data-testid="sherin-speech"]').innerText();
  assert(/largest cost increase/i.test(t), t);
  await shot(page, "sherin-points-cost-driver");
  await page.locator("#graph-d-drivers .main-svg").first().waitFor();
});

console.log("Guided journey (live LangGraph run)");
await page.click('nav a[href="/journey"]');
await page.waitForSelector('[data-testid="scene-1"]');
await page.selectOption('select[aria-label="Animation speed"]', "3");
await check("Play: Sherin walks into scene 1, turns, and points at the revenue chart", async () => {
  await trackPoses();
  const x0 = await walkerX();
  await page.getByRole("button", { name: "Play Journey" }).click();
  await page.waitForSelector('[data-testid="scene-1"] [data-revealed="true"]', { timeout: 20000 });
  await page.waitForFunction(() => window.__poses.has("point"), null, { timeout: 20000 });
  assert(await page.evaluate(() => window.__walked), "never walked");
  assert(Math.abs((await walkerX()) - x0) > 40, "did not move");
  await shot(page, "journey-scene1");
});
await check("Pause freezes Sherin; Resume continues", async () => {
  await page.getByRole("button", { name: "Pause" }).click();
  const a = await walkerX(); const narr = await page.locator('[data-testid="narration"] li').count();
  await page.waitForTimeout(1500);
  assert(Math.abs((await walkerX()) - a) < 1, "moved while paused");
  assert(await page.locator('[data-testid="narration"] li').count() === narr, "narration advanced while paused");
  await page.getByRole("button", { name: "Resume" }).click();
});
await check("Scene 2: graph stays interactive mid-journey (click a cost-driver bar → records)", async () => {
  await page.waitForSelector('[data-testid="scene-2"] [data-revealed="true"]', { timeout: 30000 });
  await page.waitForSelector("#scene-drivers .bars .point path");
  await page.locator("#scene-drivers .bars .point path").first().click({ force: true });
  await page.waitForSelector('[role="dialog"] table tbody tr', { timeout: 10000 });
  await page.keyboard.press("Escape");
  await shot(page, "journey-scene2");
});
await check("Scene 3: Sherin follows real AGENT_STARTED / TOOL_RUNNING / VALIDATION events", async () => {
  await page.waitForSelector('[data-testid="scene-3"]', { timeout: 40000 });
  await page.waitForFunction(() => /VALIDATION_STARTED/.test(document.querySelector('[data-testid="narration"]').innerText), null, { timeout: 60000 });
  const log = await page.locator('[data-testid="event-log"]').innerText();
  for (const e of ["RUN_PLANNED", "AGENT_STARTED", "TOOL_RUNNING", "TOOL_COMPLETED", "VALIDATION_STARTED", "VALIDATION_PASSED", "APPROVAL_REQUIRED"]) assert(log.includes(e), `missing ${e}`);
  assert(!/synthetic/i.test(log), "live run should not show synthetic events");
  assert(await page.evaluate(() => ["work", "think"].some((p) => window.__poses.has(p))), "no working/thinking animation");
  await shot(page, "journey-scene3");
});
await check("Scene 6: the workflow pauses at the manager's desk until an authorized decision", async () => {
  await page.waitForSelector('[data-testid="scene-6"]', { timeout: 90000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="sherin-layer"]').dataset.pose === "waiting", null, { timeout: 30000 });
  await page.waitForTimeout(4000);
  assert(await page.locator('[data-testid="scene-6"]').count() === 1, "journey moved on without a decision");
  assert(!(await page.locator('[data-testid="event-log"]').innerText()).includes("TASK_COMPLETED"), "completed before approval");
  await shot(page, "journey-scene6-waiting");
  const card = page.locator('[data-testid="scene-6"] [data-testid^="approval-"]');
  await card.getByRole("button", { name: "Approve" }).click();
});
await check("Scene 7: success only after the recorded TASK_COMPLETED", async () => {
  await page.waitForSelector('[data-testid="scene-7"]', { timeout: 40000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="event-log"]').innerText.includes("TASK_COMPLETED"), null, { timeout: 30000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="sherin-layer"]').dataset.pose === "success", null, { timeout: 30000 });
  const t = await page.locator('[data-testid="scene-7"]').innerText();
  assert(/minutes of agent execution/.test(t) && /verified/.test(t), "summary lacks run evidence");
  await shot(page, "journey-scene7");
});

console.log("Scene controls");
await check("Jump to scene, Replay Scene and Skip Animation", async () => {
  await page.selectOption('select[aria-label="Jump to scene"]', "1");
  await page.waitForSelector('[data-testid="scene-2"] [data-revealed="true"]');
  const n = await page.locator('[data-testid="narration"] li').count();
  await page.getByRole("button", { name: "Replay Scene" }).click();
  await page.waitForFunction((k) => document.querySelectorAll('[data-testid="narration"] li').length > k, n, { timeout: 20000 });
  await page.getByTestId("scene-pill-4").click();
  await page.waitForSelector('[data-testid="scene-4"]');
  await page.getByRole("button", { name: "Skip Animation" }).click();
  await page.waitForSelector('[data-testid="scene-4"] [data-revealed="true"]');
});
await check("Mute toggles and speed persists", async () => {
  await page.getByRole("button", { name: "Unmute" }).click();
  await page.getByRole("button", { name: "Mute" }).waitFor();
  await page.getByRole("button", { name: "Mute" }).click();
  assert(await page.inputValue('select[aria-label="Animation speed"]') === "3", "speed");
});

console.log("Reduced motion");
await check("prefers-reduced-motion: no walking, journey still advances with full narration", async () => {
  const rp = await ctx.newPage();
  await rp.emulateMedia({ reducedMotion: "reduce" });
  await rp.goto(BASE + "/journey", { waitUntil: "networkidle" });
  await rp.selectOption('select[aria-label="Event source"]', "synthetic");
  await rp.selectOption('select[aria-label="Animation speed"]', "3");
  await rp.evaluate(() => { window.__walked = false; const el = document.querySelector('[data-testid="sherin-layer"]'); new MutationObserver(() => { if (el.dataset.walking === "true") window.__walked = true; }).observe(el, { attributes: true }); });
  await rp.getByRole("button", { name: "Play Journey" }).click();
  await rp.waitForSelector('[data-testid="scene-3"]', { timeout: 60000 });
  assert(!(await rp.evaluate(() => window.__walked)), "walked under reduced motion");
  const narr = await rp.locator('[data-testid="narration"]').innerText();
  assert(/earned/.test(narr) && /largest increase/i.test(narr), "narration missing");
  assert(/synthetic/i.test(await rp.locator('[data-testid="event-log"]').innerText()), "synthetic events not labelled");
  await rp.close();
});

console.log(`\n${passes} passed, ${failures} failed${errors.length ? `; page errors: ${errors.join(" | ")}` : ""}`);
await browser.close();
process.exit(failures || errors.length ? 1 : 0);
