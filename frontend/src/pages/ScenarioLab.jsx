import { useState } from 'react'

import { useApi, usePost } from '../lib/api.js'
import {
  Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Constraints, Caveat,
} from '../components/ui.jsx'
import {
  BarChart, FlowDiagram, Legend, SERIES, fmt, nice, useTooltip, TipBody,
} from '../components/charts.jsx'

const COVERAGES = ['gardiner_only', 'screenline', 'city_roads_only']
const CREDITS = ['none', 'low_income', 'low_income_transit_poor', 'shift_worker',
                 'hov_discount', 'monthly_cap', 'mobility_credit', 'targeted_package']
const WINDOWS = ['0630_0930', '0700_1000', '0630_1000', '0700_0900', 'peak_plus_shoulder']

export default function ScenarioLab() {
  const [policy, setPolicy] = useState({
    peak_toll: 5, shoulder_toll: 0, window: '0630_0930', coverage: 'screenline',
    credit: 'targeted_package', hov_discount: 0, parking_surcharge: 0,
    adaptive_signals: false, ramp_metering: false, transit_priority: false,
    go_frequency_uplift: 0, label: 'custom',
  })
  const run = usePost('/api/simulate', policy)
  const library = useApi('/api/scenarios')
  const compare = useApi('/api/scenarios/compare')
  const tip = useTooltip()

  const set = (patch) => setPolicy((p) => ({ ...p, ...patch }))
  const loadPreset = (s) => set({
    peak_toll: s.peak_toll, coverage: s.coverage, credit: s.credit,
    window: s.window, label: s.id,
    hov_discount: s.credit === 'hov_discount' ? 0.5 : 0,
  })

  const r = run.data
  const m = r?.metrics
  const div = m ? Object.values(m.diversion) : []

  return (
    <>
      <div className="page-head">
        <h1>Scenario lab</h1>
        <p>
          Set a policy and the model re-solves the corridor equilibrium. Every alternative — route,
          mode, departure time, vehicle occupancy and whether to travel at all — adjusts together
          until flows stop moving.
        </p>
      </div>

      <Panel title="Policy" sub="The leader's instrument set.">
        <div className="controls">
          <Field label="Peak charge" readout={fmt.dollars(policy.peak_toll, 2)}>
            <input type="range" min="0" max="20" step="0.5" value={policy.peak_toll}
                   onChange={(e) => set({ peak_toll: Number(e.target.value) })} />
          </Field>
          <Field label="Shoulder charge" readout={fmt.dollars(policy.shoulder_toll, 2)}>
            <input type="range" min="0" max="10" step="0.5" value={policy.shoulder_toll}
                   onChange={(e) => set({ shoulder_toll: Number(e.target.value) })} />
          </Field>
          <Field label="Coverage">
            <select value={policy.coverage} onChange={(e) => set({ coverage: e.target.value })}>
              {COVERAGES.map((c) => <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
          <Field label="Charging window">
            <select value={policy.window} onChange={(e) => set({ window: e.target.value })}>
              {WINDOWS.map((w) => <option key={w} value={w}>{nice(w)}</option>)}
            </select>
          </Field>
          <Field label="Credit mechanism">
            <select value={policy.credit}
                    onChange={(e) => set({
                      credit: e.target.value,
                      hov_discount: e.target.value === 'hov_discount' ? 0.5 : policy.hov_discount,
                    })}>
              {CREDITS.map((c) => <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
          <Field label="HOV discount" readout={fmt.pct(policy.hov_discount * 100, 0)}>
            <input type="range" min="0" max="1" step="0.05" value={policy.hov_discount}
                   onChange={(e) => set({ hov_discount: Number(e.target.value) })} />
          </Field>
          <Field label="Parking surcharge" readout={fmt.dollars(policy.parking_surcharge, 2)}>
            <input type="range" min="0" max="20" step="1" value={policy.parking_surcharge}
                   onChange={(e) => set({ parking_surcharge: Number(e.target.value) })} />
          </Field>
          <Field label="GO frequency uplift" readout={fmt.pct(policy.go_frequency_uplift * 100, 0)}>
            <input type="range" min="0" max="0.5" step="0.05" value={policy.go_frequency_uplift}
                   onChange={(e) => set({ go_frequency_uplift: Number(e.target.value) })} />
          </Field>
        </div>
        <div className="controls" style={{ marginTop: 12 }}>
          {[['adaptive_signals', 'Adaptive signals'],
            ['ramp_metering', 'Ramp metering'],
            ['transit_priority', 'Transit priority']].map(([key, label]) => (
            <label className="check" key={key}>
              <input type="checkbox" checked={policy[key]}
                     onChange={(e) => set({ [key]: e.target.checked })} />
              {label}
            </label>
          ))}
        </div>
        {library.data && (
          <div className="pill-row" style={{ marginTop: 14 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', alignSelf: 'center',
                           marginRight: 4 }}>Presets:</span>
            {library.data.scenarios.map((s) => (
              <button key={s.id} className={`pill${policy.label === s.id ? ' on' : ''}`}
                      title={s.description} onClick={() => loadPreset(s)}>
                {s.label}
              </button>
            ))}
          </div>
        )}
      </Panel>

      {run.error && <ErrorBox error={run.error} />}
      {run.loading && !r && <Loading what="this policy" />}

      {r && (
        <>
          <div className="grid">
            <Tile label="Peak vehicles, charged segment" value={fmt.n(m.peak_entering_vehicles)}
                  tone={m.peak_vehicle_change_pct < 0 ? 'good' : undefined}
                  note={`${fmt.signed(m.peak_vehicle_change_pct)} vs baseline`} />
            <Tile label="Delay removed" value={fmt.pct(m.delay_reduction_pct)}
                  tone={m.delay_reduction_pct > 0 ? 'good' : 'bad'}
                  note={`${fmt.n(r.delay_hours_saved_peak)} vehicle-hours per peak`} />
            <Tile label="Travel time saved" value={`${m.travel_time_saved_min.toFixed(1)} min`}
                  tone={m.travel_time_saved_min > 0 ? 'good' : undefined}
                  note={`Gardiner route now ${m.gardiner_travel_time_min.toFixed(1)} min`} />
            <Tile label="Worst local increase" value={fmt.signed(m.worst_diversion_pct)}
                  tone={m.worst_diversion_pct > 10 ? 'bad' : 'good'}
                  note={m.worst_diversion_link ?? '—'} />
            <Tile label="Transit shift" value={`${m.transit_share_change_pp >= 0 ? '+' : ''}${m.transit_share_change_pp.toFixed(2)} pp`}
                  note={`GO at ${fmt.pct(m.go_load_factor * 100, 0)} of capacity`} />
            <Tile label="Net revenue" value={fmt.money(r.finance.net_revenue_annual)}
                  tone={r.finance.net_revenue_annual > 0 ? 'good' : 'bad'}
                  note={`${r.finance.cost_case_used} cost case, per year`} />
            <Tile label="Equity score" value={r.equity.equity_score.toFixed(3)}
                  tone={r.equity.equity_score >= 0.55 ? 'good' : 'bad'}
                  note={`Suits index ${r.equity.components.suits_index >= 0 ? '+' : ''}${r.equity.components.suits_index.toFixed(3)}`} />
            <Tile label="CO₂e change" value={fmt.signed(m.co2e_change_pct, 2)}
                  tone={m.co2e_change_pct < 0 ? 'good' : 'bad'} note="Transparent proxy, not an inventory" />
          </div>

          <Panel title="Does this policy satisfy the constraints?"
                 sub="A policy that fails any of these is excluded from the recommendation,
                      however well it scores on welfare.">
            <Constraints feasible={r.feasible} />
          </Panel>

          <div className="grid-2">
            <Panel title="Where the priced-off trips went"
                   sub="Net change attributed across the alternatives that grew. An aggregate model
                        tracks shares, not individuals, so this is an attribution rather than a
                        claim about who moved where.">
              <FlowDiagram total={r.sankey.total} flows={r.sankey.flows} />
            </Panel>

            <Panel title="Change in mode and route share"
                   sub="Percentage points relative to the calibrated baseline.">
              <BarChart
                data={Object.entries(m.mode_share_change)
                  .map(([k, v]) => ({ label: nice(k), value: v * 100 }))
                  .sort((a, b) => b.value - a.value)}
                diverging
                format={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
                axisTitle="Change in share (percentage points)"
                tooltip={{
                  ...tip,
                  render: (d) => <TipBody title={d.label} rows={[['Change', `${d.value >= 0 ? '+' : ''}${d.value.toFixed(3)} pp`]]} />,
                }}
              />
            </Panel>
          </div>

          <Panel
            title="Effect on the protected local corridors"
            sub="Diversion is the central criticism of road pricing, so it is measured link by link
                 rather than summarised."
          >
            <Table
              columns={[
                { label: 'Corridor', render: (d) => d.name },
                { label: 'Baseline', render: (d) => fmt.n(d.base_veh) },
                { label: 'Scenario', render: (d) => fmt.n(d.scenario_veh) },
                { label: 'Change', render: (d) => fmt.n(d.change_veh) },
                { label: 'Change %', render: (d) => fmt.signed(d.change_pct, 2) },
                { label: 'v/c', render: (d) => d.vc_ratio.toFixed(3) },
              ]}
              rows={div}
              rowKey={(d) => d.name}
              highlight={(d) => d.change_pct > 10}
            />
            <div className="note">
              Under expressway-only coverage these numbers rise, because Lake Shore and The
              Queensway remain a free bypass of the charging point. Under full screenline coverage
              they fall — the charge no longer has an unpriced escape route.
            </div>
          </Panel>

          <Panel title="Link loadings at equilibrium">
            <Table
              columns={[
                { label: 'Link', render: (r2) => nice(r2[0]) },
                { label: 'Vehicles', render: (r2) => fmt.n(r2[1]) },
                { label: 'v/c', render: (r2) => (m.link_vc[r2[0]] ?? 0).toFixed(3) },
                { label: 'Travel time', render: (r2) => `${(m.link_times[r2[0]] ?? 0).toFixed(2)} min` },
              ]}
              rows={Object.entries(m.link_volumes)}
              rowKey={(r2) => r2[0]}
            />
            <div className="note">
              Convergence: {r.convergence.iterations} iterations, final relative gap{' '}
              {r.convergence.gap.toExponential(2)} against a tolerance of{' '}
              {r.convergence.epsilon.toExponential(0)}.
            </div>
          </Panel>
        </>
      )}

      {compare.data && (
        <Panel
          title="All scenarios side by side"
          sub="The full library, including the operational package that uses no charge at all."
        >
          <Table
            columns={[
              { label: 'Scenario', render: (s) => s.label },
              { label: 'Charge', render: (s) => fmt.dollars(s.peak_toll, 0) },
              { label: 'Coverage', render: (s) => nice(s.coverage) },
              { label: 'Delay ↓', render: (s) => fmt.pct(s.delay_reduction_pct) },
              { label: 'Vehicles', render: (s) => fmt.signed(s.peak_vehicle_change_pct) },
              { label: 'Worst local ↑', render: (s) => fmt.signed(s.worst_diversion_pct) },
              { label: 'Net revenue', render: (s) => fmt.money(s.net_revenue_annual) },
              { label: 'Equity', render: (s) => s.equity_score.toFixed(3) },
              { label: 'Welfare', render: (s) => s.welfare.toFixed(3) },
              { label: 'Feasible', render: (s) => <Badge ok={s.feasible} /> },
            ]}
            rows={compare.data.scenarios}
            rowKey={(s) => s.id}
            highlight={(s) => s.id === 'no_toll_package'}
          />
          {(() => {
            /* Read off the computed table rather than asserted next to it. An
             * earlier version of this caption said "pricing wins" in prose while
             * the number beside it was free to say otherwise -- and once a
             * metric bug was fixed, it did. */
            const cf = compare.data.counterfactual
            const ops = cf.no_toll_package?.delay_reduction_pct ?? 0
            const alone = cf.best_priced_alone
            const both = cf.best_priced
            const chargeWins = (cf.charge_only_advantage_pp ?? 0) > 0
            return (
              <Caveat>
                <b>The highlighted row is the counterfactual that matters.</b> The operational
                package — adaptive signals, ramp management, transit priority, parking pricing
                and GO frequency, with no charge whatsoever — delivers {fmt.pct(ops)} of delay
                reduction.{' '}
                {chargeWins
                  ? <>The strongest charge on its own ({alone?.label}) reaches {fmt.pct(alone?.delay_reduction_pct ?? 0)},
                      beating it by {cf.charge_only_advantage_pp?.toFixed(1)} points — but only by
                      pricing hard and compensating sparingly.</>
                  : <>No charge on its own beats it: the strongest ({alone?.label}) reaches only{' '}
                      {fmt.pct(alone?.delay_reduction_pct ?? 0)}.</>}
                {' '}Adding a charge <i>on top of</i> the operational package reaches{' '}
                {fmt.pct(both?.delay_reduction_pct ?? 0)}, {cf.combined_advantage_pp?.toFixed(1)} points
                above operations alone. They are complements, and on delay alone the operational
                package is the harder benchmark — which is why the case for a charge rests on
                revenue, durability and demand management rather than on delay.
              </Caveat>
            )
          })()}
        </Panel>
      )}

      {tip.node}
    </>
  )
}
