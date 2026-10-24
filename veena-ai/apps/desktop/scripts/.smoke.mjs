import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
const ud = fs.mkdtempSync("/tmp/claude-0/ud-");
const app = await electron.launch({ args: [".", "--no-sandbox"], cwd: process.cwd(), env: { ...process.env, VEENA_USER_DATA: ud } });
const page = await app.firstWindow();
await page.waitForTimeout(4000);
const r = await page.evaluate(async () => {
  const out = {};
  for (const c of [{ video: { frameRate: { ideal: 5, max: 10 } }, audio: false }, { video: true, audio: false }]) {
    const src = await window.veena.listScreenSources();
    out.n = src.length;
    try {
      await window.veena.selectScreenSource(src[0].id, false);
      const s = await navigator.mediaDevices.getDisplayMedia(c);
      out[JSON.stringify(c)] = s.getVideoTracks().map((t) => JSON.stringify(t.getSettings()));
      s.getTracks().forEach((t) => t.stop());
    } catch (e) { out[JSON.stringify(c)] = "ERR " + e.name + ": " + e.message; }
  }
  return out;
});
console.log(JSON.stringify(r, null, 1));
await app.close();
