import { defineConfig } from "@playwright/test";

// End-to-end journeys against a RUNNING Career_flo server (single origin: API + built frontend).
// Locally: deploy/hf-space/start.sh on :7860.  CI: backend started with FRONTEND_DIST and a scripted Qwen stand-in.
export default defineConfig({
  testDir: "e2e",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "test-results/e2e-results.json" }]],
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:7860", viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
});
