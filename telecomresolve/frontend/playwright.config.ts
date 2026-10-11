import { defineConfig } from "@playwright/test";

// Starts a fresh demo backend (isolated SQLite files) and the Vite dev server.
const py = process.env.PYTHON ?? "python3";
const db = "/tmp/tr-e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5173", screenshot: "only-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {} },
  webServer: [
    {
      command: `rm -rf ${db} && mkdir -p ${db} && cd ../backend && APP_MODE=demo DATABASE_URL=sqlite:///${db}/app.db ` +
        `CHECKPOINT_URL=sqlite:///${db}/cp.db ${py} -m app.seed --reset && APP_MODE=demo DATABASE_URL=sqlite:///${db}/app.db ` +
        `CHECKPOINT_URL=sqlite:///${db}/cp.db ${py} -m uvicorn app.main:app --port 8000`,
      url: "http://127.0.0.1:8000/ready", reuseExistingServer: false, timeout: 60_000,
    },
    { command: "npx vite --port 5173 --strictPort", url: "http://127.0.0.1:5173", reuseExistingServer: false },
  ],
});
