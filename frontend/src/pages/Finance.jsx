import { useState } from 'react'

import { usePost } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat } from '../components/ui.jsx'
import {
  BarChart, GroupedBars, Legend, SERIES, fmt, nice, useTooltip, TipBody,
} from '../components/charts.jsx'

export default function Finance() {
  const [toll, setToll] = useState(5)
  const [coverage, setCoverage] = useState('screenline')
  const [credit, setCredit] = useState('targeted_package')
  const [costCase, setCostCase] = useState('medium')

  const policy = {
    peak_toll: toll, coverage, credit,
    hov_discount: credit === 'hov_discount' ? 0.5 : 0,
    label: 'finance view',
    config: { admin_cost_scenario: costCase },
  }
  const run = usePost('/api/simulate', policy)
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the revenue model" />

  const f = run.data.finance
  const cases = f.cost_cases
  const recycle = run.data.revenue_recycling ?? []
  const benefit = run.data.equity.recycling ?? []

  return (
    <>
      <div className="page-head">
        <h1>Does the charge pay for itself, and where does the money go?</h1>
        <p>
          Collection costs at proposal stage are genuinely uncertain, so nothing here is a single
          point estimate. Every figure is produced under a low, medium and high cost case, and the
          headline always carries the other two alongside it.
        </p>
      </div>

      <Panel title="Policy and cost case">
        <div className="controls">
          <Field label="Peak charge" readout={fmt.dollars(toll, 2)}>
            <input type="range" min="0" max="20" step="0.5" value={toll}
                   onChange={(e) => setToll(Number(e.target.value))} />
          </Field>
          <Field label="Coverage">
            <select value={coverage} onChange={(e) => setCoverage(e.target.value)}>
              {['gardiner_only', 'screenline', 'city_roads_only'].map((c) =>
                <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
          <Field label="Credit mechanism">
            <select value={credit} onChange={(e) => setCredit(e.target.value)}>
              {['none', 'low_income', 'low_income_transit_poor', 'shift_worker', 'hov_discount',
                'monthly_cap', 'mobility_credit', 'targeted_package'].map((c) =>
                <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
          <Field label="Administrative cost case">
            <select value={costCase} onChange={(e) => setCostCase(e.target.value)}>
              <option value="low">Low — efficient electronic system</option>
              <option value="medium">Medium — central case</option>
              <option value="high">High — conservative</option>
            </select>
          </Field>
        </div>
      </Panel>

      <div className="grid">
        <Tile label="Gross revenue" value={fmt.money(f.gross_revenue_annual)} note="Per year" />
        <Tile label="Credits paid out" value={fmt.money(f.credits_annual)} note="Per year" />
        <Tile label="Net revenue" value={fmt.money(f.net_revenue_annual)}
              tone={f.net_revenue_annual > 0 ? 'good' : 'bad'}
              note={f.net_positive ? 'Funds transit investment' : 'Does not cover its own costs'} />
        <Tile label="Charged transactions" value={fmt.n(f.charged_vehicles_annual)}
              note="Per year" />
        <Tile label="Average charge collected"
              value={fmt.dollars(f.average_charge_per_vehicle)}
              note="Per charged vehicle, after window coverage" />
        <Tile label="Revenue per vehicle removed"
              value={f.revenue_per_vehicle_removed ? fmt.dollars(f.revenue_per_vehicle_removed) : '—'}
              note="Net revenue ÷ vehicles taken off the peak" />
        <Tile label="Revenue per delay-hour saved"
              value={f.revenue_per_delay_hour_saved ? fmt.dollars(f.revenue_per_delay_hour_saved) : '—'}
              note="Net revenue ÷ vehicle-hours of delay removed" />
        <Tile label="Cost ratio" value={fmt.pct((cases[costCase]?.cost_ratio ?? 0) * 100)}
              tone={(cases[costCase]?.cost_ratio ?? 0) < 0.4 ? 'good' : 'bad'}
              note="Collection cost as a share of gross revenue" />
      </div>

      <Panel
        title="Net revenue under all three cost cases"
        sub="A single net-revenue figure would hide the fact that the sign of the answer can change
             with an assumption nobody can pin down before the scheme operates."
      >
        <GroupedBars
          categories={['Low cost', 'Medium cost', 'High cost']}
          series={[
            { label: 'Gross revenue', color: SERIES[2],
              values: ['low', 'medium', 'high'].map(() => f.gross_revenue_annual / 1e6) },
            { label: 'Total costs', color: SERIES[1],
              values: ['low', 'medium', 'high'].map((c) =>
                (cases[c].admin_cost + cases[c].fixed_cost + cases[c].enforcement_cost
                  + cases[c].credits) / 1e6) },
            { label: 'Net revenue', color: SERIES[0],
              values: ['low', 'medium', 'high'].map((c) => cases[c].net_revenue / 1e6) },
          ]}
          yTitle="$ million per year"
          format={(v) => v.toFixed(0)}
          tooltip={{
            ...tip,
            render: (cat, s, v) => (
              <TipBody title={`${cat} — ${s.label}`} rows={[['Amount', fmt.money(v * 1e6)]]} />
            ),
          }}
        />
        <Legend items={[
          { label: 'Gross revenue', color: SERIES[2] },
          { label: 'Total costs', color: SERIES[1] },
          { label: 'Net revenue', color: SERIES[0] },
        ]} />
        <Table
          columns={[
            { label: 'Cost case', render: (r) => r[0] },
            { label: 'Admin', render: (r) => fmt.money(r[1].admin_cost) },
            { label: 'Fixed', render: (r) => fmt.money(r[1].fixed_cost) },
            { label: 'Enforcement', render: (r) => fmt.money(r[1].enforcement_cost) },
            { label: 'Credits', render: (r) => fmt.money(r[1].credits) },
            { label: 'Net revenue', render: (r) => fmt.money(r[1].net_revenue) },
            { label: 'Cost ratio', render: (r) => fmt.pct(r[1].cost_ratio * 100) },
            { label: 'Positive?', render: (r) => <Badge ok={r[1].net_revenue > 0} /> },
          ]}
          rows={[['Low', cases.low], ['Medium', cases.medium], ['High', cases.high]]}
          rowKey={(r) => r[0]}
          highlight={(r) => r[0].toLowerCase() === costCase}
        />
        <Caveat>
          <b>A single-corridor gateway charge is financially marginal at low prices.</b> Fixed
          operating costs do not scale down with the size of the scheme, so at modest charges the
          system can spend more collecting the money than it raises — particularly once credits are
          paid. That is a genuine finding about pilot economics, not a modelling artefact, and it
          is one of the strongest arguments for pairing the charge with a wider scheme or a
          City-controlled instrument with lower collection overhead.
        </Caveat>
      </Panel>

      {f.net_revenue_annual > 0 && recycle.length > 0 && (
        <Panel
          title="Where net revenue would go"
          sub="The proposal commits to spending the money where the charge is felt: station access
               and first/last mile first, then bus priority and traffic management, then direct
               mobility credits."
        >
          <BarChart
            data={recycle.map((r) => ({ label: r.programme, value: r.annual_amount, full: r }))}
            format={(v) => fmt.money(v)}
            axisTitle="Annual allocation"
            tooltip={{
              ...tip,
              render: (d) => (
                <TipBody title={d.full.programme} rows={[
                  ['Share', fmt.pct(d.full.share * 100, 0)],
                  ['Annual', fmt.money(d.full.annual_amount)],
                ]} />
              ),
            }}
          />
          <Table
            columns={[
              { label: 'Programme', render: (r) => r.programme },
              { label: 'Share', render: (r) => fmt.pct(r.share * 100, 0) },
              { label: 'Annual amount', render: (r) => fmt.money(r.annual_amount) },
              { label: 'Detail', render: (r) =>
                <span style={{ whiteSpace: 'normal' }}>{r.note}</span> },
            ]}
            rows={recycle}
            rowKey={(r) => r.programme}
          />
        </Panel>
      )}

      <Panel
        title="Who benefits from the reinvestment"
        sub="Benefit is allocated to sub-areas in proportion to transit ridership and inversely to
             current access quality, since station access and first/last mile improvements are
             worth most where access is currently worst."
      >
        <BarChart
          data={benefit.map((b) => ({ label: b.subarea, value: b.annual_benefit, full: b }))}
          color={SERIES[2]}
          format={(v) => fmt.money(v)}
          axisTitle="Annual benefit from recycled revenue"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.full.subarea} rows={[
                ['Benefit share', fmt.pct(d.full.benefit_share * 100, 1)],
                ['Annual benefit', fmt.money(d.full.annual_benefit)],
                ['Transit access score', d.full.transit_access.toFixed(2)],
              ]} />
            ),
          }}
        />
        <div className="note">
          Sub-areas with the weakest current transit access receive the largest share, which is the
          mechanism by which recycling is meant to offset the charge for the travellers with the
          fewest alternatives. Whether it does so in practice depends on delivery, which no model
          can assert.
        </div>
      </Panel>

      <Panel title="Break-even">
        <dl className="kv">
          <dt>Break-even cost ratio</dt>
          <dd>
            {fmt.pct(f.break_even_admin_ratio * 100, 2)} — the share of gross revenue that can be
            absorbed by collection, enforcement and credits before net revenue reaches zero.
          </dd>
          <dt>Actual cost ratio, {costCase} case</dt>
          <dd>{fmt.pct((cases[costCase]?.cost_ratio ?? 0) * 100, 2)}</dd>
          <dt>Verdict</dt>
          <dd>
            <Badge ok={f.net_positive}>
              {f.net_positive ? 'Covers its costs and funds investment'
                : 'Does not cover its own collection costs'}
            </Badge>
          </dd>
        </dl>
      </Panel>

      {tip.node}
    </>
  )
}
