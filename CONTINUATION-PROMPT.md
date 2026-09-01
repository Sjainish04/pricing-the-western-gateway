# Continuation prompt

Paste the block below into a fresh session to pick this project up with full
context. Delete the "What I want you to do next" section at the end and replace
it with whatever you actually want.

Last refreshed 2026-08-31, against a working tree with 193 tests passing.

---

```
You are continuing work on an existing, working project. Read this whole brief
before touching anything, then read README.md and docs/METHODS.md in the project
root. HANDOVER-2026-08-19.md and HANDOVER-2026-08-20.md are dated records of how
it was built — useful history, but this brief supersedes them where they differ.

## The project

A bounded-corridor Stackelberg game modelling a peak-period congestion charge on
Toronto's Gardiner Expressway western gateway (Highway 427 to the Humber River),
built for the UTTAN 2026 Student Competition (team: Bahar Shahkaram, Siddhartha
Pahari, Jainish Solanki, University of Toronto).

Built 2026-08-18 to 2026-08-20 in three sessions. State: working end to end,
193 tests passing, deployed at https://uttan-congestion.vercel.app.
Roughly 10,800 lines of Python and 7,700 of frontend.

It answers the four questions the source proposal poses — where to price, what
the price should be, who to protect, what to do with the money — and tests the
charge against a serious non-priced alternative rather than assuming pricing wins.

## Running it

Backend first, because the frontend proxies /api to it:
  cd backend && pip install -r requirements-local.txt && python run.py   -> :8088
  cd frontend && npm install && npm run dev                              -> :5178
  cd backend && python -m pytest tests/ -q            193 tests, ~72s
  cd backend && python -m pytest tests/ -q -m "not slow"   148 tests, ~5s

requirements-local.txt is the runtime set and requirements-dev.txt adds pytest
and httpx. The backend file is deliberately NOT called requirements.txt: the
Vercel CLI treats a requirements.txt beside a FastAPI app as a separate
deployable service and then refuses every top-level buildCommand / functions /
outputDirectory with "the owning service is ambiguous". Renaming it is what
keeps this a single project. api/requirements.txt is what the function installs.

Use localhost, NOT 127.0.0.1, for the frontend: Vite binds IPv6 ::1, so
http://127.0.0.1:5178 refuses the connection. The backend accepts both.

## Architecture

backend/uttan/  (26 modules)
  config.py           every parameter in one place
  datasets.py         public-data CSVs, each input tagged PUBLISHED/DERIVED/ESTIMATED
  network.py          5-link BPR network, route composition, alpha calibration
  demand.py           70 traveller segments, value of time
  generalized_cost.py GC[i,a] = beta_t*T + C + tau + S + R - D
  choice_model.py     nested logit, ASC calibration, logsum welfare measure
  congestion.py       Method of Successive Averages -> stochastic user equilibrium
  toll_policy.py      leader's instrument set, 10 credit mechanisms
  equity.py           who PAYS: Suits index + concentration curve, burden
  incidence.py        who WINS: 4 welfare components, STEPS, Suits benchmarks
  geographic.py       burden by sub-area; income explains only 46% of it
  political.py        acceptability (3rd game level) + trust, ride-hail follower
  finance.py          revenue under low/medium/high cost cases
  metrics.py          congestion, mobility, diversion, emissions
  simulate.py         one scenario end to end + calibration cache
  game.py             Stackelberg search, Pigouvian, price of anarchy, Pareto
  phasing.py          the leader moves more than once: WHEN to charge
  bargaining.py       City <-> Province, Nash bargaining + side payments
  joint_game.py       both gates at once, and price x timing jointly
  reversion.py        does the delay reduction last? London says no
  rejoin_validation.py  the 55% rejoin fraction against the Gardiner record
  comparators.py      nine real schemes, used as evidence not decoration
  site_selection.py   gateway screening + Dirichlet weight sensitivity
  sensitivity.py      tornado, Monte Carlo (Latin hypercube), convergence study
  precomputed.py      on-disk cache + config-hash guard
  scenarios.py        23-scenario library
backend/api/main.py   FastAPI, 36 endpoints
backend/scripts/precompute.py  regenerates the cache
frontend/src/pages/   18 pages; components/charts.jsx is hand-built SVG
docs/METHODS.md       every modelling decision and why
docs/DATA-REQUESTS.md the four asks that coding cannot close

## The model in brief

Network split at the Humber — this is the most consequential structural choice:
  gardiner_west   Hwy 427 -> Humber      the charged segment, 8.2 km
  gardiner_east   Humber -> downtown     shared by everybody, 10.3 km
  lakeshore_west  City-road bypass of the charged segment
  lakeshore_east  Lake Shore into downtown
  queensway_west  secondary bypass
The charged segment is 8.2 km of an 18.5 km trip, so the cheapest evasion is
exiting before the gantry and rejoining past it. A single-link corridor reported
+0.5% diversion at $4 (implausible); split, it reports +11.6% on The Queensway.

Eight follower actions (drive, two bypasses, carpool, retime, GO, TTC, don't
travel). Nested logit, not MNL — MNL's IIA would make a priced-off driver as
likely to board a train as to divert, understating the study's central risk.

70 segments = 7 sub-areas x 5 income quintiles x fixed/flexible schedule.
Transit access is a property of the sub-area. Mississauga/west GTA is 40% of
demand, so many of those charged are not Toronto residents.

Link performance: t(v) = t_free + d_signal + t_free*alpha*(v/c)^beta, beta fixed
at 4.5, alpha fitted on three links. Two links are HELD OUT and inherit the
fitted arterial alpha; their errors (-6.3%, -3.0%) are a real out-of-sample
check. Mode-share error 0.037 pp.

## Game theory (three levels: leader -> travellers -> voters)

  Pigouvian first-best, charged segment    $9.73
  Pigouvian, untolled downstream section   $18.34   <- larger, and untouchable
  Welfare-maximising uniform screenline    $15.50
  Price of anarchy                         1.140  ($55.9M/yr wasted)

Constrained leader search over price x window x coverage x credit, subject to
diversion cap, equity floor, minimum congestion improvement, transit capacity,
and acceptability. Both the constrained and unconstrained winners are reported.

Acceptability is modelled from Eliasson's consumer perspective (own net position)
and citizen perspective (whether pricing is seen as a fair allocation mechanism
at all, which rises with income), plus an experience shift. It reproduces the
Stockholm anchors (~38% support before, ~61% after). It is tested AFTER
operation, because requiring majority support up front would rule out every
charge ever built.

TWO BELIEFS. A traveller votes on the position they BELIEVE they will be in, and
before a scheme runs only the toll is certain. The time saving is a FORECAST
(discounted by `cfg.charge_efficacy_belief`) and the recycled revenue is a
PROMISE (discounted by `cfg.revenue_trust`). They are separate doubts and on
this corridor the forecast is worth $1.68 a trip against $0.28 for the promise
-- about six times larger -- so disbelief in the CHARGE moves support 38.0% ->
23.6% where disbelief in the MONEY moves it only to 35.3%. Efficacy applies only
before operation; afterwards the `experience` coefficient already carries it and
discounting twice would break the Stockholm anchors. This exists
because Edinburgh lost 74.4-25.6 on trust rather than economics (one in four
believed the revenue would reach transport) and Manchester lost with GBP 3bn
attached -- neither reachable in a model where recycling enters at face value,
since there a large enough package always wins. It defaults to 1.0 (full belief),
which reproduces every earlier result bit-identically, and the level is INVERTED
rather than tuned: `political.trust_sensitivity` reports the threshold the
recommendation requires. On this corridor trust is NOT the binding constraint --
the promise is worth $0.28 a trip against a $2.35 toll, so disbelieving all of it
moves support only 38.0% -> 35.3%. The Manchester test holds the money FULLY believed and
varies belief in the charge: no package up to 8x carries the vote at 50% belief
or below, which is the actual Manchester failure (its GBP 3bn was credible; the
charge was not).

Ride-hailing is a second follower choosing pass-through, which comes out interior.

Current recommendation: $10, full western screenline, 06:30-09:30, income +
transit-poor credits. -7.6% peak vehicles, 39.4% delay removed, ~$5.5M net
revenue, equity score 0.562, support 38% -> 61%.

## The three modules the last session added, and what they found

SEQUENCING (phasing.py). At an identical $10 charge, expected discounted welfare
over ten years ranges from 0.429 (transit, pilot, then referendum — the Stockholm
path) to -0.131 (charge immediately — the NYC 2008 path). 0.56 welfare points
separate the best ordering from charging now, at the same price. None of it is a
better policy; all of it is a better chance the policy exists. The pilot does
most of the work. Interior optimum at year 1.

BARGAINING (bargaining.py). The 2027 Gardiner transfer does NOT work the way it
looks. The repair liability moving City -> Province cancels out of the bargain: a
lump sum shifts a player's deal and no-deal payoffs equally. What changes is the
Province's FALLBACK — after the transfer it owns the road and authorises itself,
so it gains the option of a freeway-only charge, which this model finds pushes
+11.6% onto City streets. The political-cost rate is unobservable, so it is
inverted rather than tuned: the zone of agreement closes at $3.91 per charged
trip pre-transfer and $8.75 post. The Province did refuse in 2017, so its
valuation sits above the pre-transfer threshold — a revealed bound from a real
decision.

DEPENDENT GATES (joint_game.gate_dependence_sweep). P(enacted) = P(voters) x
P(deal) assumed independence. Support now enters the Province's political cost
rate -- authorising an unpopular scheme costs more -- as a rotation about the 50%
referendum threshold, so `gate_dependence` defaults to 0 and nothing computed
under independence moves. It barely matters at the assumed $0.90 (the deal gate
does not bind, P(deal) ~ 0.997 either way) but at $3.50, just below the $3.91 the
2017 refusal implies, waiting for support becomes 5.69x more valuable. The
RANKING never changes at any cost or dependence tested: independence understated
the case for building support first rather than reversing it.

JOINT PRICE AND TIMING (joint_game.joint_optimum). Solved together the answer is
$12 starting year 1. The price sits against the EQUITY FLOOR, not against
acceptability: support falls only ~6 points across $2-$25 because a larger charge
also recycles more, so an unconstrained solve just runs to the grid edge ($16+).
Sequential solving reaches the same place here because the best charge is the
same at every start year, though the best year is NOT the same at every charge --
the asymmetry is why the order matters. Below $8 P(deal) is zero: a charge too
small to be worth collecting is also too small to be worth authorising.

JOINT (joint_game.py). P(enacted) = P(voters) x P(deal). At the assumed political
cost the deal gate does not bind and the joint answer is the phased one. But
sweeping the cost, the recommendation REVERSES at $3.50 — just below the $3.91
the 2017 refusal implies — to "wait until after the transfer". Both arguments are
reported; which dominates is empirical and this study cannot settle it.

## Equity, grounded in six mentor PDFs from Dr Imran

The model IMPLEMENTS their methods rather than citing them:
  Eliasson ITF DP 2016-13     four welfare components, Suits benchmarks,
                              consumer/citizen split, concentration warning
  FHWA income-equity primer   income/geographic/modal equity, toll-account barrier
  Greenlining equity-first    means-tested fees, charge the ride-hail platform
  Shaheen (UC Berkeley TSRC)  STEPS framework
  SFCTA case studies, RPA     London/Stockholm/NYC outcomes, sequencing lesson

NOTE: poppler may not be installed, in which case the Read tool FAILS on PDFs.
Extract with pypdf to the scratchpad first.

The central equity result — under a flat $10 screenline charge:
                          Q1 ($24k)    Q5 ($215k)
  toll paid per trip        $2.43        $5.48
  welfare loss, % income   -1.82%       -0.11%
Q5 pays more than twice the dollars; Q1 loses 17x more of its income. Both are
true, and reporting only the first is how equity analyses mislead.

Welfare components 1-3 are computed exactly as the change in the nested-logit
logsum (compensating variation), verified against an analytic case: raising every
option by $5 costs exactly $5 of surplus.

Suits benchmarks from real schemes: Stockholm -0.09, Helsinki -0.09, Gothenburg
-0.13, Lyon -0.16; US sales tax -0.11, Texas fuel tax -0.25. This corridor's flat
design (-0.196) is MORE regressive than every operating charge.

Revenue recycling is capped at recycling_capture_share = 0.5 and reported both
before and after. Crediting 100% of net revenue back to the 40,465 corridor
travellers made every revenue-positive scheme a Pareto improvement — an artefact.
Before recycling, a flat $10 charge leaves 0% of travellers better off.

## Headline findings

1. Gateway choice is robust: Etobicoke-Gardiner wins 95.8% of 6,000 alternative
   criterion weightings; TOPSIS agrees. It also scores worst of five on
   governance, which the screening states rather than buries.
2. A freeway-only charge leaks badly: $4 pushes +11.6% onto The Queensway,
   breaching the 10% cap. Full screenline coverage turns diversion negative.
   BUT this finding flips at rejoin_fraction 0.49 and the assumed value is 0.55
   — a margin of 0.06 in a number nothing local has measured. Quote
   breakeven_rejoin_fraction() rather than implying the leak is certain. The
   recommendation itself does not depend on it.
3. The recommended charge does NOT beat good operations on delay: the no-charge
   operational package removes 45.2%, the recommended design 39.4%, a $5
   screenline charge 35.5%. A charge only wins on delay if priced hard and
   compensated sparingly ($10 means-tested, 54.7%). Together they reach 64.4%.
   They are complements, and the case for a charge rests on revenue, durability
   and demand management, not delay. (This REVERSES the earlier finding that
   pricing won by ~2 points -- see the metrics.compute bug below.)
3b. The delay reduction is a FIRST-YEAR effect. Background growth takes 39.4%
   to 34.7% over ten years. London's went to zero in five, but only because the
   freed road space was reallocated; reproducing that here needs ~28% of the
   charged links' capacity handed over, and at that point traffic is down MORE
   than at the start. Pricing converts congestion into road space -- what
   happens to delay depends on what you spend it on. See reversion.py.
4. A single-corridor pilot is financially marginal: fixed collection costs don't
   scale down, so at modest charges it can spend more collecting than it raises.
5. Equity design is what makes a scheme PASSABLE, not a cost imposed on it.
6. Governance branch B (City arterials only) is the most regressive option of
   all: it prices the road lower-income Lake Shore residents use while leaving
   the expressway free.
7. Sequencing is worth more than the price (see phasing.py above).

## Two claims that were overturned by later work — do not restate the old ones

THE CORRIDOR IS NOT THE NEW JERSEY CASE. An earlier handover said this model
reproduced FHWA's NYC finding (NJ residents paying 45% of tolls on 24% of trips,
ratio 1.88). It does not. Under the recommended design the 905 pays 36.2% of the
charge on 40.0% of trips — ratio 0.904 — and receives 44.4% of the recycled
benefit, making it a NET RECIPIENT by 8 points. Lakeshore West GO gives west-GTA
travellers a way out and enough take it. The burden lands on inner Etobicoke
instead: Alderwood at 0.81% of household income. If the submission claims a
905-pays-disproportionately story it is wrong, and a judge with the FHWA paper
open will catch it.

THE 2027 LEVERAGE STORY REVERSES. See joint_game.py above: on the model's own
revealed bound the advice is to wait until after the transfer, not to rush a deal
before it.

## How to work on this codebase

The failure mode here is NOT crashes. Every serious bug found so far produced a
plausible-looking NUMBER. Eighteen are listed across the two handovers; the
pattern to internalise:
  - a sign convention silently inverted a conclusion (Suits index)
  - a per-vehicle charge divided per-person for only one alternative
  - a transfer counted in one account but not the other (parking surcharge)
  - a benefit credited at face value to too small a population (recycling)
  - a missing dict key defaulted to 0.0 and zeroed an entire mechanism
So: verify new quantities against cases with known answers, and add a regression
test that pins the PROPERTY rather than the output value. A pinned value would
not have caught the two bugs found on 2026-08-31, both below.

TIES AND UNSTABLE SORTS. The Suits index walked segments in np.argsort(income)
order, but income takes only five distinct values, so all 70 segments arrive in
14-way ties carrying very different burdens — and argsort defaults to an UNSTABLE
quicksort. The index moved with the tie order (by 0.045-0.089, wider than the
gaps between the benchmarks it is compared against) and was not reproducible
across numpy versions. Fixed by aggregating each income level to one point.
Anywhere else this codebase sorts a quantity with ties, check the same thing.

A METRIC SCORED BOTH SIDES ON THE SCENARIO'S NETWORK. `metrics.compute` took one
link set and used it for the scenario AND the baseline. Every "against baseline"
figure is a ratio, so evaluating baseline volumes on an improved network shrinks
the denominator and a scenario is charged for the improvement it made while
credited with none of it. The no-charge operational package was understated by
11.2 points, which reversed a headline finding. It survived because a pure-price
scenario changes no capacity, so for most of the library the two networks were
the same object and the bug was invisible. Pass `base_links` whenever a scenario
touches capacity.

PANDAS 3.0 BROKE A JSON GUARD SILENTLY. datasets.records() used
df.where(pd.notna(df), None) to turn missing cells into None; in pandas 3.0 that
stopped substituting and the value came back as nan. Nothing failed loudly —
FastAPI normalises nan to null on the way out, and every in-process consumer
happened to test for both — so the only symptom was the precomputed cache test.
Converting per value depends on no pandas behaviour at all.

PERFORMANCE: profile before assuming numpy is the bottleneck — it never is in
this codebase; pandas row iteration is. Caching route_composition() took a
scenario run from 1160ms to 9ms. Later, adding rejoin_fraction to the Monte Carlo
made every draw a cache miss and took the suite from 30s to 3h58m. ANY parameter
added to a sweep that is read inside the equilibrium loop will do this again.
Check the suite's wall-clock after adding one.

SENSITIVITY analysis holds the choice constants FIXED at the central config.
Re-fitting them per draw is circular: they absorb the parameter and the analysis
reports near-zero sensitivity.

THE PRECOMPUTED CACHE. Four endpoints (rejoin, phasing, bargaining, joint) are
served from backend/data/precomputed/ because they exceed Vercel's function
timeout. Every file stores a hash of the FULL model config and is refused if the
running config differs, so a parameter change makes the API slower, never wrong.
test_precomputed.py recomputes and compares, which is the only check that catches
a changed SOLVER rather than a changed parameter. Regenerate after any change to
config.py or to those four modules:
  cd backend && python scripts/precompute.py && python -m pytest tests/test_precomputed.py -q
On an M-series Mac the whole regeneration is ~20s; the ~100s/~70s figures in the
handovers were measured on slower hardware. The Vercel timeout argument still
holds — serverless CPU is much slower than a dev laptop.

WEBGL MAPS DO NOT RENDER in the Claude Code preview pane and never will — it
keeps document.visibilityState permanently "hidden", so requestAnimationFrame
never fires and MapLibre stalls before requesting a tile. Calling _render()
manually freezes the renderer. Leaflet works there (DOM img tiles). The app
probes webgl && rAF up front and falls back to a 2D Leaflet map, AND accepts a
runtime failure report from the 3D map, because a pre-flight probe alone is not
enough. Verify map geometry numerically in Node, not visually.

## Known limitations — do not quote figures without these

- Screenline demand is DERIVED, not counted (120k two-way weekday, interpolated).
- Observed travel times are ESTIMATES, and alpha is fitted to them.
- The OD pattern is synthetic (Census-derived, not a TTS extract).
- The 55% rejoin fraction drives the diversion result and has no local
  observation behind it. Finding #2 above flips at 0.49.
- Collection costs are assumed and change the SIGN of the financial answer.
- Acceptability coefficients are a calibrated stance, not estimates.
- Emissions are a proxy, not an inventory.
- Physiological and Social equity (STEPS) are not modelled at all, and say so.
- The New York comparison is UNRESOLVED, not passed: the model predicts -13.1%
  at $9 against -11% observed, and the leading explanation (different quantities
  — year-round all-day zone entries vs AM-peak screenline) is plausible but not
  established. If it survives a like-for-like comparison, the demand response is
  too strong.
- Version control: the canonical repo has 13 commits on the original author's
  machine. Check whether the working tree you are in is a git repo at all before
  assuming a diff exists.

## What I want you to do next

<< Replace this section with your actual request. The current ranked backlog:
  1. The data requests (docs/DATA-REQUESTS.md) still dominate everything: a real
     screenline count and probe travel times, and a TTS extract for the OD
     pattern. Every figure above is downstream of them.
  2. Ask the City for Gardiner Section 3 counts. The natural experiment this
     study wants is running right now on the charged segment — Islington and
     Kipling at 3 lanes -> 2 since April 2025, Park Lawn westbound on-ramp
     closed since August 2026 — and nobody has published a number from it. A
     ramp closure is the closest physical analogue to a gantry in the record,
     and it would move the rejoin fraction off ESTIMATED.
  3. Settle the New York comparison like-for-like. The MTA publishes CRZ entries
     by hour, so the -13.1% vs -11% gap is resolvable, and it is the highest-
     value open item on the comparison page.
  4. Survey corridor commuters (n ~ 150). The acceptability coefficients are the
     newest and least grounded part of the model and the sequencing result rests
     on one of them.
  5. Reproduce Edinburgh's finding that car ownership predicted the vote better
     than income did. The segments carry transit access, which is related but
     not the same thing. >>

Work in the existing style: dense, specific comments that explain WHY a choice
was made and what breaks otherwise; tests that pin properties not outputs; and
say plainly when something is an assumption rather than a measurement.
```
