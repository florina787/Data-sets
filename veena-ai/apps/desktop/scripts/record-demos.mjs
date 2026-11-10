// Records authentic product demos from the REAL app with REAL local models.
// Synthetic, non-sensitive sample data only. Writes a WebM of the whole session
// plus marks.json (start/end of each demo and of each model wait), which
// scripts/cut-demos.sh turns into short clips.
//
//   npm run build && xvfb-run -a -s "-screen 0 1440x900x24" node scripts/record-demos.mjs <out-dir>
//
// Needs Ollama with qwen2.5:1.5b and qwen3-vl:2b-instruct, plus espeak-ng and ffmpeg
// for the synthetic meeting speech.
import { _electron as electron } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const out = path.resolve(process.argv[2] ?? "demo-recording");
fs.mkdirSync(out, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "veena-demo-"));

// Synthetic meeting speech (espeak voice; invented project, invented names).
const raw = path.join(tmp, "meeting.raw.wav");
const wav = path.join(tmp, "meeting.wav");
execFileSync("espeak-ng", [
  "-s", "145", "-w", raw,
  "Let's ship the Falcon search update on Friday. Ravi will update the runbook by Thursday. Mei will confirm the Redis memory limit with the infrastructure team.",
]);
execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", raw, "-ac", "1", "-ar", "16000", wav]);

// Privacy: the Home screen shows public/founder.png when it exists (a private local
// photo, never committed). Refuse to record while it is in the build.
for (const f of ["public/founder.png", "dist/founder.png"]) {
  if (fs.existsSync(path.resolve(import.meta.dirname, "..", f))) {
    console.error(`refusing to record: ${f} exists. Move it out of apps/desktop (and rebuild) first.`);
    process.exit(2);
  }
}

