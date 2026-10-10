import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// En local, le frontend appelle /api en relatif : Vite relaie vers le backend.
// Aucune configuration CORS ni variable d'environnement n'est nécessaire.
const backend = { target: "http://127.0.0.1:8000", changeOrigin: true };
const proxy = { "/api": backend, "/docs": backend, "/openapi.json": backend };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: { proxy },
  preview: { proxy },
});
