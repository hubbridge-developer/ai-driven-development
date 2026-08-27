import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    // On GKE the dev server sits behind a GCE L7 LB that cuts idle connections
    // at ~30s. Vite responds to a dropped-then-reconnected HMR socket with a full
    // page reload — which looks like "the page refreshes every 30 seconds".
    // Disable HMR when VITE_DISABLE_HMR=1 (set in k8s); keep it on for local dev.
    hmr: process.env.VITE_DISABLE_HMR === '1' ? false : undefined,
    proxy: {
      '/api': {
        target: 'http://add-api:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://add-api:8001',
        ws: true,
      },
    },
  },
})
