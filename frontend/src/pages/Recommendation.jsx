import { useApi } from '../lib/api.js'
import {
  Panel, Tile, Loading, ErrorBox, Table, Badge, Constraints, Caveat,
} from '../components/ui.jsx'
import { BarChart, SERIES, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'

export default function Recommendation() {
  const { data, loading, error } = useApi('/api/recommendation')
  const tip = useTooltip()

  if (error) return <ErrorBox error={error} />
  if (loading) {
    return <Loading what="the constrained leader search (this evaluates ~200 equilibria)" />
  }
  if (data.status === 'no feasible policy') {
    return (
      <Panel title="No feasible policy">
        <p>{data.note}</p>
      </Panel>
    )
  }

  const d = data
  const m = d.detail.metrics
  const alts = d.alternatives_considered

  return (
    <>
      <div className="page-head">
        <h1>Recommendation</h1>
        <p>
          The best policy in the searched strategy space that satisfies every constraint: the
          local-diversion cap, the equity floor, the minimum congestion improvement, and transit
          capacity. Reported in the format the proposal asks for.
        </p>
      </div>

      <Panel title="The answer">
        <dl className="kv" style={{ fontSize: 14.5, rowGap: 9 }}>
          <dt>Recommended corridor</dt><dd>{d.recommended_corridor}</dd>
          <dt>Charging period</dt><dd>{d.recommended_charging_period}</dd>
          <dt>Price</dt>
          <dd><b>{fmt.dollars(d.recommended_price, 2)}</b> per inbound vehicle, peak period</dd>
          <dt>Coverage</dt>
          <dd>
            {nice(d.coverage)} — every inbound crossing of the western screenline, not the
            expressway alone
          </dd>
          <dt>Equity mechanism</dt><dd>{nice(d.equity_mechanism)}</dd>
          <dt>Diversion mitigation</dt><dd>{d.diversion_mitigation}</dd>
          <dt>Expected traffic reduction</dt>
          <dd>{fmt.signed(d.expected_traffic_reduction_pct)} peak vehicles on the charged segment</dd>
          <dt>Expected delay reduction</dt><dd>{fmt.pct(d.expected_delay_reduction_pct)}</dd>
          <dt>Expected net revenue</dt>
          <dd>{fmt.money(d.expected_net_revenue_annual)} per year, medium cost case</dd>
          <dt>Equity score</dt><dd>{d.equity_score.toFixed(3)}</dd>
          <dt>Governance pathway</dt><dd>{d.governance_pathway}</dd>
        </dl>
      </Panel>

      <div className="grid">
        <Tile label="Peak vehicles" value={fmt.n(m.peak_entering_vehicles)}
              tone="good" note={`${fmt.signed(m.peak_vehicle_change_pct)} vs baseline`} />
        <Tile label="Delay removed" value={fmt.pct(m.delay_reduction_pct)} tone="good"
              note={`${fmt.n(d.detail.delay_hours_saved_peak)} vehicle-hours per peak`} />
        <Tile label="Travel time saved" value={`${m.travel_time_saved_min.toFixed(1)} min`}
              tone="good" note={`Corridor now ${m.gardiner_speed_kmh} km/h`} />
        <Tile label="Worst local change" value={fmt.signed(m.worst_diversion_pct)}
              tone={m.worst_diversion_pct <= 10 ? 'good' : 'bad'}
              note={m.worst_diversion_link ?? '—'} />
        <Tile label="Transit shift"
              value={`${m.transit_share_change_pp >= 0 ? '+' : ''}${m.transit_share_change_pp.toFixed(2)} pp`}
              note={`GO at ${fmt.pct(m.go_load_factor * 100, 0)} of capacity`} />
        <Tile label="Auto occupancy" value={m.auto_occupancy.toFixed(3)}
              note="Persons per vehicle, up from 1.150" />
        <Tile label="CO₂e change" value={fmt.signed(m.co2e_change_pct, 2)}
              tone={m.co2e_change_pct < 0 ? 'good' : 'bad'} note="Proxy, not an inventory" />
        <Tile label="Equity score" value={d.equity_score.toFixed(3)}
              tone="good" note="Above the 0.55 floor" />
      </div>

      <Panel title="Constraint compliance">
        <Constraints feasible={d.detail.feasible} />
      </Panel>

      <Panel
        title="How the recommendation compares with theory"
        sub="The recommended price sits between what the textbook prescribes and what a
             constraint-free optimiser would choose."
      >
        <Table
          columns={[
            { label: 'Benchmark', render: (r) => r[0] },
            { label: 'Charge', render: (r) => r[1] },
            { label: 'What it means', render: (r) =>
              <span style={{ whiteSpace: 'normal' }}>{r[2]}</span> },
          ]}
          rows={[
            ['First-best Pigouvian charge',
             fmt.dollars(d.benchmarks.first_best_pigouvian_toll),
             'The delay one extra vehicle imposes on everybody else, on the charged segment only. '
             + 'Ignores diversion, equity and collection cost.'],
            ['Welfare-maximising uniform charge',
             fmt.dollars(d.benchmarks.welfare_maximising_uniform_toll),
             'The screenline charge that minimises total travel cost, with no regard for who bears it.'],
            ['Recommended charge', fmt.dollars(d.recommended_price),
             'The best price that also respects the diversion cap, the equity floor and transit capacity.'],
            ['Price of anarchy', d.benchmarks.price_of_anarchy.toFixed(4),
             'Total travel cost under selfish choice, relative to the least-cost allocation. '
             + 'This bounds what any pricing policy can win.'],
          ]}
          rowKey={(r) => r[0]}
          highlight={(r) => r[0] === 'Recommended charge'}
        />
        <div className="note">
          The recommended charge lands close to the first-best figure for the charged segment,
          which is a useful coincidence rather than a design goal: the constraints happen to bite
          at a similar price to the one theory prescribes. The welfare-maximising uniform charge is
          higher because it is indifferent to who pays.
        </div>
      </Panel>

      <Panel
        title="Against the alternatives that were seriously considered"
        sub="Including the operational package that uses no charge at all, and both governance
             branches."
      >
        <BarChart
          data={alts.map((a) => ({
            label: a.label, value: a.delay_reduction_pct,
            color: a.feasible ? SERIES[0] : SERIES[1], full: a,
          }))}
          format={(v) => `${v.toFixed(1)}%`}
          axisTitle="Delay removed (%)"
          tooltip={{
            ...tip,
            render: (x) => (
              <TipBody title={x.full.label} rows={[
                ['Delay removed', fmt.pct(x.full.delay_reduction_pct)],
                ['Net revenue', fmt.money(x.full.net_revenue_annual)],
                ['Equity score', x.full.equity_score.toFixed(3)],
                ['Feasible', x.full.feasible ? 'yes'
                  : `no — ${x.full.failed_constraints.join(', ')}`],
              ]} />
            ),
          }}
        />
        <Table
          columns={[
            { label: 'Option', render: (a) => a.label },
            { label: 'Charge', render: (a) => fmt.dollars(a.peak_toll, 0) },
            { label: 'Delay ↓', render: (a) => fmt.pct(a.delay_reduction_pct) },
            { label: 'Worst local ↑', render: (a) => fmt.signed(a.worst_diversion_pct) },
            { label: 'Net revenue', render: (a) => fmt.money(a.net_revenue_annual) },
            { label: 'Equity', render: (a) => a.equity_score.toFixed(3) },
            { label: 'Feasible', render: (a) => <Badge ok={a.feasible} /> },
          ]}
          rows={alts}
          rowKey={(a) => a.id}
        />
      </Panel>

      <Panel title="The search behind the recommendation">
        <dl className="kv">
          <dt>Designs evaluated</dt><dd>{fmt.n(d.search.evaluated)}</dd>
          <dt>Satisfying every constraint</dt>
          <dd>
            {fmt.n(d.search.feasible_count)}{' '}
            ({fmt.pct((d.search.feasible_count / d.search.evaluated) * 100, 0)})
          </dd>
          <dt>Best if constraints were ignored</dt>
          <dd>
            {d.search.best_unconstrained.label} — welfare{' '}
            {d.search.best_unconstrained.welfare.toFixed(4)}, equity{' '}
            {d.search.best_unconstrained.equity_score.toFixed(3)}
          </dd>
          <dt>Cost of the constraints</dt>
          <dd>{d.search.cost_of_constraints?.toFixed(4)} of welfare on the model's scale</dd>
          <dt>Constraints applied</dt>
          <dd>
            Local diversion ≤ {d.search.constraints.max_diversion_increase_pct}% ·
            equity ≥ {d.search.constraints.min_equity_score} ·
            delay reduction ≥ {d.search.constraints.min_delay_reduction_pct}% ·
            transit within capacity
          </dd>
        </dl>
      </Panel>

      <Panel title="What would change this recommendation">
        <Caveat>
          <b>This is a modelling result, not advice.</b> Three things would move it materially, and
          all three are answerable with data the City and Metrolinx already hold.
        </Caveat>
        <ol style={{ marginTop: 12, paddingLeft: 20, fontSize: 13.5,
                     color: 'var(--text-secondary)' }}>
          <li style={{ marginBottom: 7 }}>
            <b>A real screenline count and probe travel times.</b> The demand base and the
            calibration targets are the two most consequential estimated inputs, and both are
            measurable.
          </li>
          <li style={{ marginBottom: 7 }}>
            <b>Observed bypass behaviour during the Gardiner rehabilitation.</b> The rejoin
            fraction governs how much a gateway charge leaks; the Section 3 construction period is
            a natural experiment for it.
          </li>
          <li style={{ marginBottom: 7 }}>
            <b>A procurement estimate for collection.</b> The sign of the financial answer at
            modest prices depends on fixed operating cost, which no model can resolve.
          </li>
          <li>
            <b>The governance decision itself.</b> If provincial authorisation does not arrive,
            branch B is not a variation on the recommendation — it is a different policy with
            different economics, and it is reported separately for that reason.
          </li>
        </ol>
      </Panel>

      {tip.node}
    </>
  )
}
