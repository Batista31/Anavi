import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Any request to /api/** is forwarded to the FastAPI backend.
      // The browser never makes a cross-origin call — no CORS needed.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
      },
    },
  },
})
