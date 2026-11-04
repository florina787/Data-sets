// Records a real screen capture of the guided journey (live LangGraph run, real approval) for sharing.
//   OUT=../docs/media node e2e/record-journey.mjs     (needs the API on :8000 and vite preview on :4173)
import { createRequire } from "node:module";
import { mkdirSync, renameSync } from "node:fs";
const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch { playwright = require("/opt/node22/lib/node_modules/playwright"); }
const OUT = process.env.OUT ?? "recordings";
const SPEED = process.env.SPEED ?? "1.5";
mkdirSync(OUT, { recursive: true });

const browser = await playwright.chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, recordVideo: { dir: OUT, size: { width: 1600, height: 900 } } });
await ctx.addInitScript(() => { localStorage.setItem("sherin.char.muted", "true"); });
const page = await ctx.newPage();
await page.goto("http://localhost:4173/journey", { waitUntil: "networkidle" });
await page.selectOption('select[aria-label="Animation speed"]', SPEED);
await page.waitForTimeout(1200);
await page.getByRole("button", { name: "Play Journey" }).click();
await page.waitForFunction(() => document.querySelector('[data-testid="scene-6"]') && document.querySelector('[data-testid="sherin-layer"]').dataset.pose === "waiting", null, { timeout: 300000 });
await page.waitForTimeout(4000); // the workflow is genuinely paused here
await page.locator('[data-testid="scene-6"] [data-testid^="approval-"]').getByRole("textbox").fill("Within mandate. Approved.");
await page.waitForTimeout(800);
await page.locator('[data-testid="scene-6"] [data-testid^="approval-"]').getByRole("button", { name: "Approve" }).click();
await page.waitForFunction(() => document.querySelector('[data-testid="scene-7"]') && document.querySelector('[data-testid="sherin-layer"]').dataset.pose === "success", null, { timeout: 120000 });
await page.waitForTimeout(5000);
const video = page.video();
await ctx.close();
const path = await video.path();
renameSync(path, `${OUT}/sherin-guided-journey.webm`);
console.log(`saved ${OUT}/sherin-guided-journey.webm`);
await browser.close();
