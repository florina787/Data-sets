// Captures documentation screenshots from a running app (backend :8000, frontend :5173).
// Usage: node e2e/capture-screenshots.mjs [outDir]
import { chromium } from "@playwright/test";
import fs from "node:fs";

const out = process.argv[2] ?? "../docs/screenshots";
const base = process.env.APP_URL ?? "http://127.0.0.1:5173";
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

async function shot(name, full = true) {
  await page.waitForTimeout(900);
  // Sticky header/composer would repeat over a full-page capture; un-stick them for documentation shots.
  if (full) await page.addStyleTag({ content: "header, .sticky { position: static !important; }" });
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: full });
  console.log("captured", name);
}
async function askCard(tag) {
  await page.goto(base + "/");
  await page.evaluate(() => localStorage.removeItem("cic.session"));
  await page.goto(base + "/");
  await page.getByRole("button", { name: new RegExp("^" + tag) }).click();
  await page.waitForSelector("text=Uncertainty & method", { timeout: 60000 });
}

await page.goto(base + "/");
await page.evaluate(() => localStorage.removeItem("cic.session"));
await page.goto(base + "/");
await shot("01-home", false);

await askCard("Sentiment × topics");
await shot("02-q1-negative-topics");
await page.getByRole("button", { name: "Compare the top two topics." }).click();
await page.waitForFunction(() => document.querySelectorAll("article").length >= 2 && document.body.innerText.includes("Resolved '#1, #2'"), null, { timeout: 60000 });
await shot("06-memory-follow-up");

await askCard("Agent coaching");
await shot("03-q2-coaching");

await page.goto(base + "/explorer/C0000479");
await page.waitForSelector("text=Analyse sentiment trajectory");
await shot("08-explorer", false);
await page.goto(base + "/");
await page.getByRole("button", { name: "Start a new session" }).click().catch(() => {});
await page.goto(base + "/explorer/C0000479");
await page.getByRole("button", { name: "Analyse sentiment trajectory" }).click();
await page.getByRole("link", { name: "Ask Intelligence" }).first().click(); // client-side navigation keeps the stream alive
await page.waitForSelector("text=Turning point", { timeout: 60000 }).catch(() => {});
await page.waitForSelector("text=Uncertainty & method", { timeout: 60000 });
await shot("04-q3-trajectory");

await askCard("Leadership priorities");
await shot("05-q4-leadership");

await page.goto(base + "/");
await page.getByRole("button", { name: "Start a new session" }).click().catch(() => {});
await page.getByRole("textbox").fill("Find conversations where the customer asked to escalate an app crash.");
await page.keyboard.press("Enter");
await page.waitForSelector("text=Supporting evidence", { timeout: 60000 });
await shot("07-retrieval");

for (const [path, name, wait] of [["/leadership", "09-leadership-dashboard", "Executive summary"], ["/sentiment", "10-sentiment", "How to read this"],
  ["/coaching", "11-coaching", "Conversation review queue"], ["/harness", "12-agent-harness", "Recent requests"], ["/prompts", "13-prompt-library", "System instruction"],
  ["/metrics", "14-system-metrics", "Node latency"], ["/governance", "15-governance", "Controls"]]) {
  await page.goto(base + path);
  await page.waitForSelector(`text=${wait}`, { timeout: 60000 });
  if (path === "/harness") await page.locator(".react-flow__node").first().waitFor();
  await shot(name, path !== "/harness");
}

await page.goto(base + "/sentiment");
await page.waitForSelector("text=How to read this");
await page.locator(".recharts-bar-rectangle").first().click();
await page.waitForSelector("text=Conversations behind this data point", { timeout: 15000 });
await shot("16-drilldown", false);

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
const m = await mobile.newPage();
await m.goto(base + "/");
await m.waitForTimeout(1200);
await m.screenshot({ path: `${out}/17-mobile-home.png` });
console.log("captured 17-mobile-home");

await browser.close();
if (errors.length) { console.error("Page errors:", errors); process.exit(1); }