const app = await electron.launch({
  args: [".", "--no-sandbox", "--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${wav}`],
  cwd: path.resolve(import.meta.dirname, ".."),
  env: { ...process.env, VEENA_USER_DATA: path.join(tmp, "userdata") },
  recordVideo: { dir: out, size: { width: 1440, height: 900 } },
});
const page = await app.firstWindow();
const T0 = Date.now();
page.on("dialog", (d) => void d.accept());
const marks = [];
// Marks are saved after every step, so a failed run still keeps its timeline.
const mark = (name) => {
  marks.push({ name, t: (Date.now() - T0) / 1000 });
  fs.writeFileSync(path.join(out, "marks.json"), JSON.stringify(marks, null, 2));
  console.log(name, ((Date.now() - T0) / 1000).toFixed(1));
};
const pause = (ms) => page.waitForTimeout(ms);
const idle = () => page.waitForFunction(() => !document.querySelector("button[aria-label='Stop generating']"), null, { timeout: 900_000 });
const typeSlowly = async (locator, text) => {
  await locator.click();
  await page.keyboard.type(text, { delay: 28 });
};

// DEMOS=meeting,interview records only those steps (setup always runs).
const only = (process.env.DEMOS || "").split(",").filter(Boolean);
const want = (name) => only.length === 0 || only.includes(name);
let failed = null;
try {
// ---- Setup (not part of a demo clip) ----
await page.getByRole("heading", { name: "Welcome to VEENA" }).waitFor({ timeout: 90_000 });
await page.getByRole("button", { name: "Check my computer" }).click();
await page.getByText("Recommended", { exact: true }).waitFor();
await page.getByRole("button", { name: "Continue" }).click();
await page.getByText(/Local AI runtime \(Ollama .*\) is running/).waitFor({ timeout: 60_000 });
await page.getByRole("button", { name: "Continue" }).click();
await page.getByLabel("Use for text").selectOption("qwen2.5:1.5b");
await page.getByLabel("Use for vision").selectOption("qwen3-vl:2b-instruct");
for (let i = 0; i < 3; i++) await page.getByRole("button", { name: "Continue" }).click();
await page.getByText("VEENA is ready.").waitFor({ timeout: 300_000 });
await page.getByRole("button", { name: "Finish setup" }).click();
await page.getByText("Recent sessions").waitFor();
await pause(1500);

// ---- 1. Ask a question, answered by the local model ----
if (want("chat")) {
await page.getByRole("button", { name: "New conversation" }).click();
await pause(800);
mark("chat:start");
await typeSlowly(page.getByLabel("Message"), "Write a short Python function that checks whether a word is a palindrome.");
await page.keyboard.press("Enter");
mark("chat:wait");
await page.locator(".prose-veena").last().waitFor({ timeout: 300_000 });
mark("chat:streaming");
await idle();
await pause(2500);
mark("chat:end");

}
// ---- 2. Documents with citations ----
if (want("docs")) {
await page.getByRole("button", { name: "Knowledge" }).first().click();
await pause(800);
mark("docs:start");
await typeSlowly(page.getByLabel("Collection name"), "Project Falcon docs");
await page.getByRole("button", { name: "Create" }).click();
const doc = path.join(tmp, "falcon-design.md");
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
await pause(1200);
await page.getByLabel("Use in answers").check();
await page.getByRole("button", { name: "New conversation" }).click();
await pause(600);
await typeSlowly(page.getByLabel("Message"), "What is Falcon's search latency budget, and which index does it use?");
await page.keyboard.press("Enter");
mark("docs:wait");
await page.locator(".prose-veena").last().waitFor({ timeout: 300_000 });
mark("docs:streaming");
await idle();
await pause(800);
await page.getByRole("button", { name: /\[1\]/ }).first().click();
await pause(3000);
mark("docs:end");
await page.locator("aside[aria-label='Context'] input[type=checkbox]").first().uncheck().catch(() => undefined);

}
// ---- 3. Screen intelligence (the shared screen is VEENA's own window showing the code answer) ----
if (want("screen")) {
await page.getByRole("button", { name: "Screen Intelligence" }).first().click();
await pause(800);
mark("screen:start");
await page.getByRole("button", { name: "Choose screen or window" }).click();
const dialog = page.getByRole("dialog", { name: "Choose what to share" });
await dialog.locator("button[aria-pressed]").first().waitFor({ timeout: 30_000 });
await pause(1200);
await dialog.locator("button[aria-pressed]").first().click();
await pause(600);
await dialog.getByRole("button", { name: "Share", exact: true }).click();
await page.getByLabel("Live preview of the shared screen").waitFor();
await pause(1500);
await page.getByRole("button", { name: "Summarize Screen" }).click();
mark("screen:wait");
await page.locator(".prose-veena").last().waitFor({ timeout: 900_000 });
mark("screen:streaming");
await idle();
await pause(3000);
mark("screen:end");
await page.getByRole("button", { name: "Stop Sharing", exact: true }).click();

}
// ---- 4. Meeting notes from speech ----
if (want("meeting")) {
await page.getByRole("button", { name: "Meeting Copilot" }).first().click();
await pause(800);
mark("meeting:start");
await page.getByRole("checkbox").first().check();
await pause(500);
await page.getByRole("button", { name: "Start meeting session" }).click();
await pause(1000);
await page.getByRole("button", { name: "Start microphone" }).click();
mark("meeting:listening");
await page.getByText(/Redis/i).first().waitFor({ timeout: 180_000 });
await pause(4000);
await page.getByRole("button", { name: "Stop microphone" }).click();
await pause(800);
await page.getByRole("button", { name: "Generate notes" }).click();
mark("meeting:wait");
// Notes are ready when "Key takeaways" appears and the button offers "Regenerate".
await page.getByRole("button", { name: /Regenerate/ }).waitFor({ timeout: 900_000 });
await page.getByText("Key takeaways").first().waitFor();
mark("meeting:notes");
await pause(3500);
mark("meeting:end");

}
// ---- 5. Interview practice ----
if (want("interview")) {
await page.getByRole("button", { name: "Interview Practice" }).first().click();
await pause(800);
mark("interview:start");
await page.locator("select").nth(1).selectOption("architecture");
await pause(600);
await page.getByRole("button", { name: /Start practice interview/ }).click();
mark("interview:wait1");
await page.getByLabel("Your answer").waitFor({ timeout: 1_200_000 });
mark("interview:question");
await pause(1500);
await typeSlowly(
  page.getByLabel("Your answer"),
  "I would split documents into passages, embed them, store vectors in FAISS, retrieve the top passages for each question and cite them in the answer.",
);
await page.getByRole("button", { name: "Get feedback" }).click();
mark("interview:wait2");
await page.getByText("Feedback", { exact: true }).waitFor({ timeout: 900_000 });
mark("interview:feedback");
await pause(3500);
mark("interview:end");

}
// ---- 6. Evidence and memory: the Agents page ----
if (want("agents")) {
await page.getByRole("button", { name: "Agents" }).first().click();
mark("agents:start");
await page.getByText("The semantic spine").waitFor();
await pause(3000);
const scroller = page.locator("main .overflow-y-auto").first();
for (let y = 0; y <= 1300; y += 20) {
  await scroller.evaluate((el, top) => el.scrollTo(0, top), y);
  await pause(30);
}
await pause(2500);
mark("agents:end");

}
// Hero still: a cited answer in the night theme.
if (want("library")) {
await page.getByRole("button", { name: "Library" }).first().click();
await pause(1500);
mark("library:shot");
await page.screenshot({ path: path.join(out, "still-library.png") });

}
} catch (e) {
  failed = e;
  console.error("demo step failed:", e.message);
  await page.screenshot({ path: path.join(out, "failure.png") }).catch(() => {});
}
// Always close the app so the video file is finalised, even after a failed step.
const video = page.video();
await app.close();
const vpath = await video.path();
fs.renameSync(vpath, path.join(out, "session.webm"));
console.log("saved", path.join(out, "session.webm"));
if (failed) process.exit(1);
