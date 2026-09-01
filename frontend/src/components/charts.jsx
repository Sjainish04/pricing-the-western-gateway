/* Hand-built SVG chart primitives.
 *
 * Written directly rather than pulled from a chart library so every mark obeys
 * the same rules: thin marks, rounded data-ends anchored to the baseline, a 2px
 * surface gap between adjacent fills, recessive grid and axes, and a hover
 * tooltip on every plotted form.  Colours come from CSS custom properties, so
 * light and dark are two validated palettes rather than an automatic flip.
 */
import { useCallback, useLayoutEffect, useRef, useState } from 'react'

export const SERIES = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)',
]

export const fmt = {
  n: (v, d = 0) => (v == null || Number.isNaN(v) ? '—' :
    Number(v).toLocaleString('en-CA', { minimumFractionDigits: d, maximumFractionDigits: d })),
  pct: (v, d = 1) => (v == null ? '—' : `${Number(v).toFixed(d)}%`),
  signed: (v, d = 1) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(d)}%`),
  money: (v) => {
    if (v == null) return '—'
    const a = Math.abs(v)
    const sign = v < 0 ? '-' : ''
    if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(2)}B`
    if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`
    if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}k`
    return `${sign}$${a.toFixed(2)}`
  },
  dollars: (v, d = 2) => (v == null ? '—' : `$${Number(v).toFixed(d)}`),
}

/** Human-readable names for the model's internal identifiers. */
export const NICE = {
  drive_gardiner: 'Drive Gardiner',
  drive_lakeshore: 'Bypass via Lake Shore',
  drive_queensway: 'Bypass via Queensway',
  carpool_gardiner: 'Carpool (HOV2+)',
  shift_offpeak: 'Retime to shoulder',
  go_rail: 'Lakeshore West GO',
  ttc: 'TTC',
  forgo_remote: 'Not travelling / remote',
  gardiner_west: 'Gardiner 427–Humber',
  gardiner_east: 'Gardiner Humber–core',
  lakeshore_west: 'Lake Shore 427–Humber',
  lakeshore_east: 'Lake Shore Humber–core',
  queensway_west: 'Queensway 427–Humber',
  gardiner_only: 'Expressway only',
  screenline: 'Full screenline',
  city_roads_only: 'City arterials only',
  none: 'No credit',
  low_income: 'Low-income credit',
  low_income_transit_poor: 'Income + transit-poor',
  shift_worker: 'Shift-worker credit',
  hov_discount: 'HOV discount',
  monthly_cap: 'Monthly cap',
  mobility_credit: 'Transit mobility credit',
  targeted_package: 'Targeted package',
  means_tested: 'Means-tested (Q1 exempt)',
  equity_first: 'Equity-first',
  '0630_0930': '06:30–09:30',
  '0700_1000': '07:00–10:00',
  '0630_1000': '06:30–10:00',
  '0700_0900': '07:00–09:00',
  peak_plus_shoulder: '06:00–10:30',
}
export const nice = (k) => NICE[k] ?? k

/* ------------------------------------------------------------- tooltip */

