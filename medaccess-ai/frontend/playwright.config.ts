import { defineConfig, devices } from "@playwright/test";

// Expects the backend on :8000 and `vite preview` on :4173 (see README "End-to-end tests").
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  retries: 0,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"], ["junit", { outputFile: "test-results/e2e-junit.xml" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:4173",
    screenshot: "only-on-failure",
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
});
