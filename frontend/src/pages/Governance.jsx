import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat, Finding } from '../components/ui.jsx'
import { LineChart, Legend, SERIES, fmt, useTooltip } from '../components/charts.jsx'

const REGIME_LABEL = {
  pre_transfer: 'Before fall 2027',
  post_transfer: 'After fall 2027',
}

/* The City and the Province as players, not as two scenarios. */
export default function Governance() {
  const run = useApi('/api/game/bargaining')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the bargaining problem" />

  const { precedent: p, comparison: c, breakeven: bk, side_payment: sp,
          side_payment_curve: spc, power_sensitivity: pw, assumptions } = run.data
  const pre = c.regimes.pre_transfer
  const post = c.regimes.post_transfer

  const curveFor = (regime) => spc.rows
    .filter((r) => r.regime === regime)
    .map((r) => ({ x: r.political_cost_per_charged_trip, y: r.total_surplus_annual / 1e6 }))

  return (
    <>
      <div className="page-head">
        <h1>Who has to agree, and what changes in fall 2027</h1>
        <p>
          The governance branches elsewhere in this study are two assumptions about how a
          negotiation turns out — not a game. The negotiation is real, and it has been played
          once already. In December 2016 Toronto Council voted {p.council_vote.split(' in')[0]} to
          toll the Gardiner and the DVP. In January 2017 the Province refused, and offered
          instead a doubled municipal share of the gas tax worth about{' '}
          {fmt.money(p.side_payment_annual)} a year. A disagreement outcome, a side payment, and
          a revealed price for provincial authorisation.
        </p>
      </div>

      <Panel title="The one time this game was actually played" sub="December 2016 – January 2017">
        <div className="grid">
          <Tile label="Council vote" value={p.council_vote.split(' in')[0]} note="in favour of tolls" />
          <Tile label="Province" value="Refused" tone="bad" note={p.province_response} />
          <Tile label="Compensation accepted"
                value={fmt.money(p.side_payment_annual)}
                note="a year, in gas tax revenue" />
          <Tile label="…as a share of the disputed prize"
                value={fmt.n(p.side_payment_vs_toll_estimate, 2)}
                note="against the City's own toll estimate" />
        </div>
        <ul>{p.what_it_shows.map((x) => <li key={x}>{x}</li>)}</ul>
        <Caveat>{p.caveat}</Caveat>
      </Panel>

      <Panel
        title="Why the Province and the City do not want the same thing"
        sub="The asymmetry is derived from where corridor demand comes from, not assumed"
      >
        <div className="grid">
          <Tile label="Demand from outside Toronto"
                value={fmt.pct(100 * pre.constituencies.non_toronto_share, 0)}
                note="Mississauga and the west GTA" />
          <Tile label="Province's position if no deal"
                value={fmt.money(pre.disagreement.province)}
                note={pre.disagreement.province_fallback} />
          <Tile label="City's position if no deal"
                value={fmt.money(pre.disagreement.city)}
                note={pre.disagreement.city_fallback} />
        </div>
        <Finding kicker="The asymmetry"
                 lede="A charge can be jointly worth having and still be refused.">
          <p className="aside">
            Those travellers are not the City's voters and they are the Province's —
            disproportionately so, since 905 seats decide provincial majorities. The same
            charge therefore costs the Province more politically than the City, while the
            congestion benefit lands mostly inside Toronto. That is not a failure of analysis;
            it is the record.
          </p>
        </Finding>
      </Panel>

      <Panel
        title="What the 2027 transfer actually changes"
        sub="Not the repair liability — that cancels out of the bargain entirely"
      >
        <Table
          columns={[
            { key: 'q', label: '' },
            { key: 'pre', label: REGIME_LABEL.pre_transfer },
            { key: 'post', label: REGIME_LABEL.post_transfer },
          ]}
          rows={[
            { q: 'Can the City charge the Gardiner alone?', pre: 'No — needs authorisation', post: 'No' },
            { q: 'Can the Province?', pre: 'No — does not own it', post: 'Yes' },
            { q: "Province's fallback", pre: pre.disagreement.province_fallback, post: post.disagreement.province_fallback },
            { q: "City's fallback", pre: pre.disagreement.city_fallback, post: post.disagreement.city_fallback },
            {
              q: 'City share of revenue (Nash)',
              pre: pre.nash ? fmt.pct(100 * pre.nash.city_share, 1) : '—',
              post: post.nash ? fmt.pct(100 * post.nash.city_share, 1) : '—',
            },
            {
              q: 'City surplus over its fallback',
              pre: pre.nash ? fmt.money(pre.nash.city_surplus) : '—',
              post: post.nash ? fmt.money(post.nash.city_surplus) : '—',
            },
          ]}
          rowKey={(r) => r.q}
        />
        <p>
          Today the two hold a mutual veto, which is what makes this a genuine bilateral bargain.
          After the transfer the Province owns the road <i>and</i> authorises itself. The City's
          fallback does not improve — it still has only a charge on its own arterials, which this
          study finds is the most regressive design in the library.
        </p>
        <Finding kicker="What the City loses" tone="bad"
                 lede={`The option the Province gains is a freeway-only charge — and it pushes ${fmt.signed(c.province_unilateral_diversion_pct)} onto The Queensway.`}>
          <p className="aside">
            That breaches the local-street cap. Those are City streets, and after 2027 the City
            would have no standing to object.
          </p>
        </Finding>
        <Caveat>{c.why_the_loss_of_leverage_is_small}</Caveat>
      </Panel>

      <Panel
        title="The unobservable, inverted"
        sub="Rather than tune the political cost until the model reproduces 2017, find the rate at which a deal becomes impossible"
      >
        <div className="grid">
          <Tile label="Assumed political cost"
                value={fmt.dollars(bk.assumed_per_charged_trip, 2)}
                note="per charged trip per year — a stated stance" />
          <Tile label="Deal dies above (before transfer)"
                value={fmt.dollars(c.breakeven_political_cost.pre_transfer.threshold_per_charged_trip, 2)}
                tone="bad" />
          <Tile label="Deal dies above (after transfer)"
                value={fmt.dollars(c.breakeven_political_cost.post_transfer.threshold_per_charged_trip, 2)}
                tone="good"
                note="a deal survives a HIGHER cost after the transfer" />
        </div>
        <p>
          The Province <i>did</i> refuse in 2017, so on this model its true valuation sits{' '}
          <b>above</b> the pre-transfer threshold — a revealed-preference bound from a real
          decision, which is worth more than a fitted coefficient.
        </p>
      </Panel>

      <Panel
        title="Side payments: the instrument the 2017 negotiation actually used"
        sub="Everything above divides only the charge's own revenue. That is not how this was settled."
      >
        <div className="grid">
          <Tile label="Corridor net revenue"
                value={fmt.money(sp.corridor_net_revenue_annual)} note="a year" />
          <Tile label="The 2017 side payment"
                value={fmt.money(sp.observed_2017_side_payment)} note="a year" />
          <Tile label="Ratio"
                value={`${fmt.n(sp.observed_vs_corridor_revenue, 1)}×`}
                tone="bad"
                note="the settlement dwarfed the prize" />
          <Tile label="Total surplus available"
                value={fmt.money(sp.total_surplus_annual)}
                tone={sp.deal_exists_with_transfers ? 'good' : 'bad'}
                note={sp.deal_exists_with_transfers ? 'a deal exists' : 'no transfer can close it'} />
        </div>
        <Finding kicker="The wrong number to argue over"
                 lede="The 2017 settlement was thirty times the corridor's entire net revenue.">
          <p className="aside">
            With a transfer available the problem is transferable-utility: the <b>total</b>{' '}
            surplus decides whether a deal exists, and the split only decides who banks it. A
            scheme jointly worth doing can always be made mutually acceptable by a payment; one
            that is not cannot be rescued by any split.
          </p>
        </Finding>

        <LineChart
          series={[
            { label: 'Before fall 2027', color: SERIES[2], data: curveFor('pre_transfer') },
            { label: 'After fall 2027', color: SERIES[0], data: curveFor('post_transfer') },
          ]}
          xTitle="Political cost per charged trip ($/year)"
          yTitle="Total surplus ($M/year)"
          format={(v) => `$${fmt.n(v, 0)}M`}
          xFormat={(v) => fmt.dollars(v, 2)}
          zeroLine
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Before fall 2027', color: SERIES[2] },
          { label: 'After fall 2027', color: SERIES[0] },
        ]} />
        <Caveat>{spc.note}</Caveat>
      </Panel>

      <Panel
        title="Bargaining power divides a surplus; it does not create one"
        sub="Whether a deal exists is set by the fallbacks alone, so it is invariant to who is stronger"
      >
        <Table
          columns={[
            { key: 'bargaining_power_city', label: "City's bargaining power",
              render: (r) => fmt.n(r.bargaining_power_city, 2) },
            { key: 'city_share', label: 'City share of revenue',
              render: (r) => (r.city_share == null ? '—' : fmt.pct(100 * r.city_share, 1)) },
            { key: 'zone', label: 'Deal possible?',
              render: (r) => <Badge ok={r.has_zone_of_agreement} /> },
          ]}
          rows={pw.rows}
          rowKey={(r) => r.bargaining_power_city}
        />
        <Caveat>{pw.note}</Caveat>
      </Panel>

      <Panel title="What this rests on">
        <ul>{assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </Panel>

      {tip.node}
    </>
  )
}
