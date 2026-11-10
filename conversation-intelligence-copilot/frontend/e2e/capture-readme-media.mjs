// Captures the README's focused screenshots and the demo recording from a running app (backend :8000, frontend :5173).
// Usage: node e2e/capture-readme-media.mjs [outDir]   (then scripts/readme_demo_gif.sh turns the recording into a GIF)
import { chromium } from "@playwright/test";
import fs from "node:fs";

const out = process.argv[2] ?? "../docs/readme";
const base = process.env.APP_URL ?? "http://127.0.0.1:5173";
fs.mkdirSync(`${out}/shots`, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium" });

async function fresh(page) {
  await page.goto(base + "/");
  await page.evaluate(() => localStorage.removeItem("cic.session"));
  await page.goto(base + "/");
}
async function ask(page, question, mode) {
  await fresh(page);
  if (mode) await page.getByTestId(`mode-${mode}`).click();
  await page.getByRole("textbox").fill(question);
  await page.keyboard.press("Enter");
  await page.waitForSelector("text=Uncertainty & method", { timeout: 90000 });
  await page.waitForTimeout(1200);
}
// Scroll the element to the top of whichever container scrolls, leaving `pad` pixels above it.
async function scrollTo(locator, pad = 84) {
  await locator.first().evaluate((el, pad) => {
    el.scrollIntoView({ block: "start" });
    let p = el.parentElement;
    while (p && !(p.scrollHeight > p.clientHeight && getComputedStyle(p).overflowY !== "visible")) p = p.parentElement;
    (p ?? window).scrollBy(0, -pad);
  }, pad);
  await locator.page().waitForTimeout(700);
}
async function shot(page, name) {
  // The sticky composer would cover the bottom of every shot; hide its pinned container.
  await page.evaluate(() => {
    let el = document.querySelector("textarea, [role=textbox]");
    while (el && !["sticky", "fixed"].includes(getComputedStyle(el).position)) el = el.parentElement;
    if (el) el.style.visibility = "hidden";
  });
  await page.screenshot({ path: `${out}/shots/${name}.png` });
  console.log("captured", name);
}

// Focused screenshots (skip with DEMO_ONLY=1).
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
const page = await ctx.newPage();
if (!process.env.DEMO_ONLY) {

await ask(page, "What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?");
await scrollTo(page.getByText("Zero-LLM route"));
await shot(page, "q1-answer");

await ask(page, "Which recurring customer concerns should contact-centre leadership review first?");
await scrollTo(page.getByText("Priority matrix: volume vs negative rate"));
await shot(page, "q4-answer");
await scrollTo(page.getByText("Evidence review"));
await shot(page, "evidence-review");
await scrollTo(page.getByText("AI decision replay"));
await page.getByText("AI decision replay").first().click().catch(() => {});
await page.waitForTimeout(800);
await shot(page, "decision-replay");

await ask(page, "X-ray conversation C0000479");
await scrollTo(page.getByText("Conversation X-Ray · C0000479"));
await shot(page, "xray");

// Interpretive questions would call the local model in AUTO; Analytics only keeps the capture fast and deterministic.
await ask(page, "What is driving negative sentiment in duplicate charges?", "analytics_only");
await scrollTo(page.getByText("Candidate drivers (agent behaviour and context)"));
await shot(page, "root-cause");

await page.goto(base + "/harness");
await page.locator(".react-flow__node").first().waitFor();
await page.waitForTimeout(1200);
await shot(page, "agent-harness");
}
await ctx.close();

// Demo recording: ask Q1 from the home page and scroll through the answer. Frames are screenshots taken in a loop
// (Playwright's own video recorder needs a bundled ffmpeg); scripts/readme_demo_gif.sh assembles them.
const rec = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: "dark" });
const demo = await rec.newPage();
const frames = `${out}/.frames`;
fs.rmSync(frames, { recursive: true, force: true });
fs.mkdirSync(frames, { recursive: true });
await fresh(demo);
await demo.waitForTimeout(800);
let recording = true;
const started = Date.now();
const recorder = (async () => {
  for (let i = 0; recording; i++) {
    await demo.screenshot({ path: `${frames}/${String(i).padStart(5, "0")}.png` });
    await new Promise((r) => setTimeout(r, 40));
  }
})();
await demo.waitForTimeout(900);
const box = demo.getByRole("textbox");
await box.click();
await box.pressSequentially("What were the top 5 topics associated with negative sentiment last month?", { delay: 30 });
await demo.waitForTimeout(500);
await demo.keyboard.press("Enter");
await demo.waitForSelector("text=Uncertainty & method", { timeout: 90000 });
await demo.waitForTimeout(1600);
for (const target of ["Zero-LLM route", "Top negative topics · November", "Supporting evidence", "Evidence review"]) {
  await demo.getByText(target).first().evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "start" }));
  await demo.waitForTimeout(2400);
}
recording = false;
await recorder;
const n = fs.readdirSync(frames).length;
fs.writeFileSync(`${frames}/fps.txt`, (n / ((Date.now() - started) / 1000)).toFixed(2));
console.log(`recorded ${n} frames`);
await browser.close();
