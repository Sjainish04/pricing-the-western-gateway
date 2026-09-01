/* The basemaps on offer, for both map engines.
 *
 * Everything here is free to use with no API key, token or account, which is
 * the constraint that rules out Mapbox, Stadia, Thunderforest and most of the
 * satellite providers.
 *
 * Only OpenFreeMap's `liberty` style ships a 3D building layer.  The others
 * carry the same `building` source-layer with `render_height` on it, so the
 * extrusion layer is injected for them -- see `buildingExtrusionLayer`.  That
 * keeps 3D buildings available on every vector style rather than only the one.
 */

// --- vector styles, used by the 3D (MapLibre) view -------------------------

export const VECTOR_BASEMAPS = [
  {
    id: 'liberty',
    label: 'Streets',
    url: 'https://tiles.openfreemap.org/styles/liberty',
    tone: 'light',
    buildingColor: 'hsl(35,8%,85%)',
    nativeBuildings: true,
    note: 'Full detail: street names, land use, transit lines.',
  },
  {
    id: 'bright',
    label: 'Bright',
    url: 'https://tiles.openfreemap.org/styles/bright',
    tone: 'light',
    buildingColor: 'hsl(35,8%,84%)',
    note: 'Higher contrast roads — the clearest for tracing the corridor.',
  },
  {
    id: 'positron',
    label: 'Minimal',
    url: 'https://tiles.openfreemap.org/styles/positron',
    tone: 'light',
    buildingColor: '#dcdcdc',
    note: 'Muted greys, so the modelled corridor carries all the colour.',
  },
  {
    id: 'dark',
    label: 'Dark',
    url: 'https://tiles.openfreemap.org/styles/dark',
    tone: 'dark',
    buildingColor: '#2b2b2b',
    note: 'Dark ground. The congestion ramp reads most vividly against it.',
  },
  {
    id: 'fiord',
    label: 'Midnight',
    url: 'https://tiles.openfreemap.org/styles/fiord',
    tone: 'dark',
    buildingColor: '#3b4763',
    note: 'Deep blue cartography, good for presenting on a projector.',
  },
]

/**
 * The extrusion layer OpenFreeMap's `liberty` style defines, generalised so it
 * can be added to any of the others.  They all carry the same `building`
 * source-layer with `render_height` and `render_min_height` attributes.
 */
export const buildingExtrusionLayer = (color) => ({
  id: 'building-3d',
  type: 'fill-extrusion',
  source: 'openmaptiles',
  'source-layer': 'building',
  minzoom: 14,
  paint: {
    'fill-extrusion-base': ['get', 'render_min_height'],
    'fill-extrusion-color': color,
    'fill-extrusion-height': ['get', 'render_height'],
    'fill-extrusion-opacity': 0.8,
  },
})

// --- raster tiles, used by the 2D (Leaflet) fallback -----------------------

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

// Four providers were dropped on 2026-08-31 because they had stopped serving
// usable tiles without a key, and both failed in the way that is hardest to
// notice: HTTP 200 with a degraded image rather than an error the map could
// report.
//
//   carto_voyager / carto_light / carto_dark -- CARTO now returns a tile
//     stamped "API KEY REQUIRED" across its face. `carto_voyager` was the
//     DEFAULT, so the 2D fallback opened watermarked, and nothing in the
//     console said why.
//   opentopo -- returns a blank 103-byte 1-bit PNG.
//
// What remains is verified keyless, which is the property the whole map design
// rests on: no key, no token, no account. Check with a tile request before
// adding a provider back, and check the BYTES, not the status code.
export const RASTER_BASEMAPS = [
  {
    id: 'osm',
    label: 'Streets',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: OSM_ATTR,
    tone: 'light',
    maxZoom: 19,
  },
  {
    id: 'esri_imagery',
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
    tone: 'dark',
    maxZoom: 19,
    note: 'Shows the actual land use the bypass routes run through.',
  },
]

/** The basemap that suits the current interface theme. */
export function defaultBasemap(list, theme) {
  const wanted = theme === 'dark' ? 'dark' : 'light'
  return list.find((b) => b.tone === wanted) ?? list[0]
}
