/* A 3D view of the study corridor over Toronto's building fabric.
 *
 * MapLibre GL with OpenFreeMap vector tiles.  Both are open source and need no
 * API key, token or account, which matters for a submission that has to keep
 * working after the author stops paying attention to it.
 *
 * The 3D is doing analytical work, not decoration.  The corridor's problem is
 * that an 8.2 km charged segment sits inside a much longer trip with two
 * arterial bypasses running beside it, and those bypasses are ordinary
 * neighbourhood streets.  Flat, they are three parallel lines.  Extruded, with
 * height carrying volume and colour carrying saturation, you can see the
 * expressway drain and the neighbourhood streets swell as you change the price.
 *
 * What is actually drawn in three dimensions:
 *   - each link as a raised ribbon, height proportional to peak volume
 *   - real gantry portals: two columns and a crossbeam spanning the roadway
 *   - transit stations as extruded platform blocks
 *   - the city's own buildings, from the basemap's extrusion layer
 *   - a static dash marking the links the charge does not apply to
 *
 * Note on imports: MapLibre GL v6 exports named symbols only -- it has no
 * default export -- so `import maplibregl from 'maplibre-gl'` silently yields
 * undefined and fails at `new maplibregl.Map(...)`.
 */
import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, NavigationControl, Popup, ScaleControl } from 'maplibre-gl'

import { buildingExtrusionLayer } from '../lib/basemaps.js'
import { nearestOnLine, orientedRect, ribbonPolygon } from '../lib/geometry.js'
import 'maplibre-gl/dist/maplibre-gl.css'

const START = { center: [-79.4930, 43.6190], zoom: 12.2, pitch: 62, bearing: 24 }

/* How long to wait before handing back to the 2D map. Two deadlines, because
   "no frames are being painted" and "frames are painting but the tiles are
   slow" need opposite responses -- see the watchdog in the init effect.

   PIPELINE_DEAD_MS is short: if requestAnimationFrame is not running, no amount
   of waiting will start it, and the reader should get a working map instead.

   SLOW_NETWORK_MS is generous on purpose. Roughly 1.5 MB has to arrive before
   MapLibre reports `loaded()` -- the library chunk, the style, and a viewport
   of vector tiles -- which is over 5 s on a slow connection and over 8 s on 3G.
   The previous single 5 s deadline took the 3D map away from precisely the
   readers whose connection could least afford to have downloaded it. */
const PIPELINE_DEAD_MS = 4000
const SLOW_NETWORK_MS = 25000

// v/c bands: a sequential ramp from clear to saturated, so severity reads as
// depth of colour, with a distinct critical red at the top of the scale.
const BANDS = [
  { max: 0.60, color: '#1baf7a', label: 'Free flowing (v/c < 0.60)' },
  { max: 0.75, color: '#86b6ef', label: 'Busy (0.60 – 0.75)' },
  { max: 0.88, color: '#2a78d6', label: 'Heavy (0.75 – 0.88)' },
  { max: 0.96, color: '#eb6834', label: 'Near capacity (0.88 – 0.96)' },
  { max: 99, color: '#d03b3b', label: 'At or over capacity (> 0.96)' },
]
const bandColor = (vc) =>
  vc == null ? '#898781' : (BANDS.find((b) => vc < b.max) ?? BANDS.at(-1)).color

/** A horizon for the low camera angles, tuned to the basemap's tone. */
function applySky(map, basemap) {
  const dark = basemap?.tone === 'dark'
  try {
    map.setSky(dark
      ? { 'sky-color': '#0d1626', 'horizon-color': '#243349', 'fog-color': '#1a2334',
          'horizon-fog-blend': 0.6, 'fog-ground-blend': 0.75, 'sky-horizon-blend': 0.8 }
      : { 'sky-color': '#9ec5f4', 'horizon-color': '#e8eef5', 'fog-color': '#dfe6ee',
          'horizon-fog-blend': 0.6, 'fog-ground-blend': 0.7, 'sky-horizon-blend': 0.8 })
  } catch { /* older MapLibre has no sky; everything else still works */ }
}

