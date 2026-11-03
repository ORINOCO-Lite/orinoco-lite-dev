import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "dist-authentication",
    lib: {
      entry: "shared/editor.ts",
      formats: ["es"],
      fileName: () => "repository-auth.js",
    },
  },
});
