import { useState } from 'react'

import { usePost, useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat } from '../components/ui.jsx'
import { BarChart, GroupedBars, Legend, SERIES, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'

const DESIGNS = {
  flat: { label: '$10 flat, no credits',
    policy: { peak_toll: 10, coverage: 'screenline', credit: 'none' } },
  income: { label: '$10 + income & transit-poor credits',
    policy: { peak_toll: 10, coverage: 'screenline', credit: 'low_income_transit_poor' } },
  means: { label: '$10 means-tested (San Francisco)',
    policy: { peak_toll: 10, coverage: 'screenline', credit: 'means_tested' } },
  equity_first: { label: '$10 equity-first package',
    policy: { peak_toll: 10, coverage: 'screenline', credit: 'equity_first' } },
  targeted: { label: '$5 + targeted package',
    policy: { peak_toll: 5, coverage: 'screenline', credit: 'targeted_package' } },
}

export default function Incidence() {
  const [design, setDesign] = useState('flat')
  const run = usePost('/api/simulate', { ...DESIGNS[design].policy, label: design })
  const rideHail = useApi('/api/political/ride-hailing')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the welfare incidence" />

  const inc = run.data.incidence
  const acc = run.data.acceptability
  const rows = inc.welfare_by_quintile
  const conc = inc.burden_concentration
  const bench = inc.benchmark

  return (
    <>
      <div className="page-head">
        <h1>Who wins, who loses, and who lets it happen</h1>
        <p>
          Counting tolls paid is the traditional equity analysis and it is not enough.
          Eliasson separates four components of the welfare effect — the toll, the cost of
          adapting, the time saved on a quieter road, and the revenue returned — and only the
          first appears on an incidence table. This page computes all four, then asks whether
          the result could survive a vote.
        </p>
      </div>

      <Panel title="Design under examination">
        <div className="pill-row">
          {Object.entries(DESIGNS).map(([k, d]) => (
            <button key={k} className={`pill${design === k ? ' on' : ''}`}
                    onClick={() => setDesign(k)}>{d.label}</button>
          ))}
        </div>
      </Panel>

      <div className="grid">
        <Tile label="Better off, before revenue returns"
              value={fmt.pct(inc.winners_share_before_recycling * 100, 0)}
              tone={inc.winners_share_before_recycling > 0.5 ? 'good' : 'bad'}
              note="The charge on its own" />
        <Tile label="Better off, after revenue returns"
              value={fmt.pct(inc.winners_share * 100, 0)}
              tone={inc.winners_share > 0.5 ? 'good' : undefined}
              note={`Assumes the corridor captures ${fmt.pct(inc.capture_share * 100, 0)} of net revenue`} />
        <Tile label="Regressive before recycling"
              value={inc.regressive_before_recycling ? 'Yes' : 'No'}
              tone={inc.regressive_before_recycling ? 'bad' : 'good'}
              note="Lowest quintile loses more of its income than the highest" />
        <Tile label="Would pass a vote today"
              value={acc.implementable_now ? 'Yes' : 'No'}
              tone={acc.implementable_now ? 'good' : 'bad'}
              note={`${fmt.pct(acc.before_operation.support_share * 100, 0)} support among corridor travellers`} />
      </div>

      <Panel
        title="The four components of the welfare effect"
        sub="Negative means worse off. The toll is what the traveller hands over; the resource
             column is their adaptation cost netted against the time they save; surplus is the
             first three components together, and is what the charge itself does to them."
      >
        <Table
          columns={[
            { label: 'Quintile', render: (r) => r.quintile },
            { label: 'Household income', render: (r) => fmt.money(r.household_income) },
            { label: '1. Toll paid', render: (r) => fmt.dollars(r.tolls_per_trip) },
            { label: '2+3. Adaptation & time', render: (r) => fmt.dollars(r.resource_per_trip) },
            { label: '= Surplus', render: (r) => fmt.dollars(r.surplus_per_trip) },
            { label: 'Surplus, % of income', render: (r) => fmt.pct(r.surplus_pct_income, 3) },
            { label: '4. Revenue returned', render: (r) => fmt.dollars(r.recycled_per_trip) },
            { label: 'Net position', render: (r) => fmt.dollars(r.net_per_trip) },
            { label: 'Net, % of income', render: (r) => fmt.pct(r.net_pct_income, 3) },
          ]}
          rows={rows}
          rowKey={(r) => r.quintile}
          highlight={(r) => r.quintile === 'Q1'}
        />

        <div className="grid-2" style={{ marginTop: 16 }}>
          <div>
            <Legend items={[{ label: 'Surplus per trip, before revenue returns', color: SERIES[1] }]} />
            <BarChart
              data={rows.map((r) => ({ label: r.quintile, value: r.surplus_per_trip, full: r }))}
              diverging
              format={(v) => `$${v.toFixed(2)}`}
              axisTitle="Welfare change per trip ($), charge only"
              tooltip={{ ...tip, render: (d) => (
                <TipBody title={`${d.full.quintile} — ${fmt.money(d.full.household_income)}`} rows={[
                  ['Toll paid', fmt.dollars(d.full.tolls_per_trip)],
                  ['Adaptation & time', fmt.dollars(d.full.resource_per_trip)],
                  ['Surplus', fmt.dollars(d.full.surplus_per_trip)],
                  ['% of income', fmt.pct(d.full.surplus_pct_income, 3)],
                ]} />) }}
            />
          </div>
          <div>
            <Legend items={[{ label: 'Surplus loss as a share of income', color: SERIES[0] }]} />
            <BarChart
              data={rows.map((r) => ({ label: r.quintile, value: r.surplus_pct_income, full: r }))}
              diverging
              format={(v) => `${v.toFixed(2)}%`}
              axisTitle="Welfare change as % of household income"
              tooltip={{ ...tip, render: (d) => (
                <TipBody title={d.full.quintile} rows={[
                  ['Surplus', fmt.dollars(d.full.surplus_per_trip)],
                  ['% of income', fmt.pct(d.full.surplus_pct_income, 3)],
                ]} />) }}
            />
          </div>
        </div>

        <Caveat>
          <b>These two charts are the whole equity argument.</b> On the left, higher-income
          travellers lose more dollars — which is why a scheme can be called progressive. On the
          right, the same charge takes a far larger share of a low-income household's income.
          Both are true. Reporting only the first is the most common way an equity analysis
          misleads, and it is exactly what Eliasson warns against.
        </Caveat>
      </Panel>

      <Panel
        title="Averages hide the people who are actually hurt"
        sub="A scheme can look mildly regressive on average while a real subgroup faces a
             serious cost. Eliasson reports the share of each income group paying above a
             threshold; the same is done here against household income."
      >
        <GroupedBars
          categories={conc.by_quintile.map((r) => r.quintile)}
          series={conc.thresholds.map((t, i) => ({
            label: `> ${(t * 100).toFixed(1)}% of income`,
            color: SERIES[i],
            values: conc.by_quintile.map((r) => 100 * r[`share_above_${t}`]),
          }))}
          yTitle="Share of the group (%)"
          format={(v) => `${v.toFixed(0)}%`}
          tooltip={{ ...tip, render: (cat, s, v) => (
            <TipBody title={`${cat} — ${s.label}`} rows={[['Share of group', fmt.pct(v, 1)]]} />) }}
        />
        <Legend items={conc.thresholds.map((t, i) => ({
          label: `> ${(t * 100).toFixed(1)}% of income`, color: SERIES[i] }))} />
        <Table
          columns={[
            { label: 'Quintile', render: (r) => r.quintile },
            { label: 'Income', render: (r) => fmt.money(r.household_income) },
            ...conc.thresholds.map((t) => ({
              label: `> ${(t * 100).toFixed(1)}%`,
              render: (r) => fmt.pct(100 * r[`share_above_${t}`], 1),
            })),
            { label: 'Worst case in group', render: (r) => fmt.pct(r.max_burden_pct, 2) },
          ]}
          rows={conc.by_quintile}
          rowKey={(r) => r.quintile}
        />
        <div className="note">{conc.note}</div>
      </Panel>

      <Panel
        title="How regressive is this, against schemes that actually operate?"
        sub="The Suits index runs from +1 (perfectly progressive) to −1. Operating congestion
             charges cluster in a narrow band, which makes them a fair yardstick."
      >
        <BarChart
          data={[
            // Keyed on the scheme id, not the city: three of these rows are
            // "United States" and would collide.
            ...bench.comparisons.map((b) => ({
              label: b.scheme.replace(/_/g, ' ').replace(/^us /, 'US ')
                .replace(/\w/g, (c) => c.toUpperCase()).replace(/^US /, 'US '),
              value: b.suits_index, color: 'var(--seq-250)', full: b,
            })),
            { label: 'THIS MODEL', value: bench.model_suits_index,
              color: SERIES[1], full: { city: 'This model', note: bench.verdict, source: '' } },
          ].sort((a, b) => a.value - b.value)}
          diverging
          format={(v) => v.toFixed(3)}
          axisTitle="Suits index (negative = regressive)"
          tooltip={{ ...tip, render: (d) => (
            <TipBody title={d.full.city} rows={[
              ['Suits index', d.value.toFixed(3)],
              ...(d.full.source ? [['Source', d.full.source.slice(0, 60)]] : []),
            ]} />) }}
        />
        <Caveat><b>{bench.verdict}</b> {bench.note}</Caveat>
      </Panel>

      <Panel
        title="The STEPS equity framework"
        sub="Shaheen's five dimensions. Three are scored from model output; two are declared
             unmodelled, because a generalized-cost corridor model genuinely cannot see them
             and scoring them would imply coverage this study does not have."
      >
        <Table
          columns={[
            { label: 'Dimension', render: (s) => s.dimension },
            { label: 'Verdict', render: (s) => (
              <Badge kind={s.verdict.startsWith('reduces') ? 'pass'
                : s.verdict === 'not modelled' ? 'info' : 'warn'}>{s.verdict}</Badge>) },
            { label: 'What it covers', render: (s) =>
              <span style={{ whiteSpace: 'normal' }}>{s.definition}</span> },
            { label: 'Evidence', render: (s) =>
              <span style={{ whiteSpace: 'normal' }}>{s.evidence}</span> },
          ]}
          rows={inc.steps}
          rowKey={(s) => s.dimension}
          highlight={(s) => !s.modelled}
        />
      </Panel>

      <div className="grid-2">
        <Panel title="Modal equity"
               sub="FHWA's third equity type: does the scheme reward those who had already
                    stopped driving?">
          <dl className="kv">
            <dt>Transit riders gained</dt>
            <dd>{fmt.n(inc.modal_equity.transit_riders_gained)}</dd>
            <dt>Drivers retained</dt>
            <dd>{fmt.n(inc.modal_equity.drivers_retained)}</dd>
            <dt>Time saved, drivers</dt>
            <dd>{inc.modal_equity.time_saved_for_drivers_min.toFixed(1)} min</dd>
            <dt>Time saved, transit riders</dt>
            <dd>{inc.modal_equity.time_saved_for_transit_min.toFixed(1)} min</dd>
          </dl>
          <div className="note">{inc.modal_equity.note}</div>
        </Panel>

        <Panel title="Can everybody actually pay?"
               sub="An equity mechanism that lives in the payment system rather than the price.">
          <dl className="kv">
            <dt>Travellers who cannot hold a toll account</dt>
            <dd>{fmt.pct(inc.payment_access.share_of_travellers_exposed * 100, 1)}
              {' '}({fmt.n(inc.payment_access.travellers_exposed)} people)</dd>
            <dt>Assumed rate, lowest quintile</dt>
            <dd>{fmt.pct(inc.payment_access.assumed_rate_by_quintile.Q1 * 100, 0)}</dd>
            <dt>Assumed rate, highest quintile</dt>
            <dd>{fmt.pct(inc.payment_access.assumed_rate_by_quintile.Q5 * 100, 0)}</dd>
          </dl>
          <div className="note">{inc.payment_access.note}</div>
        </Panel>
      </div>

      <Panel
        title="Would it survive a vote?"
        sub="The third level of the game. A policy that maximises welfare and cannot be enacted
             is a proposal, not a policy — New York lost its federal funding in 2008 for exactly
             this reason."
      >
        <div className="grid" style={{ marginBottom: 16 }}>
          <Tile label="Support before it operates"
                value={fmt.pct(acc.before_operation.support_share * 100, 0)}
                tone={acc.before_operation.passes_referendum ? 'good' : 'bad'}
                note="A referendum held today, on a proposal" />
          <Tile label="Support once operating"
                value={fmt.pct(acc.after_operation.support_share * 100, 0)}
                tone={acc.after_operation.passes_referendum ? 'good' : 'bad'}
                note="Once the traffic effect is visible" />
          <Tile label="Experience gain" value={`+${acc.experience_gain_pp.toFixed(1)} pp`}
                note="The Stockholm shift" />
        </div>

        <GroupedBars
          categories={acc.before_operation.by_quintile.map((r) => r.quintile)}
          series={[
            { label: 'Before operating', color: SERIES[1],
              values: acc.before_operation.by_quintile.map((r) => 100 * r.support) },
            { label: 'After operating', color: SERIES[0],
              values: acc.after_operation.by_quintile.map((r) => 100 * r.support) },
          ]}
          yTitle="Predicted support (%)"
          format={(v) => `${v.toFixed(0)}%`}
          tooltip={{ ...tip, render: (cat, s, v) => (
            <TipBody title={`${cat} — ${s.label}`} rows={[['Support', fmt.pct(v, 1)]]} />) }}
        />
        <Legend items={[
          { label: 'Before operating', color: SERIES[1] },
          { label: 'After operating', color: SERIES[0] },
        ]} />

        <Caveat><b>{acc.verdict}</b> {acc.benchmark}</Caveat>
        <div className="note">
          Support is modelled from two things Eliasson separates: the traveller's own net
          position, and their view of whether pricing is a fair way to allocate road space at
          all — which rises with income, and is why congestion pricing is partly an elite
          project regardless of how the money is spent. {acc.before_operation.note}
        </div>
      </Panel>

      {rideHail.data && (
        <Panel
          title="Ride-hailing is a second player, not a passive one"
          sub="The operator chooses how much of the charge to pass to riders. London removed its
               ride-hail exemption; New York prices it separately and charges a shared trip less
               per rider."
        >
          <Table
            columns={[
              { label: 'Charge per trip', render: (r) => fmt.dollars(r.charge_per_trip) },
              { label: 'Passed to rider', render: (r) => fmt.pct(r.pass_through * 100, 0) },
              { label: 'Rider pays', render: (r) => fmt.dollars(r.rider_price_increase) },
              { label: 'Operator absorbs', render: (r) => fmt.dollars(r.operator_absorbs ?? 0) },
              { label: 'Trips', render: (r) => fmt.signed(r.trip_change_pct, 2) },
              { label: 'Empty repositioning trips', render: (r) => fmt.n(r.deadhead_vehicle_trips) },
            ]}
            rows={rideHail.data.response_curve}
            rowKey={(r, i) => i}
          />
          <div className="note">{rideHail.data.case.recommendation}</div>
          <Table
            columns={[
              { label: 'City', render: (p) => p.city },
              { label: 'What they did', render: (p) =>
                <span style={{ whiteSpace: 'normal' }}>{p.action}</span> },
              { label: 'Detail', render: (p) =>
                <span style={{ whiteSpace: 'normal' }}>{p.detail}</span> },
            ]}
            rows={rideHail.data.case.precedents}
            rowKey={(p) => p.city}
          />
        </Panel>
      )}

      <Panel title="Where this analysis comes from">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5,
                     color: 'var(--text-secondary)' }}>
          <li style={{ marginBottom: 5 }}>
            <b>Eliasson (2016), <i>Is Congestion Pricing Fair?</i></b> — ITF Discussion Paper
            2016-13. The four welfare components, the Suits index, the consumer/citizen
            distinction, and the warning that averages hide the harmed subgroup.
          </li>
          <li style={{ marginBottom: 5 }}>
            <b>FHWA, <i>Income-Based Equity Impacts of Congestion Pricing</i></b> — the three
            equity types (income, geographic, modal) and the toll-account access barrier.
          </li>
          <li style={{ marginBottom: 5 }}>
            <b>Greenlining Institute (2020), <i>An Equity-First Approach</i></b> — means-tested
            fees, revenue targeted at underinvested communities, and charging the ride-hail
            platform rather than the driver.
          </li>
          <li style={{ marginBottom: 5 }}>
            <b>Shaheen et al. (2019), UC Berkeley TSRC</b> — the STEPS framework.
          </li>
          <li>
            <b>SFCTA (2020) case studies and RPA (2019)</b> — London, Stockholm and New York
            outcomes, and the sequencing lesson: transit first, then the charge.
          </li>
        </ul>
      </Panel>

      {tip.node}
    </>
  )
}