/**
 * Only OpenFreeMap's `liberty` style defines a 3D building layer, but every one
 * of them carries the same `building` source-layer with `render_height` on it.
 * Injecting the extrusion keeps 3D buildings available on all five styles
 * rather than just the one.
 */
function ensureBuildings(map, basemap) {
  if (map.getLayer('building-3d')) return
  if (!map.getSource('openmaptiles')) return
  try {
    map.addLayer(buildingExtrusionLayer(basemap?.buildingColor ?? '#d8d4cf'))
  } catch { /* style without the expected source-layer: skip silently */ }
}

// Ribbon width and height. Freeways are drawn wider so the hierarchy survives
// at low zoom; height carries volume, which is what actually changes.
const ribbonWidth = (kind) => (kind === 'freeway' ? 80 : 52)
const ribbonHeight = (volume) => 25 + Math.min((volume ?? 0) / 90, 190)

const GANTRY_CLEARANCE = 26      // metres of headroom under the crossbeam
const GANTRY_BEAM = 9

// A cinematic pass along the corridor, west to east, ending downtown.
const TOUR = [
  { center: [-79.5390, 43.6095], zoom: 14.6, pitch: 70, bearing: 68, hold: 3200,
    caption: 'Highway 427 — where the charge would begin' },
  { center: [-79.5090, 43.6170], zoom: 14.2, pitch: 72, bearing: 62, hold: 3000,
    caption: 'Islington and Royal York — the ramps that feed the charged segment' },
  { center: [-79.4880, 43.6200], zoom: 13.6, pitch: 74, bearing: 88, hold: 3400,
    caption: 'Lake Shore and The Queensway running beside it — the bypasses' },
  { center: [-79.4740, 43.6295], zoom: 14.6, pitch: 70, bearing: 44, hold: 3200,
    caption: 'The Humber River screenline — the charging boundary' },
  { center: [-79.4200, 43.6370], zoom: 13.4, pitch: 72, bearing: 76, hold: 3000,
    caption: 'The shared downstream section, which no gateway charge can price' },
  { center: [-79.3840, 43.6420], zoom: 14.6, pitch: 66, bearing: -38, hold: 3600,
    caption: 'Downtown — the destination every one of these trips is heading for' },
]

