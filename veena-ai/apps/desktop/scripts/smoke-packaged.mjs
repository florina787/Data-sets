// Smoke test of a PACKAGED build: launches the installed/unpacked executable,
// waits for the bundled backend, checks security basics, and (with --ask,
// when Ollama and a model are available) asks one real question.
//
//   node scripts/smoke-packaged.mjs <path-to-executable> [--ask]
import { _electron as electron } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const exe = process.argv[2];
const ask = process.argv.includes("--ask");
if (!exe || !fs.existsSync(exe)) {
  console.error(`executable not found: ${exe}`);
  process.exit(2);
}
const userData = fs.mkdtempSync(path.join(os.tmpdir(), "veena-smoke-"));
const fail = (msg) => {
  console.error(`SMOKE FAIL: ${msg}`);
  process.exitCode = 1;
};

const t0 = Date.now();
const args = process.platform === "linux" ? ["--no-sandbox"] : [];
const app = await electron.launch({ executablePath: exe, args, env: { ...process.env, VEENA_USER_DATA: userData } });
try {
  const page = await app.firstWindow();
  let info;
  for (let i = 0; i < 180; i++) {
    info = await page.evaluate(() => window.veena?.backendInfo());
    if (info?.status === "ready" || info?.status === "failed") break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  if (info?.status !== "ready") {
    fail(`backend status ${info?.status}: ${info?.error ?? ""}\n${await page.evaluate(() => window.veena.backendLog())}`);
  } else {
    console.log(`backend ready in ${((Date.now() - t0) / 1000).toFixed(1)} s at ${info.url}`);
    const resources = await app.evaluate(() => process.resourcesPath);
    console.log(`resources: ${resources}`);
    if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(info.url)) fail("backend is not on loopback");
    if ((await fetch(`${info.url}/api/sessions`)).status !== 401) fail("backend accepted a request without the token");
    const h = { Authorization: `Bearer ${info.token}`, "Content-Type": "application/json" };
    const status = await (await fetch(`${info.url}/api/status`, { headers: h })).json();
    console.log(`ollama running: ${status.ollama.running}; models: ${status.models.map((m) => m.name).join(", ") || "none"}; tesseract: ${status.tesseract}`);
    const isolated = await page.evaluate(() => typeof window.require === "undefined" && typeof window.process === "undefined");
    if (!isolated) fail("renderer can reach Node globals");
    await page.getByRole("heading", { name: "Welcome to VEENA" }).waitFor({ timeout: 30000 });
    console.log("first-run setup screen rendered");
    const hw = await (await fetch(`${info.url}/api/system/hardware`, { headers: h })).json();
    console.log(`hardware: ${hw.hardware.cpu.name}, ${hw.hardware.ram_gb} GB RAM, recommended profile ${hw.recommendation.profile}`);
    if (ask) {
      const model = status.models.find((m) => !m.vision)?.name;
      if (!status.ollama.running || !model) fail("--ask needs Ollama with a text model");
      else {
        const sid = (await (await fetch(`${info.url}/api/sessions`, { method: "POST", headers: h, body: "{}" })).json()).id;
        await fetch(`${info.url}/api/settings`, { method: "PATCH", headers: h, body: JSON.stringify({ text_model: model }) });
        const text = await (await fetch(`${info.url}/api/chat`, { method: "POST", headers: h, body: JSON.stringify({ session_id: sid, text: "What is 2 plus 2? Answer with the number." }) })).text();
        const events = text.trim().split("\n").map((l) => JSON.parse(l));
        const answer = events.filter((e) => e.type === "token").map((e) => e.t).join("");
        console.log(`answer from ${model}: ${answer.trim().slice(0, 60)}`);
        if (!answer.includes("4")) fail("unexpected answer");
      }
    }
  }
} finally {
  await app.close();
}
console.log(process.exitCode ? "SMOKE FAILED" : "SMOKE PASSED");
