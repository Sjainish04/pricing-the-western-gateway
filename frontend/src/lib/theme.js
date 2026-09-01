/* Interface theme: light, dark, or follow the operating system.
 *
 * The stylesheet already defines a complete dark palette three ways -- on bare
 * `:root` for light, under `prefers-color-scheme: dark` for the system setting,
 * and under `[data-theme="dark"]` so an explicit choice wins in either
 * direction.  All this does is stamp the attribute and remember the choice.
 *
 * `resolved` is what the interface is actually showing right now, which is what
 * the map needs in order to pick a matching basemap: "system" is not an answer
 * to "should I load the dark tiles?".
 */
import { useCallback, useEffect, useState } from 'react'

const KEY = 'uttan-theme'
export const THEMES = ['light', 'dark', 'system']

const systemPrefersDark = () =>
  window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false

function apply(choice) {
  const root = document.documentElement
  if (choice === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', choice)
}

/** Read the stored choice before React mounts, to avoid a flash of the wrong theme. */
export function initTheme() {
  let stored = null
  try { stored = localStorage.getItem(KEY) } catch { /* private mode */ }
  const choice = THEMES.includes(stored) ? stored : 'system'
  apply(choice)
  return choice
}

export function useTheme() {
  const [choice, setChoice] = useState(() => {
    try {
      const stored = localStorage.getItem(KEY)
      return THEMES.includes(stored) ? stored : 'system'
    } catch { return 'system' }
  })
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return undefined
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const set = useCallback((next) => {
    setChoice(next)
    apply(next)
    try { localStorage.setItem(KEY, next) } catch { /* private mode */ }
  }, [])

  const resolved = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice
  return { choice, resolved, set }
}
