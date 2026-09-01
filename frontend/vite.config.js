import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Pinned to this file's directory rather than process.cwd(), so the dev server
// can be launched from any working directory with an absolute --config path.
const here = dirname(fileURLToPath(import.meta.url))

/* MapLibre GL v6 is ESM-only and runs its tile parsing in a SEPARATE module
 * file. It locates that file at runtime with
 *
 *     new URL('./maplibre-gl-worker.mjs', import.meta.url)
 *
 * which, from the hashed chunk Rollup emits, resolves to
 * /assets/maplibre-gl-worker.mjs. Rollup has no reason to emit that file --
 * nothing imports it statically -- so it was simply absent from the build and
 * the request 404'd.
 *
 * The failure is silent and total: the worker never starts, so vector tiles
 * download and are never parsed. The style never reaches "loaded", `load`
 * never fires, no glyphs are ever requested, and the map paints empty frames
 * forever without emitting an error. That is the 3D map not working, for every
 * visitor on every machine.
 *
 * Emitted with fixed names, not hashed ones, because the URL above is computed
 * from the literal filename. The worker imports ./maplibre-gl-shared.mjs, so
 * that has to sit beside it. */
function maplibreWorkerAssets() {
  const dist = resolve(here, 'node_modules/maplibre-gl/dist')
  return {
    name: 'maplibre-worker-assets',
    apply: 'build',
    generateBundle() {
      for (const file of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) {
        this.emitFile({
          type: 'asset',
          fileName: `assets/${file}`,
          source: readFileSync(resolve(dist, file), 'utf8'),
        })
      }
    },
  }
}

export default defineConfig({
  root: here,
  plugins: [react(), maplibreWorkerAssets()],
  // Left unbundled in dev for the same reason: pre-bundling rewrites the module
  // into .vite/deps, where the sibling worker file does not exist, so the dev
  // server hits the identical 404.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    port: 5178,
    proxy: { '/api': { target: 'http://127.0.0.1:8088', changeOrigin: true } },
  },
  build: { outDir: resolve(here, 'dist'), sourcemap: false, emptyOutDir: true },
})
