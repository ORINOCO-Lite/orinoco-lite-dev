import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  build: {
    emptyOutDir: true,
    outDir: resolve(import.meta.dirname, "dist-review"),
    sourcemap: false,
  },
  plugins: [react()],
  root: resolve(import.meta.dirname, "review"),
});
