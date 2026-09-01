import { useApi } from '../lib/api.js'
import { Panel, Tile, Loading, ErrorBox, Table, Badge, Caveat, Finding } from '../components/ui.jsx'
import { BarChart, LineChart, ScatterChart, Timeline, Legend, SERIES, fmt, useTooltip, TipBody } from '../components/charts.jsx'

/* Colour follows what a benchmark IS, not its rank, so a re-sort cannot repaint
 * the survivors.
 *
 * Three slots, not four. The taxes are NOT plotted as a fourth series: they are
 * a yardstick, not a comparator, and giving them a categorical hue would say
 * otherwise. Grey said it correctly but failed validation against the green in
 * both light and dark (adjacent DE 14.5 and 12.6, below the 15 normal-vision
 * floor), and every low-chroma alternative was worse. So they are rendered as a
 * reference strip below the chart instead, which is what a yardstick is.
 *
 * The remaining trio validates: one WARN in light on the green's 2.74 contrast,
 * which the skill relieves with visible labels -- every bar is directly
 * labelled and a full table sits below. Dark passes clean, and was selected
 * against the dark surface rather than flipped: the obvious blue/purple pairing
 * passes in light and collapses to DE 1.9 in dark. */
const KIND_COLOR = {
  operating_charge: SERIES[0],   // blue
  proposed_charge: SERIES[2],    // green
  here: SERIES[1],               // orange -- the same colour in every chart
}

const STATUS = {
  operating: { kind: 'pass', label: 'operating' },
  rejected: { kind: 'fail', label: 'rejected at referendum' },
  withdrawn: { kind: 'warn', label: 'failed in the legislature' },
}

/* Comparison used as evidence rather than as decoration: what the operating
 * record says about THIS model, including where it disagrees. */
