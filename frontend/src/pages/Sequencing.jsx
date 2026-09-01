import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat, Finding } from '../components/ui.jsx'
import { BarChart, LineChart, Legend, SERIES, fmt, useTooltip, TipBody } from '../components/charts.jsx'

/* The phased game. `game.py` has the leader move once; every scheme in the
 * record moved more than once, and the order decided whether it survived. */
export default function Sequencing() {
  const run = useApi('/api/game/phasing')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the sequencing paths" />

  const { comparison: c, frontier: f, assumptions } = run.data
  const paths = c.paths
  const best = paths.find((p) => p.path.key === c.best) ?? paths[0]
  const now = paths.find((p) => p.path.key === 'charge_now')

  return (
    <>
      <div className="page-head">
        <h1>When to charge, not just how much</h1>
        <p>
          The leader in the main model moves once. Every congestion charge in the record moved
          more than once, and the order is what decided whether it survived. Stockholm expanded
          transit first, ran the charge as a pilot, then held the referendum, and turned a
          two-to-one majority against into a majority for. New York in 2008 moved once and lost
          its federal funding because it could not get the legislative authority in time.
          A single-shot model reports the welfare of a charge as though enacting it were free —
          which assumes away the constraint that actually killed the 2008 attempt.
        </p>
      </div>

      <Panel
        title="The result"
        sub={`Every path below charges the same $${c.charge.toFixed(0)}. The only thing that differs is the order.`}
      >
        <div className="grid">
          <Tile label="Best sequence" value={best.path.name}
                note={best.path.precedent} />
          <Tile label="Support when the charge is proposed"
                value={fmt.pct(100 * best.support_at_gate, 0)}
                tone="good"
                note={`vs ${fmt.pct(100 * (now?.support_at_gate ?? 0), 0)} if charged immediately`} />
          <Tile label="Chance it is ever enacted"
                value={fmt.pct(100 * best.enactment_probability, 0)}
                tone="good"
                note={`vs ${fmt.pct(100 * (now?.enactment_probability ?? 0), 0)} if charged immediately`} />
          <Tile label="Value of sequencing"
                value={fmt.n(c.sequencing_value, 3)}
                tone="good"
                note="welfare points, against charging now" />
        </div>
        <Finding kicker="The result" tone="good"
                 lede="None of that is a better policy.">
          <p className="aside">
            The charge is identical in every row — same price, same coverage, same credits.
            The entire difference is how likely it is to exist.
          </p>
        </Finding>
      </Panel>

      <Panel title="Expected discounted welfare by path" sub={`${c.horizon_years}-year horizon, ${fmt.pct(100 * c.discount_rate, 0)} discount rate`}>
        <BarChart
          data={paths.map((p) => ({
            label: p.path.name,
            value: p.expected_discounted_welfare,
            color: p.path.key === c.best ? SERIES[0]
              : p.path.key === 'charge_now' ? SERIES[2] : SERIES[1],
          }))}
          diverging
          format={(v) => fmt.n(v, 2)}
          axisTitle="Expected discounted welfare"
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Best ordering', color: SERIES[0] },
          { label: 'Other phased paths', color: SERIES[1] },
          { label: 'Charge immediately', color: SERIES[2] },
        ]} />
      </Panel>

      <Panel title="Every path, with its precedent">
        <Table
          columns={[
            { key: 'name', label: 'Path', render: (p) => <b>{p.path.name}</b> },
            { key: 'precedent', label: 'Precedent', render: (p) => p.path.precedent || '—' },
            { key: 'year', label: 'Charge from',
              render: (p) => (p.charge_year == null ? 'never' : `year ${p.charge_year}`) },
            { key: 'support', label: 'Support at the gate',
              render: (p) => (p.support_at_gate == null ? '—' : fmt.pct(100 * p.support_at_gate, 0)) },
            { key: 'p', label: 'P(enacted)',
              render: (p) => fmt.pct(100 * p.enactment_probability, 0) },
            { key: 'w', label: 'E[discounted welfare]',
              render: (p) => fmt.n(p.expected_discounted_welfare, 3) },
            { key: 'verdict', label: '',
              render: (p) => (p.path.key === c.best
                ? <Badge kind="pass">best</Badge>
                : p.path.key === 'charge_now' ? <Badge kind="warn">2008 attempt</Badge> : null) },
          ]}
          rows={paths}
          rowKey={(p) => p.path.key}
          highlight={(p) => p.path.key === c.best}
        />
        <div className="note">
          {paths.map((p) => (
            <p key={p.path.key} style={{ marginBottom: 8 }}>
              <b>{p.path.name}.</b> {p.path.rationale}
            </p>
          ))}
        </div>
      </Panel>

      <Panel
        title="How long to wait"
        sub="Transit is committed at year 0 throughout, so the only thing varying is how long the leader waits before charging"
      >
        <LineChart
          series={[{
            label: 'Expected discounted welfare',
            color: SERIES[0],
            data: f.rows.map((r) => ({ x: r.charge_start_year, y: r.expected_discounted_welfare })),
          }]}
          xTitle="Charge starts in year"
          yTitle="Expected discounted welfare"
          format={(v) => fmt.n(v, 2)}
          xFormat={(v) => fmt.n(v, 0)}
          zeroLine
          tooltip={tip}
        />
        <div className="grid">
          <Tile label="Optimal start" value={`year ${f.optimal_start_year}`}
                tone="good"
                note={f.interior_optimum ? 'an interior optimum' : 'a corner — one force dominates'} />
          <Tile label="Cost of charging immediately"
                value={fmt.n(f.cost_of_charging_immediately, 3)}
                note="welfare points lost to enactment risk" />
          <Tile label="Cost of waiting to year 6"
                value={fmt.n(f.cost_of_waiting_too_long, 3)}
                note="welfare points lost to discounting" />
        </div>
        <Finding kicker="When"
                 lede="Charge as soon as the alternative lands, and not a year later.">
          <p className="aside">
            Waiting buys the probability the charge is ever enacted and costs discounted
            benefit-years. Both forces are real, so the optimum is interior rather than at
            either end — and it lands at <b>year {f.optimal_start_year}</b>, the year the
            transit uplift is fully delivered. Past delivery, support stops rising and further
            delay is pure discounted loss.
          </p>
        </Finding>
        <Caveat>{f.reading}</Caveat>
      </Panel>

      <Panel title="What this rests on">
        <ul>
          {assumptions.map((a) => <li key={a}>{a}</li>)}
        </ul>
        <Caveat>
          Support is modelled as a probability rather than a threshold —{' '}
          {c.enactment.note.toLowerCase()} The gate sits at{' '}
          {fmt.pct(100 * c.enactment.threshold, 0)} support.
        </Caveat>
      </Panel>

      {tip.node}
    </>
  )
}
