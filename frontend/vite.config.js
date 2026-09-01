import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Pinned to this file's directory rather than process.cwd(), so the dev server
// can be launched from any working directory with an absolute --config path.
const here = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  root: here,
  plugins: [react()],
  server: {
    port: 5178,
    proxy: { '/api': { target: 'http://127.0.0.1:8088', changeOrigin: true } },
  },
  build: { outDir: resolve(here, 'dist'), sourcemap: false, emptyOutDir: true },
})
