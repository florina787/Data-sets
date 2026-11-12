// Real screen-capture test of the desktop app (packaged executable, or Electron + main.js in dev):
// list sources through VEENA's own bridge, select a screen exactly as the picker does, receive real
// frames through getDisplayMedia, check they are not blank, stop, and check the stream is released.
//
//   node scripts/smoke-capture.mjs <executable> [main.js] [--out result.json]
// macOS CI runners cannot grant Screen Recording; there the result is "no-permission", not a pass.
import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [exe, maybeMain] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const outIdx = process.argv.indexOf("--out");
const out = outIdx > 0 ? process.argv[outIdx + 1] : null;
const userData = fs.mkdtempSync(path.join(os.tmpdir(), "veena-capture-"));
const args = [...(maybeMain ? [maybeMain] : []), ...(process.platform === "linux" ? ["--no-sandbox"] : [])];
const result = { platform: process.platform, status: "fail", steps: {} };
const app = await electron.launch({ executablePath: exe, args, env: { ...process.env, VEENA_USER_DATA: userData} });
try {
  const page = await app.firstWindow();
  await page.waitForFunction(() => !!window.veena, null, { timeout: 30000 });
  // Let the window paint first, so the screen has real content to capture.
  await page.waitForSelector("h1, h2", { timeout: 60000 }).catch(() => undefined);
  await page.waitForTimeout(1500);
  const access = await page.evaluate(() => window.veena.mediaAccess("screen"));
  result.steps.permission = access;
  const sources = await page.evaluate(() => window.veena.listScreenSources());
  result.steps.sources = sources.map((s) => ({ name: s.name, kind: s.kind, previewable: s.previewable, thumbnail: !!s.thumbnail }));
  const screen = sources.find((s) => s.kind === "screen");
  if (!screen) throw new Error("no screen source listed");
  if (process.platform === "darwin" && access !== "granted") {
    result.status = "no-permission";
    result.note = "macOS Screen Recording permission cannot be granted on a CI runner; listing worked, capture not attempted.";
  } else {
    if (!screen.thumbnail) throw new Error(`screen listed without a preview: ${screen.note}`);
    const cap = await page.evaluate(async (id) => {
      await window.veena.selectScreenSource(id, false);
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 5 } }, audio: false });
      const video = document.createElement("video");
      video.muted = true;
      video.srcObject = stream;
      await video.play();
      for (let i = 0; i < 50 && !video.videoWidth; i++) await new Promise((r) => setTimeout(r, 100));
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 36;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(video, 0, 0, 64, 36);
      const d = ctx.getImageData(0, 0, 64, 36).data;
      let min = 765, max = 0;
      for (let i = 0; i < d.length; i += 4) { const v = d[i] + d[i + 1] + d[i + 2]; min = Math.min(min, v); max = Math.max(max, v); }
      const width = video.videoWidth, height = video.videoHeight;
      const track = stream.getVideoTracks()[0];
      const settings = track.getSettings();
      stream.getTracks().forEach((t) => t.stop());
      video.srcObject = null;
      // A second getDisplayMedia without a new selection must be refused (single-use consent).
      let reused = false;
      try { await navigator.mediaDevices.getDisplayMedia({ video: true }); reused = true; } catch { /* expected */ }
      return { width, height, contrast: max - min, trackState: track.readyState, settings: { width: settings.width, height: settings.height }, reusedWithoutConsent: reused };
    }, screen.id);
    result.steps.capture = cap;
    if (!cap.width) throw new Error("no frames received");
    if (cap.contrast < 10) throw new Error("captured frame is blank");
    if (cap.trackState !== "ended") throw new Error("capture stream not released after stop");
    if (cap.reusedWithoutConsent) throw new Error("a second capture started without a new user selection");
    result.status = "pass";
  }
} catch (e) {
  result.error = String(e?.message ?? e);
} finally {
  await app.close().catch(() => undefined);
}
console.log(JSON.stringify(result, null, 2));
if (out) fs.writeFileSync(out, JSON.stringify(result, null, 2));
process.exit(result.status === "fail" ? 1 : 0);
