// Records the frame sequences behind the README's animated GIFs.
//
//   1. start the app (any port), e.g. FOODCARE_API_PORT=9710 python -m app
//   2. node e2e/record-media.mjs http://127.0.0.1:9710 /tmp/frames
//   3. python scripts/make_gifs.py /tmp/frames docs/media
//
// Every frame is a real screenshot of the running app, not a mock-up.
import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const [base = "http://127.0.0.1:9710", out = "/tmp/frames"] = process.argv.slice(2);
const here = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch(process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let seq = {};

async function frame(name, opts = {}) {
  const dir = path.join(out, name);
  fs.mkdirSync(dir, { recursive: true });
  seq[name] = (seq[name] ?? 0) + 1;
  await page.screenshot({ path: path.join(dir, `${String(seq[name]).padStart(3, "0")}.png`), ...opts });
}
async function hold(name, n, ms = 120) { for (let i = 0; i < n; i++) { await frame(name); await sleep(ms); } }
const nav = () => page.getByRole("navigation", { name: "Primary" });
const main = () => page.getByRole("main");
async function go(label) {
  await nav().getByRole("link", { name: label, exact: true }).click();
  await page.waitForLoadState("networkidle");
  await sleep(600);
}

await page.goto(base);
await page.getByLabel("Signed in as").selectOption({ label: "Val Park (Viewer)" });
await page.waitForLoadState("networkidle");
await sleep(1500);

// 1. executive: Executive Command from the hero down to the data sources
await hold("executive", 6, 150);
for (let i = 0; i < 14; i++) { await page.mouse.wheel(0, 140); await sleep(140); await frame("executive"); }
await hold("executive", 6, 150);
await page.evaluate(() => window.scrollTo(0, 0));

// 2. orbit: one full 12-second turn of the potatoes around Jerry (element only, small file)
const sources = page.locator("section[aria-labelledby=sources-title]");
await sources.scrollIntoViewIfNeeded();
const orbit = sources.locator(".orbit");
await page.mouse.move(2, 790); // hovering the orbit pauses it, by design
const b = await orbit.boundingBox();
const clip = { x: b.x + 10, y: b.y - 34, width: b.width - 20, height: b.height + 24 };
fs.mkdirSync(path.join(out, "orbit"), { recursive: true });
for (let i = 0; i < 48; i++) {
  await page.screenshot({ path: path.join(out, "orbit", `${String(i + 1).padStart(3, "0")}.png`), clip });
  await sleep(250);
}
await page.evaluate(() => window.scrollTo(0, 0));

// 3. tour: one stop per main page
for (const label of ["Executive Command", "Quality Intelligence", "Potato Inspection", "Inventory", "Agent Intelligence", "System Observability", "Model Evaluation Lab"]) {
  await go(label);
  await hold("tour", 6, 150);
}

// 4. inspection: upload a synthetic image, grade, open several potatoes
await go("Potato Inspection");
await hold("inspection", 4);
await main().getByLabel(/Photo of potatoes/).setInputFiles(path.join(here, "fixtures", "synthetic-potatoes.jpg"));
await main().getByLabel("Batch title").fill("Synthetic batch (drawn shapes)");
await main().getByRole("button", { name: "Inspect", exact: true }).click();
for (let i = 0; i < 20; i++) {
  await frame("inspection");
  if (await main().getByRole("img", { name: /Annotated inspection image/ }).isVisible()) break;
  await sleep(250);
}
await hold("inspection", 6);
const result = main().getByRole("img", { name: /Annotated inspection image/ });
await result.scrollIntoViewIfNeeded();
for (const n of [0, 3, 8, 11]) {
  await main().getByRole("list", { name: "Potatoes" }).getByRole("listitem").nth(n).click();
  await sleep(300);
  await hold("inspection", 5);
}

// 5. copilot: type a question, watch the cited answer arrive
await go("Ask Copilot");
const q = "Is there enough apple stock for the Ontario weekend campaign?";
const box = main().getByLabel("Ask the copilot");
for (let i = 0; i <= q.length; i += 4) { await box.fill(q.slice(0, i)); await frame("copilot"); }
await box.fill(q);
await main().getByRole("button", { name: "Ask", exact: true }).click();
for (let i = 0; i < 20; i++) {
  await frame("copilot");
  if (await main().getByText(/high risk/).first().isVisible()) break;
  await sleep(200);
}
await hold("copilot", 12, 150);

// 6. agents: the graphs of that answer, scrolled top to bottom
await go("Agent Intelligence");
await hold("agents", 6);
const height = await page.evaluate(() => document.scrollingElement.scrollHeight);
for (let y = 0; y < height - 800; y += 160) {
  await page.mouse.wheel(0, 160);
  await sleep(160);
  await frame("agents");
}
await hold("agents", 8);

// 7. still image: token usage panel on System Observability
await go("System Observability");
const panel = main().getByTestId("token-usage");
await panel.waitFor();
await sleep(800);
await page.setViewportSize({ width: 1440, height: 1000 });
await sleep(400);
const card = panel.locator("xpath=ancestor::section[1]");
fs.mkdirSync(path.join(out, "stills"), { recursive: true });
await card.screenshot({ path: path.join(out, "stills", "token-usage.png") });
await page.screenshot({ path: path.join(out, "stills", "observability.png"), fullPage: true });

await browser.close();
console.log("frames:", seq);
