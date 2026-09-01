import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat } from '../components/ui.jsx'
import { BarChart, LineChart, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'

export default function Baseline() {
  const { data, loading, error } = useApi('/api/validation')
  const conv = useApi('/api/sensitivity/convergence')
  const tip = useTooltip()

  if (error) return <ErrorBox error={error} />
  if (loading) return <Loading what="the baseline calibration" />

  const shares = data.share_validation
  const links = data.link_validation
  const held = links.filter((l) => l.role === 'held out')
  const worstHeld = held.reduce((a, b) =>
    Math.abs(b.error_pct) > Math.abs(a.error_pct) ? b : a, held[0])
  const el = data.toll_elasticity

  return (
    <>
      <div className="page-head">
        <h1>Is the baseline credible?</h1>
        <p>
          Nothing about a toll is worth reporting until the no-charge case reproduces the corridor
          as it actually behaves. This page is that evidence: observed volumes, observed travel
          times, an out-of-sample check, the implied behavioural response, and confirmation that
          the results do not depend on where the solver stopped.
        </p>
      </div>

      <div className="grid">
        <Tile label="Mode-share error" value={`${data.max_share_error_pp.toFixed(4)} pp`}
              tone="good" note="Largest gap between modelled and observed" />
        <Tile label="Held-out link error" value={fmt.signed(worstHeld?.error_pct, 1)}
              tone={Math.abs(worstHeld?.error_pct ?? 99) < 10 ? 'good' : 'bad'}
              note={`Worst of ${held.length} links excluded from the fit`} />
        <Tile label="Calibration passes" value={fmt.n(data.calibration_iterations)}
              note="Each solving a full equilibrium" />
        <Tile label="GO peak load factor"
              value={fmt.pct(data.transit_headroom.go_load_factor * 100, 0)}
              note={`${fmt.n(data.transit_headroom.go_capacity)} places available`} />
      </div>

      <Panel
        title="Modelled versus observed travel time"
        sub="Alpha in the volume-delay curve is fitted on gardiner_west, gardiner_east and
             lakeshore_west. Beta is held at a literature value rather than fitted, so the two
             parameters cannot trade off against each other and produce a meaningless fit."
      >
        <Table
          columns={[
            { label: 'Link', render: (r) => nice(r.link_id) },
            { label: 'Role', render: (r) =>
              <Badge kind={r.role === 'calibrated' ? 'info' : 'warn'}>{r.role}</Badge> },
            { label: 'α', render: (r) => r.alpha.toFixed(3) },
            { label: 'β', render: (r) => r.beta },
            { label: 'v/c', render: (r) => r.vc_ratio.toFixed(3) },
            { label: 'Modelled', render: (r) => `${r.modelled_min.toFixed(2)} min` },
            { label: 'Observed', render: (r) => `${r.observed_min.toFixed(2)} min` },
            { label: 'Error', render: (r) => fmt.signed(r.error_pct, 2) },
          ]}
          rows={links}
          rowKey={(r) => r.link_id}
          highlight={(r) => r.role === 'held out'}
        />
        <div className="note">
          The two highlighted rows were never shown to the fit. Their arterial alpha is inherited
          from Lake Shore Blvd W, and they still land within {
            Math.max(...held.map((h) => Math.abs(h.error_pct))).toFixed(1)
          }% of observed. That is the strongest single piece of evidence that the volume-delay
          curve is capturing something real rather than absorbing error into a free parameter.
        </div>
      </Panel>

      <Panel
        title="Modelled versus observed mode and route split"
        sub="The alternative-specific constants are fitted at the equilibrium implied by each trial
             value, not at frozen travel times, so the calibration stays consistent with the
             congestion feedback the model later relies on."
      >
        <Table
          columns={[
            { label: 'Alternative', render: (r) => nice(r.alternative) },
            { label: 'Observed', render: (r) => fmt.pct(r.observed * 100, 2) },
            { label: 'Modelled', render: (r) => fmt.pct(r.modelled * 100, 2) },
            { label: 'Error', render: (r) => `${r.error_pp >= 0 ? '+' : ''}${r.error_pp.toFixed(3)} pp` },
            { label: 'Constant ($)', render: (r) => r.constant_dollars.toFixed(2) },
          ]}
          rows={shares}
          rowKey={(r) => r.alternative}
        />
        <div className="note">
          The constants absorb everything the observed attributes do not explain — vehicle
          ownership, comfort, autonomy, and the strong reluctance to abandon a trip. They are
          large, and that is expected: a corridor where driving is slower and dearer than the
          train, yet still carries a third of all trips, can only be reproduced by admitting
          those unmodelled preferences explicitly.
        </div>
      </Panel>

      <Panel
        title="Does the model respond to price plausibly?"
        sub="The logit scale governs how strongly travellers react. Left unchecked it is just a
             number in a config file, so the implied response is reported here for comparison
             against schemes that actually operate."
      >
        <LineChart
          series={[{
            label: 'Change in charged-segment volume',
            data: [{ toll: 0, change: 0 }, ...el.points.map((p) => ({ toll: p.toll, change: p.change_pct }))]
              .map((p) => ({ x: p.toll, y: p.change })),
          }]}
          xTitle="Peak charge ($ per vehicle)"
          yTitle="Change in peak vehicles (%)"
          format={(v) => `${v.toFixed(0)}%`}
          xFormat={(v) => `$${v.toFixed(0)}`}
          zeroLine
          tooltip={{
            ...tip,
            render: (p) => (
              <TipBody title={`$${p.x.toFixed(0)} charge`} rows={[['Volume change', fmt.signed(p.y)]]} />
            ),
          }}
        />
        <Table
          columns={[
            { label: 'Charge', render: (r) => fmt.dollars(r.toll, 0) },
            { label: 'Peak vehicles', render: (r) => fmt.n(r.volume) },
            { label: 'Change', render: (r) => fmt.signed(r.change_pct, 2) },
            { label: 'Arc elasticity',
              render: (r) => r.arc_elasticity_vs_generalized_cost.toFixed(3) },
          ]}
          rows={el.points}
          rowKey={(r) => r.toll}
        />
        <div className="note">{el.note}</div>
        <Caveat>
          A $4 charge removes about {Math.abs(el.points.find((p) => p.toll === 4)?.change_pct ?? 0).toFixed(0)}%
          of peak vehicles from the charged segment. For comparison, Stockholm's charge cut
          cordon traffic by roughly 20% and London's by roughly 15%, so this model sits at the
          conservative end of observed experience rather than claiming an unusually strong
          response.
        </Caveat>
      </Panel>

      <Panel
        title="Do the results depend on when the solver stopped?"
        sub="The plan asks for several convergence tolerances rather than one, so a result cannot
             be an artefact of stopping the iteration early."
      >
        {conv.loading ? <Loading what="the convergence study" /> : conv.error ? (
          <ErrorBox error={conv.error} />
        ) : (
          <>
            <div style={{ marginBottom: 10 }}>
              <Badge ok={conv.data.stable}>
                {conv.data.stable
                  ? 'Stable across five tolerances'
                  : 'Sensitive to the convergence tolerance'}
              </Badge>
            </div>
            <Table
              columns={[
                { label: 'ε', render: (r) => r.epsilon.toExponential(0) },
                { label: 'Iterations', render: (r) => r.iterations },
                { label: 'Final gap', render: (r) => r.gap.toExponential(2) },
                { label: 'Peak vehicles', render: (r) => fmt.n(r.peak_vehicles) },
                { label: 'vs tightest', render: (r) => `${r.vehicles_vs_tightest_pct.toFixed(4)}%` },
                { label: 'Delay reduction', render: (r) => fmt.pct(r.delay_reduction_pct) },
              ]}
              rows={conv.data.results}
              rowKey={(r) => r.epsilon}
            />
          </>
        )}
      </Panel>

      <Panel title="Methodological notes">
        <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-secondary)', fontSize: 13.5 }}>
          {data.notes.map((n) => <li key={n} style={{ marginBottom: 5 }}>{n}</li>)}
        </ul>
      </Panel>

      {tip.node}
    </>
  )
}
