/* Picks the map the current browser context can actually render, and offers
 * the basemaps that engine supports.
 *
 * The 3D view is the better one -- extruded ribbons give volume a second
 * channel and the building fabric shows what the bypass routes run past -- but
 * it needs WebGL and a stream of animation frames, and an embedded preview
 * pane or a background tab provides neither.
 *
 * There are two separate guards, because they catch different things:
 *
 *   1. A pre-flight probe for WebGL and animation frames, which catches the
 *      common case before a blank panel is ever shown.
 *   2. A failure report from the 3D map itself.  The probe can pass and the
 *      map still fail -- a blocked tile host, a corporate proxy, a driver that
 *      advertises WebGL but cannot render.  Without this, any such cause left
 *      the reader with an empty rectangle and no map at all.
 *
 * Either way the 2D view takes over, and it carries the same model output, so
 * no analysis is lost by falling back -- only the extra visual channel.
 */
import { Suspense, lazy, useCallback, useEffect, useState } from 'react'

import { RASTER_BASEMAPS, VECTOR_BASEMAPS, defaultBasemap } from '../lib/basemaps.js'
import { probe3D } from '../lib/capabilities.js'
import { ChunkBoundary } from './ui.jsx'

const Map3D = lazy(() => import('./Map3D.jsx'))
const Map2D = lazy(() => import('./Map2D.jsx'))

export default function CorridorMap({ theme = 'light', ...props }) {
  const [probe, setProbe] = useState(null)
  const [failure, setFailure] = useState(null)   // reported by the 3D map
  const [override, setOverride] = useState(null) // reader's explicit choice
  const [vectorId, setVectorId] = useState(null)
  const [rasterId, setRasterId] = useState(null)

  useEffect(() => {
    let live = true
    probe3D().then((p) => { if (live) setProbe(p) })
    return () => { live = false }
  }, [])

  // Follow the interface theme until the reader picks a basemap themselves.
  useEffect(() => { setVectorId(null); setRasterId(null) }, [theme])

  const handleUnavailable = useCallback((reason) => {
    setFailure((previous) => previous ?? reason)
    // Release an explicit 3D choice too. Without this the override outranks the
    // failure report and the reader stays pinned on a view that just told us it
    // cannot render -- which is precisely the blank panel this exists to avoid.
    setOverride((previous) => (previous === '3d' ? null : previous))
  }, [])

  if (!probe) {
    return <div className="loading">Checking what this browser can render…</div>
  }

  const canTry3D = probe.ok && !failure
  const mode = override ?? (canTry3D ? '3d' : '2d')
  const list = mode === '3d' ? VECTOR_BASEMAPS : RASTER_BASEMAPS
  const chosenId = mode === '3d' ? vectorId : rasterId
  const setChosen = mode === '3d' ? setVectorId : setRasterId
  const basemap = list.find((b) => b.id === chosenId) ?? defaultBasemap(list, theme)

  const explanation = failure
    ? `The 3D view was available but ${failure}.`
    : probe.reason

  const retry3D = () => { setFailure(null); setOverride('3d') }

  return (
    <div>
      {(!probe.ok || failure) && mode === '2d' && (
        <div className="caveat" style={{ marginTop: 0, marginBottom: 12 }}>
          <b>Showing the 2D map.</b> {explanation} It draws the same model output —
          links coloured by volume/capacity and weighted by volume, charging points and
          transit stations — so nothing in the analysis is lost.
          <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="ghost" onClick={retry3D}>Try the 3D map again</button>
            <a className="pill" href="/mapcheck" style={{ textDecoration: 'none' }}>
              Run the full diagnostic
            </a>
          </div>
        </div>
      )}

      <div className="map-chooser">
        <div className="pill-row" style={{ margin: 0 }}>
          <button
            className={`pill${mode === '3d' ? ' on' : ''}`}
            onClick={retry3D}
            title={canTry3D ? '3D extruded corridor' : 'The 3D view did not start here'}
          >
            3D
          </button>
          <button className={`pill${mode === '2d' ? ' on' : ''}`}
                  onClick={() => setOverride('2d')}>2D</button>
        </div>
        <div className="pill-row" style={{ margin: 0 }}>
          {list.map((b) => (
            <button
              key={b.id}
              className={`pill${b.id === basemap.id ? ' on' : ''}`}
              title={b.note ?? b.label}
              onClick={() => setChosen(b.id)}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {basemap.note && <div className="note" style={{ marginTop: 0 }}>{basemap.note}</div>}

      {/* Both maps arrive as lazy chunks, so a tab left open across a deploy
        * asks for a filename that no longer exists and the import rejects.
        * Without a boundary React unmounts the subtree and the map area simply
        * goes blank -- the failure this page is least able to explain. */}
      <ChunkBoundary>
        <Suspense fallback={<div className="loading">Loading the map…</div>}>
          {mode === '3d'
            ? <Map3D basemap={basemap} onUnavailable={handleUnavailable} {...props} />
            : <Map2D basemap={basemap} {...props} />}
        </Suspense>
      </ChunkBoundary>
    </div>
  )
}
