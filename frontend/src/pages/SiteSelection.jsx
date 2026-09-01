import { useMemo, useState } from 'react'

import { useApi, post } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat } from '../components/ui.jsx'
import { BarChart, Heatmap, SERIES, fmt, useTooltip, TipBody } from '../components/charts.jsx'

const CRITERION_LABEL = {
  peak_delay_index: 'Peak delay',
  traffic_base: 'Traffic base',
  transit_substitute: 'Transit substitute',
  revenue_potential: 'Revenue potential',
  diversion_risk: 'Diversion risk',
  equity_exposure: 'Equity exposure',
  governance_feasibility: 'Governance feasibility',
}

export default function SiteSelection() {
  const { data, loading, error } = useApi('/api/site/screening?draws=6000')
  const [weights, setWeights] = useState(null)
  const [custom, setCustom] = useState(null)
  const tip = useTooltip()

  const nominal = data?.weighted_sum?.weights
  const active = weights ?? nominal

  const rescore = async (next) => {
    setWeights(next)
    try {
      setCustom(await post('/api/site/rescore', { weights: next }))
    } catch { setCustom(null) }
  }

  const ranking = custom?.weighted_sum?.ranking ?? data?.weighted_sum?.ranking
  const topsis = custom?.topsis ?? data?.topsis

  const heat = useMemo(() => {
    if (!ranking) return null
    const criteria = Object.keys(CRITERION_LABEL)
    return {
      rows: ranking.map((r) => r.name.replace(/ \(.*\)/, '')),
      cols: criteria.map((c) => CRITERION_LABEL[c]),
      values: ranking.map((r) => criteria.map((c) => r.criteria[c].normalised)),
    }
  }, [ranking])

  if (error) return <ErrorBox error={error} />
  if (loading) return <Loading what="the gateway scorecard" />

  const sens = data.weight_sensitivity.results
    .slice()
    .sort((a, b) => b.win_probability - a.win_probability)
  const selected = data.selected

  return (
    <>
      <div className="page-head">
        <h1>Which gateway should be priced?</h1>
        <p>
          Stage 0 of the study. Five major approaches to central Toronto are scored on the
          criteria the proposal sets out, then the ranking is re-run under thousands of
          alternative weightings — because a multi-criteria score is only ever as good as its
          weights, and weights are subjective.
        </p>
      </div>

      <div className="grid">
        <Tile label="Selected corridor" value="Gardiner West"
              note="Highway 427 to the Humber River" />
        <Tile label="Weighted score" value={selected.score.toFixed(3)}
              note="Nominal criterion weights" />
        <Tile label="Wins under random weights"
              value={fmt.pct(selected.win_probability * 100, 1)}
              tone={selected.win_probability > 0.7 ? 'good' : undefined}
              note="6,000 Dirichlet draws around the nominal set" />
        <Tile label="Second method agrees"
              value={data.methods_agree ? 'Yes' : 'No'}
              tone={data.methods_agree ? 'good' : 'bad'}
              note="TOPSIS ranks by distance to the ideal point" />
      </div>

      <Panel
        title="Ranking under the nominal weights"
        sub="Higher is a better pricing candidate. Diversion risk and equity exposure are
             inverted before scoring, so a candidate is never rewarded for being worse on them."
      >
        <BarChart
          data={ranking.map((r, i) => ({
            label: r.name.replace(/ \(.*\)/, ''),
            value: r.score,
            color: i === 0 ? SERIES[0] : 'var(--seq-250)',
            full: r,
          }))}
          format={(v) => v.toFixed(3)}
          axisTitle="Weighted multi-criteria score"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.full.name} rows={[
                ['Score', d.value.toFixed(4)],
                ['Daily vehicles', fmt.n(d.full.daily_vehicles)],
                ...Object.entries(CRITERION_LABEL).map(([k, lab]) =>
                  [lab, d.full.criteria[k].normalised.toFixed(2)]),
              ]} />
            ),
          }}
        />
      </Panel>

      <Panel
        title="Is the answer an artefact of the weights?"
        sub="Weight vectors are drawn from a Dirichlet distribution centred on the nominal set,
             so the ranking faces a wide spread of reasonable opinion about what matters. The
             probability of ranking first is a far more honest summary than one weighted score."
      >
        <Table
          columns={[
            { label: 'Gateway', render: (r) => r.name },
            { label: 'P(rank 1)', render: (r) => fmt.pct(r.win_probability * 100, 1) },
            { label: 'P(top 2)', render: (r) => fmt.pct(r.top2_probability * 100, 1) },
            { label: 'Mean rank', render: (r) => r.mean_rank.toFixed(2) },
            { label: 'Score, 5th–95th pct',
              render: (r) => `${r.score_p05.toFixed(3)} – ${r.score_p95.toFixed(3)}` },
          ]}
          rows={sens}
          rowKey={(r) => r.gateway_id}
          highlight={(r) => r.gateway_id === selected.gateway_id}
        />
        <div className="note">
          Etobicoke–Gardiner ranks first in {fmt.pct(selected.win_probability * 100, 1)} of draws
          and in the top two in {fmt.pct(sens[0].top2_probability * 100, 1)}. The QEW/427 gateway
          has a larger traffic base and higher revenue potential, but it is a 400-series
          provincial highway with the weakest City authority and the hardest boundary to define,
          which is what keeps it second.
        </div>
      </Panel>

      <Panel
        title="Where each candidate is strong and weak"
        sub="Normalised 0–1 after inverting the criteria where less is better. Every cell carries
             its number, so the ranking never depends on reading a colour."
      >
        {heat && (
          <Heatmap
            rows={heat.rows} cols={heat.cols} values={heat.values}
            format={(v) => v.toFixed(2)}
            tooltip={{
              ...tip,
              render: (r, c, v) => (
                <TipBody title={r} rows={[[c, v?.toFixed(3) ?? '—']]} />
              ),
            }}
          />
        )}
      </Panel>

      <Panel
        title="Change the weights yourself"
        sub="Re-scores live. If the top candidate flips under a weighting you consider
             reasonable, that is a finding about the method, and it should be reported."
      >
        <div className="controls">
          {Object.entries(CRITERION_LABEL).map(([key, label]) => (
            <Field key={key} label={label} readout={(active?.[key] ?? 0).toFixed(2)}>
              <input
                type="range" min="0" max="0.5" step="0.01"
                value={active?.[key] ?? 0}
                onChange={(e) => rescore({ ...active, [key]: Number(e.target.value) })}
              />
            </Field>
          ))}
          <button className="ghost" onClick={() => { setWeights(null); setCustom(null) }}>
            Reset to nominal
          </button>
        </div>
        {custom && (
          <div style={{ marginTop: 14 }}>
            <Table
              columns={[
                { label: '#', render: (r) => r.rank },
                { label: 'Gateway', render: (r) => r.name },
                { label: 'Weighted sum', render: (r) => r.score.toFixed(4) },
                { label: 'TOPSIS rank',
                  render: (r) => topsis.find((t) => t.gateway_id === r.gateway_id)?.rank ?? '—' },
              ]}
              rows={custom.weighted_sum.ranking}
              rowKey={(r) => r.gateway_id}
              highlight={(r) => r.rank === 1}
            />
          </div>
        )}
      </Panel>

      <Panel title="What the screening does not settle">
        <Caveat>
          <b>The selected corridor scores worst of the five on governance.</b> A charge on the
          Gardiner requires provincial authorisation, because Ontario law does not permit a toll
          on a highway where the Crown is the road authority unless an Act allows it, and the
          expressway transfers to the Province in fall 2027. The screening says this is the
          strongest <i>policy test case</i>; it does not say it is the easiest to deliver. That
          gap is why the model carries a second governance branch throughout.
        </Caveat>
      </Panel>

      {tip.node}
    </>
  )
}
