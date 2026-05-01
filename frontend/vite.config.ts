import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // bind mounts en Mac/Windows no propagan eventos fs nativos: usar polling.
    watch: { usePolling: true, interval: 200 },
    hmr: {
      // accedido tanto vía localhost:5173 como vía Caddy (puerto 443).
      // El cliente HMR adapta al protocol/host real.
      clientPort: 5173,
    },
    proxy: {
      // Cuando se accede directo a localhost:5173, /api proxea al backend.
      // Cuando se accede vía Caddy, Caddy ya lo proxea — esto sobra pero no estorba.
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
})
