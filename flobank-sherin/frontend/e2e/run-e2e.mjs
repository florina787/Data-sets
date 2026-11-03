// Browser acceptance test. Requires the API (port 8000) and `vite preview` (port 4173) to be running.
//   BASE_URL=http://localhost:4173 SHOTS=docs/screenshots node e2e/run-e2e.mjs
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch { playwright = require("/opt/node22/lib/node_modules/playwright"); }
const { chromium } = playwright;

const BASE = process.env.BASE_URL ?? "http://localhost:4173";
const SHOTS = process.env.SHOTS ?? "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
const ROUTES = ["/", "/chat", "/portfolio", "/guardian", "/harness", "/azure", "/python", "/tokens", "/savings", "/metrics", "/approvals", "/esg", "/reports", "/settings"];

let failures = 0, passes = 0;
async function check(name, fn) {
  try { await fn(); passes++; console.log(`  ✓ ${name}`); }
  catch (e) { failures++; console.log(`  ✗ ${name}\n      ${String(e.message ?? e).split("\n")[0]}`); }
}
function assert(c, msg) { if (!c) throw new Error(msg); }
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` }); };

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e)));
const setRole = (role, user) => page.evaluate(([r, u]) => { localStorage.setItem("sherin.role", JSON.stringify(r)); localStorage.setItem("sherin.user", JSON.stringify(u)); }, [role, user]);

console.log("Routes");
for (const r of ROUTES) {
  await check(`${r} renders with Sherin's avatar`, async () => {
    await page.goto(BASE + r, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const avatars = await page.$$eval('[data-testid="sherin-avatar"]', (els) => els.map((e) => e.getAttribute("data-src")));
    assert(avatars.length >= 2, `expected sidebar + page avatar, got ${avatars.length}`);
    assert(new Set(avatars).size === 1 && avatars[0] === "/sherin/sherin-ghibli.png", `avatar sources differ: ${[...new Set(avatars)]}`);
    assert(pageErrors.length === 0, `page errors: ${pageErrors.join(" | ")}`);
    await shot(page, `route${r === "/" ? "-home" : r.replace("/", "-")}`);
  });
}

console.log("Financial Command Center");
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await check("8 KPI cards and all 8 giant charts render as interactive Plotly charts", async () => {
  await page.waitForSelector('[data-testid="kpi-ai_cost"]');
  assert((await page.$$('[data-testid^="kpi-"]')).length === 9, "kpi-row + 8 cards"); // includes the row container
  for (const g of ["a", "b", "c", "d", "e", "f", "g", "h"]) {
    await page.locator(`#graph-${g}`).scrollIntoViewIfNeeded();
    await page.waitForSelector(`#graph-${g} .js-plotly-plot .main-svg`, { timeout: 15000 });
  }
});
await check("KPI drill-down opens with breakdown rows", async () => {
  await page.locator('[data-testid="kpi-ai_cost"]').click();
  await page.waitForSelector('[role="dialog"] table tbody tr');
  const rows = await page.$$eval('[role="dialog"] table tbody tr', (r) => r.length);
  assert(rows === 10, `expected 10 AI cost categories, got ${rows}`);
  await shot(page, "kpi-drilldown");
  await page.keyboard.press("Escape");
});
await check("Graph D category opens underlying cost records", async () => {
  await page.locator("#graph-d").scrollIntoViewIfNeeded();
  await page.locator("#graph-d button", { hasText: "LLM inference" }).click();
  await page.waitForSelector('[role="dialog"] table tbody tr');
  const txt = await page.locator('[role="dialog"]').innerText();
  assert(/records in/.test(txt) && /T\d{6}/.test(txt), "cost records with task ids");
  await page.keyboard.press("Escape");
});
await check("Graph A granularity switch (day/week/quarter/year)", async () => {
  for (const g of ["Day", "Week", "Quarter", "Year"]) {
    await page.locator("#graph-a").getByRole("radio", { name: g }).click();
    await page.waitForTimeout(700);
  }
  await page.waitForSelector("#graph-a .js-plotly-plot .main-svg");
});
await check("Currency switch shows INR and CAD consistently", async () => {
  await page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "INR" }).click();
  await page.waitForFunction(() => document.querySelector('[data-testid="kpi-bank_revenue"]')?.textContent?.includes("₹"));
  await page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "CAD" }).click();
  await page.waitForFunction(() => document.querySelector('[data-testid="kpi-ai_cost"]')?.textContent?.includes("C$"));
  await page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "USD" }).click();
});

