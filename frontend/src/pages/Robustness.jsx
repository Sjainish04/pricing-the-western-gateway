import { useState } from 'react'

import { useApi, usePost } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat } from '../components/ui.jsx'
import { Tornado, BarChart, SERIES, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'

const OUTCOMES = [
  ['delay_reduction_pct', 'Delay removed (%)', (v) => `${v.toFixed(1)}%`],
  ['peak_vehicle_change_pct', 'Vehicle change (%)', (v) => `${v.toFixed(1)}%`],
  ['net_revenue_annual', 'Net revenue', (v) => fmt.money(v)],
  ['equity_score', 'Equity score', (v) => v.toFixed(3)],
  ['worst_diversion_pct', 'Worst local increase (%)', (v) => `${v.toFixed(1)}%`],
]

export default function Robustness() {
  const [outcome, setOutcome] = useState('delay_reduction_pct')
  const tornado = usePost('/api/sensitivity/tornado', {
    peak_toll: 5, coverage: 'screenline', credit: 'targeted_package', label: 'central',
  })
  const mc = useApi('/api/sensitivity/monte-carlo?draws=100')
  const tip = useTooltip()

  const meta = OUTCOMES.find((o) => o[0] === outcome)
  const fmtOut = meta[2]

  return (
    <>
      <div className="page-head">
        <h1>How much of this is the data, and how much is the guesses?</h1>
        <p>
          Two complementary tests. One moves a single assumption at a time, to say which
          assumptions matter. The other moves all of them at once, to say whether the
          recommendation survives — which is the question a reviewer actually cares about.
        </p>
      </div>

      <Panel
        title="One assumption at a time"
        sub="Central case: a $5 screenline charge with the targeted credit package. Bar length is
             the outcome swing produced by moving that one parameter across its plausible range."
        right={
          <Field label="Outcome">
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              {OUTCOMES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </Field>
        }
      >
        {tornado.loading && !tornado.data ? (
          <Loading what="the tornado analysis (28 model runs)" />
        ) : tornado.error ? <ErrorBox error={tornado.error} /> : (
          <>
            <Tornado
              rows={tornado.data.parameters.map((p) => ({
                parameter: p.parameter,
                low: p.effects[outcome].low,
                high: p.effects[outcome].high,
              })).sort((a, b) => Math.abs(b.high - b.low) - Math.abs(a.high - a.low))}
              centralValue={tornado.data.central[outcome]}
              format={fmtOut}
            />
            <Table
              columns={[
                { label: 'Parameter', render: (p) => p.parameter },
                { label: 'Range', render: (p) => `±${p.spread_pct}%` },
                { label: 'Low', render: (p) => fmtOut(p.effects[outcome].low) },
                { label: 'Central', render: (p) => fmtOut(p.effects[outcome].central) },
                { label: 'High', render: (p) => fmtOut(p.effects[outcome].high) },
                { label: 'Swing', render: (p) => fmtOut(p.effects[outcome].swing) },
                { label: 'Why uncertain', render: (p) =>
                  <span style={{ whiteSpace: 'normal' }}>{p.reason}</span> },
              ]}
              rows={tornado.data.parameters
                .slice()
                .sort((a, b) => b.effects[outcome].swing - a.effects[outcome].swing)}
              rowKey={(p) => p.parameter}
            />
          </>
        )}
      </Panel>

      <Panel
        title="Everything uncertain at once"
        sub="Latin hypercube sampling over fourteen parameters, so each range is covered evenly with
             far fewer draws than random sampling would need. Win probability is the share of draws
             in which a policy has the highest welfare among those still satisfying every
             constraint in that draw."
      >
        {mc.loading ? (
          <Loading what="the Monte Carlo analysis (this runs several hundred equilibria)" />
        ) : mc.error ? <ErrorBox error={mc.error} /> : (
          <>
            <div className="grid" style={{ marginBottom: 16 }}>
              <Tile label="Draws" value={fmt.n(mc.data.draws)} note="Latin hypercube" />
              <Tile label="Most robust policy" value={mc.data.most_robust}
                    note={`Wins ${fmt.pct((mc.data.policies[0]?.win_probability ?? 0) * 100)} of draws`} />
              <Tile label="Parameters varied" value={Object.keys(mc.data.parameters).length}
                    note="Every ESTIMATED input plus the behavioural parameters" />
            </div>

            <BarChart
              data={mc.data.policies.map((p, i) => ({
                label: p.label, value: p.win_probability * 100,
                color: i === 0 ? SERIES[0] : 'var(--seq-250)', full: p,
              }))}
              format={(v) => `${v.toFixed(1)}%`}
              axisTitle="Probability of being the best feasible policy"
              tooltip={{
                ...tip,
                render: (d) => (
                  <TipBody title={d.full.label} rows={[
                    ['Wins', fmt.pct(d.full.win_probability * 100)],
                    ['Feasible in', fmt.pct(d.full.feasible_probability * 100)],
                    ['Delay removed, median', fmt.pct(d.full.delay_reduction_pct.p50)],
                    ['Net revenue, median', fmt.money(d.full.net_revenue_annual.p50)],
                  ]} />
                ),
              }}
            />

            <Table
              columns={[
                { label: 'Policy', render: (p) => p.label },
                { label: 'P(best)', render: (p) => fmt.pct(p.win_probability * 100) },
                { label: 'P(feasible)', render: (p) => fmt.pct(p.feasible_probability * 100) },
                { label: 'Delay ↓ (5th–95th)', render: (p) =>
                  `${p.delay_reduction_pct.p05.toFixed(1)} – ${p.delay_reduction_pct.p95.toFixed(1)}%` },
                { label: 'Delay ↓ median', render: (p) => fmt.pct(p.delay_reduction_pct.p50) },
                { label: 'Net revenue median', render: (p) => fmt.money(p.net_revenue_annual.p50) },
                { label: 'Equity median', render: (p) => p.equity_score.p50.toFixed(3) },
                { label: 'Worst local ↑ median', render: (p) => fmt.signed(p.worst_diversion_pct.p50) },
              ]}
              rows={mc.data.policies}
              rowKey={(p) => p.label}
              highlight={(p) => p.label === mc.data.most_robust}
            />
            <div className="note">{mc.data.note}</div>

            <Caveat>
              <b>Read the feasibility column before the win column.</b> A policy can post the
              highest median delay reduction and still be the wrong recommendation if it only
              satisfies the diversion and equity constraints in a minority of draws. Robustness
              here means surviving the uncertainty, not winning the central case.
            </Caveat>
          </>
        )}
      </Panel>

      {mc.data && (
        <Panel
          title="What was varied, and why it is uncertain"
          sub="Each parameter's range is a judgement about how little we know, stated explicitly
               rather than left implicit in a point estimate."
        >
          <Table
            columns={[
              { label: 'Parameter', render: (r) => r[0] },
              { label: 'Range', render: (r) => `±${r[1].spread_pct}%` },
              { label: 'Why uncertain', render: (r) =>
                <span style={{ whiteSpace: 'normal' }}>{r[1].reason}</span> },
            ]}
            rows={Object.entries(mc.data.parameters)}
            rowKey={(r) => r[0]}
          />
        </Panel>
      )}

      {tip.node}
    </>
  )
}
