# Data requests

Four asks, in priority order. The first two are §11A-1 and A-2 of the handover
and dominate every other open item: `α` is fitted to observed travel times and
the demand total is interpolated, so every delay, revenue and equity figure in
the study is downstream of them.

This document exists because those items cannot be closed by modelling. Each
entry states **exactly what is wanted**, in what form, **why**, and **which
published result changes** if the answer differs from what is currently
assumed — so the value of each request is legible before anyone spends
goodwill asking for it.

**Provenance tiers** are those used throughout the model: `PUBLISHED` (named
public source), `DERIVED` (computed from published numbers by a documented
rule), `ESTIMATED` (a planning assumption). Every request below is an attempt
to move a specific input from `ESTIMATED` or `DERIVED` to `PUBLISHED`.

---

## Request 1 — Screenline volumes and probe travel times

**To:** City of Toronto, Transportation Services (Traffic Management Centre /
Data & Analytics)

**Priority:** highest. These are the two most consequential estimated inputs in
the model and both are routinely measured.

### What is wanted

**1a. AM peak volumes across the western screenline.** Directional hourly
counts, 06:00–10:00, an average weekday, most recent full year available, at:

| Location | Why |
|---|---|
| Gardiner Expressway east of Highway 427 | the charged segment |
| Gardiner Expressway at the Humber River | the downstream split |
| Lake Shore Blvd W east of Highway 427 | the primary bypass |
| Lake Shore Blvd W at the Humber River | the rejoin point |
| The Queensway east of Highway 427 | the secondary bypass |
| Park Lawn Rd and Royal York Rd ramps, both directions | ramp entry/exit |

Vehicle classification (light / heavy) if held, but **not** a blocker — the
totals alone would settle the central question.

**1b. Probe or Bluetooth travel times** for the same period and the same five
links, as an average weekday profile in 15-minute bins, with a measure of
spread (standard deviation or the 85th percentile) if available.

Any recent, stable period is acceptable **provided it is labelled**. A period
during the Section 3 lane reductions is still useful — see Request 3 — but it
must not be mistaken for a normal baseline.

### Why

The model currently uses **40,465 AM-peak inbound person-trips**, derived by
interpolating a 120,000 two-way weekday screenline volume between the published
140,000 system average and the 164,000 downtown count, then reducing to the
peak and the inbound direction. That is a documented rule applied to published
numbers, but it is not a count.

Observed peak travel times are `ESTIMATED`, and `α` in the link performance
curve is fitted to them in closed form. An error in an observed time propagates
directly into the fitted `α`, and `α` governs how much worse an arterial gets
when tolled traffic diverts onto it — which is the central risk the study
exists to measure.

### What changes if the answer differs

- **Every delay figure**, including the headline 39.4% of delay removed.
- **Revenue**, roughly linearly in the volume: net revenue is \$5.55M/yr on the
  current demand, and the scheme's financial viability is already marginal.
- **The out-of-sample validation.** Two links are held out and inherit the
  fitted arterial `α`, with errors of −6.3% and −3.0%. Those errors are the
  strongest evidence in the study that the curve captures something real; with
  observed times they become a genuine test rather than an internal check.
- **The diversion cap.** The cap binds at +11.6% on The Queensway under a \$4
  freeway-only charge — a finding that already sits close to its threshold.

---

## Request 2 — Transportation Tomorrow Survey extract

