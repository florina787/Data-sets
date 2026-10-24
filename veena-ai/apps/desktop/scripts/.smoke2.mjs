import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
const ud = fs.mkdtempSync("/tmp/claude-0/ud-");
const app = await electron.launch({ args: [".", "--no-sandbox"], cwd: process.cwd(), env: { ...process.env, VEENA_USER_DATA: ud } });
const page = await app.firstWindow();
await page.waitForTimeout(4000);
const seq = [];
for (let i = 0; i < 10; i++) {
  const kind = i % 2 ? "window" : "screen";
  const t0 = Date.now();
  const n = await app.evaluate(async ({ desktopCapturer }, kind) => (await desktopCapturer.getSources({ types: [kind], thumbnailSize: { width: 360, height: 220 } })).length, kind);
  seq.push(`${kind[0]}${n}@${Date.now() - t0}ms`);
}
console.log(seq.join(" "));
await app.close();
