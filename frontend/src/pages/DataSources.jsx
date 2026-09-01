import { useState } from 'react'

import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Caveat } from '../components/ui.jsx'
import { fmt } from '../components/charts.jsx'

const TIER_NOTE = {
  PUBLISHED: 'Taken directly from a named public source.',
  DERIVED: 'Computed from published values by a documented rule.',
  ESTIMATED: 'A planning assumption. These are what the sensitivity analysis tests.',
}

const WORKING_SOURCES = [
  ['City of Toronto — About the Gardiner Expressway',
   'https://www.toronto.ca/services-payments/streets-parking-transportation/road-maintenance/bridges-and-expressways/expressways/gardiner-expressway/about-the-gardiner-expressway/'],
  ['City of Toronto — Gardiner Section 3: Highway 427 to Humber River',
   'https://www.toronto.ca/services-payments/streets-parking-transportation/road-maintenance/bridges-and-expressways/expressways/gardiner-expressway/gardiner-expressway-rehabilitation-strategy/section-3-highway-427-to-humber-river/'],
  ['City of Toronto — 2026 Congestion Management Plan',
   'https://www.toronto.ca/news/city-of-torontos-congestion-plan-drives-co-ordinated-action-to-keep-people-moving/'],
  ['City of Toronto / Province — Gardiner and DVP transfer',
   'https://www.toronto.ca/news/city-of-toronto-and-province-of-ontario-advancing-transfer-of-gardiner-expressway-and-don-valley-parkway/'],
  ['CANCEA — Impact of Congestion in the GTHA and Ontario',
   'https://www.cancea.ca/index.php/2024/12/09/impact-of-congestion-in-the-gtha-and-ontario-economic-and-social-risks/'],
  ['Metrolinx — Business Case Manual Volume 2 (value of time)',
   'https://assets.metrolinx.com/image/upload/v1663237565/Documents/Metrolinx/Metrolinx-Business-Case-Guidance-Volume-2.pdf'],
  ['Metrolinx — Lakeshore West Line GO Expansion',
   'https://www.metrolinx.com/en/projects-and-programs/lakeshore-west-line-go-expansion'],
  ['GO Transit — Fare information',
   'https://www.gotransit.com/en/ways-to-pay/fare-information'],
  ['GO Transit — Mimico station',
   'https://www.gotransit.com/en/find-a-station-or-stop/mi'],
  ['TTC — Fares and passes', 'https://www.ttc.ca/Fares-and-passes'],
  ['DMG / TTS — Auto Passenger Travel and Auto Occupancy in the GTA',
   'https://dmg.utoronto.ca/wp-content/uploads/2023/03/auto_pass.pdf'],
  ['Transportation Tomorrow Survey', 'http://www.transportationtomorrow.on.ca/'],
  ['U of T School of Cities — Could Congestion Pricing Unlock a Better Toronto?',
   'https://schoolofcities.utoronto.ca/could-congestion-pricing-unlock-a-better-toronto/'],
  ['Build Canada — Adaptive traffic intersections',
   'https://www.buildcanada.com/toronto/memos/adaptive-traffic-intersections'],
  ['Build Canada — Congestion pricing',
   'https://www.buildcanada.com/toronto/memos/congestion-pricing'],
  ['Ontario — Public Transportation and Highway Improvement Act',
   'https://www.ontario.ca/laws/statute/90p50'],
]

