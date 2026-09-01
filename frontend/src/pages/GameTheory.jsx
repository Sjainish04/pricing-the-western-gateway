import { useState } from 'react'

import { useApi, usePost } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat } from '../components/ui.jsx'
import {
  BarChart, LineChart, ScatterChart, Legend, SERIES, fmt, nice, useTooltip, TipBody,
} from '../components/charts.jsx'

function LeaderFollower() {
  return (
    <svg viewBox="0 0 720 260" width="100%" style={{ maxWidth: 720 }} role="img"
         aria-label="Stackelberg leader and follower structure">
      <rect x="12" y="16" width="220" height="74" rx="9" fill="var(--series-1)" />
      <text x="122" y="43" textAnchor="middle" style={{ fill: '#fff', fontSize: 13, fontWeight: 650 }}>
        LEADER — Road authority
      </text>
      <text x="122" y="61" textAnchor="middle" style={{ fill: '#fff', fontSize: 11 }}>
        price · window · coverage
      </text>
      <text x="122" y="77" textAnchor="middle" style={{ fill: '#fff', fontSize: 11 }}>
        credits · revenue recycling
      </text>

      <path d="M232,53 L300,53" stroke="var(--axis)" strokeWidth="2" markerEnd="url(#ar)" />
      <defs>
        <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6"
                orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--axis)" />
        </marker>
      </defs>
      <text x="266" y="44" textAnchor="middle" className="tick">commits</text>

      {[['Commuters', 'route · mode · time · occupancy · trip', 16],
        ['Ride-hailing', 'repositioning · pass-through', 78],
        ['Freight', 'retime · reroute · absorb', 140],
        ['Transit operators', 'capacity constraint in this model', 202]].map(([who, what, y]) => (
        <g key={who}>
          <rect x="304" y={y} width="404" height="50" rx="8" fill="var(--surface-1)"
                stroke="var(--axis)" strokeWidth="1" />
          <text x="318" y={y + 21} style={{ fill: 'var(--text-primary)', fontSize: 12.5,
                fontWeight: 620 }}>{who}</text>
          <text x="318" y={y + 38} style={{ fill: 'var(--text-secondary)', fontSize: 11.5 }}>
            {what}
          </text>
        </g>
      ))}

      <path d="M304,240 L240,240 L240,100" stroke="var(--series-2)" strokeWidth="2" fill="none"
            strokeDasharray="4 3" markerEnd="url(#ar)" />
      <text x="150" y="140" className="tick" style={{ fill: 'var(--series-2)' }}>
        equilibrium response
      </text>
      <text x="150" y="156" className="tick" style={{ fill: 'var(--series-2)' }}>
        anticipated by the leader
      </text>
    </svg>
  )
}

