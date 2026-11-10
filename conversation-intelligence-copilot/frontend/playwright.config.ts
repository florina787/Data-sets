import { defineConfig, devices } from "@playwright/test";

// Starts (or reuses) the backend on :8000 and the Vite dev server on :5173.
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.APP_URL ?? "http://127.0.0.1:5173",
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || "/opt/pw-browsers/chromium" },
    trace: "retain-on-failure",
  },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    { command: "../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --port 8000", url: "http://127.0.0.1:8000/health", reuseExistingServer: true, timeout: 60_000 },
    { command: "npx vite --port 5173", url: "http://127.0.0.1:5173", reuseExistingServer: true, timeout: 60_000 },
  ],
});
