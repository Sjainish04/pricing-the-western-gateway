import { useMemo, useState } from 'react'

import { useApi, usePost } from '../lib/api.js'
import CorridorMap from '../components/CorridorMap.jsx'
import { useAppTheme } from '../App.jsx'
import { Panel, Tile, Loading, ErrorBox, Table, Field, Caveat } from '../components/ui.jsx'
import { fmt, nice, NICE } from '../components/charts.jsx'

const VIEW_POLICIES = {
  baseline: { label: 'No charge (baseline)', policy: { peak_toll: 0, label: 'baseline' } },
  freeway_4: {
    label: '$4 expressway only',
    policy: { peak_toll: 4, coverage: 'gardiner_only', credit: 'none', label: 'freeway 4' },
  },
  freeway_8: {
    label: '$8 expressway only',
    policy: { peak_toll: 8, coverage: 'gardiner_only', credit: 'none', label: 'freeway 8' },
  },
  screenline_5: {
    label: '$5 full screenline',
    policy: { peak_toll: 5, coverage: 'screenline', credit: 'none', label: 'screenline 5' },
  },
  recommended: {
    label: '$10 screenline + credits',
    policy: {
      peak_toll: 10, coverage: 'screenline', credit: 'low_income_transit_poor',
      label: 'recommended',
    },
  },
}

