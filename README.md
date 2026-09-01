# Pricing the Western Gateway, Fairly

A Stackelberg congestion-pricing model for Toronto's Etobicoke–Gardiner western
gateway, Highway 427 to the Humber River, built for the UTTAN 2026 student
competition proposal.

The model answers the four questions the proposal poses: **where** pricing should
be tested, **what** the price should be, **who** should be protected, and **what**
should be done with the money — and it tests the charge against a serious
non-priced alternative rather than assuming pricing must win.

---

## Quick start

Two processes. Backend first.

```bash
cd backend && pip install -r requirements-local.txt && python run.py
```

```bash
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5178>. The API is on <http://127.0.0.1:8088>, with
interactive docs at <http://127.0.0.1:8088/docs>.

The first request calibrates the model (a few seconds) and everything after that
is cached.

Run the tests:

```bash
cd backend && python -m pytest tests/ -q
```

---

## What the model does

A five-link corridor is solved to a **stochastic user equilibrium**: travellers
pick the action with the lowest perceived generalized cost, but the cost of
driving depends on how many other people drive, and the fixed point of that loop
is found by the Method of Successive Averages.

Eight follower actions cover every response the proposal asks about — route,
mode, departure time, vehicle occupancy, and whether to travel at all:

| Action | What it represents |
|---|---|
| `drive_gardiner` | Pay the charge and stay on the expressway |
| `drive_lakeshore` | Exit before the gantry, run Lake Shore Blvd W, rejoin past it |
| `drive_queensway` | The secondary bypass via The Queensway |
| `carpool_gardiner` | HOV2+, splitting the per-vehicle charge |
| `shift_offpeak` | Retime into the shoulder |
| `go_rail` | Lakeshore West GO from Long Branch, Mimico or Park Lawn |
| `ttc` | Streetcar and Kipling subway feeder |
| `forgo_remote` | Work remotely or suppress the trip |

Choice is **nested logit**, not plain multinomial logit. Plain MNL imposes
independence of irrelevant alternatives, under which a driver priced off the
Gardiner is as likely to board a train as to divert onto Lake Shore. That would
systematically understate diversion — the single risk the study most needs to
measure. Setting every nest scale to 1.0 recovers MNL, and the scales are exposed
for sensitivity testing.

### The network, and why it is split at the Humber

```
gardiner_west    Hwy 427 → Humber River        ← the charged segment, 8.2 km
gardiner_east    Humber River → downtown       ← shared by everybody, 10.3 km
lakeshore_west   the City-road bypass of the charged segment
lakeshore_east   Lake Shore into downtown
queensway_west   the secondary bypass
```

The charged segment is only 8.2 km of a roughly 18.5 km trip. The cheapest way to
avoid a gateway charge is therefore not to stop driving but to **leave the
expressway before the gantry, run an arterial, and re-enter past it**. A
single-link corridor cannot represent that and reports an implausibly small
diversion effect. Because bypassers rejoin, diversion also partly defeats itself
— the shared downstream section gets busier — which is an emergent result rather
than an assumption.

### Link performance

```
t(v) = t_free + d_signal + t_free · α · (v/c)^β
```

`d_signal` is fixed control delay — signals on the arterials, ramp friction on
the freeway — that exists even at low volume. Splitting it out of the BPR term
matters: without it, a slow-but-uncongested arterial needs a huge α, which then
wildly overstates how much worse that arterial gets when traffic diverts onto it.

`β` is held at a literature value so it cannot trade off against `α`. `α` is
**fitted** so the base run reproduces observed peak travel times, on
`gardiner_west`, `gardiner_east` and `lakeshore_west`. The other two links
inherit the fitted arterial value and are **held out**, so their
predicted-versus-observed error is a genuine out-of-sample check.

### The 3D corridor view

The **Corridor & gantries** page renders the study area in 3D with
[MapLibre GL](https://maplibre.org) over [OpenFreeMap](https://openfreemap.org)
vector tiles. Both are open source and need **no API key, token or account**.

The links are drawn on their real alignments and coloured by modelled
volume/capacity under whichever policy is selected, so the map shows model
output rather than a basemap with pins on it. Switching between the
expressway-only and full-screenline options makes the diversion argument
visible: the arterials warm as traffic bypasses the gantry, then cool once the
bypass is priced too.

**If the map is blank**, open `/mapcheck`. It tests WebGL, the three
OpenFreeMap endpoints and the MapLibre lifecycle in order, and names the first
thing that fails. The most common cause is a background tab — browsers stop
issuing animation frames to one, and MapLibre drives its entire pipeline
(style load, tile requests, paint) from them, so it stalls before requesting a
single tile. The map now detects that and says so on screen instead of showing
an empty rectangle.

The basemap needs an internet connection. Nothing else on the page does.

---

## Repository layout

```
uttan-congestion/
├── backend/
│   ├── uttan/                  the model
│   │   ├── config.py           every parameter, in one place
│   │   ├── datasets.py         public-data loading with provenance
│   │   ├── network.py          BPR links, route composition, calibration
│   │   ├── demand.py           70 traveller segments, value of time
│   │   ├── generalized_cost.py the GC[i,a] term from the proposal
│   │   ├── choice_model.py     nested logit + constant calibration
│   │   ├── congestion.py       MSA fixed point → stochastic user equilibrium
│   │   ├── toll_policy.py      the leader's instrument set
│   │   ├── equity.py           burden, Suits index, credits, equity score
│   │   ├── incidence.py        who wins: four welfare components, STEPS
│   │   ├── geographic.py       burden by sub-area, income-independent variation
│   │   ├── political.py        acceptability, trust, ride-hail as 2nd follower
│   │   ├── finance.py          revenue under three cost cases
│   │   ├── metrics.py          congestion, mobility, diversion, emissions
│   │   ├── simulate.py         one scenario end to end + calibration cache
│   │   ├── game.py             Stackelberg search, Pigouvian, Pareto frontier
│   │   ├── phasing.py          the leader moves more than once: when to charge
│   │   ├── bargaining.py       City ↔ Province, Nash bargaining + side payments
│   │   ├── joint_game.py       both gates at once, and price × timing jointly
│   │   ├── reversion.py        does the delay reduction last? London says no
│   │   ├── rejoin_validation.py  the rejoin fraction against the record
│   │   ├── comparators.py      nine operating schemes, used as evidence
│   │   ├── site_selection.py   gateway screening with weight sensitivity
│   │   ├── sensitivity.py      tornado, Monte Carlo, convergence study
│   │   ├── precomputed.py      the on-disk cache and its config-hash guard
│   │   └── scenarios.py        the 23-scenario library
│   ├── api/main.py             FastAPI HTTP layer, 36 endpoints
│   ├── data/                   14 public-data files + provenance table
│   │   └── precomputed/        six cached responses, config-hash guarded
│   ├── scripts/precompute.py   regenerates that cache
│   └── tests/                  193 tests, 45 marked slow
├── frontend/                   React + Vite, 18 pages, hand-built SVG charts
├── api/index.py                re-exports the FastAPI app for Vercel
└── docs/
    ├── METHODS.md              modelling decisions and their justification
    └── DATA-REQUESTS.md        the four asks that coding cannot close
