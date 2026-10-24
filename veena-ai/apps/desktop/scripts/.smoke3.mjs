import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
const ud = fs.mkdtempSync("/tmp/claude-0/ud-");
const app = await electron.launch({ args: [".", "--no-sandbox", "--use-fake-device-for-media-stream"], cwd: process.cwd(), env: { ...process.env, VEENA_USER_DATA: ud } });
const page = await app.firstWindow();
await page.waitForTimeout(5000);
const r = await page.evaluate(async () => {
  const info = await window.veena.backendInfo();
  const s = await (await fetch(info.url + "/api/sessions", { method: "POST", headers: { Authorization: "Bearer " + info.token, "Content-Type": "application/json" }, body: "{}" })).json();
  return await new Promise((resolve) => {
    const ws = new WebSocket(info.url.replace("http", "ws") + "/ws/audio?session_id=" + s.id + "&source=mic", ["veena", info.token]);
    ws.onmessage = (m) => resolve("message: " + m.data);
    ws.onclose = (e) => resolve("closed code " + e.code);
  });
});
console.log(r);
await app.close();
