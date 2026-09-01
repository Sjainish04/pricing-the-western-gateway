/* The 2D corridor map, and the reason it exists.
 *
 * Leaflet draws raster tiles as ordinary DOM <img> elements and its vector
 * overlays as SVG.  Neither needs WebGL, and neither needs requestAnimationFrame
 * to appear.  That makes it the fallback whenever the 3D view cannot run --
 * embedded preview panes, background tabs, machines without hardware
 * acceleration -- and it carries exactly the same model output: links coloured
 * by volume/capacity and weighted by volume, charging points, transit stations.
 *
 * The 3D view is better for showing why diversion matters, because height gives
 * volume a second channel and the buildings give the neighbourhood streets
 * context.  This one always works.
 */
import { useEffect, useRef, useState } from 'react'

const BANDS = [
  { max: 0.60, color: '#1baf7a', label: 'Free flowing (v/c < 0.60)' },
  { max: 0.75, color: '#86b6ef', label: 'Busy (0.60 – 0.75)' },
  { max: 0.88, color: '#2a78d6', label: 'Heavy (0.75 – 0.88)' },
  { max: 0.96, color: '#eb6834', label: 'Near capacity (0.88 – 0.96)' },
  { max: 99, color: '#d03b3b', label: 'At or over capacity (> 0.96)' },
]
const bandColor = (vc) =>
  vc == null ? '#898781' : (BANDS.find((b) => vc < b.max) ?? BANDS.at(-1)).color

/* Burden shown as a sequential ramp over its own observed range rather than a
 * fixed scale, because the spread across sub-areas is narrow (roughly 0.5% to
 * 0.8% of income) and a fixed 0-1 scale would render every marker the same
 * colour.  Radius carries trip share, so a large circle is a large group and a
 * dark circle is a heavily burdened one -- two channels, two variables. */
const BURDEN_RAMP = ['#dbeafe', '#93c5fd', '#3b82f6', '#1d4ed8', '#172554']
function burdenColor(value, lo, hi) {
  if (value == null || hi <= lo) return BURDEN_RAMP[0]
  const t = Math.min(Math.max((value - lo) / (hi - lo), 0), 0.999)
  return BURDEN_RAMP[Math.floor(t * BURDEN_RAMP.length)]
}

