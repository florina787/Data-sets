import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

const backend = path.resolve(here, "../backend");
const db = path.resolve(here, "../var/e2e.db");
// Optional explicit browser binary (e.g. a pre-installed Chromium); otherwise Playwright's default.
const chromium = process.env.PW_CHROMIUM;

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: [
    {
      command: `rm -f ${db} ${db}-wal ${db}-shm && python -m app.seed && python -m uvicorn app.main:app --port 8000`,
      cwd: backend,
      env: { DATABASE_URL: `sqlite:///${db}`, APP_ENV: "demo", EVAL_EXECUTION: "background" },
      url: "http://127.0.0.1:8000/ready",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    { command: "npx vite preview --port 5173 --strictPort", url: "http://127.0.0.1:5173", timeout: 60_000, reuseExistingServer: false },
  ],
});
