import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Lecteur autonome du prototype : un seul fichier JS (React compris), inséré dans les exports HTML
 * par le backend (backend/export_html.py). Styles en ligne uniquement : aucun CSS à joindre.
 */
export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist-player",
    emptyOutDir: true,
    lib: {
      entry: "src/player/standalone.tsx",
      name: "ProtoLabPlayer",
      formats: ["iife"],
      fileName: () => "protolab-player.js",
    },
  },
});