export default function DataSources() {
  const { data, loading, error } = useApi('/api/data/sources')
  const [tier, setTier] = useState('all')

  if (error) return <ErrorBox error={error} />
  if (loading) return <Loading what="the data inventory" />

  const rows = data.sources.filter((s) => tier === 'all' || s.tier === tier)
  const summary = data.summary
  const total = Object.values(summary).reduce((a, b) => a + b, 0)

  return (
    <>
      <div className="page-head">
        <h1>Data and provenance</h1>
        <p>
          Every number the model consumes, with where it came from. A study that mixes published
          counts with planning assumptions and reports both to three decimal places is not being
          transparent, so each input is tagged and the tags are visible everywhere.
        </p>
      </div>

      <div className="grid">
        <Tile label="Total inputs" value={total} note="Tracked with provenance" />
        {['PUBLISHED', 'DERIVED', 'ESTIMATED'].map((t) => (
          <Tile key={t} label={t} value={summary[t] ?? 0}
                note={TIER_NOTE[t]}
                tone={t === 'PUBLISHED' ? 'good' : t === 'ESTIMATED' ? 'bad' : undefined} />
        ))}
      </div>

      <Panel title="Input inventory">
        <div className="pill-row">
          {['all', 'PUBLISHED', 'DERIVED', 'ESTIMATED'].map((t) => (
            <button key={t} className={`pill${tier === t ? ' on' : ''}`} onClick={() => setTier(t)}>
              {t === 'all' ? `All (${total})` : `${t} (${summary[t] ?? 0})`}
            </button>
          ))}
        </div>
        <Table
          columns={[
            { label: 'Input', render: (s) => s.key },
            { label: 'Value', render: (s) =>
              Number(s.value) >= 10000
                ? fmt.n(s.value)
                : Number(s.value).toLocaleString('en-CA', { maximumFractionDigits: 3 }) },
            { label: 'Unit', render: (s) => s.unit },
            { label: 'Tier', render: (s) => <span className={`tier ${s.tier}`}>{s.tier}</span> },
            { label: 'Source', render: (s) =>
              <span style={{ whiteSpace: 'normal' }}>{s.source}</span> },
            { label: 'Note', render: (s) =>
              <span style={{ whiteSpace: 'normal', color: 'var(--text-secondary)' }}>{s.note}</span> },
          ]}
          rows={rows}
          rowKey={(s) => s.key}
          highlight={(s) => s.tier === 'ESTIMATED'}
        />
        <div className="note">{data.note}</div>
      </Panel>

      <Panel title="Working sources">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>
          {WORKING_SOURCES.map(([label, url]) => (
            <li key={url} style={{ marginBottom: 4 }}>
              <a href={url} target="_blank" rel="noreferrer">{label}</a>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Known limitations">
        <Caveat>
          <b>These are the things a reviewer should press on first.</b>
        </Caveat>
        <ul style={{ marginTop: 12, paddingLeft: 18, fontSize: 13.5,
                     color: 'var(--text-secondary)' }}>
          <li style={{ marginBottom: 6 }}>
            <b>Screenline demand is derived, not counted.</b> The 120,000 two-way weekday figure
            for the western segment is interpolated between the published system average and the
            downtown count. A real study would use the City's own count for that specific
            screenline.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>Observed travel times are estimates.</b> The calibration targets come from reported
            corridor travel times rather than a licensed probe-data feed. Since alpha is fitted to
            them, an error here propagates into every delay result.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>The origin-destination pattern is synthetic.</b> Sub-area shares and income mixes are
            constructed from Census neighbourhood profiles rather than drawn from a TTS extract, so
            the segmentation is representative rather than observed.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>The rejoin fraction drives the diversion result.</b> Assuming 55% of bypassing
            drivers re-enter the expressway past the gantry is an estimate with no local
            observation behind it.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>Ride-hailing and freight are not separately calibrated.</b> Both carry instruments in
            the model, but their behaviour is folded into the commuter response.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>Emissions are a proxy, not an inventory.</b> CO₂e moves with vehicle-kilometres and
            with time in stop-start conditions. That is enough to rank policies and not enough to
            quote as an absolute figure.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>Collection costs are assumed, and they change the sign of the financial answer.</b>
            {' '}Nothing in the model can resolve them before a scheme is procured.
          </li>
          <li style={{ marginBottom: 6 }}>
            <b>The parking instrument reaches only 70% of drivers.</b> Through-trips, drop-offs,
            deliveries and employer-provided spaces are outside a destination levy, and that share
            is itself an estimate.
          </li>
          <li>
            <b>No microsimulation.</b> There are no individual vehicles, queues, signals or
            incidents, so nothing here speaks to intersection-level performance or ramp queueing.
          </li>
        </ul>
      </Panel>
    </>
  )
}
