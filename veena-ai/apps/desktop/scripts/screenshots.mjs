// Captures README screenshots from the REAL app with real local models.
// Needs Ollama with qwen2.5:1.5b and qwen2.5vl:3b. Linux: run under xvfb-run.
//   npm run build && xvfb-run -a -s "-screen 0 1440x900x24" node scripts/screenshots.mjs
import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const out = path.resolve(import.meta.dirname, "..", "..", "..", "docs", "images");
fs.mkdirSync(out, { recursive: true });
const userData = fs.mkdtempSync(path.join(os.tmpdir(), "veena-shots-"));
const args = process.platform === "linux" ? [".", "--no-sandbox"] : ["."];
const app = await electron.launch({ args, cwd: path.resolve(import.meta.dirname, ".."), env: { ...process.env, VEENA_USER_DATA: userData } });
const page = await app.firstWindow();
page.on("dialog", (d) => void d.accept());
const shot = async (name) => {
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`saved ${name}.png`);
};
const idle = () => page.waitForFunction(() => !document.querySelector("button[aria-label='Stop generating']"), null, { timeout: 900_000 });

// Setup wizard: hardware step.
await page.getByRole("heading", { name: "Welcome to VEENA" }).waitFor({ timeout: 90_000 });
await page.getByRole("button", { name: "Check my computer" }).click();
await page.getByText("Recommended", { exact: true }).waitFor();
await shot("setup");
await page.getByRole("button", { name: "Continue" }).click();
await page.getByLabel("Use for text").selectOption("qwen2.5:1.5b");
await page.getByLabel("Use for vision").selectOption("qwen2.5vl:3b");
await page.getByRole("button", { name: "Continue" }).click();
await page.getByRole("button", { name: "Finish setup" }).click();
await page.getByText("Recent sessions").waitFor();
await page.waitForTimeout(1500); // let the hero fade in
await shot("welcome");

// Conversation with a code answer.
await page.getByLabel("Message").fill("Show a short Python function that checks whether a string is a palindrome, and explain it briefly.");
await page.keyboard.press("Enter");
await page.locator(".prose-veena").last().waitFor({ timeout: 300_000 });
await idle();
await shot("conversation");

// Knowledge with a cited answer.
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
await page.getByLabel("Search query").fill("what index does Falcon use");
await page.getByRole("button", { name: "Search" }).click();
await page.getByText(/result\(s\) in/).waitFor();
await shot("knowledge");
await page.getByLabel("Use in answers").check();
await page.getByRole("button", { name: "New conversation" }).click();
await page.getByLabel("Message").fill("Which vector index does Project Falcon use, and what is its latency budget? Cite sources.");
await page.keyboard.press("Enter");
await page.locator(".prose-veena").last().waitFor({ timeout: 300_000 });
await idle();
await page.getByRole("button", { name: /\[1\]/ }).first().click();
await shot("citations");
await page.getByLabel("Use in answers").uncheck().catch(() => undefined);
await page.locator("aside[aria-label='Context'] input[type=checkbox]").first().uncheck().catch(() => undefined);

// Screen intelligence: share the screen and analyse code shown in VEENA itself.
await page.getByRole("button", { name: "Screen Intelligence" }).first().click();
await page.getByRole("button", { name: "Choose screen or window" }).click();
await page.locator("button[aria-pressed]").first().waitFor();
await shot("screen-picker");
await page.locator("button[aria-pressed]").first().click();
await page.getByRole("button", { name: "Share", exact: true }).click();
await page.getByRole("button", { name: "Explain Code" }).waitFor();
await page.getByRole("button", { name: "Summarize Screen" }).click();
// A 3B vision model on a CPU-only machine can take minutes on a cold start.
await page.locator(".prose-veena").last().waitFor({ timeout: 900_000 });
await idle();
await page.locator("main .overflow-y-auto").first().evaluate((el) => el.scrollTo(0, el.scrollHeight));
await shot("screen");
await page.getByRole("button", { name: "Stop Sharing", exact: true }).click();

// Interview practice with real feedback.
await page.getByRole("button", { name: "Interview Practice" }).first().click();
await page.locator("select").nth(1).selectOption("architecture");
await page.getByRole("button", { name: /Start practice interview/ }).click();
await page.getByLabel("Your answer").waitFor({ timeout: 180_000 });
await page
  .getByLabel("Your answer")
  .fill(
    "I would split documents into passages, embed them with a sentence-transformer, store vectors in FAISS, retrieve the top passages for each question, and pass them to the model with citations. I would evaluate retrieval with a labelled question set and monitor latency.",
  );
await page.getByRole("button", { name: "Get feedback" }).click();
await page.getByText("Feedback", { exact: true }).waitFor({ timeout: 300_000 });
await shot("interview");

// Meeting notes from a typed transcript.
await page.getByRole("button", { name: "Meeting Copilot" }).first().click();
await page.getByRole("checkbox").first().check();
await page.getByRole("button", { name: "Start meeting session" }).click();
for (const line of [
  "Asha: Let's ship the Falcon search update on Friday.",
  "Ravi: Agreed. I will update the runbook by Thursday.",
  "Mei: I still need to confirm the Redis memory limit with infra.",
  "Asha: Decision made, Friday release. Mei owns the Redis check.",
]) {
  await page.getByLabel("Add transcript line").fill(line);
  await page.getByRole("button", { name: "Add" }).click();
  await page.waitForTimeout(300);
}
await page.getByRole("button", { name: "Generate notes" }).click();
await page.getByRole("heading", { name: "Summary" }).first().waitFor({ timeout: 900_000 });
await shot("meeting");

// Analytics after real use.
await page.getByRole("button", { name: "Analytics" }).first().click();
await page.waitForTimeout(2500);
await shot("analytics");

await page.getByRole("button", { name: "Settings" }).first().click();
await page.waitForTimeout(1500);
await shot("settings");
await app.close();
