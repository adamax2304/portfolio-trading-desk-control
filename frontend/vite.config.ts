import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { writeFileSync, mkdirSync } from "node:fs";

// Build stamp — computed once at config load (build time). Lets the operator + backend
// see exactly which UI bundle is live (kills "stale frontend" ambiguity). PART 0.
const d = new Date();
const p = (n: number) => String(n).padStart(2, "0");
const BUILD_ID = `b-${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}-${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}`;
const BUILD_TIME = d.toISOString();

// Plugin: write dist/build_info.json so the backend can report the served UI build id.
function stampPlugin() {
  return {
    name: "build-stamp",
    closeBundle() {
      try {
        mkdirSync("dist", { recursive: true });
        writeFileSync("dist/build_info.json", JSON.stringify({ build_id: BUILD_ID, build_time: BUILD_TIME }, null, 2));
      } catch { /* dist not present */ }
    },
  };
}

// Dev proxy → FastAPI backend on :8010. In production the Mini App is served over HTTPS
// and VITE_API_BASE points at the deployed control API.
export default defineConfig({
  plugins: [react(), stampPlugin()],
  define: {
    __BUILD_ID__: JSON.stringify(BUILD_ID),
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
  },
  server: {
    port: 5173,
    // allow tunnel hosts (cloudflared/ngrok) so the Telegram Mini App can load the dev server
    // over HTTPS; /api is proxied to the backend so app + API share one public origin.
    allowedHosts: true,
    proxy: { "/api": "http://127.0.0.1:8010" },
  },
});
