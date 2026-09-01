import { Suspense, createContext, lazy, useContext } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { useTheme } from './lib/theme.js'

import Overview from './pages/Overview.jsx'
import SiteSelection from './pages/SiteSelection.jsx'
import Corridor from './pages/Corridor.jsx'
import Baseline from './pages/Baseline.jsx'
import ScenarioLab from './pages/ScenarioLab.jsx'
import GameTheory from './pages/GameTheory.jsx'
import Equity from './pages/Equity.jsx'
import Geographic from './pages/Geographic.jsx'
import Compare from './pages/Compare.jsx'
import Sequencing from './pages/Sequencing.jsx'
import Governance from './pages/Governance.jsx'
import Timing from './pages/Timing.jsx'
import Incidence from './pages/Incidence.jsx'
import Finance from './pages/Finance.jsx'
import Robustness from './pages/Robustness.jsx'
import Recommendation from './pages/Recommendation.jsx'
import DataSources from './pages/DataSources.jsx'

// Also pulls in MapLibre, so it stays out of the main bundle.
const MapCheck = lazy(() => import('./pages/MapCheck.jsx'))

const SECTIONS = [
  {
    group: 'Where',
    items: [
      { to: '/', label: 'Overview', glyph: '◎', element: <Overview /> },
      { to: '/site', label: 'Gateway screening', glyph: '⚖', element: <SiteSelection /> },
      { to: '/corridor', label: 'Corridor & gantries', glyph: '🗺', element: <Corridor /> },
    ],
  },
  {
    group: 'How much',
    items: [
      { to: '/baseline', label: 'Baseline & validation', glyph: '✓', element: <Baseline /> },
      { to: '/scenarios', label: 'Scenario lab', glyph: '⚗', element: <ScenarioLab /> },
      { to: '/game', label: 'Game theory', glyph: '♟', element: <GameTheory /> },
    ],
  },
  {
    group: 'Who pays',
    items: [
      { to: '/equity', label: 'Equity model', glyph: '⚖', element: <Equity /> },
      { to: '/geographic', label: 'Geographic equity', glyph: '⌖', element: <Geographic /> },
      { to: '/incidence', label: 'Winners & losers', glyph: '◑', element: <Incidence /> },
      { to: '/finance', label: 'Revenue & recycling', glyph: '$', element: <Finance /> },
      { to: '/compare', label: 'Other cities', glyph: '🌐', element: <Compare /> },
    ],
  },
  {
    group: 'When, and who agrees',
    items: [
      { to: '/sequencing', label: 'Sequencing', glyph: '⇢', element: <Sequencing /> },
      { to: '/governance', label: 'City ↔ Province', glyph: '⚑', element: <Governance /> },
      { to: '/timing', label: 'The 2027 deadline', glyph: '⏱', element: <Timing /> },
    ],
  },
  {
    group: 'How sure',
    items: [
      { to: '/robustness', label: 'Sensitivity', glyph: '≈', element: <Robustness /> },
      { to: '/data', label: 'Data & provenance', glyph: '⛁', element: <DataSources /> },
      { to: '/mapcheck', label: 'Map diagnostic', glyph: '⚙', element: <MapCheck /> },
    ],
  },
  {
    group: 'Answer',
    items: [
      { to: '/recommendation', label: 'Recommendation', glyph: '★', element: <Recommendation /> },
    ],
  },
]

/** Lets any page read the resolved theme -- the map uses it to pick a basemap. */
export const ThemeContext = createContext({ choice: 'system', resolved: 'light', set: () => {} })
export const useAppTheme = () => useContext(ThemeContext)

const THEME_OPTIONS = [
  ['light', 'Light'],
  ['dark', 'Dark'],
  ['system', 'Auto'],
]

function ThemeSwitch() {
  const { choice, set } = useAppTheme()
  return (
    <div className="theme-switch" role="group" aria-label="Interface theme">
      {THEME_OPTIONS.map(([value, label]) => (
        <button
          key={value}
          className={choice === value ? 'on' : undefined}
          aria-pressed={choice === value}
          onClick={() => set(value)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const theme = useTheme()
  const all = SECTIONS.flatMap((s) => s.items)
  return (
    <ThemeContext.Provider value={theme}>
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          Pricing the Western Gateway
          <span>Etobicoke–Gardiner congestion charge · UTTAN 2026</span>
        </div>
        <nav className="nav">
          {SECTIONS.map((section) => (
            <div key={section.group}>
              <div className="nav-group">{section.group}</div>
              {section.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={it.to === '/'}>
                  <span className="glyph" aria-hidden="true">{it.glyph}</span>
                  {it.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <ThemeSwitch />
      </aside>
      <main className="main">
        <Suspense fallback={<div className="loading">Loading…</div>}>
          <Routes>
            {all.map((it) => <Route key={it.to} path={it.to} element={it.element} />)}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
    </ThemeContext.Provider>
  )
}
