import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend serves `dist/` in production (with SPA fallback),
// so the app only ever calls relative `/api/...` URLs.
const backend = process.env.TE_BACKEND_URL ?? "http://127.0.0.1:8000";

// Base path: "/" by default (dev, Docker image at the root). For a prefixed deployment
// (e.g. Caddy `handle_path /talentengine/*`), build with VITE_BASE=/talentengine/.
const base = process.env.VITE_BASE ?? "/";

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: backend, changeOrigin: true } },
  },
  preview: {
    port: 4173,
    proxy: { "/api": { target: backend, changeOrigin: true } },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
    target: "es2020",
  },
});
