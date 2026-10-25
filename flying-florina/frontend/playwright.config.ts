import { defineConfig, devices } from "@playwright/test";

// E2E runs against an isolated backend (fresh synthetic DB in a temp dir) and the Vite dev server.
const API_PORT = 8010;
const UI_PORT = 5183;
const dataDir = process.env.FF_E2E_DATA_DIR ?? `${process.env.TMPDIR ?? "/tmp"}/ff-e2e-${Date.now()}`;

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: `http://127.0.0.1:${UI_PORT}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `../backend/.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: { FF_DATA_DIR: dataDir, FF_GENERATED_DIR: `${dataDir}/generated`, OFFLINE_MODE: "true", DEMO_MODE: "true", FF_CORS_ORIGINS: `http://127.0.0.1:${UI_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${UI_PORT} --strictPort`,
      url: `http://127.0.0.1:${UI_PORT}`,
      env: { FF_BACKEND_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
