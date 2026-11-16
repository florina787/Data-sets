import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// GitHub Pages serves this site from /<repo>/femora/ ; set FEMORA_BASE in CI. Local dev uses "/".
export default defineConfig({
  base: process.env.FEMORA_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  server: { host: "127.0.0.1", port: 5174 },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], css: false, globals: true },
});
