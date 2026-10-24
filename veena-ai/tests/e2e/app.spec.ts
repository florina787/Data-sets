/**
 * End-to-end tests of the packaged-equivalent desktop app against the REAL
 * local stack: Electron + Python backend + Ollama (qwen2.5:1.5b, qwen2.5vl:3b)
 * + faster-whisper + Tesseract. Nothing here is mocked.
 *
 * The microphone is Chromium's fake capture device playing a clearly labelled
 * SIMULATED INPUT: speech synthesised by espeak-ng (see beforeAll).
 *
 * Run from apps/desktop:  xvfb-run -a npx playwright test
 */
import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const APP_DIR = path.resolve(__dirname, "../../apps/desktop");
const TEXT_MODEL = "qwen2.5:1.5b";
const VISION_MODEL = "qwen2.5vl:3b";

let app: ElectronApplication;
let page: Page;
let tmp: string;

function synthSpeech(text: string, out: string) {
  const raw = out.replace(/\.wav$/, ".raw.wav");
  execFileSync("espeak-ng", ["-s", "145", "-w", raw, text]);
  // Pad with silence so VAD sees the end of the utterance before the file loops.
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", raw, "-af", "adelay=500,apad=pad_dur=4", "-ac", "1", "-ar", "48000", out]);
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "veena-e2e-"));
  const wav = path.join(tmp, "question.wav");
  synthSpeech("What is the difference between a list and a tuple in Python?", wav);
  app = await electron.launch({
    args: [APP_DIR, "--no-sandbox", "--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${wav}`],
    cwd: APP_DIR,
    env: { ...process.env, VEENA_USER_DATA: path.join(tmp, "userdata") },
  });
  page = await app.firstWindow();
  page.on("dialog", (d) => void d.accept());
});

test.afterEach(async ({}, info) => {
  if (info.status !== info.expectedStatus) {
    const log = await page.evaluate(() => window.veena!.backendLog()).catch(() => "");
    await info.attach("backend-log", { body: log, contentType: "text/plain" });
    fs.writeFileSync(path.join(tmp, `backend-${info.title.slice(0, 20).replace(/\W+/g, "_")}.log`), log);
    console.log(`backend log saved under ${tmp}`);
  }
});

test.afterAll(async () => {
  await app?.close();
});

test("renderer is isolated from Node and exposes only the narrow bridge", async () => {
  const r = await page.evaluate(() => ({
    require: typeof (window as unknown as { require?: unknown }).require,
    process: typeof (window as unknown as { process?: unknown }).process,
    bridge: Object.keys((window as unknown as { veena: object }).veena).sort(),
  }));
  expect(r.require).toBe("undefined");
  expect(r.process).toBe("undefined");
  expect(r.bridge).toEqual(
    ["appInfo", "backendInfo", "backendLog", "listScreenSources", "mediaAccess", "onBackendStatus", "onShortcut", "openExternal", "restartBackend", "saveFile", "selectScreenSource"].sort(),
  );
});

test("backend is bound to loopback and rejects requests without the token", async () => {
  await expect.poll(async () => (await page.evaluate(() => window.veena!.backendInfo())).status, { timeout: 90_000 }).toBe("ready");
  const info = await page.evaluate(() => window.veena!.backendInfo());
  expect(info.url).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/);
  const r = await fetch(`${info.url}/api/sessions`);
  expect(r.status).toBe(401);
  const ok = await fetch(`${info.url}/api/health`);
  expect((await ok.json()).ok).toBe(true);
});

test("first-run setup detects hardware, models, and measures a real benchmark", async () => {
  await expect(page.getByRole("heading", { name: "Welcome to VEENA" })).toBeVisible();
  await page.getByRole("button", { name: "Check my computer" }).click();
  await expect(page.getByText("Memory", { exact: true })).toBeVisible();
  await expect(page.getByText("Recommended", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/Ollama .* is running/)).toBeVisible();
  await page.getByLabel("Use for text").selectOption(TEXT_MODEL);
  await page.getByLabel("Use for vision").selectOption(VISION_MODEL);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Run benchmark" }).click();
  await expect(page.getByText(/tokens\/s · first token/)).toBeVisible({ timeout: 180_000 });
  await expect(page.getByText(/× real time/)).toBeVisible();
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page.getByText("Your intelligent conversation companion.").first()).toBeVisible();
});

