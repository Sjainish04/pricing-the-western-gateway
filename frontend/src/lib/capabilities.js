/* Can this browser context actually run the 3D map?
 *
 * Two things have to be true, and both fail silently if you do not check them.
 *
 * WebGL is the obvious one.  The subtle one is animation frames: MapLibre
 * drives its entire pipeline -- style resolution, tile requests, painting --
 * from requestAnimationFrame, and browsers stop issuing those to a hidden or
 * background tab.  In an embedded preview pane the document can report
 * `visibilityState: "hidden"` permanently, so the map constructs cleanly,
 * attaches its controls, resolves its style, and then sits there forever
 * without requesting a single tile.
 *
 * Probing for that up front means the interface can fall back to a 2D map that
 * works anywhere, instead of showing a blank rectangle and blaming the user.
 */

export function webglSupport() {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    if (!gl) return { ok: false, detail: 'no WebGL context available' }
    const dbg = gl.getExtension('WEBGL_debug_renderer_info')
    return {
      ok: true,
      detail: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'WebGL available',
    }
  } catch (err) {
    return { ok: false, detail: String(err) }
  }
}

/** Resolves true if an animation frame arrives within `timeout` ms. */
export function animationFrames(timeout = 1200) {
  return new Promise((resolve) => {
    let settled = false
    requestAnimationFrame(() => {
      if (!settled) { settled = true; resolve(true) }
    })
    setTimeout(() => {
      if (!settled) { settled = true; resolve(false) }
    }, timeout)
  })
}

/** Full capability probe for the 3D map. */
export async function probe3D() {
  const gl = webglSupport()
  const raf = await animationFrames()
  const ok = gl.ok && raf

  let reason = null
  if (!gl.ok) {
    reason = `This browser has no WebGL context (${gl.detail}), which the 3D renderer requires. `
      + 'Hardware acceleration is usually the cause.'
  } else if (!raf) {
    reason = 'This view is not receiving animation frames — the page reports '
      + `visibilityState "${document.visibilityState}". Browsers withhold them from hidden and `
      + 'background tabs, and the 3D renderer needs them before it will request a single tile. '
      + 'Opening the app in a normal foreground browser window enables the 3D view.'
  }

  return { ok, reason, webgl: gl, animationFrames: raf }
}
