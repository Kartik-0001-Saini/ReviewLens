import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the app runs on :5173 and forwards /api calls to FastAPI on :8000,
// so the browser only ever talks to our own server, never to the AI provider.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});
