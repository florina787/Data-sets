import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": { target: process.env.API_URL ?? "http://localhost:8000", changeOrigin: true } } },
  preview: { port: 4173, proxy: { "/api": { target: process.env.API_URL ?? "http://localhost:8000", changeOrigin: true } } },
  build: { chunkSizeWarningLimit: 5000 },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], globals: true, css: false },
} as any);
