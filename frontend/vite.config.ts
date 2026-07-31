import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The dev server proxies API + WebSocket calls to the FastAPI backend so the
// frontend needs no hardcoded backend URL in development.
// `--mode demo` (see .env.demo) builds the static GitHub Pages demo, which is
// served from a subpath and reads pre-baked JSON instead of the REST API.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    base: env.VITE_BASE_PATH || "/",
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          // Split heavy vendors so the initial paint doesn't wait on charts.
          manualChunks: {
            react: ["react", "react-dom", "react-router-dom"],
            charts: ["recharts"],
            motion: ["framer-motion"],
            query: ["@tanstack/react-query"],
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
        "/ws": {
          target: "ws://localhost:8000",
          ws: true,
        },
      },
    },
  };
});
