import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000", "/metrics": "http://localhost:8000" } },
  build: {
    chunkSizeWarningLimit: 2500,
    rollupOptions: { output: { manualChunks: { echarts: ["echarts", "echarts-for-react"], maplibre: ["maplibre-gl"], recharts: ["recharts"] } } },
  },
});
