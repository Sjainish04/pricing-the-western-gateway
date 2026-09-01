import { useState } from 'react'

import { usePost, useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat, Finding } from '../components/ui.jsx'
import {
  BarChart, GroupedBars, LineChart, Legend, SERIES, fmt, nice, useTooltip, TipBody,
} from '../components/charts.jsx'

const CREDITS = ['none', 'low_income', 'low_income_transit_poor', 'shift_worker',
                 'hov_discount', 'monthly_cap', 'mobility_credit', 'targeted_package']

export default function Equity() {
  const [toll, setToll] = useState(5)
  const [credit, setCredit] = useState('targeted_package')
  const [coverage, setCoverage] = useState('screenline')

  const policy = {
    peak_toll: toll, coverage, credit,
    hov_discount: credit === 'hov_discount' ? 0.5 : 0, label: 'equity view',
  }
  const run = usePost('/api/simulate', policy)
  const plain = usePost('/api/simulate', { ...policy, credit: 'none', hov_discount: 0 })
  const segments = useApi('/api/data/segments')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the distributional analysis" />

  const e = run.data.equity
  const q = e.by_quintile
  const eNone = plain.data?.equity

  return (
    <>
      <div className="page-head">
        <h1>Who pays, and who has an alternative</h1>
        <p>
          Equity is treated as a design constraint and a simulation output, not a claim. The raw
          components come first — who pays, how much, as a share of income, with what alternative
          available — and only then are they folded into an index whose weights stay visible.
        </p>
      </div>

      <Panel title="Policy under examination">
        <div className="controls">
          <Field label="Peak charge" readout={fmt.dollars(toll, 2)}>
            <input type="range" min="0" max="15" step="0.5" value={toll}
                   onChange={(e2) => setToll(Number(e2.target.value))} />
          </Field>
          <Field label="Coverage">
            <select value={coverage} onChange={(e2) => setCoverage(e2.target.value)}>
              {['gardiner_only', 'screenline', 'city_roads_only'].map((c) =>
                <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
          <Field label="Credit mechanism">
            <select value={credit} onChange={(e2) => setCredit(e2.target.value)}>
              {CREDITS.map((c) => <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
        </div>
      </Panel>

      <div className="grid">
        <Tile label="Equity score" value={e.equity_score.toFixed(3)}
              tone={e.equity_score >= 0.55 ? 'good' : 'bad'}
              note={e.no_charge ? 'No charge in force' : 'Composite of three components'} />
        <Tile label="Suits index"
              value={`${e.components.suits_index >= 0 ? '+' : ''}${e.components.suits_index.toFixed(3)}`}
              tone={e.components.suits_index >= 0 ? 'good' : 'bad'}
              note={e.regressive ? 'Negative — regressive' : 'Positive — progressive in incidence'} />
        <Tile label="Q1 burden ÷ Q5 burden" value={`${e.burden_ratio_q1_q5.toFixed(2)}×`}
              tone={e.burden_ratio_q1_q5 > 2 ? 'bad' : 'good'}
              note="Charge as a share of household income" />
        <Tile label="Paid by travellers with no transit option"
              value={fmt.pct(e.components.transit_access_gap * 100)}
              tone={e.components.transit_access_gap > 0.3 ? 'bad' : 'good'}
              note="Transit accessibility score below 0.50" />
      </div>

      <Panel
        title="Two measures of fairness that disagree"
        sub="Both are correct, and reporting only one would be misleading."
      >
        <div className="grid-2">
          <div>
            <Legend items={[{ label: 'Net charge per trip', color: SERIES[0] }]} />
            <BarChart
              data={q.map((r) => ({ label: `${r.quintile} · ${fmt.money(r.household_income)}`,
                                    value: r.net_toll_per_trip, full: r }))}
              format={(v) => `$${v.toFixed(2)}`}
              axisTitle="Net charge paid per trip ($)"
              tooltip={{
                ...tip,
                render: (d) => (
                  <TipBody title={`${d.full.quintile} — ${fmt.money(d.full.household_income)}`} rows={[
                    ['Gross charge', fmt.dollars(d.full.gross_toll_per_trip)],
                    ['Credit received', fmt.dollars(d.full.credit_per_trip)],
                    ['Net charge', fmt.dollars(d.full.net_toll_per_trip)],
                    ['Annual', fmt.money(d.full.net_annual_toll)],
                  ]} />
                ),
              }}
            />
            <div className="note">
              In absolute dollars the charge falls mainly on higher-income travellers, because they
              drive more. That is what makes the Suits index{' '}
              {e.components.suits_index >= 0 ? 'positive' : 'negative'}.
            </div>
          </div>
          <div>
            <Legend items={[{ label: 'Burden as % of income', color: SERIES[1] }]} />
            <BarChart
              data={q.map((r) => ({ label: r.quintile, value: r.burden_pct_income, full: r }))}
              color={SERIES[1]}
              format={(v) => `${v.toFixed(3)}%`}
              axisTitle="Annual charge as a share of household income"
              tooltip={{
                ...tip,
                render: (d) => (
                  <TipBody title={d.full.quintile} rows={[
                    ['Annual charge', fmt.money(d.full.net_annual_toll)],
                    ['Household income', fmt.money(d.full.household_income)],
                    ['Burden', fmt.pct(d.full.burden_pct_income, 4)],
                  ]} />
                ),
              }}
            />
            <div className="note">
              Relative to income the same charge lands {e.burden_ratio_q1_q5.toFixed(1)} times
              harder on the lowest quintile. This is the measure that matters for whether a
              household can absorb the cost.
            </div>
          </div>
        </div>
      </Panel>

      {e.suits_curve?.length > 0 && (() => {
        const worst = e.suits_curve.reduce((a, r) => (r.gap > a.gap ? r : a))
        return (
          <Panel
            title="The curve behind the Suits index"
            sub="The index is one number standing for a whole curve — and two schemes with the same index can hurt different people"
          >
            <LineChart
              series={[
                { label: 'Charge paid', color: SERIES[1],
                  data: e.suits_curve.map((r) => ({ x: r.cumulative_income_share, y: r.cumulative_charge_share })) },
                { label: 'Proportional (charge tracks income)', color: SERIES[0],
                  data: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
              ]}
              xTitle="Cumulative share of income, poorest to richest"
              yTitle="Cumulative share of the charge paid"
              format={(v) => fmt.pct(100 * v, 0)}
              xFormat={(v) => fmt.pct(100 * v, 0)}
              markers={false}
              tooltip={tip}
            />
            <Legend items={[
              { label: 'Charge paid', color: SERIES[1] },
              { label: 'Proportional', color: SERIES[0] },
            ]} />
            <Finding kicker="What the number hides"
                     tone={e.components.suits_index < 0 ? 'bad' : 'good'}
                     lede={`The charge bites hardest around the ${fmt.pct(100 * worst.cumulative_income_share, 0)} mark: those travellers hold ${fmt.pct(100 * worst.cumulative_income_share, 0)} of the corridor's income and pay ${fmt.pct(100 * worst.cumulative_charge_share, 0)} of its charge.`}>
              <p className="aside">
                Above the diagonal is the regressive direction. The Suits index is twice the area
                between the two lines, so it can only say <i>how much</i> — not <i>where</i>. Here
                the widest gap falls below the top quintile rather than at the very bottom,
                which the credits reach first. A design tuned only on the bottom quintile would
                leave this untouched and still report an improved index. One point per income
                quintile, joined by chords &mdash; the curve cannot be read finer than the income
                data behind it.
              </p>
            </Finding>
          </Panel>
        )
      })()}

      <Panel
        title="The full distributional table"
        sub="Time savings are counted only for travellers who still drive, since somebody priced
             onto a train does not collect the road's travel-time gain."
      >
        <Table
          columns={[
            { label: 'Quintile', render: (r) => r.quintile },
            { label: 'Household income', render: (r) => fmt.money(r.household_income) },
            { label: 'Value of time', render: (r) => `$${r.value_of_time_hourly.toFixed(2)}/h` },
            { label: 'Share of travellers', render: (r) => fmt.pct(r.share_of_travellers * 100) },
            { label: 'Gross charge', render: (r) => fmt.dollars(r.gross_toll_per_trip) },
            { label: 'Credit', render: (r) => fmt.dollars(r.credit_per_trip) },
            { label: 'Net / trip', render: (r) => fmt.dollars(r.net_toll_per_trip) },
            { label: 'Net / year', render: (r) => fmt.money(r.net_annual_toll) },
            { label: '% of income', render: (r) => fmt.pct(r.burden_pct_income, 3) },
            { label: 'Time saved', render: (r) => `${r.time_saved_min.toFixed(2)} min` },
            { label: 'Transit shift', render: (r) => `${r.transit_shift_pp >= 0 ? '+' : ''}${r.transit_shift_pp.toFixed(2)} pp` },
            { label: 'No alternative', render: (r) => fmt.pct(r.no_transit_alternative * 100, 0) },
          ]}
          rows={q}
          rowKey={(r) => r.quintile}
        />
      </Panel>

      <Panel
        title="Does the credit actually change anything?"
        sub="The selected mechanism against the same charge with no credit at all."
      >
        {plain.loading || !eNone ? <Loading what="the no-credit comparison" /> : (
          <>
            <GroupedBars
              categories={q.map((r) => r.quintile)}
              series={[
                { label: 'No credit', color: SERIES[1],
                  values: eNone.by_quintile.map((r) => r.burden_pct_income) },
                { label: nice(credit), color: SERIES[0],
                  values: q.map((r) => r.burden_pct_income) },
              ]}
              yTitle="Burden as % of household income"
              format={(v) => v.toFixed(3)}
              tooltip={{
                ...tip,
                render: (cat, s, v) => (
                  <TipBody title={`${cat} — ${s.label}`} rows={[['Burden', fmt.pct(v, 4)]]} />
                ),
              }}
            />
            <Legend items={[
              { label: 'No credit', color: SERIES[1] },
              { label: nice(credit), color: SERIES[0] },
            ]} />
            <Table
              columns={[
                { label: 'Measure', render: (r) => r[0] },
                { label: 'No credit', render: (r) => r[1] },
                { label: nice(credit), render: (r) => r[2] },
              ]}
              rows={[
                ['Equity score', eNone.equity_score.toFixed(3), e.equity_score.toFixed(3)],
                ['Suits index', eNone.components.suits_index.toFixed(3),
                 e.components.suits_index.toFixed(3)],
                ['Q1 ÷ Q5 burden', `${eNone.burden_ratio_q1_q5.toFixed(2)}×`,
                 `${e.burden_ratio_q1_q5.toFixed(2)}×`],
                ['Delay removed', fmt.pct(plain.data.metrics.delay_reduction_pct),
                 fmt.pct(run.data.metrics.delay_reduction_pct)],
                ['Net revenue', fmt.money(plain.data.finance.net_revenue_annual),
                 fmt.money(run.data.finance.net_revenue_annual)],
              ]}
              rowKey={(r) => r[0]}
            />
            <Caveat>
              <b>Credits buy fairness with congestion relief and revenue.</b> Rebating the charge
              to the people most likely to be priced off necessarily weakens the behavioural
              signal, and it costs money that would otherwise fund transit. That trade-off is why
              the proposal prefers targeted credits over broad exemptions, and why the model
              reports delay and revenue alongside every equity number rather than after them.
            </Caveat>
          </>
        )}
      </Panel>

      <Panel
        title="Where the charge lands geographically"
        sub="Compares each sub-area's share of the charge with its share of trips. A charge share
             above the trip share means that community carries more than its travel would imply."
      >
        <BarChart
          data={e.by_subarea.map((s) => ({
            label: s.subarea,
            value: (s.charge_share - s.trip_share) * 100,
            full: s,
          })).sort((a, b) => b.value - a.value)}
          diverging
          format={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
          axisTitle="Charge share minus trip share (percentage points)"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.full.subarea} rows={[
                ['Share of trips', fmt.pct(d.full.trip_share * 100, 2)],
                ['Share of charge', fmt.pct(d.full.charge_share * 100, 2)],
                ['Net charge per trip', fmt.dollars(d.full.net_toll_per_trip)],
                ['Burden % of income', fmt.pct(d.full.burden_pct_income, 4)],
                ['Transit access score', d.full.transit_access.toFixed(2)],
              ]} />
            ),
          }}
        />
        <div className="note">
          Spatial concentration index: {e.components.spatial_concentration.toFixed(4)} — the share
          of the charge that would have to be redistributed for it to fall exactly in proportion
          to travel.
        </div>
      </Panel>

      <Panel
        title="The index, and its weights"
        sub="Built only after the components are visible, and the weights are exposed rather than
             embedded."
      >
        <Table
          columns={[
            { label: 'Component', render: (r) => r[0] },
            { label: 'Value', render: (r) => r[1] },
            { label: 'Weight', render: (r) => r[2] },
            { label: 'Contribution', render: (r) => r[3] },
          ]}
          rows={[
            ['Burden inequality (from Suits)', e.components.burden_inequality.toFixed(4),
             e.weights.burden, (e.components.burden_inequality * e.weights.burden).toFixed(4)],
            ['Transit access gap', e.components.transit_access_gap.toFixed(4),
             e.weights.access, (e.components.transit_access_gap * e.weights.access).toFixed(4)],
            ['Spatial concentration', e.components.spatial_concentration.toFixed(4),
             e.weights.spatial, (e.components.spatial_concentration * e.weights.spatial).toFixed(4)],
          ]}
          rowKey={(r) => r[0]}
        />
        <div className="note">
          Equity score = 1 − (weighted sum of penalties) = {e.equity_score.toFixed(4)}. The
          weights are tested in the sensitivity analysis; they are a judgement, not a measurement.
        </div>
      </Panel>

      {segments.data && (
        <Panel
          title="Traveller segmentation"
          sub="70 segments: seven sub-areas × five income quintiles × fixed or flexible schedule.
               Transit accessibility is attached to the sub-area, because whether Lakeshore West GO
               is a realistic option is a fact about where somebody lives."
        >
          <Table
            columns={[
              { label: 'Quintile', render: (r) => r[0] },
              { label: 'Value of time', render: (r) => `$${r[1].toFixed(2)}/h` },
            ]}
            rows={Object.entries(segments.data.value_of_time_by_quintile)}
            rowKey={(r) => r[0]}
          />
          <Caveat>
            <b>The value-of-time floor matters more than it looks.</b> Scaling the value of time
            with income is standard, but taken literally it implies delay to a low-income
            traveller is nearly free — which would quietly bias every equity result in this study.
            A floor of $9.50 an hour is applied to prevent that artefact.
          </Caveat>
        </Panel>
      )}

      {tip.node}
    </>
  )
}
