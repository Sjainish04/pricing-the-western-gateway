/* Small presentational pieces shared across the pages. */
import { Component, useEffect, useRef, useState } from 'react'

import { fmt } from './charts.jsx'

/**
 * Counts a figure up when it first appears.
 *
 * Purely presentational, and it stops at the true value -- the reader always
 * ends up looking at the real number.  Skipped entirely when the visitor has
 * asked for reduced motion, and skipped for non-numeric values.
 */
export function Counter({ value, format = (v) => fmt.n(v), duration = 900 }) {
  const [shown, setShown] = useState(value)
  const previous = useRef(value)

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduce || typeof value !== 'number' || !Number.isFinite(value)) {
      setShown(value)
      previous.current = value
      return undefined
    }
    const from = typeof previous.current === 'number' ? previous.current : 0
    const start = performance.now()
    let frame
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1)
      // Ease-out cubic: fast at first, settling gently onto the true value.
      setShown(from + (value - from) * (1 - (1 - t) ** 3))
      if (t < 1) frame = requestAnimationFrame(step)
      else previous.current = value
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])

  return <>{format(shown)}</>
}

export function Hero({ eyebrow, title, children, figures = [] }) {
  return (
    <div className="hero">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {children && <p>{children}</p>}
      {figures.length > 0 && (
        <div className="hero-figures">
          {figures.map((f) => (
            <div className="fig" key={f.label}>
              <div className="n">{f.value}</div>
              <div className="l">{f.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Panel({ title, sub, children, right }) {
  return (
    <section className="panel">
      {(title || right) && (
        <div style={{ display: 'flex', justifyContent: 'space-between',
                      alignItems: 'flex-start', gap: 14 }}>
          <div style={{ minWidth: 0 }}>
            {title && <h2>{title}</h2>}
            {sub && <p className="sub">{sub}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

/**
 * A single number with its label.  `tone` colours the value for good or bad, and
 * is only ever used alongside the sign or wording in `note`, so the meaning
 * never rests on colour alone.
 */
export function Tile({ label, value, note, tone }) {
  // `tone` goes on the tile as well as the value. Colouring only the number
  // makes the signal invisible in greyscale and to a colourblind reader -- and
  // a sister project had this exact prop silently dead app-wide because a
  // background-clip rule beat the inline colour. A rule along the tile's top
  // edge cannot be overridden by a text-colour trick.
  return (
    <div className={`tile${tone ? ` tone-${tone}` : ''}`}>
      <div className="label">{label}</div>
      <div className={`value${tone ? ` ${tone}` : ''}`}>{value}</div>
      {note && <div className="note" style={{ border: 0, padding: 0, marginTop: 4 }}>{note}</div>}
    </div>
  )
}

export function Badge({ ok, children, kind }) {
  const cls = kind ?? (ok ? 'pass' : 'fail')
  return <span className={`badge ${cls}`}>{children ?? (ok ? 'Passes' : 'Fails')}</span>
}

/**
 * The table view every chart is paired with.  Required rather than optional:
 * three light-mode palette slots sit below 3:1 contrast on the light surface, so
 * the table is the documented relief for anyone the colour channel fails.
 */
export function Table({ columns, rows, rowKey, highlight }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key ?? c.label}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r, i) : i}
                className={highlight && highlight(r) ? 'highlight' : undefined}>
              {columns.map((c) => (
                <td key={c.key ?? c.label}>{c.render ? c.render(r) : r[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Loading({ what = 'model output' }) {
  return <div className="loading">Solving the corridor equilibrium for {what}…</div>
}

export function ErrorBox({ error }) {
  return (
    <div className="error">
      <b>Could not load model output.</b> {String(error)}
      <div style={{ marginTop: 6, fontWeight: 400 }}>
        Make sure the backend is running: <code>python run.py</code> in <code>backend/</code>.
      </div>
    </div>
  )
}

/**
 * A result, as distinct from the prose explaining it.
 *
 * This study's value is its findings, and until this existed every one of them
 * rendered as an undifferentiated paragraph -- the reader had to work out which
 * sentence was the conclusion. `tone` carries good/bad through the left rule
 * rather than through text colour alone, so the signal survives greyscale
 * printing and a colourblind reader.
 *
 * `kicker` names what kind of claim it is ("The result", "Robustness"), which
 * matters on pages carrying several findings of different weight.
 */
export function Finding({ kicker, lede, tone, children }) {
  const cls = ['finding', tone].filter(Boolean).join(' ')
  return (
    <div className={cls}>
      {kicker && <span className="kicker">{kicker}</span>}
      {lede && <p className="lede">{lede}</p>}
      {children}
    </div>
  )
}

export function Caveat({ children }) {
  return <div className="caveat">{children}</div>
}

export function Field({ label, children, readout }) {
  return (
    <div className="field">
      <label>{label}{readout != null && <span className="readout">  {readout}</span>}</label>
      {children}
    </div>
  )
}

export function Constraints({ feasible }) {
  if (!feasible) return null
  const rows = [
    ['Local diversion', feasible.checks.diversion,
      (c) => `${fmt.signed(c.value_pct)} vs ${c.limit_pct}% cap`],
    ['Equity floor', feasible.checks.equity,
      (c) => `${c.value.toFixed(3)} vs ${c.minimum} minimum`],
    ['Congestion gain', feasible.checks.congestion,
      (c) => `${fmt.pct(c.value_pct)} vs ${c.minimum_pct}% minimum`],
    ['Transit capacity', feasible.checks.transit_capacity,
      (c) => `GO load ${(c.go_load_factor * 100).toFixed(0)}%`],
  ]
  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <Badge ok={feasible.passes}>
          {feasible.passes ? 'All policy constraints satisfied'
            : `Fails: ${feasible.failed.join(', ')}`}
        </Badge>
      </div>
      <Table
        columns={[
          { label: 'Constraint', render: (r) => r[0] },
          { label: 'Result', render: (r) => r[2](r[1]) },
          { label: 'Status', render: (r) => <Badge ok={r[1].passes} /> },
        ]}
        rows={rows}
        rowKey={(r) => r[0]}
      />
    </div>
  )
}

/* A lazily-loaded chunk that fails to arrive is the one error this app cannot
 * render its way around: React unmounts the subtree and the user gets an empty
 * box with nothing to act on. It happens for a mundane reason -- the tab was
 * open across a deploy, so it is asking for a chunk filename that no longer
 * exists -- and the fix is always the same, so say so and offer it.
 *
 * A class component because error boundaries have no hook equivalent. */
export class ChunkBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    // A stale-chunk failure, as opposed to a genuine bug in the component.
    const message = String(error?.message ?? error)
    const isStale = /dynamically imported module|Importing a module script failed|MIME type|Failed to fetch/i.test(message)

    return (
      <div className="errorbox">
        <b>{isStale ? 'This page was updated while you had it open.' : 'That part of the page failed to load.'}</b>
        <p className="aside">
          {isStale
            ? 'The map is loaded on demand, and this tab is still asking for the previous version of it. Reloading picks up the current one.'
            : message}
        </p>
        <button className="pill" onClick={() => window.location.reload()}>Reload</button>
      </div>
    )
  }
}
