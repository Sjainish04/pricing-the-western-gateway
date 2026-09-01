/* A self-contained diagnostic for the 3D map.
 *
 * The map depends on three things that can each fail independently and
 * silently: a WebGL context, reachable OpenFreeMap resources, and MapLibre
 * getting far enough through its own lifecycle to request tiles.  This page
 * tests each one and prints the result on screen, so a failure can be
 * identified without opening developer tools.
 */
import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap } from 'maplibre-gl'

import 'maplibre-gl/dist/maplibre-gl.css'

const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty'

function webglReport() {
  const canvas = document.createElement('canvas')
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
  if (!gl) {
    return {
      ok: false,
      detail: 'No WebGL context could be created. MapLibre cannot render without one. '
        + 'This is usually hardware acceleration being disabled in the browser.',
    }
  }
  const dbg = gl.getExtension('WEBGL_debug_renderer_info')
  return {
    ok: true,
    detail: [
      `context: ${gl instanceof WebGL2RenderingContext ? 'WebGL2' : 'WebGL1'}`,
      dbg ? `renderer: ${gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)}` : null,
      `max texture: ${gl.getParameter(gl.MAX_TEXTURE_SIZE)}px`,
    ].filter(Boolean).join(' · '),
  }
}

export default function MapCheck() {
  const containerRef = useRef(null)
  const [checks, setChecks] = useState([])
  const [events, setEvents] = useState([])
  const [tiles, setTiles] = useState(0)

  const push = (name, ok, detail) =>
    setChecks((c) => [...c.filter((x) => x.name !== name), { name, ok, detail }])
  const log = (msg) =>
    setEvents((e) => [...e, `${new Date().toISOString().slice(11, 23)}  ${msg}`].slice(-40))

  useEffect(() => {
    let map
    let cancelled = false

    // 1. WebGL
    const gl = webglReport()
    push('1. WebGL context', gl.ok, gl.detail)

    // 2. Page visibility. MapLibre drives everything off requestAnimationFrame,
    //    which browsers do not fire for a hidden or background tab.
    requestAnimationFrame(() => !cancelled && push(
      '2. Animation frames', true,
      `visibilityState is "${document.visibilityState}" and rAF fired — MapLibre can render.`,
    ))
    setTimeout(() => {
      if (cancelled) return
      setChecks((c) => c.some((x) => x.name === '2. Animation frames') ? c : [...c, {
        name: '2. Animation frames', ok: false,
        detail: `visibilityState is "${document.visibilityState}" and requestAnimationFrame never `
          + 'fired. MapLibre stalls before it requests a single tile. This happens when the tab is '
          + 'in the background — bring this tab to the foreground and reload.',
      }])
    }, 2500)

    // 3. Can the browser reach the basemap?
    ;(async () => {
      for (const [name, url] of [
        ['3. Style JSON', STYLE_URL],
        ['4. Tile index', 'https://tiles.openfreemap.org/planet'],
      ]) {
        try {
          const t0 = performance.now()
          const r = await fetch(url)
          const ms = Math.round(performance.now() - t0)
          push(name, r.ok, `HTTP ${r.status} in ${ms} ms`)
        } catch (err) {
          push(name, false, `${err.name}: ${err.message} — the browser could not reach the host.`)
        }
      }
      try {
        const tj = await (await fetch('https://tiles.openfreemap.org/planet')).json()
        const url = tj.tiles[0].replace('{z}', 12).replace('{x}', 1143).replace('{y}', 1495)
        const r = await fetch(url)
        const buf = await r.arrayBuffer()
        push('5. A real Toronto tile', r.ok && buf.byteLength > 0,
          `HTTP ${r.status}, ${buf.byteLength.toLocaleString()} bytes`)
      } catch (err) {
        push('5. A real Toronto tile', false, `${err.name}: ${err.message}`)
      }
    })()

    // 6. MapLibre itself
    try {
      map = new MapLibreMap({
        container: containerRef.current,
        style: STYLE_URL,
        center: [-79.4930, 43.6190],
        zoom: 12.1,
        pitch: 55,
      })
      push('6. Map constructed', true, 'MapLibre accepted the container and style URL.')
    } catch (err) {
      push('6. Map constructed', false, `${err.name}: ${err.message}`)
      return () => { cancelled = true }
    }

    map.on('styledata', () => log('styledata — style parsed'))
    map.on('sourcedata', (e) => {
      if (e.sourceId === 'openmaptiles' && e.isSourceLoaded) log('sourcedata — basemap tiles in')
    })
    map.on('idle', () => log('idle — finished rendering'))
    map.on('error', (e) => log(`ERROR — ${e?.error?.message ?? String(e?.error ?? e)}`))
    map.on('load', () => {
      log('load — map ready')
      push('7. Map loaded', true, 'The style, sprite and glyphs all resolved.')
    })

    const timer = setInterval(() => {
      if (cancelled) return
      setTiles(performance.getEntriesByType('resource')
        .filter((r) => /\/planet\/.*\.pbf$/.test(r.name)).length)
      if (map.loaded?.()) {
        push('8. Tiles rendered', map.queryRenderedFeatures().length > 0,
          `${map.queryRenderedFeatures().length} features currently drawn`)
      }
    }, 1500)

    setTimeout(() => {
      if (cancelled) return
      setChecks((c) => c.some((x) => x.name === '7. Map loaded') ? c : [...c, {
        name: '7. Map loaded', ok: false,
        detail: 'MapLibre never fired its load event within 12 seconds. If check 2 failed this is '
          + 'the cause; otherwise the style, sprite or glyph request is hanging.',
      }])
    }, 12000)

    return () => {
      cancelled = true
      clearInterval(timer)
      map?.remove()
    }
  }, [])

  const failed = checks.filter((c) => !c.ok)

  return (
    <>
      <div className="page-head">
        <h1>Map diagnostic</h1>
        <p>
          Each dependency the 3D map needs, tested in order. Read down until the first failure —
          that is the cause. Send me what this page says and I can fix it directly.
        </p>
      </div>

      <div className="panel">
        <h2>Results</h2>
        <p className="sub">
          {failed.length === 0
            ? 'Every check has passed so far.'
            : `First failure: ${failed[0].name}.`}
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Check</th><th>Status</th><th>Detail</th></tr>
            </thead>
            <tbody>
              {[...checks].sort((a, b) => a.name.localeCompare(b.name)).map((c) => (
                <tr key={c.name}>
                  <td>{c.name}</td>
                  <td><span className={`badge ${c.ok ? 'pass' : 'fail'}`}>
                    {c.ok ? 'pass' : 'FAIL'}
                  </span></td>
                  <td style={{ whiteSpace: 'normal', textAlign: 'left' }}>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          Vector tiles requested so far: <b>{tiles}</b>. If this stays at 0 while checks 3–5 pass,
          MapLibre is not reaching its render loop.
        </div>
      </div>

      <div className="panel">
        <h2>MapLibre event log</h2>
        <p className="sub">Raw lifecycle events, newest last.</p>
        <pre style={{
          background: 'var(--page)', border: '1px solid var(--border)', borderRadius: 8,
          padding: 12, fontSize: 12, maxHeight: 240, overflow: 'auto', margin: 0,
        }}>
          {events.length ? events.join('\n') : 'no events yet…'}
        </pre>
      </div>

      <div className="panel">
        <h2>Live map</h2>
        <p className="sub">A bare MapLibre instance with no application code around it.</p>
        <div ref={containerRef} className="map3d" style={{ height: 380 }} />
      </div>
    </>
  )
}