export default function GameTheory() {
  const analysis = useApi('/api/game/analysis')
  const [coverage, setCoverage] = useState('screenline')
  const grid = usePost('/api/game/grid', {
    tolls: [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15], coverage, credit: 'none',
  })
  const search = usePost('/api/game/stackelberg', {})
  const tip = useTooltip()

  if (analysis.error) return <ErrorBox error={analysis.error} />
  if (analysis.loading) return <Loading what="the game-theoretic benchmarks" />

  const pig = analysis.data.pigouvian
  const so = analysis.data.social_optimum
  const rows = grid.data?.results ?? []
  const frontier = search.data?.pareto_frontier ?? []
  const best = search.data?.best_feasible
  const bestUn = search.data?.best_unconstrained

  return (
    <>
      <div className="page-head">
        <h1>The Stackelberg game</h1>
        <p>
          The road authority moves first and travellers respond, so the authority is optimising
          over a response function rather than over behaviour directly. Three quantities here are
          not visible in a plain scenario sweep: the textbook first-best charge, the cost of
          letting travellers choose selfishly, and what the policy constraints cost.
        </p>
      </div>

      <div className="grid">
        <Tile label="First-best charge, tolled segment"
              value={fmt.dollars(pig.first_best_toll_charged_segment)}
              note="Marginal external cost at the no-toll equilibrium" />
        <Tile label="First-best charge, full Gardiner"
              value={fmt.dollars(pig.first_best_toll_full_gardiner)}
              note="Includes the untolled downstream section" />
        <Tile label="Welfare-maximising uniform charge"
              value={fmt.dollars(so.optimal_uniform_toll, 2)}
              note="Least total travel cost, screenline coverage" />
        <Tile label="Price of anarchy" value={so.price_of_anarchy.toFixed(4)}
              note={`${fmt.money(so.welfare_gain_annual)} a year is on the table`} />
      </div>

      <Panel title="Who moves, and when" sub="The structure that makes this a Stackelberg problem.">
        <LeaderFollower />
        <div className="note">
          Ride-hailing and freight carry their own instruments in the model but are not separately
          calibrated, so their responses are represented inside the commuter response. Transit
          operators enter as a crowding constraint rather than as a strategic player, which is the
          MVP treatment the plan specifies.
        </div>
      </Panel>

      <Panel
        title="The externality nobody pays for"
        sub="An entering vehicle feels its own travel time but imposes v · dt/dv minutes of delay on
             everyone already on the link. Valued at the average value of time of corridor users,
             that is the first-best charge."
      >
        <BarChart
          data={Object.entries(pig.by_link).map(([k, v]) => ({
            label: nice(k), value: v.marginal_external_cost,
            color: k.startsWith('gardiner') ? SERIES[0] : SERIES[1], full: v,
          }))}
          format={(v) => `$${v.toFixed(2)}`}
          axisTitle="Marginal external congestion cost ($ per additional vehicle)"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.full.name} rows={[
                ['Volume', fmt.n(d.full.volume)],
                ['v/c ratio', d.full.vc_ratio.toFixed(3)],
                ['Delay imposed', `${d.full.delay_minutes_imposed.toFixed(1)} min`],
                ['External cost', fmt.dollars(d.full.marginal_external_cost)],
              ]} />
            ),
          }}
        />
        <Caveat>
          <b>The theoretical answer is far above any deliverable price.</b> The untolled downstream
          section carries the largest externality of all, at{' '}
          {fmt.dollars(pig.by_link.gardiner_east.marginal_external_cost)} per vehicle — and a
          gateway charge on the western segment cannot touch it. This is the clearest statement of
          why the recommendation is not simply "charge the Pigouvian toll": {pig.note}
        </Caveat>
      </Panel>

      <Panel
        title="The price ladder"
        sub="How each outcome moves with the charge. Shown as separate charts rather than one
             chart with two vertical axes, because two measures on different scales cannot share
             an axis honestly."
        right={
          <div className="pill-row" style={{ margin: 0 }}>
            {['gardiner_only', 'screenline'].map((c) => (
              <button key={c} className={`pill${coverage === c ? ' on' : ''}`}
                      onClick={() => setCoverage(c)}>{nice(c)}</button>
            ))}
          </div>
        }
      >
        {grid.loading && !rows.length ? <Loading what="the price ladder" /> : (
          <>
            <div className="grid-2">
              <div>
                <Legend items={[
                  { label: 'Delay removed', color: SERIES[0] },
                  { label: 'Worst local increase', color: SERIES[1] },
                ]} />
                <LineChart
                  series={[
                    { label: 'Delay removed', color: SERIES[0],
                      data: rows.map((r) => ({ x: r.peak_toll, y: r.delay_reduction_pct })) },
                    { label: 'Worst local increase', color: SERIES[1],
                      data: rows.map((r) => ({ x: r.peak_toll, y: r.worst_diversion_pct })) },
                  ]}
                  xTitle="Peak charge ($)" yTitle="Percent"
                  format={(v) => `${v.toFixed(0)}%`} xFormat={(v) => `$${v.toFixed(0)}`}
                  zeroLine
                  tooltip={{
                    ...tip,
                    render: (p, s) => (
                      <TipBody title={`$${p.x} charge`} rows={[[s.label, fmt.signed(p.y)]]} />
                    ),
                  }}
                />
              </div>
              <div>
                <Legend items={[
                  { label: 'Net revenue', color: SERIES[2] },
                  { label: 'Gross revenue', color: SERIES[3] },
                ]} />
                <LineChart
                  series={[
                    { label: 'Net revenue', color: SERIES[2],
                      data: rows.map((r) => ({ x: r.peak_toll, y: r.net_revenue_annual / 1e6 })) },
                    { label: 'Gross revenue', color: SERIES[3],
                      data: rows.map((r) => ({ x: r.peak_toll, y: r.gross_revenue_annual / 1e6 })) },
                  ]}
                  xTitle="Peak charge ($)" yTitle="$ million per year"
                  format={(v) => `${v.toFixed(0)}`} xFormat={(v) => `$${v.toFixed(0)}`}
                  zeroLine
                  tooltip={{
                    ...tip,
                    render: (p, s) => (
                      <TipBody title={`$${p.x} charge`} rows={[[s.label, fmt.money(p.y * 1e6)]]} />
                    ),
                  }}
                />
              </div>
            </div>
            <Table
              columns={[
                { label: 'Charge', render: (r) => fmt.dollars(r.peak_toll, 0) },
                { label: 'Vehicles', render: (r) => fmt.signed(r.peak_vehicle_change_pct) },
                { label: 'Delay ↓', render: (r) => fmt.pct(r.delay_reduction_pct) },
                { label: 'Time saved', render: (r) => `${r.travel_time_saved_min.toFixed(1)} min` },
                { label: 'Worst local ↑', render: (r) => fmt.signed(r.worst_diversion_pct) },
                { label: 'Transit', render: (r) => `${r.transit_share_change_pp >= 0 ? '+' : ''}${r.transit_share_change_pp.toFixed(2)} pp` },
                { label: 'Gross', render: (r) => fmt.money(r.gross_revenue_annual) },
                { label: 'Net', render: (r) => fmt.money(r.net_revenue_annual) },
                { label: 'Equity', render: (r) => r.equity_score.toFixed(3) },
                { label: 'Welfare', render: (r) => r.welfare.toFixed(3) },
                { label: 'Feasible', render: (r) => <Badge ok={r.feasible} /> },
              ]}
              rows={rows}
              rowKey={(r) => r.label}
            />
          </>
        )}
      </Panel>

      <Panel
        title="Total travel cost against the charge"
        sub="The least-cost point is the social optimum a uniform charge can reach. Below it,
             travellers are collectively over-using the road; above it, the charge is removing
             trips worth more than the delay they cause."
      >
        <LineChart
          series={[{ label: 'System cost', color: SERIES[0],
            data: so.curve.map((c) => ({ x: c.toll, y: c.cost_vs_base_pct })) }]}
          xTitle="Uniform screenline charge ($)"
          yTitle="Total travel cost vs no-charge (%)"
          format={(v) => `${v.toFixed(1)}%`} xFormat={(v) => `$${v.toFixed(0)}`}
          zeroLine height={280}
          tooltip={{
            ...tip,
            render: (p) => (
              <TipBody title={`$${p.x} charge`} rows={[
                ['Cost vs baseline', fmt.signed(p.y, 2)],
                ['Charged-segment vehicles',
                 fmt.n(so.curve.find((c) => c.toll === p.x)?.gardiner_west_veh)],
              ]} />
            ),
          }}
        />
        <div className="note">{so.note}</div>
      </Panel>

      <Panel
        title="The Pareto frontier"
        sub="Congestion relief against equity, with bubble area proportional to net revenue.
             Presenting the frontier matters more than presenting the weighted winner: it shows
             the trade-off instead of hiding it inside a choice of weights."
      >
        {search.loading && !frontier.length ? (
          <Loading what="the leader's strategy space (this searches ~200 equilibria)" />
        ) : search.error ? <ErrorBox error={search.error} /> : (
          <>
            <Legend items={[
              { label: 'On the frontier, feasible', color: SERIES[0] },
              { label: 'On the frontier, constraint-breaking', color: SERIES[1] },
            ]} />
            <ScatterChart
              points={frontier.map((f) => ({
                ...f,
                color: f.feasible ? SERIES[0] : SERIES[1],
                revenue_abs: Math.abs(f.net_revenue_annual),
              }))}
              xKey="delay_reduction_pct" yKey="equity_score" sizeKey="revenue_abs"
              xTitle="Delay removed (%)" yTitle="Equity score"
              xFormat={(v) => `${v.toFixed(0)}%`} yFormat={(v) => v.toFixed(2)}
              highlight={(p) => best && p.label === best.label}
              tooltip={{
                ...tip,
                render: (p) => (
                  <TipBody title={p.label} rows={[
                    ['Delay removed', fmt.pct(p.delay_reduction_pct)],
                    ['Equity score', p.equity_score.toFixed(3)],
                    ['Net revenue', fmt.money(p.net_revenue_annual)],
                    ['Worst local increase', fmt.signed(p.worst_diversion_pct)],
                    ['Feasible', p.feasible ? 'yes' : `no — ${p.failed_constraints.join(', ')}`],
                  ]} />
                ),
              }}
            />
            <Table
              columns={[
                { label: 'Policy', render: (f) => f.label },
                { label: 'Delay ↓', render: (f) => fmt.pct(f.delay_reduction_pct) },
                { label: 'Equity', render: (f) => f.equity_score.toFixed(3) },
                { label: 'Net revenue', render: (f) => fmt.money(f.net_revenue_annual) },
                { label: 'Worst local ↑', render: (f) => fmt.signed(f.worst_diversion_pct) },
                { label: 'Welfare', render: (f) => f.welfare.toFixed(3) },
                { label: 'Feasible', render: (f) => <Badge ok={f.feasible} /> },
              ]}
              rows={frontier}
              rowKey={(f) => f.label}
              highlight={(f) => best && f.label === best.label}
            />
          </>
        )}
      </Panel>

      {best && bestUn && (
        <Panel title="What the constraints cost">
          <div className="grid-2">
            <div>
              <h3 style={{ fontSize: 13.5, margin: '0 0 8px' }}>Best feasible policy</h3>
              <dl className="kv">
                <dt>Design</dt><dd>{best.label}</dd>
                <dt>Delay removed</dt><dd>{fmt.pct(best.delay_reduction_pct)}</dd>
                <dt>Equity score</dt><dd>{best.equity_score.toFixed(3)}</dd>
                <dt>Net revenue</dt><dd>{fmt.money(best.net_revenue_annual)}</dd>
                <dt>Welfare</dt><dd>{best.welfare.toFixed(4)}</dd>
              </dl>
            </div>
            <div>
              <h3 style={{ fontSize: 13.5, margin: '0 0 8px' }}>
                Best ignoring the constraints
              </h3>
              <dl className="kv">
                <dt>Design</dt><dd>{bestUn.label}</dd>
                <dt>Delay removed</dt><dd>{fmt.pct(bestUn.delay_reduction_pct)}</dd>
                <dt>Equity score</dt><dd>{bestUn.equity_score.toFixed(3)}</dd>
                <dt>Net revenue</dt><dd>{fmt.money(bestUn.net_revenue_annual)}</dd>
                <dt>Welfare</dt><dd>{bestUn.welfare.toFixed(4)}</dd>
              </dl>
            </div>
          </div>
          <div className="note">
            Protecting local streets and low-income travellers costs{' '}
            {search.data.cost_of_constraints?.toFixed(4)} of welfare on this scale —
            {' '}{search.data.feasible_count} of {search.data.evaluated} designs searched satisfy
            every constraint. Stating that price explicitly is more useful than quietly reporting
            only the constrained winner.
          </div>
        </Panel>
      )}

      {tip.node}
    </>
  )
}