export function useTooltip() {
  const [tip, setTip] = useState(null)
  const show = useCallback((e, content) => {
    setTip({ x: e.clientX, y: e.clientY, content })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  const node = tip ? (
    <div
      className="tooltip"
      style={{
        left: Math.min(tip.x + 14, window.innerWidth - 296),
        top: Math.max(tip.y - 12, 8),
      }}
    >
      {tip.content}
    </div>
  ) : null
  return { show, hide, node }
}

export function TipBody({ title, rows }) {
  return (
    <>
      <div className="tt-title">{title}</div>
      {rows.map(([k, v]) => (
        <div className="tt-row" key={k}>
          <span>{k}</span>
          <b>{v}</b>
        </div>
      ))}
    </>
  )
}

/* --------------------------------------------------------------- legend */

export function Legend({ items }) {
  if (!items || items.length < 2) return null
  return (
    <div className="legend">
      {items.map((it) => (
        <span className="key" key={it.label}>
          <span className="swatch" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

/* --------------------------------------------------------- axis helpers */

function ticks(min, max, count = 5) {
  if (min === max) return [min]
  const raw = (max - min) / count
  const mag = 10 ** Math.floor(Math.log10(Math.abs(raw)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10
  const out = []
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) {
    out.push(Number(v.toFixed(10)))
  }
  return out
}

/**
 * Place direct labels beside points without letting them overlap.
 *
 * Greedy and deliberately simple: try right of the mark, then left, then above,
 * then below, and take the first placement whose box misses every box already
 * placed. Points are handled in reading order so the result is stable between
 * renders rather than shuffling as data changes.
 *
 * Not a general label-placement solver -- with enough crowded points it will
 * run out of candidate positions and fall back to the right-hand slot. That is
 * the honest failure: a label slightly overlapping is recoverable, a chart with
 * no labels at all is not.
 */
function placeLabels(marks, plotW, padL, padT, plotH) {
  const CH = 6.1        // approximate advance width of the label font
  const H = 13
  const placed = []
  const hits = (b) => placed.some((o) =>
    b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h)

  return marks.map((m) => {
    const w = m.text.length * CH
    const gap = m.r + 6
    const options = [
      { anchor: 'start', tx: m.x + gap, ty: m.y + 4, x: m.x + gap, y: m.y - H / 2 },
      { anchor: 'end', tx: m.x - gap, ty: m.y + 4, x: m.x - gap - w, y: m.y - H / 2 },
      { anchor: 'middle', tx: m.x, ty: m.y - gap - 2, x: m.x - w / 2, y: m.y - gap - H - 2 },
      { anchor: 'middle', tx: m.x, ty: m.y + gap + H - 2, x: m.x - w / 2, y: m.y + gap },
    ]
    const fits = (o) =>
      o.x >= padL - 2 && o.x + w <= padL + plotW + 2 &&
      o.y >= padT - 2 && o.y + H <= padT + plotH + 2 &&
      !hits({ ...o, w, h: H })
    const chosen = options.find(fits) ?? options[0]
    placed.push({ x: chosen.x, y: chosen.y, w, h: H })
    return { ...m, ...chosen }
  })
}

/** Measure the container so charts fill their panel without a fixed width. */
function useWidth(fallback = 720) {
  const ref = useRef(null)
  const [w, setW] = useState(fallback)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width
      if (width > 0) setW(width)
    })
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/* ------------------------------------------------------------ bar chart */

/**
 * Horizontal bars. The default form for magnitude across a short list of named
 * categories: labels stay readable at any length, which a rotated x-axis never
 * manages.
 */
export function BarChart({
  data, valueKey = 'value', labelKey = 'label', height,
  color, format = fmt.n, axisTitle, diverging = false, tooltip,
}) {
  const [ref, width] = useWidth()
  const rowH = 27
  const padL = 172
  const padR = 68
  const padT = 8
  // Deep enough for a tick row AND an axis title beneath it. At 30 the two
  // baselines were 14px apart with ~13px glyphs, so the title clipped the
  // zero tick -- invisible on most bars and obvious on the one that matters.
  const padB = axisTitle ? 44 : 30
  const h = height ?? data.length * rowH + padT + padB
  const plotW = Math.max(width - padL - padR, 80)

  const values = data.map((d) => Number(d[valueKey]) || 0)
  const hasNeg = diverging || values.some((v) => v < 0)
  const maxAbs = Math.max(...values.map(Math.abs), 1e-9)
  const min = hasNeg ? -maxAbs : 0
  const max = hasNeg ? maxAbs : Math.max(...values, 1e-9)
  const x = (v) => padL + ((v - min) / (max - min || 1)) * plotW
  const zero = x(0)

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={h} role="img">
        {ticks(min, max, 4).map((t) => (
          <g key={t}>
            <line className="gridline" x1={x(t)} x2={x(t)} y1={padT} y2={h - padB} />
            <text className="tick" x={x(t)} y={h - padB + 14} textAnchor="middle">
              {format(t)}
            </text>
          </g>
        ))}
        <line className="baseline" x1={zero} x2={zero} y1={padT} y2={h - padB} />

        {data.map((d, i) => {
          const v = Number(d[valueKey]) || 0
          const bx = v >= 0 ? zero : x(v)
          const bw = Math.max(Math.abs(x(v) - zero), 1.5)
          const y = padT + i * rowH + 5
          const barH = rowH - 12
          const fill = d.color ?? color ??
            (diverging ? (v >= 0 ? 'var(--series-1)' : 'var(--series-2)') : SERIES[0])
          return (
            <g
              key={`${d[labelKey] ?? 'row'}-${i}`}
              onMouseMove={tooltip ? (e) => tooltip.show(e, tooltip.render(d)) : undefined}
              onMouseLeave={tooltip ? tooltip.hide : undefined}
              style={{ cursor: tooltip ? 'default' : undefined }}
            >
              <rect x={padL} y={padT + i * rowH} width={plotW} height={rowH} fill="transparent" />
              <rect x={bx} y={y} width={bw} height={barH} rx={4} fill={fill} />
              <text
                className="mark-label" x={padL - 9} y={y + barH / 2 + 4} textAnchor="end"
                style={{ fill: 'var(--text-secondary)' }}
              >
                {d[labelKey]}
              </text>
              {/* A negative bar grows leftward and its value label grows
                  further left again, so on a long bar the label crossed the
                  axis gutter and landed on top of the category name. When the
                  outside placement would leave the plot, the label moves just
                  inside the bar's end instead, with a surface halo so it stays
                  legible over the fill. */}
              {(() => {
                const outside = v >= 0 ? bx + bw + 7 : bx - 7
                const escapes = v < 0 && outside - String(format(v)).length * 6.1 < padL + 2
                return (
                  <text
                    className="mark-label"
                    x={escapes ? bx + 7 : outside}
                    y={y + barH / 2 + 4}
                    textAnchor={v >= 0 ? 'start' : (escapes ? 'start' : 'end')}
                    style={escapes ? {
                      paintOrder: 'stroke',
                      stroke: 'var(--surface-1)',
                      strokeWidth: 3,
                      strokeLinejoin: 'round',
                    } : undefined}
                  >
                    {format(v)}
                  </text>
                )
              })()}
            </g>
          )
        })}
        {axisTitle && (
          <text className="axis-title" x={padL + plotW / 2} y={h - 6} textAnchor="middle">
            {axisTitle}
          </text>
        )}
      </svg>
    </div>
  )
}

/* ----------------------------------------------------------- line chart */

/**
 * One or more series over a continuous x. Used for the price ladder: toll on x,
 * outcome on y.  Never two y-axes -- a second measure of a different scale gets
 * its own chart.
 */
export function LineChart({
  series, xKey = 'x', yKey = 'y', height = 260, xTitle, yTitle,
  format = fmt.n, xFormat = fmt.n, markers = true, tooltip, zeroLine = false,
}) {
  const [ref, width] = useWidth()
  const padL = 62
  const padR = 20
  const padT = 12
  const padB = 42
  const plotW = Math.max(width - padL - padR, 80)
  const plotH = height - padT - padB

  const all = series.flatMap((s) => s.data)
  if (!all.length) return <div ref={ref} className="loading">No data</div>

  const xs = all.map((d) => Number(d[xKey]))
  const ys = all.map((d) => Number(d[yKey]))
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  let yMin = Math.min(...ys, zeroLine ? 0 : Infinity)
  let yMax = Math.max(...ys, zeroLine ? 0 : -Infinity)
  if (yMin === yMax) { yMin -= 1; yMax += 1 }
  const pad = (yMax - yMin) * 0.08
  yMin -= pad
  yMax += pad

  const X = (v) => padL + ((v - xMin) / (xMax - xMin || 1)) * plotW
  const Y = (v) => padT + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={height} role="img">
        {ticks(yMin, yMax, 4).map((t) => (
          <g key={`y${t}`}>
            <line className="gridline" x1={padL} x2={padL + plotW} y1={Y(t)} y2={Y(t)} />
            <text className="tick" x={padL - 8} y={Y(t) + 4} textAnchor="end">{format(t)}</text>
          </g>
        ))}
        {ticks(xMin, xMax, 5).map((t) => (
          <text key={`x${t}`} className="tick" x={X(t)} y={height - padB + 16} textAnchor="middle">
            {xFormat(t)}
          </text>
        ))}
        {zeroLine && yMin < 0 && yMax > 0 && (
          <line className="baseline" x1={padL} x2={padL + plotW} y1={Y(0)} y2={Y(0)}
                strokeDasharray="3 3" />
        )}
        <line className="baseline" x1={padL} x2={padL} y1={padT} y2={padT + plotH} />
        <line className="baseline" x1={padL} x2={padL + plotW} y1={padT + plotH} y2={padT + plotH} />

        {series.map((s, si) => {
          const pts = [...s.data].sort((a, b) => a[xKey] - b[xKey])
          const d = pts.map((p, i) =>
            `${i ? 'L' : 'M'}${X(p[xKey]).toFixed(2)},${Y(p[yKey]).toFixed(2)}`).join(' ')
          const stroke = s.color ?? SERIES[si % SERIES.length]
          return (
            <g key={s.label ?? si}>
              <path d={d} fill="none" stroke={stroke} strokeWidth={2}
                    strokeLinejoin="round" strokeLinecap="round" />
              {markers && pts.map((p, i) => (
                <circle
                  key={i} cx={X(p[xKey])} cy={Y(p[yKey])} r={4.5}
                  fill={stroke} stroke="var(--surface-1)" strokeWidth={2}
                  onMouseMove={tooltip ? (e) => tooltip.show(e, tooltip.render(p, s)) : undefined}
                  onMouseLeave={tooltip ? tooltip.hide : undefined}
                />
              ))}
            </g>
          )
        })}
        {yTitle && (
          <text className="axis-title" transform={`rotate(-90) translate(${-(padT + plotH / 2)} 14)`}
                textAnchor="middle">{yTitle}</text>
        )}
        {xTitle && (
          <text className="axis-title" x={padL + plotW / 2} y={height - 6} textAnchor="middle">
            {xTitle}
          </text>
        )}
      </svg>
    </div>
  )
}

/* -------------------------------------------------------- scatter chart */

/**
 * The Pareto view: two objectives on the axes, a third as bubble area, and a
 * fourth as fill.  Bubble area (not radius) is proportional to the value, so a
 * doubled value looks doubled.
 */
export function ScatterChart({
  points, xKey, yKey, sizeKey, height = 380, xTitle, yTitle,
  xFormat = fmt.n, yFormat = fmt.n, tooltip, highlight, labels = false,
}) {
  const [ref, width] = useWidth()
  const padL = 66
  const padR = 26
  const padT = 14
  const padB = 46
  const plotW = Math.max(width - padL - padR, 80)
  const plotH = height - padT - padB
  if (!points.length) return <div ref={ref} className="loading">No data</div>

  const xs = points.map((p) => Number(p[xKey]))
  const ys = points.map((p) => Number(p[yKey]))
  const xr = [Math.min(...xs), Math.max(...xs)]
  const yr = [Math.min(...ys), Math.max(...ys)]
  const xp = (xr[1] - xr[0]) * 0.08 || 1
  const yp = (yr[1] - yr[0]) * 0.08 || 0.02
  const X = (v) => padL + ((v - (xr[0] - xp)) / ((xr[1] + xp) - (xr[0] - xp) || 1)) * plotW
  const Y = (v) => padT + plotH - ((v - (yr[0] - yp)) / ((yr[1] + yp) - (yr[0] - yp) || 1)) * plotH

  const sizes = sizeKey ? points.map((p) => Math.abs(Number(p[sizeKey]) || 0)) : []
  const sMax = sizes.length ? Math.max(...sizes, 1e-9) : 1
  const R = (v) => (sizeKey ? 5 + 13 * Math.sqrt(Math.abs(v || 0) / sMax) : 6)

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={height} role="img">
        {ticks(yr[0] - yp, yr[1] + yp, 4).map((t) => (
          <g key={`y${t}`}>
            <line className="gridline" x1={padL} x2={padL + plotW} y1={Y(t)} y2={Y(t)} />
            <text className="tick" x={padL - 8} y={Y(t) + 4} textAnchor="end">{yFormat(t)}</text>
          </g>
        ))}
        {ticks(xr[0] - xp, xr[1] + xp, 5).map((t) => (
          <g key={`x${t}`}>
            <line className="gridline" x1={X(t)} x2={X(t)} y1={padT} y2={padT + plotH} />
            <text className="tick" x={X(t)} y={height - padB + 16} textAnchor="middle">
              {xFormat(t)}
            </text>
          </g>
        ))}
        <line className="baseline" x1={padL} x2={padL} y1={padT} y2={padT + plotH} />
        <line className="baseline" x1={padL} x2={padL + plotW} y1={padT + plotH} y2={padT + plotH} />

        {points.map((p, i) => {
          const isHi = highlight && highlight(p)
          return (
            <circle
              key={p.label ?? i}
              cx={X(Number(p[xKey]))} cy={Y(Number(p[yKey]))} r={R(p[sizeKey])}
              fill={p.color ?? SERIES[0]}
              fillOpacity={isHi ? 0.95 : 0.62}
              stroke={isHi ? 'var(--text-primary)' : 'var(--surface-1)'}
              strokeWidth={2}
              onMouseMove={tooltip ? (e) => tooltip.show(e, tooltip.render(p)) : undefined}
              onMouseLeave={tooltip ? tooltip.hide : undefined}
            />
          )
        })}

        {/* Direct labels. Without them a scatter carries identity in colour and
            hover alone, so the reader cannot tell which point is which -- and on
            a printed page or in a screenshot cannot recover it at all. Placed
            after the circles so text sits above every mark. */}
        {labels && placeLabels(points.map((p, i) => ({
          text: String(p.label ?? ''),
          x: X(Number(p[xKey])),
          y: Y(Number(p[yKey])),
          r: R(p[sizeKey]),
          hi: !!(highlight && highlight(p)),
          i,
        })), plotW, padL, padT, plotH).map((l) => (
          <text
            key={l.text + l.i}
            className="mark-label"
            x={l.tx} y={l.ty} textAnchor={l.anchor}
            style={{
              fill: l.hi ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontWeight: l.hi ? 650 : 500,
              paintOrder: 'stroke',
              stroke: 'var(--surface-1)',
              strokeWidth: 3,
              strokeLinejoin: 'round',
            }}
          >
            {l.text}
          </text>
        ))}
        {yTitle && (
          <text className="axis-title" transform={`rotate(-90) translate(${-(padT + plotH / 2)} 14)`}
                textAnchor="middle">{yTitle}</text>
        )}
        {xTitle && (
          <text className="axis-title" x={padL + plotW / 2} y={height - 6} textAnchor="middle">
            {xTitle}
          </text>
        )}
      </svg>
    </div>
  )
}

/* --------------------------------------------------------- grouped bars */

/**
 * Grouped vertical bars for a handful of categories across 2-4 series.  Bars
 * inside a group are separated by a 2px surface gap so adjacent fills never
 * appear to merge into one mark.
 */
export function GroupedBars({
  categories, series, height = 280, format = fmt.n, yTitle, tooltip,
}) {
  const [ref, width] = useWidth()
  const padL = 62
  const padR = 16
  const padT = 12
  const padB = 48
  const plotW = Math.max(width - padL - padR, 120)
  const plotH = height - padT - padB

  const values = series.flatMap((s) => s.values)
  const yMax = Math.max(...values, 1e-9) * 1.1
  const yMin = Math.min(...values, 0)
  const Y = (v) => padT + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH

  const groupW = plotW / categories.length
  const gap = 2
  const barW = Math.max((groupW * 0.74 - gap * (series.length - 1)) / series.length, 3)

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={height} role="img">
        {ticks(yMin, yMax, 4).map((t) => (
          <g key={t}>
            <line className="gridline" x1={padL} x2={padL + plotW} y1={Y(t)} y2={Y(t)} />
            <text className="tick" x={padL - 8} y={Y(t) + 4} textAnchor="end">{format(t)}</text>
          </g>
        ))}
        <line className="baseline" x1={padL} x2={padL + plotW} y1={Y(Math.max(yMin, 0))}
              y2={Y(Math.max(yMin, 0))} />

        {categories.map((cat, ci) => {
          const gx = padL + ci * groupW + groupW * 0.13
          return (
            <g key={cat}>
              {series.map((s, si) => {
                const v = s.values[ci] ?? 0
                const bx = gx + si * (barW + gap)
                const y0 = Y(Math.max(yMin, 0))
                const y = Y(v)
                return (
                  <rect
                    key={s.label}
                    x={bx} y={Math.min(y, y0)} width={barW}
                    height={Math.max(Math.abs(y0 - y), 1.5)} rx={4}
                    fill={s.color ?? SERIES[si % SERIES.length]}
                    onMouseMove={tooltip ? (e) => tooltip.show(e, tooltip.render(cat, s, v)) : undefined}
                    onMouseLeave={tooltip ? tooltip.hide : undefined}
                  />
                )
              })}
              <text className="tick" x={padL + ci * groupW + groupW / 2} y={height - padB + 16}
                    textAnchor="middle">{cat}</text>
            </g>
          )
        })}
        {yTitle && (
          <text className="axis-title" transform={`rotate(-90) translate(${-(padT + plotH / 2)} 14)`}
                textAnchor="middle">{yTitle}</text>
        )}
      </svg>
    </div>
  )
}

/* ---------------------------------------------------------- flow diagram */

/**
 * Where the priced-off trips went.  Ribbon thickness is proportional to trips.
 * Labelled as a net attribution, not a claim about individuals, because an
 * aggregate model tracks shares rather than people.
 */
export function FlowDiagram({ total, flows, height = 250 }) {
  const [ref, width] = useWidth()
  if (!flows?.length) {
    return <div className="loading">No trips left the Gardiner under this policy.</div>
  }
  const padT = 16
  const srcX = 12
  const srcW = 128
  const tgtX = Math.max(width - 250, srcX + srcW + 90)
  const plotH = height - padT * 2
  const sum = flows.reduce((a, f) => a + f.value, 0) || 1

  let y = padT
  const bands = flows.map((f, i) => {
    const bh = Math.max((f.value / sum) * (plotH - (flows.length - 1) * 3), 5)
    const band = { ...f, y, h: bh, color: SERIES[(i + 1) % SERIES.length] }
    y += bh + 3
    return band
  })

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={height} role="img">
        <rect x={srcX} y={padT} width={srcW} height={plotH} rx={5} fill="var(--series-1)" />
        <text x={srcX + srcW / 2} y={padT + plotH / 2 - 4} textAnchor="middle"
              style={{ fill: '#fff', fontSize: 12.5, fontWeight: 650 }}>
          Left the Gardiner
        </text>
        <text x={srcX + srcW / 2} y={padT + plotH / 2 + 14} textAnchor="middle"
              style={{ fill: '#fff', fontSize: 12.5 }}>
          {fmt.n(total)} trips
        </text>

        {bands.map((b) => {
          const y0 = padT + ((b.y - padT) / (y - padT - 3 || 1)) * plotH
          const midSrc = padT + plotH / 2
          const cx = (srcX + srcW + tgtX) / 2
          return (
            <g key={b.target}>
              <path
                d={`M${srcX + srcW},${midSrc - b.h / 2} C${cx},${midSrc - b.h / 2} ${cx},${b.y} ${tgtX},${b.y}
                    L${tgtX},${b.y + b.h} C${cx},${b.y + b.h} ${cx},${midSrc + b.h / 2} ${srcX + srcW},${midSrc + b.h / 2} Z`}
                fill={b.color} fillOpacity={0.4}
              />
              <rect x={tgtX} y={b.y} width={9} height={b.h} rx={3} fill={b.color} />
              <text x={tgtX + 16} y={b.y + b.h / 2 + 4}
                    style={{ fill: 'var(--text-secondary)', fontSize: 12 }}>
                {nice(b.target)}
                <tspan style={{ fill: 'var(--text-primary)', fontWeight: 600 }}>
                  {'  '}{fmt.n(b.value)}
                </tspan>
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

/* --------------------------------------------------------------- heatmap */

/**
 * A sequential grid: one hue, light to dark, so magnitude reads as depth of
 * colour.  Every cell also carries its number, which keeps the chart readable
 * for anyone the colour channel fails.
 */
export function Heatmap({ rows, cols, values, format = fmt.n, rowLabel, colLabel, tooltip }) {
  const [ref, width] = useWidth()
  const padL = 150
  const padT = 30
  const cellH = 30
  const flat = values.flat().filter((v) => v != null && !Number.isNaN(v))
  const lo = Math.min(...flat)
  const hi = Math.max(...flat)
  const cellW = Math.max((width - padL - 14) / cols.length, 44)
  const h = padT + rows.length * cellH + 14

  const STEPS = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-400)',
                 'var(--seq-550)', 'var(--seq-700)']
  const shade = (v) => {
    if (v == null) return 'var(--grid)'
    const t = hi === lo ? 0.5 : (v - lo) / (hi - lo)
    return STEPS[Math.min(Math.floor(t * STEPS.length), STEPS.length - 1)]
  }
  const ink = (v) => {
    const t = hi === lo ? 0.5 : (v - lo) / (hi - lo)
    return t > 0.5 ? '#fff' : 'var(--text-primary)'
  }

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={Math.max(width, padL + cellW * cols.length + 14)} height={h} role="img">
        {cols.map((c, ci) => (
          <text key={c} className="tick" x={padL + ci * cellW + cellW / 2} y={padT - 10}
                textAnchor="middle">{c}</text>
        ))}
        {rows.map((r, ri) => (
          <g key={r}>
            <text className="tick" x={padL - 9} y={padT + ri * cellH + cellH / 2 + 4}
                  textAnchor="end" style={{ fill: 'var(--text-secondary)' }}>{r}</text>
            {cols.map((c, ci) => {
              const v = values[ri]?.[ci]
              return (
                <g key={c}
                   onMouseMove={tooltip ? (e) => tooltip.show(e, tooltip.render(r, c, v)) : undefined}
                   onMouseLeave={tooltip ? tooltip.hide : undefined}>
                  {/* 2px inset keeps a surface gap between neighbouring cells. */}
                  <rect x={padL + ci * cellW + 1} y={padT + ri * cellH + 1}
                        width={cellW - 2} height={cellH - 2} rx={3} fill={shade(v)} />
                  <text x={padL + ci * cellW + cellW / 2} y={padT + ri * cellH + cellH / 2 + 4}
                        textAnchor="middle"
                        style={{ fontSize: 11, fill: ink(v), fontVariantNumeric: 'tabular-nums' }}>
                    {v == null ? '' : format(v)}
                  </text>
                </g>
              )
            })}
          </g>
        ))}
      </svg>
      {(rowLabel || colLabel) && (
        <div className="note">{[rowLabel, colLabel].filter(Boolean).join(' · ')}</div>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- tornado */

/** One-at-a-time sensitivity: bar length is the swing an assumption produces. */
/**
 * Schemes on a time axis, split by whether they survived.
 *
 * The tables can list the same facts, but only a time axis shows the shape of
 * the record: three failures inside four years, then a seventeen-year gap
 * before anyone in North America tried again. That gap is the argument for
 * taking the authorisation question as seriously as the price.
 */
export function Timeline({ events, tooltip }) {
  const [ref, width] = useWidth()
  const padL = 18
  const padR = 18
  const plotW = Math.max(width - padL - padR, 120)

  const years = events.map((e) => e.year)
  const min = Math.min(...years) - 3
  const max = Math.max(...years) + 3
  const X = (y) => padL + ((y - min) / (max - min || 1)) * plotW

  // Successes above the axis, failures below, so the eye reads outcome from
  // position rather than from colour alone.
  //
  // Stacking is by horizontal PROXIMITY, not by array index. An index-based
  // stagger looks like it separates things and does not: 2008 holds three
  // events here, and whether their labels collide depends on where they sit in
  // the list rather than on where they sit on the axis. Walking each side in x
  // order and pushing a marker up a rung only when it would overlap the last
  // one placed is both correct and stable.
  const MIN_GAP = 78          // px of clear space a label needs beside its neighbour
  const RUNG = 21
  const laid = []
  for (const up of [true, false]) {
    const side = events
      .filter((e) => e.ok === up)
      .map((e) => ({ ...e, x: X(e.year), up }))
      .sort((a, b) => a.x - b.x)
    const lastAtRung = []
    for (const e of side) {
      let rung = 0
      while (lastAtRung[rung] != null && e.x - lastAtRung[rung] < MIN_GAP) rung += 1
      lastAtRung[rung] = e.x
      laid.push({ ...e, rung })
    }
  }

  // Height follows the layout rather than the layout being squeezed into a
  // fixed height. A stacked rung that runs off the bottom of the viewBox is
  // invisible, which is worse than a taller chart.
  const rungsUp = Math.max(0, ...laid.filter((e) => e.up).map((e) => e.rung)) + 1
  const rungsDown = Math.max(0, ...laid.filter((e) => !e.up).map((e) => e.rung)) + 1
  const above = 30 + rungsUp * RUNG
  const below = 44 + rungsDown * RUNG
  const axisY = above
  const height = above + below

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={height} role="img">
        <line className="baseline" x1={padL} x2={padL + plotW} y1={axisY} y2={axisY} />
        {ticks(min, max, 5).map((t) => (
          <g key={t}>
            <line className="gridline" x1={X(t)} x2={X(t)} y1={axisY - 4} y2={axisY + 4} />
            <text className="tick" x={X(t)} y={axisY + 18} textAnchor="middle">
              {Math.round(t)}
            </text>
          </g>
        ))}
        {laid.map((e) => {
          const y = e.up ? axisY - 26 - e.rung * RUNG : axisY + 30 + e.rung * RUNG
          return (
            <g
              key={e.label + e.year}
              onMouseMove={(ev) => tooltip?.show(ev, <TipBody title={`${e.label}, ${e.year}`}
                rows={[['Outcome', e.outcome], ['Lesson', e.lesson ?? '—']]} />)}
              onMouseLeave={() => tooltip?.hide()}
            >
              <line x1={e.x} x2={e.x} y1={axisY} y2={y} stroke="var(--axis)" strokeWidth="1" />
              <circle cx={e.x} cy={y} r="5.5"
                      fill={e.up ? 'var(--good)' : 'var(--critical)'}
                      stroke="var(--surface-1)" strokeWidth="1.5" />
              <text x={e.x} y={e.up ? y - 10 : y + 16} textAnchor="middle"
                    className="tick" style={{ fontWeight: 600 }}>
                {e.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export function Tornado({ rows, centralValue, format = fmt.pct, height }) {
  const [ref, width] = useWidth()
  const rowH = 28
  const padL = 200
  const padR = 74
  const padT = 8
  const padB = 32
  const h = height ?? rows.length * rowH + padT + padB
  const plotW = Math.max(width - padL - padR, 90)

  const lo = Math.min(...rows.map((r) => Math.min(r.low, r.high)), centralValue)
  const hi = Math.max(...rows.map((r) => Math.max(r.low, r.high)), centralValue)
  const X = (v) => padL + ((v - lo) / (hi - lo || 1)) * plotW

  return (
    <div ref={ref} className="chart-scroll">
      <svg width={width} height={h} role="img">
        {ticks(lo, hi, 4).map((t) => (
          <g key={t}>
            <line className="gridline" x1={X(t)} x2={X(t)} y1={padT} y2={h - padB} />
            <text className="tick" x={X(t)} y={h - padB + 14} textAnchor="middle">{format(t)}</text>
          </g>
        ))}
        <line x1={X(centralValue)} x2={X(centralValue)} y1={padT} y2={h - padB}
              stroke="var(--text-primary)" strokeWidth={1.5} strokeDasharray="4 3" />

        {rows.map((r, i) => {
          const y = padT + i * rowH + 6
          const bh = rowH - 13
          const a = X(Math.min(r.low, r.high))
          const b = X(Math.max(r.low, r.high))
          return (
            <g key={r.parameter}>
              <rect x={a} y={y} width={Math.max(b - a, 2)} height={bh} rx={4}
                    fill="var(--series-1)" fillOpacity={0.82} />
              <text className="mark-label" x={padL - 9} y={y + bh / 2 + 4} textAnchor="end">
                {r.parameter}
              </text>
              <text className="mark-label" x={b + 7} y={y + bh / 2 + 4}>
                {format(Math.abs(r.high - r.low))}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="note">
        Dashed line is the central case. Bar length is the outcome swing produced by
        moving that one assumption across its plausible range.
      </div>
    </div>
  )
}
