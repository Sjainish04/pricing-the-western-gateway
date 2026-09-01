import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat, Finding } from '../components/ui.jsx'
import { LineChart, Legend, SERIES, fmt, useTooltip } from '../components/charts.jsx'

/* The joint game. Sequencing and authorisation are one problem: the phased
 * game says wait for transit, the bargaining game says there is a deadline. */
export default function Timing() {
  const run = useApi('/api/game/joint')
  const jointOpt = useApi('/api/game/joint-optimum')
  const dep = useApi('/api/game/gate-dependence')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the joint timing game" />

  const { frontier: f, window: w, deadline_sensitivity: ds, gates, assumptions } = run.data
  const live = ds.rows.filter((r) => r.charge_ever_enacted)
  const switchAt = ds.recommendation_switches_at

  return (
    <>
      <div className="page-head">
        <h1>The deadline on waiting</h1>
        <p>
          The phased game asks when to charge and answers <i>as soon as the alternative is
          delivered</i>. The bargaining game asks whether the City and the Province can agree,
          and finds the City's hand changes at a fixed date. Solved separately, each is missing
          the other's binding constraint — one says wait, the other says there is a deadline on
          waiting. Here they are one question.
        </p>
      </div>

      <Panel title="Two gates, not one">
        <div className="grid">
          <Tile label="The public" value="P(voters)" note={gates.voters} />
          <Tile label="The two governments" value="P(deal)" note={gates.governments} />
          <Tile label="Combined" value="P(voters) × P(deal)" note={gates.combined} />
        </div>
        <p>
          A charge needs a public that will tolerate it <b>and</b> two governments that can agree.
          Both gates are logistic rather than thresholds, so nothing here is an artefact of which
          side of a cliff a year happened to fall on.
        </p>
        <Caveat>{gates.independence_caveat}</Caveat>
      </Panel>

      <Panel
        title="At the assumed political cost, the second gate does not bind"
        sub={`The transfer lands ${f.years_until_transfer} years out, so years 0 and 1 begin before it and year ${f.first_post_transfer_year} does not`}
      >
        <Table
          columns={[
            { key: 'charge_start_year', label: 'Charge from', render: (r) => `year ${r.charge_start_year}` },
            { key: 'regime', label: 'Regime',
              render: (r) => (r.regime === 'pre_transfer'
                ? <Badge kind="info">before transfer</Badge>
                : <Badge kind="warn">after transfer</Badge>) },
            { key: 'support_at_gate', label: 'Support',
              render: (r) => fmt.pct(100 * r.support_at_gate, 0) },
            { key: 'p_voters', label: 'P(voters)', render: (r) => fmt.pct(100 * r.p_voters, 0) },
            { key: 'p_deal', label: 'P(deal)', render: (r) => fmt.pct(100 * r.p_deal, 0) },
            { key: 'p_joint', label: 'P(both)', render: (r) => fmt.pct(100 * r.p_joint, 0) },
            { key: 'expected_discounted_welfare', label: 'E[disc W]',
              render: (r) => fmt.n(r.expected_discounted_welfare, 3) },
          ]}
          rows={f.rows}
          rowKey={(r) => r.charge_start_year}
          highlight={(r) => r.charge_start_year === f.optimal_start_year_joint}
        />
        <Finding kicker="The honest baseline"
                 lede={`At the assumed political cost, joining the two games adds nothing.`}>
          <p className="aside">
            The bargained surplus is comfortably positive in both regimes, so the joint
            recommendation is the phased one: charge in year {f.optimal_start_year_joint}.
          </p>
        </Finding>
      </Panel>

      <Panel
        title="But the Province refused in 2017"
        sub="Which puts a floor under the political cost, and the floor is above where the answer changes"
      >
        <LineChart
          series={[
            { label: 'Before fall 2027', color: SERIES[2],
              data: ds.rows.map((r) => ({ x: r.political_cost_per_charged_trip, y: 100 * r.p_deal_pre_transfer })) },
            { label: 'After fall 2027', color: SERIES[0],
              data: ds.rows.map((r) => ({ x: r.political_cost_per_charged_trip, y: 100 * r.p_deal_post_transfer })) },
          ]}
          xTitle="Political cost per charged trip ($/year)"
          yTitle="Probability the two governments agree (%)"
          format={(v) => fmt.pct(v, 0)}
          xFormat={(v) => fmt.dollars(v, 2)}
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Before fall 2027', color: SERIES[2] },
          { label: 'After fall 2027', color: SERIES[0] },
        ]} />

        <Table
          columns={[
            { key: 'political_cost_per_charged_trip', label: '$ / charged trip',
              render: (r) => fmt.dollars(r.political_cost_per_charged_trip, 2) },
            { key: 'p_deal_pre_transfer', label: 'P(deal) before',
              render: (r) => fmt.pct(100 * r.p_deal_pre_transfer, 0) },
            { key: 'p_deal_post_transfer', label: 'P(deal) after',
              render: (r) => fmt.pct(100 * r.p_deal_post_transfer, 0) },
            { key: 'optimal_start_year', label: 'Optimal start',
              render: (r) => (r.optimal_start_year == null ? '—' : `year ${r.optimal_start_year}`) },
            { key: 'optimum_before_transfer', label: 'Act before the transfer?',
              render: (r) => (r.optimum_before_transfer == null
                ? <Badge kind="warn">no charge at all</Badge>
                : <Badge ok={r.optimum_before_transfer}
                         kind={r.optimum_before_transfer ? 'pass' : 'fail'}>
                    {r.optimum_before_transfer ? 'yes' : 'no — wait'}
                  </Badge>) },
          ]}
          rows={ds.rows}
          rowKey={(r) => r.political_cost_per_charged_trip}
          highlight={(r) => r.political_cost_per_charged_trip === ds.assumed_rate}
        />

        {switchAt != null && (
          <Finding kicker="The reversal" tone="bad"
                   lede={`The recommendation reverses at ${fmt.dollars(switchAt, 2)} per charged trip — below the level the 2017 refusal implies.`}>
            <p className="aside">
              On the model's own revealed bound, the advice is to <b>wait until after the
              transfer</b>, not to rush a deal before it.
            </p>
            <p className="aside">
              The mechanism runs against the leverage intuition. A zone of agreement survives to
              a <i>higher</i> political cost after the transfer, because once the Province owns
              the road its fallback is a unilateral charge that carries political cost of its
              own. It is exposed either way, so the cost of <i>agreeing</i> is smaller in
              difference terms.
            </p>
          </Finding>
        )}
        <Caveat>{ds.reading}</Caveat>
      </Panel>

      <Panel title="Is there a window, and how long is it?">
        <div className="grid">
          <Tile label="Transfer in" value={`${w.years_until_transfer} years`}
                note="fall 2027" />
          <Tile label="Optimal start"
                value={w.optimal_start_year == null ? '—' : `year ${w.optimal_start_year}`}
                tone={w.optimum_is_before_transfer ? 'good' : undefined} />
          <Tile label="Best before the transfer"
                value={w.best_pre_transfer ? fmt.n(w.best_pre_transfer.expected_discounted_welfare, 3) : '—'}
                note={w.best_pre_transfer ? `year ${w.best_pre_transfer.charge_start_year}` : ''} />
          <Tile label="Best after the transfer"
                value={w.best_post_transfer ? fmt.n(w.best_post_transfer.expected_discounted_welfare, 3) : '—'}
                note={w.best_post_transfer ? `year ${w.best_post_transfer.charge_start_year}` : ''} />
        </div>
        <p>
          At the assumed political cost the window is real and the optimum sits before the
          transfer, worth{' '}
          <b>{w.value_of_acting_before_the_transfer == null ? '—'
            : fmt.n(w.value_of_acting_before_the_transfer, 3)}</b> welfare points against the best
          post-transfer year. At a political cost consistent with 2017, it inverts.{' '}
          <b>Both arguments are reported, because which dominates is an empirical question about
          a rate this study cannot measure.</b>
        </p>
        <Caveat>{w.note}</Caveat>
      </Panel>

      {(() => {
        if (jointOpt.error) return <ErrorBox error={jointOpt.error} />
        if (!jointOpt.data) {
          return (
            <Panel title="Choosing the price and the year together"
                   sub="The sweep above fixes the charge — this one does not">
              <Loading what="the joint surface" />
            </Panel>
          )
        }
        const j = jointOpt.data
        const u = j.unconstrained_optimum
        const c = j.constrained_optimum
        return (
          <Panel
            title="Choosing the price and the year together"
            sub="The sweep above fixes the charge, so it answers when. The leader chooses both."
          >
            <div className="grid">
              <Tile label="Joint answer"
                    value={`$${c.charge} · year ${c.charge_start_year}`}
                    note="subject to the same constraints as the recommendation" />
              <Tile label="Without those constraints"
                    value={`$${u.charge} · year ${u.charge_start_year}`}
                    note="runs to the top of the grid — a boundary, not a result" />
              <Tile label="What the constraints cost"
                    value={j.price_of_the_constraints?.toFixed(3)}
                    note={`welfare points, binding on ${j.constraints_that_bind.join(' and ')}`} />
            </div>

            <Finding kicker="What actually sets the price"
                     lede={j.reading} />

            <Table
              rowKey={(r) => `${r.charge}-${r.charge_start_year}`}
              highlight={(r) => r.charge === c.charge && r.charge_start_year === c.charge_start_year}
              columns={[
                { key: 'charge', label: 'Charge', render: (r) => `$${r.charge}` },
                { key: 'y', label: 'Start year', render: (r) => r.charge_start_year },
                { key: 'pv', label: 'P(voters)', render: (r) => fmt.pct(100 * r.p_voters, 1) },
                { key: 'pd', label: 'P(deal)', render: (r) => fmt.pct(100 * r.p_deal, 1) },
                { key: 'w', label: 'E[disc. welfare]',
                  render: (r) => r.expected_discounted_welfare.toFixed(4) },
                { key: 'f', label: 'Passes constraint set?',
                  render: (r) => (
                    <Badge ok={r.feasible}>
                      {r.feasible ? 'yes' : r.failed_constraints.join(', ')}
                    </Badge>
                  ) },
              ]}
              rows={j.cells.filter((r) => r.charge_start_year <= 2)}
            />
            <p className="aside">
              Start years 0–2 shown; the full surface runs to year 6 and falls monotonically
              after year 1 at every price. The best <i>charge</i> is ${c.charge} at every start
              year, but the best <i>year</i> is not the same at every charge — which is why
              solving in sequence happens to work here and would not in general.
            </p>
            <p className="aside">
              The two columns answer different questions, which is why $6 can pass the
              constraint set and still be worthless. <b>P(deal)</b> is zero at and below $6
              because the scheme raises too little to cover the Province&rsquo;s political cost,
              so those rows collapse to the never-charge welfare of −0.197. That is the
              financial-marginality finding reappearing as a governance one: a charge too small
              to be worth collecting is also too small to be worth authorising.
            </p>
          </Panel>
        )
      })()}

      {(() => {
        if (dep.error) return <ErrorBox error={dep.error} />
        if (!dep.data) {
          return (
            <Panel title="The two gates are not independent"
                   sub="A scheme the public wants is cheaper to authorise">
              <Loading what="the dependence sweep" />
            </Panel>
          )
        }
        const d = dep.data
        return (
          <Panel
            title="The two gates are not independent"
            sub="P(enacted) = P(voters) × P(deal) assumed they were — this is what that cost"
          >
            <p className="aside">
              A scheme the public wants is cheaper for a government to authorise, so waiting for
              support should buy a better bargain as well as a better vote. That runs through the
              political cost rate rather than through a correlation between the two probabilities:
              a mechanism can be argued with, a coefficient cannot. At 50% support — the
              referendum threshold — the rate is unchanged whatever the dependence, so this
              rotates the line about the existing anchor rather than moving it.
            </p>

            <Table
              rowKey={(r) => r.political_cost_per_charged_trip}
              highlight={(r) => r.deal_gate_binds && r.ratio}
              columns={[
                { key: 'c', label: 'Political cost / charged trip',
                  render: (r) => `$${r.political_cost_per_charged_trip.toFixed(2)}` },
                { key: 'i', label: 'Value of waiting, independent',
                  render: (r) => r.value_of_waiting_independent.toFixed(3) },
                { key: 'd', label: '…with dependence',
                  render: (r) => r.value_of_waiting_dependent.toFixed(3) },
                { key: 'r', label: 'Ratio',
                  render: (r) => (r.ratio ? `${r.ratio}×` : '—') },
                { key: 'b', label: 'Deal gate binds?',
                  render: (r) => <Badge ok={!r.deal_gate_binds}>{r.deal_gate_binds ? 'yes' : 'no'}</Badge> },
              ]}
              rows={d.amplification}
            />

            <Finding kicker="Where the assumption actually cost something"
                     lede={d.reading}>
              <p className="aside">
                The Province refused in 2017, so its valuation sits above{' '}
                <b>${d.revealed_cost_bound}</b> per charged trip — which is precisely the regime
                where independence was understating the case for building support first.
              </p>
            </Finding>

            <Caveat>{d.caveat}</Caveat>
          </Panel>
        )
      })()}

      <Panel title="What this rests on">
        <ul>{assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </Panel>

      {tip.node}
    </>
  )
}
