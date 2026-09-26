/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

declare const process: { env: Record<string, string | undefined> }

// The dev server proxies /api to the FastAPI backend (override with VALUENGINE_API_URL).
const api = process.env.VALUENGINE_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.VITE_PORT ?? 5173),
    proxy: { '/api': api },
    // docs/METHODOLOGY.md is imported from outside the frontend root.
    fs: { allow: ['..'] },
  },
  build: {
    target: 'es2020',
    // The 3D scenes load as separate lazy chunks; three.js alone is ~600 kB before gzip.
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
