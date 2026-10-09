import { defineConfig } from "@playwright/test";

// The e2e run starts its own server on separate ports with an isolated var dir,
// so it never touches a developer's running demo.
export const API = "http://127.0.0.1:9700";
export const STORE = "http://127.0.0.1:9801";

export default defineConfig({
  testDir: ".",
  timeout: 8 * 60 * 1000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: API,
    viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
    trace: "retain-on-failure",
  },
  webServer: {
    // Stop a storefront left behind by an interrupted earlier run, then start clean.
    command:
      "(test -f ../var-e2e/run/storefront.json && kill -TERM -$(python3 -c \"import json;print(json.load(open('../var-e2e/run/storefront.json'))['pid'])\") 2>/dev/null; true) && sleep 1 && rm -rf ../var-e2e && cd ../backend && exec ../.venv/bin/python -m app",
    url: `${API}/api/health`,
    timeout: 120_000,
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
    env: {
      FOODCARE_VAR_DIR: "../var-e2e",
      FOODCARE_API_PORT: "9700",
      FOODCARE_STOREFRONT_PORT: "9801",
      FOODCARE_STOP_STOREFRONT_ON_EXIT: "1",
    },
  },
});