export default function Map3D({
  geography,
  linkVc = {},
  linkVolumes = {},
  linkTimes = {},
  linkNames = {},
  showBuildings = true,
  showTransit = true,
  showGantries = true,
  showRibbons = true,
  basemap,
  onUnavailable,
  height = 620,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const popupRef = useRef(null)
  const tourRef = useRef({ timers: [] })
  const basemapRef = useRef(basemap)
  basemapRef.current = basemap
  const boundRef = useRef(false)
  const onUnavailableRef = useRef(onUnavailable)
  onUnavailableRef.current = onUnavailable
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(null)
  const [stalled, setStalled] = useState(false)
  const [caption, setCaption] = useState(null)

  // --- create the map once -------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    let map
    try {
      map = new MapLibreMap({
        container: containerRef.current,
        style: basemap.url,
        ...START,
        antialias: true,
        maxPitch: 80,
      })
    } catch (err) {
      setFailed(String(err))
      onUnavailableRef.current?.(String(err))
      return undefined
    }

    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
    map.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }))
    // Surface every map error, not just HTTP ones. Filtering on `status`
    // discarded WebGL and style failures, which are the errors actually worth
    // showing, and left a blank panel with no explanation.
    map.on('error', (e) => {
      const err = e?.error
      const status = err?.status
      const message = status && status >= 400
        ? `basemap request failed (HTTP ${status})`
        : (err?.message ?? String(err ?? 'unknown map error'))
      setFailed(message)
      // A style or WebGL error is terminal for this view; tile 404s are not.
      if (!status) onUnavailableRef.current?.(message)
    })
    map.on('load', () => {
      // A sky gives the low camera angles a horizon to sit against. Guarded
      // because it is a newer API and its absence should not break the map.
      applySky(map, basemapRef.current)
      ensureBuildings(map, basemapRef.current)
      setReady(true)
      setStalled(false)
    })

    // Two different things can leave this panel empty, and they need opposite
    // responses:
    //
    //   the pipeline is DEAD    no requestAnimationFrame, so MapLibre stalls
    //                           before requesting a single tile. A hidden tab,
    //                           an embedded preview pane, a driver that claims
    //                           WebGL but cannot paint. Waiting achieves
    //                           nothing; hand back to 2D quickly.
    //   the pipeline is SLOW    frames are being painted, tiles are arriving,
    //                           the map simply has not finished. About 1.5 MB
    //                           has to land before `loaded()` turns true --
    //                           the library chunk, the style, and a viewport of
    //                           vector tiles -- which is over 5 s on a slow
    //                           connection and over 8 s on 3G. Bailing here
    //                           takes a working 3D map away from exactly the
    //                           readers whose connection can least afford to
    //                           have downloaded it.
    //
    // `render` fires once per painted frame and is driven by rAF, so it is a
    // direct test of the first case rather than a proxy for it. An earlier
    // single 5 s deadline could not tell the two apart, and told slow-network
    // readers the map "did not start rendering here" while it was rendering.
    let frames = 0
    map.on('render', () => { frames += 1 })

    const giveUp = (reason) => {
      if (map.loaded()) return
      setStalled(true)
      onUnavailableRef.current?.(reason)
    }

    // First deadline: is anything being painted at all?
    const deadTimer = setTimeout(() => {
      if (map.loaded() || frames > 0) return
      giveUp('it did not start rendering here')
    }, PIPELINE_DEAD_MS)

    // Second deadline: frames are painting but the map never finished. A
    // blocked tile host or a proxy that swallows some requests looks like this.
    const slowTimer = setTimeout(() => {
      giveUp(frames > 0
        ? 'it was still loading after ' + Math.round(SLOW_NETWORK_MS / 1000)
          + ' seconds, which usually means the basemap tiles are not reachable'
        : 'it did not start rendering here')
    }, SLOW_NETWORK_MS)

    popupRef.current = new Popup({ closeButton: false, closeOnClick: false })
    mapRef.current = map
    if (import.meta.env.DEV) window.__uttanMap = map

    const wake = () => {
      if (document.visibilityState !== 'visible') return
      map.resize()
      map.triggerRepaint()
      setTimeout(() => { if (map.loaded()) setStalled(false) }, 1500)
    }
    document.addEventListener('visibilitychange', wake)
    const observer = new ResizeObserver(() => {
      map.resize()
      map.triggerRepaint()
    })
    observer.observe(containerRef.current)

    return () => {
      clearTimeout(deadTimer)
      clearTimeout(slowTimer)
      tourRef.current.timers.forEach(clearTimeout)
      document.removeEventListener('visibilitychange', wake)
      observer.disconnect()
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
      boundRef.current = false
      setReady(false)
    }
  }, [])

  // --- swap the basemap without tearing the map down -----------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (!basemap?.url) return
    // setStyle discards every layer we added, so `ready` is dropped first and
    // raised again on styledata, which re-runs the geometry effect below.
    setReady(false)
    map.setStyle(basemap.url)
    const onStyle = () => {
      applySky(map, basemap)
      ensureBuildings(map, basemap)
      setReady(true)
      map.off('styledata', onStyle)
    }
    map.on('styledata', onStyle)
    return () => map.off('styledata', onStyle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap?.id])

  // --- build all the 3D geometry -------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !geography?.link_geometry) return

    const lines = geography.link_geometry.features

    // 1. Link ribbons -------------------------------------------------------
    const ribbons = {
      type: 'FeatureCollection',
      features: lines.map((f) => {
        const id = f.properties.link_id
        const vc = linkVc[id] ?? null
        const volume = linkVolumes[id] ?? null
        return {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: ribbonPolygon(f.geometry.coordinates, ribbonWidth(f.properties.kind)),
          },
          properties: {
            ...f.properties,
            vc, volume,
            color: bandColor(vc),
            height: ribbonHeight(volume),
            display: linkNames[id] ?? f.properties.name,
            minutes: linkTimes[id] ?? null,
          },
        }
      }),
    }

    // 2. Gantry portals: two columns and a crossbeam across the roadway -----
    const portalParts = []
    for (const g of geography.gantries ?? []) {
      const host = lines.find((f) => f.properties.link_id.startsWith(g.road))
      if (!host) continue
      // Snap to the road: gantry points and centrelines were digitised
      // separately, so the raw coordinate can sit a few hundred metres off the
      // carriageway the portal is supposed to span.
      const { direction, coord } = nearestOnLine(host.geometry.coordinates, [g.lon, g.lat])
      const [gLon, gLat] = coord
      const [tx, ty] = direction
      const [px, py] = [-ty, tx]
      const span = ribbonWidth(host.properties.kind) + 16
      const isDiversion = g.role === 'diversion'
      const color = isDiversion ? '#eb6834' : '#123a6b'

      // Columns, one either side of the carriageway.
      for (const side of [-1, 1]) {
        const mLon = 111_320 * Math.cos((gLat * Math.PI) / 180)
        const base = [
          gLon + (px * side * span) / 2 / mLon,
          gLat + (py * side * span) / 2 / 110_540,
        ]
        portalParts.push({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: orientedRect(base, direction, 5, 5) },
          properties: { ...g, color, base: 0, height: GANTRY_CLEARANCE + GANTRY_BEAM, part: 'column' },
        })
      }
      // Crossbeam spanning the road, sitting on top of the columns.
      portalParts.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: orientedRect([gLon, gLat], direction, 5, span),
        },
        properties: {
          ...g, color, base: GANTRY_CLEARANCE, height: GANTRY_CLEARANCE + GANTRY_BEAM,
          part: 'beam',
        },
      })
    }
    const portals = { type: 'FeatureCollection', features: portalParts }

    // 3. Transit stations as raised platform blocks -------------------------
    const stations = {
      type: 'FeatureCollection',
      features: (geography.transit ?? []).map((s) => ({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: orientedRect([s.lon, s.lat], [1, 0], 150, 34),
        },
        properties: {
          ...s,
          color: s.mode === 'go_rail' ? '#1baf7a' : '#0f8a5f',
          height: 18 + Math.min((s.peak_boardings_inbound ?? 0) / 90, 40),
        },
      })),
    }

    const setOrAdd = (id, data, addLayers) => {
      if (map.getSource(id)) map.getSource(id).setData(data)
      else { map.addSource(id, { type: 'geojson', data }); addLayers() }
    }

    setOrAdd('ribbons', ribbons, () => {
      map.addLayer({
        id: 'ribbon-3d',
        type: 'fill-extrusion',
        source: 'ribbons',
        paint: {
          'fill-extrusion-color': ['get', 'color'],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.82,
        },
      })
      // A flat footprint under the ribbon keeps the alignment legible from
      // directly overhead, where an extrusion collapses to nothing.
      map.addLayer({
        id: 'ribbon-footprint',
        type: 'line',
        source: 'ribbons',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 15, 2.5],
          'line-opacity': 0.9,
        },
      })
      if (boundRef.current) return
      boundRef.current = true
      map.on('mousemove', 'ribbon-3d', (e) => {
        const p = e.features[0].properties
        map.getCanvas().style.cursor = 'pointer'
        const vc = p.vc === 'null' || p.vc == null ? null : Number(p.vc)
        popupRef.current.setLngLat(e.lngLat).setHTML(
          `<strong>${p.display}</strong><br/>`
          + (vc != null
            ? `v/c <b>${vc.toFixed(3)}</b> · ${Number(p.volume).toLocaleString()} vehicles`
              + (p.minutes && p.minutes !== 'null'
                ? `<br/>${Number(p.minutes).toFixed(1)} min to traverse` : '')
            : 'no modelled volume')
          + (String(p.charged) === 'true'
            ? '<br/><em>inside the charging screenline</em>'
            : '<br/><em>not charged</em>'),
        ).addTo(map)
      })
      map.on('mouseleave', 'ribbon-3d', () => {
        map.getCanvas().style.cursor = ''
        popupRef.current.remove()
      })
    })

    // 4. A static dash marking the untolled links --------------------------
    //
    // This was an animated "flow pulse" that cycled line-dasharray on a 90 ms
    // interval. Every dasharray change makes MapLibre rebuild its line atlas
    // texture, so at ~11 rebuilds a second, on top of six fill-extrusion layers
    // at a steep pitch, it was enough to lock up the renderer on integrated
    // graphics. A static dash costs nothing and carries more information: it
    // marks which links the charge actually applies to.
    setOrAdd('centrelines', {
      type: 'FeatureCollection',
      features: lines.map((f) => ({
        ...f,
        properties: { ...f.properties, color: bandColor(linkVc[f.properties.link_id]) },
      })),
    }, () => {
      map.addLayer({
        id: 'link-untolled',
        type: 'line',
        source: 'centrelines',
        filter: ['!', ['get', 'charged']],
        layout: { 'line-cap': 'butt' },
        paint: {
          'line-color': '#ffffff',
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1.4, 15, 3.4],
          'line-opacity': 0.9,
          'line-dasharray': [2, 2.4],
        },
      })
    })

    setOrAdd('portals', portals, () => {
      map.addLayer({
        id: 'portal-3d',
        type: 'fill-extrusion',
        source: 'portals',
        paint: {
          'fill-extrusion-color': ['get', 'color'],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': ['get', 'base'],
          'fill-extrusion-opacity': 0.95,
        },
      })
      map.on('click', 'portal-3d', (e) => {
        const p = e.features[0].properties
        new Popup().setLngLat(e.lngLat).setHTML(
          `<strong>${p.name}</strong><br/>Role: ${p.role}<br/>`
          + `Captures ${Number(p.captures_veh_peak).toLocaleString()} peak vehicles<br/>`
          + `<span style="color:#52514e">${p.note}</span>`,
        ).addTo(map)
      })
    })

    setOrAdd('stations', stations, () => {
      map.addLayer({
        id: 'station-3d',
        type: 'fill-extrusion',
        source: 'stations',
        paint: {
          'fill-extrusion-color': ['get', 'color'],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.9,
        },
      })
      map.on('click', 'station-3d', (e) => {
        const p = e.features[0].properties
        new Popup().setLngLat(e.lngLat).setHTML(
          `<strong>${p.name}</strong><br/>`
          + `${p.mode === 'go_rail' ? 'Lakeshore West GO' : 'TTC'}<br/>`
          + `${p.ivt_to_union_min} min to Union<br/>`
          + `${Number(p.peak_boardings_inbound).toLocaleString()} inbound peak boardings`,
        ).addTo(map)
      })
    })

    // 5. Labels, drawn last so they sit above the extrusions ----------------
    const labels = {
      type: 'FeatureCollection',
      features: [
        ...(geography.gantries ?? []).map((g) => {
          const host = lines.find((f) => f.properties.link_id.startsWith(g.road))
          const at = host
            ? nearestOnLine(host.geometry.coordinates, [g.lon, g.lat]).coord
            : [g.lon, g.lat]
          return {
            type: 'Feature',
            geometry: { type: 'Point', coordinates: at },
            properties: { name: g.name, kind: 'gantry' },
          }
        }),
        ...(geography.transit ?? []).map((s) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
          properties: { name: s.name, kind: 'transit' },
        })),
      ],
    }
    setOrAdd('labels', labels, () => {
      map.addLayer({
        id: 'poi-label',
        type: 'symbol',
        source: 'labels',
        minzoom: 12.4,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 11.5,
          'text-offset': [0, 1.3],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': ['match', ['get', 'kind'], 'transit', '#0b5c40', '#0b0b0b'],
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.8,
        },
      })
    })
  }, [ready, geography, linkVc, linkVolumes, linkTimes, linkNames])

  // --- layer toggles -------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const set = (id, on) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    }
    set('building-3d', showBuildings)
    set('ribbon-3d', showRibbons)
    set('ribbon-footprint', showRibbons)
    set('link-untolled', showRibbons)
    set('station-3d', showTransit)
    set('portal-3d', showGantries)
  }, [ready, showBuildings, showTransit, showGantries, showRibbons])

  const view = (opts) => mapRef.current?.easeTo({ duration: 1400, ...opts })

  const runTour = () => {
    const map = mapRef.current
    if (!map) return
    tourRef.current.timers.forEach(clearTimeout)
    tourRef.current.timers = []
    let delay = 0
    TOUR.forEach((stop) => {
      tourRef.current.timers.push(setTimeout(() => {
        setCaption(stop.caption)
        map.flyTo({ center: stop.center, zoom: stop.zoom, pitch: stop.pitch,
                    bearing: stop.bearing, duration: 2600, essential: true })
      }, delay))
      delay += stop.hold
    })
    tourRef.current.timers.push(setTimeout(() => {
      setCaption(null)
      map.flyTo({ ...START, duration: 2600 })
    }, delay))
  }

  const stopTour = () => {
    tourRef.current.timers.forEach(clearTimeout)
    tourRef.current.timers = []
    setCaption(null)
  }

  return (
    <div>
      <div className="map-toolbar">
        <button onClick={runTour}>▶ Fly the corridor</button>
        {caption && <button className="ghost" onClick={stopTour}>Stop</button>}
        <button className="ghost" onClick={() => { stopTour(); view(START) }}>Reset</button>
        <button className="ghost" onClick={() => view({ pitch: 0, bearing: 0 })}>Top-down</button>
        <button className="ghost"
                onClick={() => view({ center: [-79.5390, 43.6095], zoom: 14.6, pitch: 70, bearing: 68 })}>
          Hwy 427 gateway
        </button>
        <button className="ghost"
                onClick={() => view({ center: [-79.4740, 43.6295], zoom: 14.6, pitch: 70, bearing: 44 })}>
          Humber screenline
        </button>
        <button className="ghost"
                onClick={() => view({ center: [-79.4880, 43.6200], zoom: 13.6, pitch: 74, bearing: 88 })}>
          The bypasses
        </button>
      </div>

      <div className="map3d-wrap" style={{ height }}>
        <div
          ref={containerRef}
          className="map3d"
          style={{ height }}
          role="application"
          aria-label="Three-dimensional map of the Etobicoke-Gardiner study corridor"
        />

        {caption && <div className="map3d-caption">{caption}</div>}

        {stalled && !failed && (
          <div className="map3d-notice">
            <b>The map has not started rendering.</b>
            <p>
              The most common cause is that this tab is not in the foreground. Browsers stop
              issuing animation frames to a hidden or background tab, and the 3D renderer needs
              them before it will request a single tile.
            </p>
            <p>
              Bring this tab to the front and reload. If it is already in front, open{' '}
              <a href="/mapcheck">the map diagnostic</a> — it tests WebGL, the network and the
              renderer in order and names the first thing that fails.
            </p>
            <p className="muted">
              Every number on this page comes from the model and is unaffected either way.
            </p>
          </div>
        )}
      </div>

      {failed && (
        <div className="caveat" style={{ marginTop: 10 }}>
          <b>The map could not load.</b> {failed}. The basemap comes from OpenFreeMap over the
          network, so this view needs an internet connection. Every number on this page comes from
          the model and is unaffected.
        </div>
      )}

      <div className="legend" style={{ marginTop: 12 }}>
        {BANDS.map((b) => (
          <span className="key" key={b.label}>
            <span className="swatch" style={{ background: b.color }} />
            {b.label}
          </span>
        ))}
      </div>
      <div className="legend">
        <span className="key">
          <span className="swatch" style={{ background: '#123a6b' }} />
          Expressway gantry portal
        </span>
        <span className="key">
          <span className="swatch" style={{ background: '#eb6834' }} />
          Arterial screenline portal
        </span>
        <span className="key">
          <span className="swatch" style={{ background: '#1baf7a' }} />
          Transit station platform
        </span>
        <span className="key" style={{ color: 'var(--text-muted)' }}>
          Ribbon height = peak vehicles · colour = volume/capacity · dashed = untolled
        </span>
      </div>
    </div>
  )
}