test("a typed question is answered by the local model with streaming", async () => {
  await page.getByLabel("Message").fill("What is 12 plus 30? Reply with only the number.");
  await page.keyboard.press("Enter");
  const answer = page.locator(".prose-veena").last();
  await expect(answer).toContainText("42", { timeout: 120_000 });
  await expect(page.getByText(TEXT_MODEL).first()).toBeVisible();
  // The session is now in history.
  await expect(page.getByRole("button", { name: /What is 12 plus 30/ }).first()).toBeVisible();
});

test("documents are indexed and answers cite them", async () => {
  await page.getByRole("button", { name: "Knowledge" }).first().click();
  await page.getByLabel("Collection name").fill("Project notes");
  await page.getByRole("button", { name: "Create" }).click();
  const doc = path.join(tmp, "falcon.md");
  fs.writeFileSync(
    doc,
    "# Project Falcon\n\nProject Falcon stores embeddings in a FAISS HNSW index with 32 neighbours per node.\n\n" +
      "The Falcon ingestion service runs nightly at 02:00 and processes PDF manuals.\n\nThe team lead for Falcon is Priya.",
  );
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Add files/ }).click();
  await (await chooser).setFiles(doc);
  await expect(page.getByText(/Indexed falcon\.md/)).toBeVisible({ timeout: 120_000 });

  await page.getByLabel("Search query").fill("which index type does Falcon use");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText(/HNSW index/).first()).toBeVisible();

  await page.getByLabel("Use in answers").check();
  await page.getByRole("button", { name: "New conversation" }).click();
  await page.getByLabel("Message").fill("Which vector index does Project Falcon use? Cite the source.");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /\[1\] falcon\.md/ }).first()).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".prose-veena").last()).toContainText(/HNSW/i, { timeout: 120_000 });
});

test("screen capture is refused without an explicit user selection", async () => {
  const err = await page.evaluate(async () => {
    try {
      const s = await navigator.mediaDevices.getDisplayMedia({ video: true });
      s.getTracks().forEach((t) => t.stop());
      return "granted";
    } catch (e) {
      return (e as Error).name;
    }
  });
  expect(err).not.toBe("granted");
});

test("user-selected screen is shared, analysed by the vision model, and stopped", async () => {
  test.setTimeout(480_000);
  await page.getByRole("button", { name: "Screen Intelligence" }).first().click();
  await page.getByRole("button", { name: "Choose screen or window" }).click();
  const dialog = page.getByRole("dialog", { name: "Choose what to share" });
  await expect(dialog).toBeVisible();
  const first = dialog.locator("button[aria-pressed]").first();
  await expect(first).toBeVisible({ timeout: 30_000 });
  await first.click();
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop sharing", exact: true })).toBeVisible();
  await expect(page.getByLabel("Live preview of the shared screen")).toBeVisible();

  await page.getByRole("button", { name: "Summarize Screen" }).click();
  // The live answer is labelled with the vision model while it generates...
  await expect(page.getByText(/vision$/).first()).toBeVisible({ timeout: 60_000 });
  // ...and on CPU-only machines the image encoding takes minutes before tokens stream.
  const t0 = Date.now();
  await expect(page.getByRole("button", { name: "Stop generating" })).toHaveCount(0, { timeout: 420_000 });
  console.log(`[measured] screen analysis with ${VISION_MODEL}: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  const bubble = page.locator(".prose-veena").last();
  await expect(bubble).not.toBeEmpty();
  await expect(page.getByText(VISION_MODEL).first()).toBeVisible();

  await page.getByRole("button", { name: "Stop Sharing", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop sharing", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Nothing is being shared" })).toBeVisible();
});

test("speech from the microphone is transcribed and the question is detected and answered", async () => {
  test.setTimeout(300_000);
  await page.getByRole("button", { name: "Conversation" }).first().click();
  await page.getByRole("button", { name: "New conversation" }).click();
  await page.getByRole("button", { name: "Start microphone" }).click();
  await expect(page.getByRole("status").filter({ hasText: /Listening|Loading speech model/ }).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/tuple/i).first()).toBeVisible({ timeout: 120_000 });
  // Detected question panel and an auto-generated answer.
  await expect(page.getByRole("button", { name: "Answer" }).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".prose-veena").first()).toContainText(/tuple/i, { timeout: 180_000 });
  await page.getByRole("button", { name: "Stop microphone" }).click();
  await expect(page.getByRole("button", { name: "Start microphone" })).toBeVisible();
});

test("a session can be deleted and disappears from history", async () => {
  const sessions = page.locator("aside li.group");
  const before = await sessions.count();
  expect(before).toBeGreaterThan(0);
  const first = sessions.first();
  await first.hover();
  await first.getByRole("button", { name: /^Delete / }).click();
  await expect(sessions).toHaveCount(before - 1);
});
