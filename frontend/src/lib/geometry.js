/* Small geodesic helpers for building 3D geometry from road centrelines.
 *
 * MapLibre extrudes polygons, not lines, so a corridor drawn as a raised ribbon
 * has to be turned into an actual polygon first. Everything here works in
 * metres and converts back to degrees at the end, so widths stay true at
 * Toronto's latitude instead of stretching with longitude.
 */

const M_PER_DEG_LAT = 110_540

export const mPerDegLon = (lat) => 111_320 * Math.cos((lat * Math.PI) / 180)

/** Unit direction of the centreline at index `i`, in metres-space. */
function tangentAt(coords, i) {
  const prev = coords[Math.max(i - 1, 0)]
  const next = coords[Math.min(i + 1, coords.length - 1)]
  const lat = coords[i][1]
  let dx = (next[0] - prev[0]) * mPerDegLon(lat)
  let dy = (next[1] - prev[1]) * M_PER_DEG_LAT
  const len = Math.hypot(dx, dy) || 1
  return [dx / len, dy / len]
}

/**
 * Turn a LineString into a polygon ribbon of the given width in metres.
 *
 * Offsets each vertex perpendicular to the local tangent, then walks back down
 * the other side to close the ring.  Good enough for a corridor at city scale;
 * it does not mitre sharp corners, which would matter for a road-surface render
 * but not for a schematic ribbon.
 */
export function ribbonPolygon(coords, widthMetres) {
  const half = widthMetres / 2
  const left = []
  const right = []

  for (let i = 0; i < coords.length; i++) {
    const [lon, lat] = coords[i]
    const [tx, ty] = tangentAt(coords, i)
    const [px, py] = [-ty, tx]           // perpendicular
    const dLon = (px * half) / mPerDegLon(lat)
    const dLat = (py * half) / M_PER_DEG_LAT
    left.push([lon + dLon, lat + dLat])
    right.push([lon - dLon, lat - dLat])
  }

  const ring = [...left, ...right.reverse()]
  ring.push(ring[0])
  return [ring]
}

/** Rectangle of `length` x `width` metres centred on a point, aligned to `dir`. */
export function orientedRect(centre, dir, lengthMetres, widthMetres) {
  const [lon, lat] = centre
  const [tx, ty] = dir
  const [px, py] = [-ty, tx]
  const mLon = mPerDegLon(lat)
  const half = { l: lengthMetres / 2, w: widthMetres / 2 }

  const corner = (a, b) => [
    lon + (tx * a + px * b) / mLon,
    lat + (ty * a + py * b) / M_PER_DEG_LAT,
  ]
  const ring = [
    corner(-half.l, -half.w),
    corner(half.l, -half.w),
    corner(half.l, half.w),
    corner(-half.l, half.w),
  ]
  ring.push(ring[0])
  return [ring]
}

/**
 * Nearest vertex on a line, with its coordinate and the line's direction there.
 *
 * The returned `coord` matters as much as the direction: gantry positions and
 * road centrelines were digitised separately, so a charging point can sit a few
 * hundred metres off its own road.  Drawing a portal at the gantry's raw
 * coordinate would leave it hanging beside the carriageway instead of spanning
 * it, so callers snap to `coord`.
 */
export function nearestOnLine(coords, point) {
  let best = { index: 0, distance: Infinity }
  for (let i = 0; i < coords.length; i++) {
    const lat = coords[i][1]
    const dx = (coords[i][0] - point[0]) * mPerDegLon(lat)
    const dy = (coords[i][1] - point[1]) * M_PER_DEG_LAT
    const d = Math.hypot(dx, dy)
    if (d < best.distance) best = { index: i, distance: d }
  }
  return { ...best, coord: coords[best.index], direction: tangentAt(coords, best.index) }
}

/** Evenly spaced points along a line, for markers that need to repeat. */
export function pointsAlong(coords, everyMetres) {
  const out = []
  let carried = 0
  for (let i = 1; i < coords.length; i++) {
    const lat = coords[i][1]
    const dx = (coords[i][0] - coords[i - 1][0]) * mPerDegLon(lat)
    const dy = (coords[i][1] - coords[i - 1][1]) * M_PER_DEG_LAT
    const seg = Math.hypot(dx, dy)
    let t = everyMetres - carried
    while (t <= seg) {
      const f = t / seg
      out.push({
        coord: [
          coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * f,
          coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * f,
        ],
        direction: tangentAt(coords, i),
      })
      t += everyMetres
    }
    carried = (carried + seg) % everyMetres
  }
  return out
}
