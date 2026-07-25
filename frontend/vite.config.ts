import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
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