export default function Map2D({
  geography,
  basemap,
  linkVc = {},
  linkVolumes = {},
  linkTimes = {},
  linkNames = {},
  showTransit = true,
  showGantries = true,
  subareaBurden = null,
  height = 560,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const layersRef = useRef({})
  const tileRef = useRef(null)
  // Leaflet is imported asynchronously, so the overlay effect below would
  // otherwise run first, find no map, bail out, and never re-run -- leaving
  // basemap tiles with no corridor drawn on them.
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined

    // Leaflet is imported asynchronously, and React StrictMode mounts every
    // effect twice in development. Between the two mounts React can detach the
    // container, so a late-resolving import would call L.map() on a node that
    // is no longer in the document -- which fails inside setView with
    // "Cannot read properties of undefined (reading '_leaflet_pos')" and leaves
    // the panel with a sized-but-empty div.
    //
    // Three guards handle it: `cancelled` for the resolve-after-unmount case,
    // `isConnected` for the detached-container case, and a local `map` binding
    // so cleanup can tear down an instance that was created after the ref was
    // already cleared.
    let map = null
    let cancelled = false

    import('leaflet').then((L) => {
      if (cancelled || !el.isConnected) return
      // A torn-down map can leave its id behind, which would make Leaflet
      // refuse to initialise the container a second time.
      if (el._leaflet_id) delete el._leaflet_id

      map = L.map(el, { scrollWheelZoom: false }).setView([43.6190, -79.4930], 12)
      mapRef.current = map
      setReady(true)
      // Leaflet mis-sizes itself when created inside a container that was
      // hidden or is still settling; this forces a recount once laid out.
      setTimeout(() => { if (!cancelled) map.invalidateSize() }, 200)
    }).catch(() => { /* chunk failed to load; the panel stays empty */ })

    return () => {
      cancelled = true
      if (map) map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !basemap) return
    let cancelled = false
    import('leaflet').then((L) => {
      if (cancelled) return
      if (tileRef.current) map.removeLayer(tileRef.current)
      tileRef.current = L.tileLayer(basemap.url, {
        attribution: basemap.attribution,
        maxZoom: basemap.maxZoom ?? 19,
      }).addTo(map)
      // Keep the basemap under the corridor overlays.
      tileRef.current.bringToBack()
    })
    return () => { cancelled = true }
  }, [ready, basemap])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !geography?.link_geometry) return
    let cancelled = false

    import('leaflet').then((L) => {
      if (cancelled) return
      Object.values(layersRef.current).forEach((layer) => map.removeLayer(layer))
      layersRef.current = {}

      const links = L.layerGroup().addTo(map)
      layersRef.current.links = links
      for (const f of geography.link_geometry.features) {
        const id = f.properties.link_id
        const vc = linkVc[id]
        const volume = linkVolumes[id]
        const minutes = linkTimes[id]
        L.polyline(
          f.geometry.coordinates.map(([lon, lat]) => [lat, lon]),
          {
            color: bandColor(vc),
            weight: 4 + Math.min((volume ?? 0) / 2200, 8),
            opacity: 0.9,
            dashArray: f.properties.charged ? null : '7 6',
          },
        ).bindPopup(
          `<b>${linkNames[id] ?? f.properties.name}</b><br/>`
          + (vc != null
            ? `v/c <b>${vc.toFixed(3)}</b> · ${Math.round(volume).toLocaleString()} vehicles`
              + (minutes != null ? `<br/>${minutes.toFixed(1)} min to traverse` : '')
            : 'no modelled volume')
          + (f.properties.charged
            ? '<br/><i>inside the charging screenline</i>'
            : '<br/><i>not charged</i>'),
        ).addTo(links)
      }

      if (showGantries) {
        const group = L.layerGroup().addTo(map)
        layersRef.current.gantries = group
        for (const g of geography.gantries ?? []) {
          const diversion = g.role === 'diversion'
          L.circleMarker([g.lat, g.lon], {
            radius: 7,
            color: '#ffffff',
            weight: 2,
            fillColor: diversion ? '#eb6834' : '#123a6b',
            fillOpacity: 1,
          }).bindPopup(
            `<b>${g.name}</b><br/>Role: ${g.role}<br/>`
            + `Captures ${g.captures_veh_peak.toLocaleString()} peak vehicles<br/>`
            + `<span style="color:#52514e">${g.note}</span>`,
          ).addTo(group)
        }
      }

      if (showTransit) {
        const group = L.layerGroup().addTo(map)
        layersRef.current.transit = group
        for (const s of geography.transit ?? []) {
          L.circleMarker([s.lat, s.lon], {
            radius: 7, color: '#ffffff', weight: 2,
            fillColor: '#1baf7a', fillOpacity: 1,
          }).bindPopup(
            `<b>${s.name}</b><br/>${s.mode === 'go_rail' ? 'Lakeshore West GO' : 'TTC'}<br/>`
            + `${s.ivt_to_union_min} min to Union<br/>`
            + `${s.peak_boardings_inbound.toLocaleString()} inbound peak boardings`,
          ).addTo(group)
        }
      }
      if (subareaBurden?.length) {
        const group = L.layerGroup().addTo(map)
        layersRef.current.subareas = group
        const values = subareaBurden.map((s2) => s2.burden_pct_income)
        const lo = Math.min(...values)
        const hi = Math.max(...values)
        for (const a of subareaBurden) {
          L.circleMarker([a.lat, a.lon], {
            // Area proportional to trip share, so the eye compares areas
            // rather than radii -- a radius-proportional encoding would
            // overstate the largest group by the square of its share.
            radius: 8 + 26 * Math.sqrt(a.trip_share),
            color: a.outside_toronto ? '#eb6834' : '#ffffff',
            weight: a.outside_toronto ? 3 : 2,
            dashArray: a.outside_toronto ? '4 3' : null,
            fillColor: burdenColor(a.burden_pct_income, lo, hi),
            fillOpacity: 0.85,
          }).bindPopup(
            `<b>${a.subarea}</b>`
            + (a.outside_toronto ? '<br/><i>outside the City of Toronto</i>' : '')
            + `<br/>Burden <b>${a.burden_pct_income.toFixed(3)}%</b> of household income`
            + `<br/>${(100 * a.trip_share).toFixed(1)}% of trips ·`
            + ` ${(100 * a.charge_share).toFixed(1)}% of the charge`
            + `<br/>Pays / uses <b>${a.pays_vs_uses.toFixed(3)}</b>`
            + `<br/>Transit access ${a.transit_access.toFixed(2)}`,
          ).addTo(group)
        }
      }
    })

    return () => { cancelled = true }
  }, [ready, geography, linkVc, linkVolumes, linkTimes, linkNames, showTransit,
      showGantries, subareaBurden])

  return (
    <div>
      <div ref={containerRef} className="map" style={{ height }} />
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
          <span className="swatch" style={{ background: '#123a6b', borderRadius: '50%' }} />
          Expressway charging point
        </span>
        <span className="key">
          <span className="swatch" style={{ background: '#eb6834', borderRadius: '50%' }} />
          Arterial screenline
        </span>
        <span className="key">
          <span className="swatch" style={{ background: '#1baf7a', borderRadius: '50%' }} />
          Transit station
        </span>
        <span className="key" style={{ color: 'var(--text-muted)' }}>
          Line weight = peak vehicles · colour = volume/capacity · dashed = untolled
        </span>
      </div>
    </div>
  )
}