**To:** Data Management Group, University of Toronto
(<https://dmg.utoronto.ca>) — standard TTS data request

**Priority:** highest, jointly with Request 1.

### What is wanted

An AM peak (06:00–09:00) weekday extract of **work trips** with:

- **Origin:** traffic zones covering Etobicoke south of Eglinton, plus
  Mississauga east of Winston Churchill Blvd
- **Destination:** the City of Toronto core and the central waterfront
- **Cross-tabulated by:** primary mode, household income band, and origin zone
- **Plus:** auto occupancy for the same origin–destination pairs

The most recent survey year, with the prior year if a comparison is
inexpensive.

### Why

The 70-segment structure — 7 sub-areas × 5 income quintiles × fixed/flexible
schedule — is **Census-derived and synthetic**, not observed. The segmentation
is representative rather than measured, which is the single biggest limitation
on the equity results.

This matters more after this session's geographic work than before it. The
model now reports that travellers from outside Toronto pay **36.2%** of the
charge on **40.0%** of the trips — a ratio of 0.904, against 1.88 for New
Jersey at the New York cordon — and that the burden concentrates on **inner
Etobicoke** rather than the 905. That finding contradicts the obvious analogy
and is being reported as a result. It rests on a synthetic OD pattern.

### What changes if the answer differs

- **The whole geographic equity page.** The 40% west-GTA share, the pays-vs-uses
  ratios, the net-contributor gaps and the finding that Alderwood carries the
  heaviest burden are all downstream of the sub-area shares.
- **The City ↔ Province bargaining model.** The political-cost asymmetry that
  drives the entire governance result is derived from the non-Toronto demand
  share. If that share is materially different, so is the bargaining outcome.
- **The Suits index and every income-equity result**, which depend on the
  income distribution of corridor users rather than of residents generally.

---

## Request 3 — Section 3 construction counts (the natural experiment)

**To:** City of Toronto, Transportation Services — Gardiner Expressway
Rehabilitation, Section 3

**Priority:** high, and **time-critical**: the treatment period ends in
December 2026.

### What is wanted

Before / during volume counts and travel times at the Request 1 locations, for:

| Period | Status |
|---|---|
| Jan – Mar 2025 | before |
| Apr 2025 – Dec 2026 | Islington Ave 3 lanes → 2, from 2025-04-07 |
| May 2025 – Dec 2026 | Kipling Ave 3 lanes → 2, from 2025-05-05 |
| Aug – Dec 2026 | Park Lawn Rd westbound on-ramp **fully closed** from 2026-08-05 |

The ramp closure is the most valuable single item: **a closed ramp is the
closest physical analogue to a charging gantry anywhere in the record.** It is
westbound and therefore contra-peak for an AM inbound study, so counts in
*both* directions are needed for it to be usable.

### Why

The model assumes **55%** of drivers who bypass the charging point re-enter the
expressway past it. Nothing local has ever measured this. `rejoin_validation.py`
searched the public record and found:

- The natural experiment this study wants **is running now, on exactly the
  right segment**, and nobody has published a number from it.
- The only measured episode is Section 2 (Dufferin–Strachan, 2024), roughly
  8 km east of the screenline, with different bypass geometry.
- **Every published figure is a travel time.** No before/after volume count
  exists for either episode, so travel times must be inverted through the link
  performance curves to say anything about volumes at all.

Identifying the rejoin fraction requires a count **downstream of the split** —
at the Humber. That is the one measurement that would settle it, and it is
Request 1a, row 2.

### What changes if the answer differs

The study's **second headline finding**. A \$4 freeway-only charge is reported
as breaching the 10% local-street diversion cap at +11.6%. That claim **flips
at a rejoin fraction of 0.49**, against the assumed 0.55 — a margin of 0.06 on
a number nothing local has measured. The \$10 screenline recommendation is
robust across 0.20–0.90 and does not depend on it.

---

## Request 4 — Two interviews the proposal already commits to

**Priority:** medium. Both would convert a calibrated stance into an estimate.

### 4a. UTTRI — behavioural parameters and the rejoin fraction

Ask specifically about:

- **Gantry-hopping behaviour** and whether any Ontario study has measured
  bypass-and-rejoin at a tolled screenline. Note that Highway 407 has a
  parallel free alternative and a 25-year operating history — if anyone has
  measured this in Ontario, it is there.
- **The nested-logit scale and nest parameters.** The model's alternative-
  specific constants come out large, which is expected on a corridor where
  driving is slower and dearer than the train yet still carries a third of
  trips, but a local estimate would be better than an admission.
- **Value of time**, currently scaled from the Metrolinx \$24/hour peak auto
  figure with an income elasticity of 0.6 and a \$9.50/hour floor. The floor is
  a deliberate choice — without it, the constant-elasticity form implies delay
  to a low-income traveller is nearly free, which would bias every equity
  result toward finding that pricing helps the poor.

### 4b. Metrolinx — Lakeshore West peak capacity

The transit-capacity constraint in the leader's search is set by
`go_peak_capacity = 12,500` inbound AM-peak places. Ask for:

- Current and committed inbound AM-peak seated and total capacity at Mimico,
  Long Branch and Port Credit
- The GO Expansion delivery schedule for the Lakeshore West line
- Observed peak load factors

This matters because the phased game's recommendation — **charge as soon as the
transit uplift is delivered, and not a year later** — is built on a 25% capacity
uplift arriving on a two-year lag. Both numbers are assumptions.

---

## What would remain assumed even if all four were answered

Stating this plainly so no one over-claims what the data would buy:

- **Acceptability coefficients** are a calibrated stance, set to reproduce the
  Stockholm anchors (≈⅓ support before, ≈⅔ after). Eliasson fits an ordered
  logit to survey data this project does not have. Only a survey of corridor
  commuters would move this — §11A-3 suggests n ≈ 150 would be enough.
- **The political cost per charged trip** in the bargaining model. Its *level*
  is arbitrary; the result rests on the *ratio* between the two governments,
  which is derived from geography. The 2017 refusal gives a revealed lower
  bound of about \$3.91, and that is as far as inference goes.
- **The delivered-alternative bonus** in the phased game — the entire
  sequencing result rests on it.
- **Collection costs**, which change the *sign* of the financial answer and
  cannot be known before procurement.
- **Emissions**, which are a proxy rather than an inventory.

---

## Suggested covering note

> We are a University of Toronto student team preparing a submission for the
> UTTAN 2026 competition, modelling a peak-period congestion charge on the
> Gardiner's western gateway between Highway 427 and the Humber River — the
> City's own Section 3 rehabilitation segment.
>
> Our model is built entirely on public data and every input is tagged with its
> provenance, so a reader can see which results rest on assumptions. Two inputs
> currently carry more weight than we are comfortable with: the screenline
> demand, which we interpolate rather than count, and observed peak travel
> times, which we estimate and then fit our link performance curves to.
>
> We would be grateful for [specific items]. We are happy to work with whatever
> form the data is already held in, to sign an appropriate data agreement, and
> to share our model, methods and results with you. We would also be glad to
> credit Transportation Services in the submission, or not to, whichever you
> prefer.
>
> If a full extract is not practical, even a single directional AM-peak count at
> the Humber River would materially improve the study — it is the one
> measurement that would settle our most uncertain assumption.

---

## Tracking

| # | Request | To | Status | Would change |
|---|---|---|---|---|
| 1a | Screenline volumes | City Transportation Services | not sent | every delay and revenue figure |
| 1b | Probe travel times | City Transportation Services | not sent | the fitted `α`, hence all diversion |
| 2 | TTS extract | DMG, U of T | not sent | the whole geographic equity page |
| 3 | Section 3 counts | City, Gardiner Section 3 | not sent | the freeway-only leakage finding |
| 4a | Interview | UTTRI | not sent | rejoin fraction, choice parameters |
| 4b | Interview | Metrolinx | not sent | the transit-capacity constraint |
