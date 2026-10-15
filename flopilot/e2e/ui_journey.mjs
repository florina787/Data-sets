// Browser end-to-end journey for FloPilot (Playwright, Chromium).
//
//   FLOPILOT_URL=http://localhost:5173 node e2e/ui_journey.mjs
//
// Optional: PLAYWRIGHT_MODULE (path to the playwright package), CHROMIUM_PATH (browser binary),
// SHOTS_DIR (where to save screenshots). Requires a fresh backend data directory so the
// landing page is shown. Exits non-zero on the first failed expectation.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "playwright");
const BASE = process.env.FLOPILOT_URL ?? "http://localhost:5173";
const SHOTS = process.env.SHOTS_DIR ?? "e2e/screenshots";
mkdirSync(SHOTS, { recursive: true });

const results = [];
async function step(name, fn) {
  const started = Date.now();
  try {
    await fn();
    results.push({ name, ok: true, ms: Date.now() - started });
    console.log(`✓ ${name}`);
  } catch (e) {
    results.push({ name, ok: false, error: String(e).split("\n")[0] });
    await page.screenshot({ path: `${SHOTS}/failure.png` }).catch(() => undefined);
    console.log(`✗ ${name}: ${String(e).split("\n")[0]}`);
    throw e;
  }
}

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const page = await browser.newPage({ viewport: { width: 1500, height: 920 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
if (process.env.E2E_DEBUG) {
  page.on("console", (m) => console.log("  [console]", m.type(), m.text().slice(0, 160)));
  page.on("response", (r) => { if (r.url().includes("/api/")) console.log("  [api]", r.status(), r.request().method(), r.url().replace(/^https?:\/\/[^/]+/, "")); });
}
const button = (text) => page.locator("button", { hasText: text });
let cardsBefore = 0;
const ask = async (text) => {
  cardsBefore = await page.locator(".bot-card").count();
  const before = await page.locator(".msg-user").count();
  await page.locator("#ask").fill(text);
  await page.locator("#ask").press("Enter");
  await page.waitForFunction((n) => document.querySelectorAll(".msg-user").length > n, before);
};
const lastCard = () => page.locator(".bot-card").last();
// A request is finished when its reply card has arrived and no progress indicator is shown.
const waitIdle = async () => {
  await page.waitForFunction((n) => !document.querySelector(".progress") && document.querySelectorAll(".bot-card").length > n,
    cardsBefore, { timeout: 60000 });
  cardsBefore = await page.locator(".bot-card").count();
};

try {
  await step("sign in with the demo analyst", async () => {
    await page.goto(BASE);
    await button("Florina (demo analyst)").click();
    await page.waitForSelector("text=Open the synthetic demo workbook");
  });
  await step("open the synthetic demo workbook and see the Excel-style grid", async () => {
    await button("Open the synthetic demo workbook").click();
    await page.waitForSelector(".cell.num");
    await page.waitForSelector("text=How can I help with your workbook?");
    await page.screenshot({ path: `${SHOTS}/01-workspace.png` });
  });
  await step("ambiguous request asks for clarification, then answers with sources", async () => {
    await ask("Summarize revenue by region");
    await waitIdle();
    cardsBefore = await page.locator(".bot-card").count();
    await lastCard().locator("button", { hasText: "Net Revenue" }).click();
    await waitIdle();
    await page.waitForSelector(".chart");
    const text = await lastCard().innerText();
    if (!text.includes("Net Revenue") || !text.includes("Sales!K2:K121")) throw new Error("answer lacks measure or source");
    await lastCard().locator("button", { hasText: "Sales!K2:K121" }).click();
    await page.waitForSelector(".col-h.sel");
    await page.screenshot({ path: `${SHOTS}/02-grounded-answer.png` });
  });
  await step("clean the sheet: proposals only, nothing applied", async () => {
    await ask("Clean the Sales sheet");
    await waitIdle();
    const n = await lastCard().locator(".proposal").count();
    if (n < 3) throw new Error(`expected several proposals, got ${n}`);
    if (!(await page.locator(".save-status").innerText()).includes("version 1")) throw new Error("workbook changed without approval");
  });
  await step("approve one proposal; another becomes out of date and can be prepared again", async () => {
    const card = lastCard();
    await card.locator(".proposal").nth(0).locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=Saved · version 2");
    await card.locator(".proposal").nth(1).locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=/prepared for version 1/");
    await card.locator(".proposal").nth(1).locator("button", { hasText: "Prepare again" }).click();
    await page.waitForFunction(() => document.querySelectorAll(".bot-card").length >= 4);
    await lastCard().locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=Saved · version 3");
  });
  await step("formula proposal: preview before/after in the grid, then apply", async () => {
    await ask("Add a profit-margin column using net revenue");
    await waitIdle();
    await lastCard().locator("button", { hasText: "Preview in grid" }).click();
    await page.waitForSelector(".compare-bar");
    await page.waitForSelector(".cell.changed");
    await page.screenshot({ path: `${SHOTS}/03-formula-preview.png` });
    await button("Before").click();
    await button("After").click();
    await lastCard().locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=Saved · version 4");
  });
  await step("report sheet with a native chart", async () => {
    await ask("Compare actual spending with budget");
    await waitIdle();
    cardsBefore = await page.locator(".bot-card").count();
    await lastCard().locator("button", { hasText: "Add to workbook as a report" }).click();
    await waitIdle();
    await lastCard().locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=Saved · version 5");
    await page.waitForSelector(".sheet-tab:has-text('Amount report')");
  });
  await step("restore version 1 from the Activity drawer", async () => {
    await button("Activity").click();
    await page.waitForSelector("text=Version 5");
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${SHOTS}/04-activity.png` });
    await page.locator(".timeline-item", { hasText: "Version 1" }).locator("button", { hasText: "Restore this version" }).click();
    await page.waitForSelector("text=Restore version 1");
    await lastCard().locator("button", { hasText: "Approve & apply" }).click();
    await page.waitForSelector("text=Saved · version 6");
    const tabs = await page.locator(".sheet-tab").allInnerTexts();
    if (tabs.some((t) => t.includes("Amount report"))) throw new Error("restored version still contains the report sheet");
  });
  await step("workbook overview request (cancellation itself is covered by backend tests)", async () => {
    await ask("What's in this workbook?");
    await waitIdle();
  });
  await step("viewer can read but not approve", async () => {
    await button("Florina ▾").click();
    await button("Sign out").click();
    await button("Victor (demo viewer)").click();
    await page.waitForSelector(".cell.num");
    await ask("Normalize the Region categories on Sales");
    await waitIdle();
    const text = await lastCard().innerText();
    if (!text.includes("Your role (viewer) cannot use")) throw new Error("viewer was able to create a proposal");
  });
  if (errors.length) throw new Error(`page errors: ${errors.join("; ")}`);
} finally {
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} steps passed${errors.length ? `, ${errors.length} page error(s)` : ""}`);
  process.exitCode = failed || errors.length ? 1 : 0;
}
