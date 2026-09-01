import { lazy, Suspense, useMemo, useState } from 'react'

import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Field, Caveat, Finding } from '../components/ui.jsx'
import { BarChart, GroupedBars, Legend, SERIES, fmt, nice, useTooltip, TipBody } from '../components/charts.jsx'
import { useAppTheme } from '../App.jsx'
import { RASTER_BASEMAPS, defaultBasemap } from '../lib/basemaps.js'

/* Lazily, so Leaflet's ~150 KB stays out of the main bundle. Importing it
   statically pulled it into the entry chunk for all sixteen pages, including
   every page with no map on it -- which is exactly the wrong trade on the slow
   connections this map is meant to serve. */
const Map2D = lazy(() => import('../components/Map2D.jsx'))

const CREDITS = ['none', 'low_income', 'low_income_transit_poor', 'shift_worker',
                 'monthly_cap', 'mobility_credit', 'targeted_package', 'means_tested']

/* FHWA's second equity type. The income analysis sorts people by quintile and
 * so cannot see any of this: a cordon collects from wherever its users live,
 * and where they live decides whether they had an alternative. */
export default function Geographic() {
  const [toll, setToll] = useState(10)
  const [coverage, setCoverage] = useState('screenline')
  const [credit, setCredit] = useState('low_income_transit_poor')
  const tip = useTooltip()
  const { resolved: theme } = useAppTheme()

  const q = `?toll=${toll}&coverage=${coverage}&credit=${credit}`
  const run = useApi(`/api/equity/geographic${q}`)
  const geo = useApi('/api/data/geography')

  // Join the model rows to their indicative points. Declared BEFORE the early
  // returns: a hook that only runs once the data has loaded changes the hook
  // count between renders, which React rejects outright ("rendered more hooks
  // than during the previous render"). It therefore reads run.data directly
  // rather than the destructured rows below.
  const mapped = useMemo(() => {
    const pts = new Map(
      (run.data?.points?.features ?? []).map((f) => [
        f.properties.subarea,
        { lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] },
      ]),
    )
    // A sub-area with no point is dropped rather than placed at a guess.
    return (run.data?.incidence?.subareas ?? [])
      .filter((r) => pts.has(r.subarea))
      .map((r) => ({ ...r, ...pts.get(r.subarea) }))
  }, [run.data])

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the geographic incidence" />

  const { incidence, decomposition, fhwa_types: types } = run.data
  const rows = incidence.subareas
  const b = incidence.boundary
  const bench = incidence.benchmark
  const outside = b.outside_toronto

  // Above 1 means an area carries more of the charge than its use of the road.
  const worstBurden = rows.reduce((a, r) => (r.burden_pct_income > a.burden_pct_income ? r : a))
  const isNewJerseyCase = outside.pays_vs_uses >= 1.0


  return (
    <>
      <div className="page-head">
        <h1>Geographic equity: who pays depends on where they live</h1>
        <p>
          FHWA distinguishes three kinds of equity — income, geographic and modal — and warns
          that most analyses stop at the first. Its New York finding is the one worth testing
          here: New Jersey residents paid about {fmt.pct(100 * bench.share_of_tolls_paid, 0)} of
          the tolls while making about {fmt.pct(100 * bench.share_of_drivers, 0)} of the trips.
          A charge at a boundary collects from the people on the far side of it. This corridor
          has the same shape — 40% of demand crosses the western gateway from outside Toronto —
          so the question is whether it has the same result.
        </p>
      </div>

      <Panel title="Policy under examination">
        <div className="controls">
          <Field label="Peak charge" readout={fmt.dollars(toll, 2)}>
            <input type="range" min="0" max="15" step="0.5" value={toll}
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
              {CREDITS.map((c) => <option key={c} value={c}>{nice(c)}</option>)}
            </select>
          </Field>
        </div>
      </Panel>

      <Panel
        title="Across the city boundary"
        sub="The comparison a quintile table cannot make"
      >
        <div className="grid">
          <Tile label="Outside Toronto — share of trips"
                value={fmt.pct(100 * outside.trip_share, 1)}
                note="Mississauga and the west GTA" />
          <Tile label="…share of the charge paid"
                value={fmt.pct(100 * outside.charge_share, 1)} />
          <Tile label="Pays vs uses"
                value={fmt.n(outside.pays_vs_uses, 3)}
                tone={isNewJerseyCase ? 'bad' : 'good'}
                note={isNewJerseyCase
                  ? 'Above 1 — carrying more than its use of the road'
                  : 'Below 1 — carrying less than its use of the road'} />
          <Tile label="New York benchmark"
                value={fmt.n(bench.ratio, 2)}
                note="New Jersey residents at the NYC cordon" />
        </div>

          <Finding kicker="The result" tone={isNewJerseyCase ? 'bad' : 'good'}>
          {isNewJerseyCase ? (
            <p className="lede">
              <b>This corridor reproduces the New York pattern.</b> Travellers from outside
              Toronto pay more of the charge than their share of trips, in a city where they
              cannot vote. That is the geographic equity problem FHWA warns about, and it needs
              a mitigation the income credits do not provide.
            </p>
          ) : (
            <p className="lede">
              <b>This corridor does not reproduce the New York pattern.</b> Under this design the
              905 pays <b>{fmt.pct(100 * outside.charge_share, 1)}</b> of the charge on{' '}
              <b>{fmt.pct(100 * outside.trip_share, 1)}</b> of the trips — a ratio of{' '}
              <b>{fmt.n(outside.pays_vs_uses, 3)}</b>, against {fmt.n(bench.ratio, 2)} for New
              Jersey at the New York cordon. The reason is that Lakeshore West GO gives west-GTA
              travellers a way out of the charge, and enough of them take it. The burden lands
              instead on <b>{worstBurden.subarea}</b>, inside Toronto, at{' '}
              {fmt.pct(worstBurden.burden_pct_income, 3)} of household income.
            </p>
          )}
          <p className="aside">
            It is still true that those travellers pay a charge set by a council they cannot vote
            for. That is a question about consent rather than about burden, and it is the same
            asymmetry that gives the Province its political cost in the bargaining model.
          </p>
          </Finding>
      </Panel>

      <Panel
        title="Where the burden actually falls"
        sub="Circle area is share of trips, colour is burden as a share of household income"
      >
        {geo.data ? (
          <Suspense fallback={<Loading what="the corridor map" />}>
          <Map2D
            geography={geo.data}
            basemap={defaultBasemap(RASTER_BASEMAPS, theme)}
            subareaBurden={mapped}
            showTransit
            showGantries={false}
            height={480}
          />
          </Suspense>
        ) : <Loading what="the corridor geography" />}
        <Caveat>
          These are indicative points, not boundaries. The sub-areas have no
          digitised polygons here, and drawing them would imply a spatial precision
          the synthetic OD pattern does not have. The Mississauga / west GTA marker
          stands for a catchment reaching far beyond it, and is placed west of the
          screenline to show the direction demand arrives from rather than where
          those travellers live. Nothing in the model reads these coordinates.
        </Caveat>
      </Panel>

      <Panel
        title="Does the money come back to where it came from?"
        sub="Share of the charge paid against share of the recycled benefit received"
      >
        <GroupedBars
          categories={rows.map((r) => r.subarea)}
          series={[
            { label: 'Share of charge paid', color: SERIES[0],
              values: rows.map((r) => 100 * r.charge_share) },
            { label: 'Share of benefit received', color: SERIES[1],
              values: rows.map((r) => 100 * r.benefit_share) },
          ]}
          format={(v) => fmt.pct(v, 0)}
          yTitle="% of corridor total"
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Share of charge paid', color: SERIES[0] },
          { label: 'Share of benefit received', color: SERIES[1] },
        ]} />
        <Caveat>
          Revenue is allocated toward station access and first-and-last-mile connections, which
          is deliberately progressive — it goes where transit access is worst. But it is
          allocated on transit need, not on where the charge was collected, so some areas are net
          contributors and others net recipients. Naming them is the difference between a
          spending plan and a transfer nobody announced.
        </Caveat>
      </Panel>

      <Panel title="Burden by sub-area" sub="Charge paid as a share of household income">
        <BarChart
          data={rows.map((r) => ({
            label: r.subarea,
            value: r.burden_pct_income,
            color: r.outside_toronto ? SERIES[3] : SERIES[0],
          }))}
          format={(v) => fmt.pct(v, 2)}
          axisTitle="% of household income"
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Inside Toronto', color: SERIES[0] },
          { label: 'Outside Toronto', color: SERIES[3] },
        ]} />
      </Panel>

      <Panel title="Every sub-area, in full">
        <Table
          columns={[
            { key: 'subarea', label: 'Sub-area',
              render: (r) => (
                <>
                  {r.subarea}{' '}
                  {r.outside_toronto && <Badge kind="warn">outside Toronto</Badge>}
                </>
              ) },
            { key: 'household_income', label: 'Income', render: (r) => fmt.money(r.household_income) },
            { key: 'transit_access', label: 'Transit access', render: (r) => fmt.n(r.transit_access, 2) },
            { key: 'trip_share', label: 'Trips', render: (r) => fmt.pct(100 * r.trip_share, 1) },
            { key: 'charge_share', label: 'Charge paid', render: (r) => fmt.pct(100 * r.charge_share, 1) },
            { key: 'pays_vs_uses', label: 'Pays / uses', render: (r) => fmt.n(r.pays_vs_uses, 3) },
            { key: 'burden_pct_income', label: 'Burden % income',
              render: (r) => fmt.pct(r.burden_pct_income, 3) },
            { key: 'net_welfare_per_trip', label: 'Net welfare / trip',
              render: (r) => fmt.dollars(r.net_welfare_per_trip, 2) },
            { key: 'net_contributor_gap', label: 'Paid − received',
              render: (r) => fmt.pct(100 * r.net_contributor_gap, 1) },
            { key: 'winners_share', label: 'Better off',
              render: (r) => fmt.pct(100 * r.winners_share, 0) },
          ]}
          rows={rows}
          rowKey={(r) => r.subarea}
          highlight={(r) => r.subarea === worstBurden.subarea}
        />
        <Caveat>
          Net welfare per trip is the full Eliasson position — tolls paid, adaptation cost, time
          gained and revenue returned — not just the charge. An area can pay more and still come
          out ahead, and several do.
        </Caveat>
      </Panel>

      <Panel
        title="Is this geography, or income wearing a map?"
        sub="Sub-areas differ in income as well as in location, so the geographic result has to be separated from the income one before it counts as a finding"
      >
        <div className="grid">
          <Tile label="Explained by income alone"
                value={fmt.pct(100 * decomposition.share_explained_by_income, 0)} />
          <Tile label="Not explained by income"
                value={fmt.pct(100 * decomposition.share_not_explained_by_income, 0)}
                tone={decomposition.share_not_explained_by_income > 0.25 ? 'good' : undefined}
                note="What location contributes on its own" />
          <Tile label="Residual vs transit access"
                value={fmt.n(decomposition.residual_vs_transit_access_corr, 2)}
                note="Correlation, 7 sub-areas" />
        </div>

        <BarChart
          data={decomposition.rows.map((r) => ({
            label: r.subarea,
            value: r.residual,
            color: r.residual > 0 ? SERIES[2] : SERIES[1],
          }))}
          diverging
          format={(v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}`}
          axisTitle="Burden above (+) or below (−) what income alone predicts"
          tooltip={tip}
        />

        <Finding kicker="Why this page exists"
                 lede={`${fmt.pct(100 * decomposition.share_not_explained_by_income, 0)} of the variation in geographic burden is not predicted by income.`}>
          <p className="aside">
            That is what justifies reading this separately from the income analysis rather than
            as a restatement of it.
          </p>
        </Finding>
        <Caveat>{decomposition.mechanism}</Caveat>
      </Panel>

      <Panel title="FHWA's three equity types, and where each one lives">
        <Table
          columns={[
            { key: 'type', label: 'Equity type' },
            { key: 'status', label: 'Treatment in this model' },
            { key: 'where', label: 'Module' },
          ]}
          rows={types}
          rowKey={(r) => r.type}
        />
      </Panel>

      <Caveat>{incidence.caveat}</Caveat>
      {tip.node}
    </>
  )
}
