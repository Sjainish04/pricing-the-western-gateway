import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Caveat, Hero, Counter } from '../components/ui.jsx'
import { BarChart, Legend, SERIES, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'

const NARRATIVE = [
  ['Toronto has a system-wide congestion problem.',
   'Congestion costs the GTHA roughly $44.7 billion a year in economic and social terms.'],
  ['Not every gateway suits pricing equally.',
   'A charge only works where priced-off travellers have somewhere else to go.'],
  ['So the corridor is screened, not assumed.',
   'Five major approaches to central Toronto are scored, then stress-tested against thousands of alternative weightings.'],
  ['Etobicoke–Gardiner wins on the combination that matters.',
   'Heavy peak demand alongside a genuine parallel rail alternative in Lakeshore West GO.'],
  ['A Stackelberg game then designs the charge.',
   'The road authority moves first; travellers respond through route, mode, time, occupancy and trip frequency.'],
  ['Equity and diversion are constraints, not footnotes.',
   'A policy that fails either is excluded from the recommendation regardless of its welfare score.'],
  ['Pricing is tested against a serious non-priced alternative.',
   'Signals, ramp management, transit priority and parking pricing, with no charge at all.'],
  ['The answer is a package, and a governance pathway.',
   'A direct expressway toll needs provincial authorisation; branch B uses only City-controlled instruments.'],
]

export default function Overview() {
  const meta = useApi('/api/meta')
  const base = useApi('/api/validation')
  const game = useApi('/api/game/analysis')
  const tip = useTooltip()

  if (meta.error) return <ErrorBox error={meta.error} />
  if (meta.loading || base.loading || game.loading) return <Loading what="the baseline corridor" />
  if (base.error) return <ErrorBox error={base.error} />

  const shares = meta.data.base_shares
  const shareRows = Object.entries(shares)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v], i) => ({
      label: nice(k),
      value: v * 100,
      color: SERIES[i % SERIES.length],
      trips: v * 40465,
    }))

  const links = base.data.link_validation
  const west = links.find((l) => l.link_id === 'gardiner_west')
  const pig = game.data?.pigouvian
  const so = game.data?.social_optimum

  return (
    <>
      <Hero
        eyebrow="UTTAN 2026 · Etobicoke–Gardiner western gateway"
        title="Pricing the Western Gateway, Fairly"
        figures={[
          { label: 'Peak inbound vehicles',
            value: <Counter value={west?.base_volume_veh ?? 0} /> },
          { label: 'Corridor speed, AM peak',
            value: <Counter value={west?.modelled_speed_kmh ?? 0}
                            format={(v) => `${v.toFixed(1)} km/h`} /> },
          { label: 'First-best charge',
            value: <Counter value={pig?.first_best_toll_charged_segment ?? 0}
                            format={(v) => fmt.dollars(v)} /> },
          { label: 'Price of anarchy',
            value: <Counter value={so?.price_of_anarchy ?? 1}
                            format={(v) => v.toFixed(3)} /> },
          { label: 'Wasted every year',
            value: <Counter value={so?.welfare_gain_annual ?? 0}
                            format={(v) => fmt.money(v)} /> },
        ]}
      >
        A bounded-corridor Stackelberg model of a peak-period congestion charge on the
        Gardiner Expressway between Highway 427 and the Humber River, built to answer where
        pricing should be tested, what the price should be, who should be protected, and what
        should be done with the money.
      </Hero>

      <div className="grid">
        <Tile label="Study corridor" value="427 → Humber"
              note="8.2 km charged segment of an 18.5 km trip" />
        <Tile label="Volume / capacity" value={west?.vc_ratio?.toFixed(3)}
              tone="bad" note="Running at capacity in the AM peak" />
        <Tile label="Person-trips modelled" value={<Counter value={40465} />}
              note="70 traveller segments" />
        <Tile label="Traveller actions" value="8"
              note="Route, mode, time, occupancy, trip frequency" />
        <Tile label="Scenarios in the library" value="21"
              note="Including a no-charge operational package" />
        <Tile label="Policy designs searched" value={<Counter value={193} />}
              note="Under four binding constraints" />
      </div>

      <Panel
        title="How travellers use the corridor today"
        sub="The calibrated no-toll baseline. The model reproduces this split exactly before any
             charge is applied, because a toll response measured from the wrong starting point is
             not worth reporting."
      >
        <Legend items={shareRows.slice(0, 4).map((r) => ({ label: r.label, color: r.color }))} />
        <BarChart
          data={shareRows}
          format={(v) => `${v.toFixed(1)}%`}
          axisTitle="Share of AM-peak inbound person-trips"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.label} rows={[
                ['Share', fmt.pct(d.value)],
                ['Person-trips', fmt.n(d.trips)],
              ]} />
            ),
          }}
        />
        <div className="note">
          Transit already carries {fmt.pct((shares.go_rail + shares.ttc) * 100)} of inbound peak
          trips on this corridor. That is unusually high for a suburban Toronto approach, and it
          is the reason this gateway scores well on equity: a charge here prices travellers who
          mostly do have an alternative.
        </div>
      </Panel>

      <Panel title="The argument, in order"
             sub="Each step is a result the model produces, not an assumption it starts from.">
        <ol style={{ paddingLeft: 20, margin: 0 }}>
          {NARRATIVE.map(([head, detail]) => (
            <li key={head} style={{ marginBottom: 9 }}>
              <b>{head}</b>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>{detail}</span>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel title="What this model is, and is not">
        <div className="grid-2">
          <div>
            <h3 style={{ fontSize: 13.5, margin: '0 0 6px' }}>It is</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-secondary)', fontSize: 13.5 }}>
              <li>A five-link corridor solved to a stochastic user equilibrium.</li>
              <li>Calibrated to observed volumes and travel times, with two links held out.</li>
              <li>Segmented by sub-area, income quintile and schedule flexibility.</li>
              <li>Constrained by explicit diversion, equity and transit-capacity limits.</li>
              <li>Tested against a non-priced operational package.</li>
            </ul>
          </div>
          <div>
            <h3 style={{ fontSize: 13.5, margin: '0 0 6px' }}>It is not</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-secondary)', fontSize: 13.5 }}>
              <li>A GTHA-wide network assignment.</li>
              <li>A microsimulation — there are no individual vehicles or signals.</li>
              <li>A calibrated emissions inventory; CO₂e is a transparent proxy.</li>
              <li>A source of statutory or financial advice on implementation.</li>
            </ul>
          </div>
        </div>
        <Caveat>
          <b>Where the numbers come from matters.</b> Every input is tagged PUBLISHED, DERIVED or
          ESTIMATED on the <a href="/data">data page</a>. The corridor demand and the observed
          travel times are the two most consequential ESTIMATED inputs, and the sensitivity
          analysis exists to show how much of each conclusion rests on them.
        </Caveat>
      </Panel>

      {tip.node}
    </>
  )
}
