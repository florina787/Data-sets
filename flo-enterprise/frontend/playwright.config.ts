import { defineConfig } from "@playwright/test";
import { existsSync } from "fs";

// Use a preinstalled Chromium when present (CI images), otherwise Playwright's managed browser.
const exe = [process.env.FLO_CHROMIUM, "/opt/pw-browsers/chromium"].find((p) => p && existsSync(p));
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: process.env.FLO_UI_URL ?? "http://localhost:8080", viewport: { width: 1440, height: 900 }, colorScheme: "dark",
    launchOptions: exe ? { executablePath: exe } : {} },
  reporter: [["list"]],
});