export default function Compare() {
  const run = useApi('/api/compare/cities')
  const trustRun = useApi('/api/political/trust')
  const tip = useTooltip()

  if (run.error) return <ErrorBox error={run.error} />
  if (run.loading && !run.data) return <Loading what="the comparative record" />

  const { schemes, positioning: pos, external_validation: ev,
          contradictions, exemptions, note } = run.data
  const operating = schemes.filter((s) => s.status === 'operating')
  const failed = schemes.filter((s) => s.status !== 'operating')
  // Most regressive first, with this study inserted in its true position rather
  // than appended -- a bar tacked on the end reads as "and also", not "here".
  const suits = [
    ...pos.suits_benchmarks.filter((b) => b.kind !== 'other_tax'),
    { city: 'This corridor', suits_index: pos.suits_index_here,
      kind: 'here', kind_label: 'This corridor',
      note: 'The recommended $10 screenline with income and transit-poor credits.' },
  ].sort((a, b) => a.suits_index - b.suits_index)
  const taxes = pos.suits_benchmarks
    .filter((b) => b.kind === 'other_tax')
    .sort((a, b) => a.suits_index - b.suits_index)

  return (
    <>
      <div className="page-head">
        <h1>What the other cities actually did</h1>
        <p>
          Six cities run a full-scale congestion charge — Singapore since 1975, London, Stockholm,
          Milan, Gothenburg, and New York since January 2025. Three more tried and failed.
          A table of them is not analysis, so this page asks the harder question: does this
          study's result sit inside the range the record has produced, and where does the record
          <i> disagree</i> with the model?
        </p>
      </div>

      <Panel
        title="Fifty years of trying"
        sub="Successes above the line, failures below"
      >
        <Timeline
          events={schemes.map((s2) => ({
            year: Number(String(s2.launched).slice(0, 4)),
            label: s2.city === 'New York' && s2.status !== 'operating' ? 'New York (1st)' : s2.city,
            ok: s2.status === 'operating',
            outcome: STATUS[s2.status]?.label ?? s2.status,
            lesson: s2.lesson,
          }))}
          tooltip={tip}
        />
        <Legend items={[
          { label: 'Operating', color: 'var(--good)' },
          { label: 'Failed', color: 'var(--critical)' },
        ]} />
        <Finding kicker="The shape of the record"
                 lede="Three failures inside four years, then seventeen years before anyone in North America tried again.">
          <p className="aside">
            Edinburgh lost a referendum in 2005, New York lost its first attempt in the
            legislature in 2008, and Manchester lost a referendum later that same year. New York
            did not charge until 2025. That gap is the argument for treating authorisation as
            seriously as price — losing an authorisation fight is not a delay, it is a generation.
          </p>
        </Finding>
      </Panel>

      <Panel
        title="Out-of-sample check against New York"
        sub="The only North American scheme, and the closest comparator this study has"
      >
        <div className="grid">
          <Tile label="New York's charge" value={fmt.dollars(ev.charge_usd, 0)}
                note="peak, passenger car, since 5 Jan 2025" />
          <Tile label="New York observed"
                value={fmt.signed(ev.observed_new_york_pct)}
                note="vehicles entering the zone, year one" />
          <Tile label="This model predicts"
                value={fmt.signed(ev.modelled_here_pct)}
                tone={ev.verdict === 'consistent' ? 'good' : 'bad'}
                note="AM-peak vehicles, same charge" />
          <Tile label="Verdict" value={ev.verdict}
                tone={ev.verdict === 'consistent' ? 'good' : 'bad'}
                note={`${fmt.n(Math.abs(ev.difference_pp), 1)} pp apart`} />
        </div>

        <Finding kicker="Out-of-sample" tone={ev.verdict === 'consistent' ? 'good' : 'bad'}
                 lede={ev.verdict === 'consistent'
                   ? 'The modelled response is the smaller of the two, which is the expected direction.'
                   : 'The modelled response is larger than New York’s, which is the wrong direction.'}>
          <p className="aside">{ev.reading}</p>
        </Finding>

        <div className="note">
          <b>Not like for like.</b>
          <ul>{ev.not_like_for_like.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
        <Caveat><b>What would settle it.</b> {ev.what_would_settle_it}</Caveat>
      </Panel>

      <Panel
        title="Where this design sits"
        sub="Against the range well-enforced schemes have actually produced"
      >
        <div className="grid">
          <Tile label="Modelled here" value={fmt.signed(pos.vehicle_change_pct)}
                note={`$${pos.charge_usd} screenline with credits`} />
          <Tile label="Operating schemes"
                value={`${Math.abs(pos.operating_range_pct[1])}–${Math.abs(pos.operating_range_pct[0])}%`}
                note="reduction in vehicle entries" />
        </div>
        <Finding kicker="Why lower"
                 lede="This design sits below the range the operating schemes produced.">
          <p className="aside">{pos.operating_range_note}</p>
        </Finding>
      </Panel>

      <Panel
        title="What each charge bought"
        sub="Charge against traffic reduction — plotted as two series, because the two bases price different events"
      >
        {(() => {
          const cr = pos.charge_response
          const pts = Object.entries(cr.groups).flatMap(([basis, rows]) =>
            rows.map((r) => ({
              label: r.city,
              charge: r.charge_usd,
              change: r.traffic_change_pct,
              basis,
              metric: r.metric,
              // Same three validated slots as the Suits chart, and the same
              // colour for this corridor in both -- an entity that changes
              // colour between two charts on one page is two entities to the
              // reader. The amber this used to carry sat at DE 13.7 from the
              // orange, below the normal-vision floor.
              color: basis === 'daily' ? KIND_COLOR.operating_charge : KIND_COLOR.proposed_charge,
            })))
          const all = [...pts, {
            label: 'This corridor', charge: pos.charge_usd, change: pos.vehicle_change_pct,
            basis: 'per_passage', metric: 'Modelled AM-peak vehicles across the screenline.',
            color: KIND_COLOR.here,
          }]
          return (
            <>
              <ScatterChart
                points={all}
                labels
                height={420}
                xKey="charge" yKey="change"
                xTitle="Peak charge (USD)"
                yTitle="Traffic change (%)"
                xFormat={(v) => fmt.dollars(v, 0)}
                yFormat={(v) => fmt.pct(v, 0)}
                highlight={(p) => p.label === 'This corridor'}
                tooltip={{
                  ...tip,
                  render: (p) => (
                    <TipBody title={p.label} rows={[
                      ['Charge', fmt.dollars(p.charge, 2)],
                      ['Basis', cr.basis_labels[p.basis] ?? p.basis],
                      ['Traffic', fmt.signed(p.change)],
                      ['Measured', p.metric],
                    ]} />
                  ),
                }}
              />
              <Legend items={[
                { label: cr.basis_labels.daily, color: KIND_COLOR.operating_charge },
                { label: cr.basis_labels.per_passage, color: KIND_COLOR.proposed_charge },
                { label: 'This corridor', color: KIND_COLOR.here },
              ]} />
              <Finding kicker="What actually moves the response"
                       lede="Price does not order the outcome.">
                <p className="aside">{cr.pattern.reading}</p>
              </Finding>
              <Caveat>
                <b>Two series, not one.</b> {cr.warning} {cr.no_fit_attempted}
              </Caveat>
            </>
          )
        })()}
      </Panel>

      <Panel
        title="Regressivity, against every published benchmark"
        sub="Suits index: 0 is proportional, negative is regressive. Sorted most regressive first."
      >
        <BarChart
          data={suits.map((b) => ({
            label: b.city,
            value: b.suits_index,
            kind: b.kind,
            kindLabel: b.kind_label,
            note: b.note,
            color: KIND_COLOR[b.kind] ?? SERIES[0],
          }))}
          diverging
          format={(v) => fmt.n(v, 2)}
          axisTitle="Suits index"
          tooltip={{
            ...tip,
            render: (d) => (
              <TipBody title={d.label} rows={[
                ['Suits index', fmt.n(d.value, 3)],
                ['Kind', d.kindLabel],
                ...(d.note ? [['Note', d.note]] : []),
              ]} />
            ),
          }}
        />
        <Legend items={[
          { label: 'Congestion charge, operating', color: KIND_COLOR.operating_charge },
          { label: 'Congestion charge, proposed', color: KIND_COLOR.proposed_charge },
          { label: 'This corridor', color: KIND_COLOR.here },
        ]} />

        <div className="note">
          <b>For scale, not for comparison.</b> These are not congestion charges and are
          deliberately not plotted with them — a charge is not made acceptable by being
          less regressive than a fuel tax. They are here because a reader with no feel
          for a Suits index has one for a sales tax.
          <div className="scale-strip">
            {taxes.map((t) => (
              <span key={t.city}>
                <b>{fmt.n(t.suits_index, 2)}</b> {t.city}
              </span>
            ))}
          </div>
        </div>
        {pos.more_regressive_than.length > 0 && (
          <Finding kicker="Regressivity" tone="bad"
                   lede={`This design is more regressive than ${pos.more_regressive_than.join(' and ')}.`}>
            <p className="aside">
              That is a finding, not a rounding error. A flat charge on a corridor whose
              lowest-income users have the weakest alternatives lands harder than a cordon
              around a dense city centre, whatever the headline rate.
            </p>
          </Finding>
        )}
      </Panel>

      <Panel
        title="Where the record contradicts this study"
        sub="Kept as a first-class result — a comparison that only finds corroboration is not being used as evidence"
      >
        {contradictions.map((c) => (
          <Finding key={c.claim_here}
                   tone={c.status === 'addressed' ? 'good' : c.severity === 'high' ? 'bad' : undefined}
                   kicker={c.status === 'addressed'
                     ? `${c.severity} severity — addressed`
                     : c.also_corroborates
                       ? `${c.severity} severity — cuts both ways`
                       : `${c.severity} severity — open`}
                   lede={c.claim_here}>
            <p className="aside"><b>The record:</b> {c.record}</p>
            <p className="aside">
              <b>{c.status === 'addressed'
                ? 'What changed:'
                : c.why_the_model_cannot_see_it ? 'Why the model cannot see it:' : 'Why it matters here:'}</b>{' '}
              {c.why_the_model_cannot_see_it ?? c.why_it_matters_here}
            </p>
            {/* An entry can cut both ways: Stockholm contradicts the claim that an
              * income instrument is required while corroborating this study's
              * geographic result. Rendering both identically was reading as a
              * single verdict it does not support. */}
            {c.also_corroborates && (
              <p className="aside"><b>But it corroborates:</b> {c.also_corroborates}</p>
            )}
            {c.how && <p className="aside"><b>Where:</b> <code>{c.how}</code></p>}
          </Finding>
        ))}
      </Panel>

      {(() => {
        // A panel that renders nothing while loading reads as a panel that does
        // not exist: this endpoint solves an equilibrium, so it is always the
        // last thing on the page to arrive.
        if (trustRun.error) return <ErrorBox error={trustRun.error} />
        if (!trustRun.data) {
          return (
            <Panel title="What people have to believe"
                   sub="Two of the contradictions above were the same missing mechanism">
              <Loading what="the trust analysis" />
            </Panel>
          )
        }
        const t = trustRun.data
        const s = t.sensitivity
        const be = s.breakeven_before_operation
        return (
          <Panel
            title="What people have to believe"
            sub="Two of the contradictions above were the same missing mechanism — this is what replaced it"
          >
            <p className="aside">
              A traveller votes on the position they <i>believe</i> they will be in, and before a
              scheme runs only one part of that is certain. You know the toll you will pay. Whether
              the road gets faster is a <i>forecast</i> that depends on other people changing their
              behaviour, and whether the revenue reaches you is a <i>promise</i>. Both are
              discounted, separately, by shares reported as thresholds rather than assumed — this
              corridor&rsquo;s levels are not observable.
            </p>

            <div className="grid">
              <Tile label="Support at full belief"
                    value={fmt.pct(100 * t.support_at_full_trust, 1)}
                    note="before operation" />
              <Tile label="Belief the vote needs"
                    value={be == null ? 'no level suffices' : fmt.pct(100 * be, 0)}
                    note={be == null ? 'resistance is to paying, not to the promise' : 'before operation'}
                    tone={be == null ? 'bad' : undefined} />
              <Tile label="Edinburgh, measured"
                    value={fmt.pct(100 * s.edinburgh_trust, 0)}
                    note="believed the revenue would reach transport" />
              <Tile label="The promise is worth"
                    value={fmt.money(t.efficacy.promised_per_trip)}
                    note="per trip — belief the money arrives" />
              <Tile label="The forecast is worth"
                    value={fmt.money(t.efficacy.forecast_per_trip)}
                    note="per trip — belief the charge works. The larger doubt" />
            </div>

            <LineChart
              height={250}
              xKey="believed"
              yKey="support"
              xTitle="Share believed"
              yTitle="Support before operation"
              format={(v) => fmt.pct(100 * v, 0)}
              xFormat={(v) => fmt.pct(100 * v, 0)}
              markers={false}
              tooltip={tip}
              series={[
                /* Both axes are a belief share 0-1, so they are directly
                 * comparable and the difference in slope IS the finding. */
                { name: 'Belief the charge works', color: SERIES[1],
                  data: t.efficacy.levels.map((r) => ({
                    believed: r.charge_efficacy_belief, support: r.support_before })) },
                { name: 'Belief the money arrives', color: SERIES[2],
                  data: s.levels.map((r) => ({
                    believed: r.revenue_trust, support: r.support_before })) },
                { name: 'Once operating', color: SERIES[0],
                  data: s.levels.map((r) => ({
                    believed: r.revenue_trust, support: r.support_after })) },
              ]}
            />
            <Legend items={[
              { label: 'Belief the charge works', color: SERIES[1] },
              { label: 'Belief the money arrives', color: SERIES[2] },
              { label: 'Once operating', color: SERIES[0] },
            ]} />
            <p className="aside">
              The steeper line is the finding: belief that the charge <i>works</i> moves support
              about six times as far as belief that the money arrives, because the forecast time
              saving is worth {fmt.money(t.efficacy.forecast_per_trip)} a trip against{' '}
              {fmt.money(t.efficacy.promised_per_trip)} for the revenue promise.
            </p>

            <Finding kicker="The two doubts" lede={t.two_beliefs}>
              <p className="aside">
                Only the toll is certain. The time saving is a <i>forecast</i> that depends on
                other people changing their behaviour; the recycled revenue is a <i>promise</i>.
                They are doubted separately, and on this corridor the forecast is much the
                larger of the two.
              </p>
            </Finding>

            <Finding kicker="The Manchester question" lede={t.manchester.reading}>
              <p className="aside">{t.package.manchester_note}</p>
              <Table
                rowKey={(r) => r.charge_efficacy_belief}
                columns={[
                  { key: 'e', label: 'Belief the charge works',
                    render: (r) => fmt.pct(100 * r.charge_efficacy_belief, 0) },
                  { key: 'x1', label: 'Support at 1× package',
                    render: (r) => fmt.pct(100 * r.points.find((p) => p.package_multiplier === 1).support, 1) },
                  { key: 'x8', label: 'at 8×',
                    render: (r) => fmt.pct(100 * r.points.find((p) => p.package_multiplier === 8).support, 1) },
                  { key: 'passes', label: 'Any package carries it?',
                    render: (r) => <Badge ok={r.any_package_passes}>{r.any_package_passes ? 'yes' : 'no'}</Badge> },
                ]}
                rows={t.manchester.series}
              />
              <p className="aside">
                The money is held <b>fully believed</b> here, because Manchester&rsquo;s £3bn was
                credible and the charge was what nobody believed in. The same table run by
                disbelieving the <i>money</i> instead is below — it reaches the same conclusion
                for the wrong reason.
              </p>
            </Finding>

            <Finding kicker="If the money is doubted instead" lede={t.package.reading}>
              <Table
                rowKey={(r) => r.revenue_trust}
                columns={[
                  { key: 'revenue_trust', label: 'Trust', render: (r) => fmt.pct(100 * r.revenue_trust, 0) },
                  { key: 'x1', label: 'Support at 1\u00d7 package',
                    render: (r) => fmt.pct(100 * r.points.find((p) => p.package_multiplier === 1).support, 1) },
                  { key: 'x8', label: 'at 8\u00d7',
                    render: (r) => fmt.pct(100 * r.points.find((p) => p.package_multiplier === 8).support, 1) },
                  { key: 'passes', label: 'Any package carries it?',
                    render: (r) => <Badge ok={r.any_package_passes}>{r.any_package_passes ? 'yes' : 'no'}</Badge> },
                ]}
                rows={t.package.series}
              />
              <p className="aside">
                Where recycling enters at face value, support is increasing and unbounded in the
                size of the package, so some package always wins. Each dollar now reaches the vote
                multiplied by trust, so the curve flattens below the threshold and no multiplier
                catches it.
              </p>
            </Finding>

            <Caveat>{t.what_it_does_not_do}</Caveat>
          </Panel>
        )
      })()}

      <Panel title="Every scheme that operates">
        <Table
          columns={[
            { key: 'city', label: 'City', render: (r) => <b>{r.city}</b> },
            { key: 'scheme', label: 'Scheme' },
            { key: 'launched', label: 'Since' },
            { key: 'charge_note', label: 'Charge' },
            { key: 'lesson', label: 'What it teaches' },
          ]}
          rows={operating}
          rowKey={(r) => r.key}
        />
      </Panel>

      <Panel
        title="And the three that failed"
        sub="Kept in the sample on purpose: comparing only against survivors is survivorship bias"
      >
        <Table
          columns={[
            { key: 'city', label: 'City', render: (r) => <b>{r.city}</b> },
            { key: 'launched', label: 'Year' },
            { key: 'status', label: 'Outcome',
              render: (r) => <Badge kind={STATUS[r.status]?.kind}>{STATUS[r.status]?.label ?? r.status}</Badge> },
            { key: 'lesson', label: 'What it teaches' },
          ]}
          rows={failed}
          rowKey={(r) => r.key}
        />
        <Caveat>{note}</Caveat>
      </Panel>

      <Panel
        title="Who each scheme lets off"
        sub="A charge's distribution is set as much by its exemptions as by its rate"
      >
        <Table
          columns={[
            { key: 'city', label: 'City', render: (r) => <b>{r.city}</b> },
            { key: 'regime', label: 'Exemptions and discounts' },
            { key: 'suits_index', label: 'Suits',
              render: (r) => (r.suits_index == null || Number.isNaN(r.suits_index)
                ? '—' : fmt.n(r.suits_index, 2)) },
          ]}
          rows={exemptions}
          rowKey={(r) => r.city + r.status}
        />
        <Finding kicker="The cautionary case" tone="bad"
                 lede="Gothenburg's company-car exemption roughly doubles the scheme's regressivity.">
          <p className="aside">
            It moves the Suits index from −0.06 to −0.13. An exemption granted for
            administrative convenience did more distributional damage than the rate ever did —
            which is the argument for deciding exemptions with the same care as the price.
          </p>
        </Finding>
      </Panel>

      {tip.node}
    </>
  )
}
