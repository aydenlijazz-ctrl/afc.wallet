import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const api = ['/get-balance', '/save-settings', '/get-settings', '/parse-custom-strategy', '/api']

export default defineConfig({
  plugins: [react()],
  // local dev: run the backend with APEX_AUTH_DISABLED=true on :8080
  server: { proxy: Object.fromEntries(api.map((p) => [p, 'http://localhost:8080'])) },
  preview: { proxy: Object.fromEntries(api.map((p) => [p, 'http://localhost:8080'])) },
  build: { rollupOptions: { output: { manualChunks: { firebase: ['firebase/app', 'firebase/auth'], charts: ['recharts'] } } } },
  test: { environment: 'jsdom' },
})