export default function Corridor() {
  const { resolved: theme } = useAppTheme()
  const geo = useApi('/api/data/geography')
  const net = useApi('/api/data/network')
  const [view, setView] = useState('baseline')
  // Off by default: the building extrusion is the heaviest layer in the scene,
  // and on integrated graphics it is the difference between a smooth corridor
  // and a stuttering one. The corridor ribbons are what the page is for.
  const [showBuildings, setShowBuildings] = useState(false)
  const [showRibbons, setShowRibbons] = useState(true)
  const [showTransit, setShowTransit] = useState(true)
  const [showGantries, setShowGantries] = useState(true)

  const run = usePost('/api/simulate', VIEW_POLICIES[view].policy)

  const { linkVc, linkVolumes, linkTimes } = useMemo(() => {
    const m = run.data?.metrics
    return {
      linkVc: m?.link_vc ?? {},
      linkVolumes: m?.link_volumes ?? {},
      linkTimes: m?.link_times ?? {},
    }
  }, [run.data])

  if (geo.error) return <ErrorBox error={geo.error} />
  if (geo.loading || net.loading) return <Loading what="the corridor geography" />

  const links = net.data.validation
  const gantries = geo.data.gantries
  const m = run.data?.metrics

  return (
    <>
      <div className="page-head">
        <h1>The corridor and where the charge would be collected</h1>
        <p>
          The charged segment is only 8.2 km of a roughly 18.5 km trip. That ratio is the central
          design problem: the cheapest way to avoid a gateway charge is not to stop driving but to
          leave the expressway before the gantry, run a City arterial, and re-enter past it. Seen
          flat those are three parallel lines; seen against the neighbourhoods they run through,
          the reason diversion matters is obvious.
        </p>
      </div>

      <div className="grid">
        <Tile label="Charged segment" value="8.2 km" note="Hwy 427 → Humber River" />
        <Tile label="Untolled downstream" value="10.3 km" note="Humber River → downtown core" />
        <Tile label="Charging points"
              value={gantries.filter((g) => g.road === 'gardiner').length}
              note="Mainline plus ramp gantries" />
        <Tile label="Arterial screenlines"
              value={gantries.filter((g) => g.role === 'diversion').length}
              note="Needed only under full screenline coverage" />
      </div>

      <Panel
        title="Study area in three dimensions"
        sub="Each link is extruded as a ribbon whose height is its peak vehicle count and whose
             colour is its volume/capacity, with real gantry portals spanning the roadway and GO
             platforms raised by boardings. Change the policy and watch the expressway drain while
             the neighbourhood streets swell. Drag to orbit, right-drag to tilt, scroll to zoom."
      >
        <div className="controls" style={{ marginBottom: 12 }}>
          <Field label="Policy shown">
            <select value={view} onChange={(e) => setView(e.target.value)}>
              {Object.entries(VIEW_POLICIES).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </Field>
          <label className="check">
            <input type="checkbox" checked={showRibbons}
                   onChange={(e) => setShowRibbons(e.target.checked)} />
            Corridor ribbons
          </label>
          <label className="check">
            <input type="checkbox" checked={showBuildings}
                   onChange={(e) => setShowBuildings(e.target.checked)} />
            City buildings
          </label>
          <label className="check">
            <input type="checkbox" checked={showGantries}
                   onChange={(e) => setShowGantries(e.target.checked)} />
            Charging points
          </label>
          <label className="check">
            <input type="checkbox" checked={showTransit}
                   onChange={(e) => setShowTransit(e.target.checked)} />
            Transit alternatives
          </label>
        </div>

        <CorridorMap
            theme={theme}
            geography={geo.data}
            linkVc={linkVc}
            linkVolumes={linkVolumes}
            linkTimes={linkTimes}
            linkNames={NICE}
            showRibbons={showRibbons}
            showBuildings={showBuildings}
            showTransit={showTransit}
            showGantries={showGantries}
        />

        {m && (
          <>
            <div className="grid" style={{ marginTop: 16 }}>
              <Tile label="Charged-segment vehicles"
                    value={fmt.n(m.peak_entering_vehicles)}
                    tone={m.peak_vehicle_change_pct < 0 ? 'good' : undefined}
                    note={`${fmt.signed(m.peak_vehicle_change_pct)} vs baseline`} />
              <Tile label="Worst local increase"
                    value={fmt.signed(m.worst_diversion_pct)}
                    tone={m.worst_diversion_pct > 10 ? 'bad' : 'good'}
                    note={m.worst_diversion_link ?? '—'} />
              <Tile label="Corridor travel time"
                    value={`${m.gardiner_travel_time_min.toFixed(1)} min`}
                    tone={m.travel_time_saved_min > 0 ? 'good' : undefined}
                    note={`${m.travel_time_saved_min.toFixed(1)} min saved`} />
              <Tile label="Delay removed" value={fmt.pct(m.delay_reduction_pct)}
                    tone={m.delay_reduction_pct > 0 ? 'good' : undefined}
                    note="Across all five links" />
            </div>
            <div className="note">
              Switch between the expressway-only and full-screenline options and watch the two
              arterials. Under an expressway-only charge they turn warmer as traffic bypasses the
              gantry; under the full screenline they cool, because the bypass is no longer free.
            </div>
          </>
        )}
      </Panel>

      <Panel
        title="The five-link network, and how well it reproduces reality"
        sub="Alpha is fitted on three links so the model matches observed peak travel times. The
             other two inherit the fitted arterial value and are held out, so their error is a
             genuine out-of-sample check rather than a restatement of the fit."
      >
        <Table
          columns={[
            { label: 'Link', render: (r) => nice(r.link_id) },
            { label: 'Role', render: (r) => r.role },
            { label: 'α', render: (r) => r.alpha.toFixed(3) },
            { label: 'Volume', render: (r) => fmt.n(r.base_volume_veh) },
            { label: 'v/c', render: (r) => r.vc_ratio.toFixed(3) },
            { label: 'Modelled', render: (r) => `${r.modelled_min.toFixed(1)} min` },
            { label: 'Observed', render: (r) => `${r.observed_min.toFixed(1)} min` },
            { label: 'Error', render: (r) => fmt.signed(r.error_pct, 2) },
            { label: 'Speed', render: (r) => `${r.modelled_speed_kmh} km/h` },
          ]}
          rows={links}
          rowKey={(r) => r.link_id}
          highlight={(r) => r.link_id === 'gardiner_west'}
        />
        <div className="note">
          The charged segment runs at a volume/capacity ratio of{' '}
          {links.find((l) => l.link_id === 'gardiner_west')?.vc_ratio} — effectively at capacity.
          That is what makes the congestion externality on this link so large, and why small
          reductions in volume buy disproportionately large travel-time gains.
        </div>
      </Panel>

      <Panel title="Route composition">
        <Table
          columns={[
            { label: 'Route', render: (r) => nice(r.alternative) },
            { label: 'Link', render: (r) => nice(r.link_id) },
            { label: 'Share of route vehicles', render: (r) => fmt.pct(r.fraction * 100, 0) },
            { label: 'Note', render: (r) =>
              <span style={{ whiteSpace: 'normal' }}>{r.note}</span> },
          ]}
          rows={net.data.routes}
          rowKey={(r, i) => `${r.alternative}-${r.link_id}-${i}`}
        />
        <Caveat>
          <b>55% of bypassing drivers are assumed to rejoin the expressway</b> downstream of the
          charging point, with the rest continuing on Lake Shore into downtown. That share is an
          ESTIMATED input and one of the more consequential ones: it determines how much a gateway
          charge leaks. It also produces an emergent result worth noting — because bypassers
          rejoin, diversion partly defeats itself by making the shared downstream section busier.
        </Caveat>
      </Panel>

      <Panel title="Charging points">
        <Table
          columns={[
            { label: 'Location', render: (g) => g.name },
            { label: 'Road', render: (g) => nice(g.road) },
            { label: 'Role', render: (g) => g.role },
            { label: 'Peak vehicles captured', render: (g) => fmt.n(g.captures_veh_peak) },
            { label: 'Note', render: (g) =>
              <span style={{ whiteSpace: 'normal' }}>{g.note}</span> },
          ]}
          rows={gantries}
          rowKey={(g) => g.gantry_id}
          highlight={(g) => g.role === 'diversion'}
        />
        <div className="note">
          The highlighted rows are arterial screenlines. They are what turns an expressway toll
          into a genuine cordon, and they are also the reason full screenline coverage scores
          worse on deliverability: it needs gantries on City streets, not just on the expressway.
        </div>
      </Panel>

      <Caveat>
        <b>The basemap is OpenFreeMap, rendered with MapLibre GL.</b> Both are open source and need
        no API key or account, so this view keeps working without a paid tile subscription. The
        road centrelines are digitised approximations used for display only — every number in the
        model comes from the lengths and capacities in <code>network.csv</code>, never from these
        coordinates. The basemap needs an internet connection; the rest of the page does not.
      </Caveat>
    </>
  )
}