```

---

## The three game-theoretic results

**Pigouvian benchmark.** An entering vehicle feels its own travel time but
imposes `v · dt/dv` minutes of delay on everyone already on the link. Valued at
the average value of time of corridor users, the first-best charge on the tolled
segment is about **$9.73**. The untolled downstream section carries a larger
externality still — around $18 per vehicle — which a gateway charge cannot touch.
That gap is the clearest statement of why the answer is not simply "charge the
Pigouvian toll".

**Price of anarchy ≈ 1.14.** Letting travellers choose selfishly wastes about 14%
of total corridor travel cost against the least-cost allocation a uniform
screenline charge can reach — roughly $55M a year. That bounds what any pricing
policy can win here.

**Constrained leader search.** The authority searches price × window × coverage ×
credit structure, subject to a local-diversion cap, an equity floor, a minimum
congestion improvement, and transit capacity. Both the constrained winner and the
unconstrained one are reported, because the gap between them is the price the
corridor pays for protecting local streets and low-income travellers.

**The two enactment gates are not independent.** `P(enacted) = P(voters) ×
P(deal)` assumed they were. A scheme the public wants is cheaper to authorise, so
support enters the Province's political cost rate directly. It barely matters at
the assumed cost — the deal gate is not binding there — but at **$3.50 per
charged trip**, just below the **$3.91** the 2017 refusal implies, allowing the
gates to move together makes waiting for support **5.7× more valuable**. The
ranking never changes: independence was understating the case for building
support first, not reversing it.

**Price and timing solved together.** The sequencing game fixes the charge, so it
answers *when*. Solved jointly the answer is **$12 starting in year 1** — and the
price sits against the **equity floor**, not against public acceptability, because
support falls only about six points across a $2–$25 range (a larger charge also
recycles more). A study arguing about the price on acceptability grounds would be
arguing about the wrong constraint. Solving the two in sequence happens to reach
the same place here, because the best price is the same at every start year even
though the best year is not the same at every price.

---

## What the model found

These are model outputs under the stated assumptions, not advice.

- **The gateway choice is robust.** Etobicoke–Gardiner ranks first in about 96% of
  6,000 alternative criterion weightings, and TOPSIS agrees with the weighted sum.
  It also scores *worst of the five* on governance, which the screening states
  explicitly rather than burying.
- **A freeway-only charge leaks badly.** At $4 it pushes traffic onto The
  Queensway by roughly 12%, breaching the 10% local-diversion cap. Charging the
  full screenline removes the free bypass and turns diversion negative.
- **The recommended charge does not beat good operations on delay.** The
  no-charge operational package — adaptive signals, ramp management, transit
  priority, parking pricing, GO frequency — removes **45.2%** of peak delay. The
  recommended design removes **39.4%**, and a $5 screenline charge only **35.5%**.
  A charge only wins on delay if it is priced hard and compensated sparingly
  ($10 means-tested reaches **54.7%**), which is the opposite of the equity
  design the study recommends. **The two together reach 64.4%** — they are
  complements, and the case for a charge here rests on revenue, durability and
  demand management, not on delay.
  *(This reverses an earlier version, which had pricing winning by ~2 points.
  The operational package was understated by 11.2 points because the baseline
  was scored on the improved network — see `metrics.compute`.)*
- **And the delay reduction is a first-year effect.** Under background demand
  growth the recommended design's 39.4% falls to 34.7% over ten years with no
  policy change at all. London's went to nothing in five — but only because the
  freed road space was handed to buses and footway. Reproducing that here takes
  about 28% of the charged links' capacity, and at that point traffic is down
  *more* than at the start. **Pricing converts congestion into road space; what
  happens to the delay benefit depends on what you then spend it on.**
- **A single-corridor pilot is financially marginal.** Fixed collection costs do
  not scale down with the size of the scheme, so at modest charges the system can
  spend more collecting the money than it raises, especially once credits are paid.
- **A flat charge is regressive, and credits demonstrably fix part of it.** The
  lowest income quintile bears roughly 4.7× the burden of the highest as a share
  of income; the targeted credit package cuts that to about 2.2×, at the cost of
  some congestion relief and a lot of revenue.
- **Governance branch B is the most regressive option of all.** Charging only
  City-controlled arterials — the fallback if provincial authorisation never
  arrives — prices the road lower-income Lake Shore residents use while leaving
  the expressway free.

---

## Grounding in the equity literature

The equity and political-economy work follows five sources supplied as mentor
material, and the model implements their methods rather than citing them:

| Source | What it contributes |
|---|---|
| Eliasson (2016), *Is Congestion Pricing Fair?* (ITF DP 2016-13) | The four welfare components, the Suits index and its benchmarks, the consumer/citizen distinction, and the warning that averages hide the harmed subgroup |
| FHWA, *Income-Based Equity Impacts of Congestion Pricing* | Income / geographic / modal equity as three distinct types; the toll-account access barrier |
| Greenlining Institute (2020), *An Equity-First Approach* | Means-tested fees, revenue targeted at underinvested communities, charging the ride-hail platform not the driver |
| Shaheen et al. (2019), UC Berkeley TSRC | The STEPS framework (Spatial, Temporal, Economic, Physiological, Social) |
| SFCTA (2020) case studies; RPA (2019) | London, Stockholm and New York outcomes; the sequencing lesson and the support-before/after anchors |

Three results follow directly:

- **A flat charge is 17× more burdensome for the lowest income quintile than
  the highest**, as a share of income — while the highest quintile pays more in
  dollars. Both are true, and reporting only the second is how equity analyses
  mislead.
- **This corridor's flat design is more regressive than every operating
  congestion charge**, against the Suits benchmarks.
- **Equity design is what makes a scheme passable**, not a cost imposed on it:
  the means-tested and equity-first packages are the only designs that would win
  a vote today.

---

## Data and honesty

Every input carries a provenance tier, visible in the interface and in
`backend/data/sources.csv`:

- **PUBLISHED** — taken from a named public source (City of Toronto counts,
  Metrolinx business-case guidance, TTS occupancy, GO/TTC fares, CANCEA).
- **DERIVED** — computed from published values by a documented rule.
- **ESTIMATED** — a planning assumption. These are what the sensitivity analysis
  exists to test.

The most consequential ESTIMATED inputs are the western screenline demand, the
observed travel times used as calibration targets, and the fraction of bypassing
drivers who rejoin the expressway. The **Data & provenance** page lists the full
set of known limitations; they are worth reading before quoting any figure.

Working sources are listed in the interface and in `docs/METHODS.md`.

---

## Deploying

The app deploys to Vercel as a static SPA plus one Python serverless function.
`vercel.json` builds the frontend, serves `frontend/dist`, and rewrites
`/api/*` to `api/index.py`, which re-exports the same FastAPI app the local
server runs — there is no second copy of the API.

```bash
npm i -g vercel
vercel            # preview
vercel --prod     # production
```

No environment variables and no database. Every input is a file in
`backend/data/`, and the model is deterministic, so a deployment cannot drift
from what runs locally.

**Six endpoints are served from disk, not computed** — the rejoin validation,
the phasing game, the bargaining sweep, the joint game, the joint
price-and-timing solve and the gate-dependence sweep. Against a hard
ceiling of 60 s on Vercel Pro and 10 s on the free tier, the two heaviest were
originally measured at ~100 s and ~70 s. They are much faster now — the whole
regeneration is about 20 s on an M-series Mac, dominated by bargaining at ~10 s
— but serverless CPU is a good deal slower than a dev laptop and the free-tier
ceiling is 10 s, so the margin is still not there. They are generated once,
committed to `backend/data/precomputed/`, and served from there:

```bash
cd backend && python scripts/precompute.py     # ~20 s
```

This is a cache, not a second set of results, and two guards keep it that way.
Every file records a hash of the full model config and is refused if the
running config differs — so a parameter change makes the API *slower*, never
wrong. And `test_precomputed.py` recomputes each entry and compares, which is
the only check that catches a changed *solver* rather than a changed parameter.
Run it before deploying:

```bash
cd backend && python -m pytest tests/test_precomputed.py -q
```

`/api/meta` reports which entries are valid, and every affected response
carries `_source: "precomputed" | "computed"`, so a reader can always tell
which they are looking at.

Regenerate after any change to `config.py` or to the four cached modules. The
fingerprint guard means forgetting is slow rather than wrong.

Two consequences worth knowing. Cold starts recalibrate — a serverless process
does not survive between requests, so the first request to a cold instance pays
about 3 s of imports and calibration. And a non-default charge on those six
endpoints falls through to live computation, which works locally and will time
out on Vercel; no page in the interface requests one.

The Python bundle is capped at 250 MB unzipped. It currently sits near 117 MB.
`scipy` was a dependency for the life of the project, is imported nowhere,
and accounted for 123 MB on its own — if anything ever needs it, add it back
deliberately and re-check.

**Why the requirements files are named as they are.** The function installs
`api/requirements.txt`. `backend/requirements-local.txt` is for running the
model locally, and `backend/requirements-dev.txt` adds the test tooling. The
backend file is deliberately *not* called `requirements.txt`: the Vercel CLI
treats a `requirements.txt` beside a FastAPI app as a separate deployable
service, refuses to accept top-level `buildCommand` / `functions` /
`outputDirectory` alongside it ("the owning service is ambiguous"), and the
deploy fails before it starts. Renaming the file is what keeps this a single
project.

**Live:** <https://uttan-congestion.vercel.app>


## Caveats

This is a bounded-corridor planning model, not a GTHA network assignment and not
a microsimulation. There are no individual vehicles, queues, signals or
incidents. Emissions are a transparent proxy that moves with vehicle-kilometres
and time in stop-start conditions — enough to rank policies, not enough to quote
as an inventory. Ride-hailing and freight carry instruments but are not
separately calibrated. Nothing here constitutes legal, financial or statutory
advice on implementation.
