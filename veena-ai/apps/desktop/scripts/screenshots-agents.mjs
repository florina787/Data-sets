// Captures the Agents page from the REAL app after real answers from local models.
// Needs Ollama with qwen2.5:1.5b. Linux: run under xvfb-run.
//   npm run build && xvfb-run -a -s "-screen 0 1440x900x24" node scripts/screenshots-agents.mjs
import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const out = path.resolve(import.meta.dirname, "..", "..", "..", "docs", "images");
fs.mkdirSync(out, { recursive: true });
const userData = fs.mkdtempSync(path.join(os.tmpdir(), "veena-agents-"));
const args = process.platform === "linux" ? [".", "--no-sandbox"] : ["."];
const app = await electron.launch({ args, cwd: path.resolve(import.meta.dirname, ".."), env: { ...process.env, VEENA_USER_DATA: userData } });
const page = await app.firstWindow();
page.on("dialog", (d) => void d.accept());
const shot = async (name) => {
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`saved ${name}.png`);
};
const idle = () => page.waitForFunction(() => !document.querySelector("button[aria-label='Stop generating']"), null, { timeout: 900_000 });
const ask = async (text) => {
  await page.getByLabel("Message").fill(text);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(500);
  await idle();
};

await page.getByRole("heading", { name: "Welcome to VEENA" }).waitFor({ timeout: 90_000 });
await page.getByRole("button", { name: "Check my computer" }).click();
await page.getByText("Recommended", { exact: true }).waitFor();
await page.getByRole("button", { name: "Continue" }).click();
await page.getByText(/Local AI runtime \(Ollama .*\) is running/).waitFor({ timeout: 60_000 });
await page.getByRole("button", { name: "Continue" }).click();
await page.getByLabel("Use for text").selectOption("qwen2.5:1.5b");
await page.getByRole("button", { name: "Continue" }).click();
await page.getByRole("button", { name: "Continue" }).click(); // privacy
await page.getByRole("button", { name: "Continue" }).click(); // permissions
await page.getByText("VEENA is ready.").waitFor({ timeout: 300_000 });
await page.getByRole("button", { name: "Finish setup" }).click();
await page.getByText("Recent sessions").waitFor();

await page.getByRole("button", { name: "Knowledge" }).first().click();
await page.getByLabel("Collection name").fill("Project Falcon docs");
await page.getByRole("button", { name: "Create" }).click();
const doc = path.join(userData, "falcon-design.md");
fs.writeFileSync(
  doc,
  "# Project Falcon design\n\nFalcon stores document embeddings in a FAISS HNSW index with 32 neighbours per node, rebuilt nightly.\n\n" +
    "The ingestion service runs at 02:00 UTC and processes PDF manuals from the shared drive.\n\n" +
    "Search requests have a p95 latency budget of 300 ms; cache hits are served from Redis.",
);
const chooser = page.waitForEvent("filechooser");
await page.getByRole("button", { name: /Add files/ }).click();
await (await chooser).setFiles(doc);
await page.getByText(/Indexed falcon-design\.md/).waitFor({ timeout: 120_000 });
await page.getByLabel("Use in answers").check();
await page.getByRole("button", { name: "New conversation" }).click();

await ask("Which vector index does Project Falcon use, and what is its latency budget? Cite sources.");
await ask("How many engineers built Falcon, which company owns it, and what does it cost per month?");
await ask("What are the Kubernetes autoscaling thresholds for the Falcon pods?");
await page.locator("main .overflow-y-auto").first().evaluate((el) => el.scrollTo(0, el.scrollHeight));
await shot("agents-answer");

await page.getByRole("button", { name: "Agents" }).first().click();
await page.getByText("The semantic spine").waitFor();
await page.waitForTimeout(2500);
await shot("agents");
const scroller = page.locator("main .overflow-y-auto").first();
await scroller.evaluate((el) => el.scrollTo(0, 620));
await shot("agents-graphs");
await scroller.evaluate((el) => el.scrollTo(0, el.scrollHeight));
await shot("agents-traces");
await app.close();
