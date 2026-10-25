import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const backend = process.env.FF_BACKEND_URL ?? "http://127.0.0.1:8000";

// Strict CSP for the production build only (Vite dev injects an inline HMR preamble).
const csp: Plugin = {
  name: "ff-csp",
  apply: "build",
  transformIndexHtml(html) {
    const policy =
      "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; " +
      "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'";
    return html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${policy}" />`);
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss(), csp],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": backend, "/health": backend },
  },
  preview: { host: "127.0.0.1", port: 4173, proxy: { "/api": backend, "/health": backend } },
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: { output: { manualChunks: { echarts: ["echarts"], flow: ["@xyflow/react"] } } },
  },

});