console.log("Copilot");
await check("Streaming answer from records, with chart and dashboard link", async () => {
  await page.goto(BASE + "/chat", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: "Message Sherin" }).fill("What is your net economic contribution?");
  await page.getByRole("button", { name: "Send" }).click();
  await page.waitForSelector('[data-testid="assistant-turn"] [data-testid="chat-chart"] .main-svg', { timeout: 20000 });
  const txt = await page.locator('[data-testid="assistant-turn"]').last().innerText();
  assert(/net economic contribution/i.test(txt) && /ROI/.test(txt), "answer text");
  assert(await page.getByRole("button", { name: /Graph B/ }).count() > 0, "link to Graph B");
  await shot(page, "chat-answer");
});
await check("Conversation history is searchable", async () => {
  await page.getByPlaceholder("Search history").fill("net economic");
  await page.waitForTimeout(800);
  assert(await page.locator('[aria-label="Conversation history"] li').count() >= 1, "history hit");
});

console.log("Agent harness + approvals");
await setRole("ENGINEER", "eng.ravi");
await check("Python debug run shows diff and pauses for approval", async () => {
  await page.goto(BASE + "/python", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Debug this Python/ }).click();
  await page.waitForSelector('[data-testid="run-inline"] [aria-label="Code diff"]', { timeout: 20000 });
  await page.waitForSelector('[data-testid="run-inline"] [data-testid^="approval-"]', { timeout: 20000 });
  await shot(page, "python-run-awaiting-approval");
});
await check("Engineer cannot approve; manager can, and the run completes with its cost", async () => {
  const card = page.locator('[data-testid="run-inline"] [data-testid^="approval-"]');
  assert(await card.getByRole("button", { name: "Approve" }).isDisabled(), "approve disabled for ENGINEER in the UI");
  // The server enforces it independently of the UI.
  const aid = (await card.getAttribute("data-testid")).replace("approval-", "");
  const status = await page.evaluate(async (id) => (await fetch(`/api/approvals/${id}/decision`, { method: "POST", headers: { "Content-Type": "application/json", "X-Role": "ENGINEER", "X-User": "eng.ravi" }, body: JSON.stringify({ decision: "approve" }) })).status, aid);
  assert(status === 403, `server returned ${status} for ENGINEER approve`);
  await setRole("SHERIN_MANAGER", "mgr.sherin");
  await page.goto(BASE + "/approvals", { waitUntil: "networkidle" });
  const pending = page.locator('[data-testid^="approval-AP-"]', { hasText: "Apply Python patch" }).first();
  await pending.getByRole("button", { name: "Approve" }).click();
  await page.waitForTimeout(1500);
  await page.goto(BASE + "/harness", { waitUntil: "networkidle" });
  await page.waitForFunction(() => /minutes of agent execution/.test(document.body.innerText), null, { timeout: 20000 });
  await page.waitForSelector('[data-testid="agent-graph"] .react-flow__node');
  await shot(page, "harness-completed");
});
await check("Guardian BLOCK cannot be approved by the manager", async () => {
  await page.goto(BASE + "/guardian?proposal=TP-1002", { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("A mandatory restriction is breached"));
  await page.getByRole("button", { name: "Request manager approval" }).click();
  const card = page.locator('[data-testid^="approval-"]').first();
  await card.waitFor();
  assert(/Mandatory policy block/.test(await card.innerText()), "blocked card");
  assert(await card.getByRole("button", { name: "Approve" }).count() === 0, "no approve button on blocked request");
  await shot(page, "guardian-block");
});

console.log("Observability");
await check("Live metrics are measured and the spend question is answered from records", async () => {
  await page.goto(BASE + "/metrics", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Why did Sherin spend more money today/ }).click();
  await page.waitForFunction(() => /Cost drivers/.test(document.body.innerText), null, { timeout: 15000 });
  assert(/measured live/i.test(await page.locator("main").innerText()), "measured badge");
});
await check("Executive report downloads", async () => {
  await page.goto(BASE + "/reports", { waitUntil: "networkidle" });
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Markdown report" }).click()]);
  assert(/sherin-executive-.*\.md$/.test(dl.suggestedFilename()), dl.suggestedFilename());
});
await check("Narrow (tablet) layout stacks panels without horizontal scroll", async () => {
  await page.setViewportSize({ width: 820, height: 1100 });
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert(overflow <= 1, `horizontal overflow ${overflow}px`);
});


console.log(`\n${passes} passed, ${failures} failed${pageErrors.length ? `; page errors: ${pageErrors.length}` : ""}`);
await browser.close();
process.exit(failures ? 1 : 0);
