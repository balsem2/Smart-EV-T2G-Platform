import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: ["smart-ev.localhost", "localhost", "127.0.0.1"],
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: ["smart-ev.localhost", "localhost", "127.0.0.1"],
  },
});
