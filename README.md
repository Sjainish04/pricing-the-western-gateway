# Pricing the Western Gateway, Fairly

### A Stackelberg Congestion-Pricing Model for Toronto’s Etobicoke–Gardiner Western Gateway

A decision-support and policy simulation platform developed for the **UTTAN 2026 Student Competition**, focused on Toronto’s western gateway from **Highway 427 to the Humber River**.

The model is built around four practical policy questions:

1. **Where** should congestion pricing be tested?
2. **What** should the charge be?
3. **Who** should be protected from disproportionate burden?
4. **How** should the resulting revenue be used?

Rather than assuming road pricing is the preferred intervention, the framework tests it against a serious **non-priced operational alternative** and evaluates each policy across congestion, diversion, equity, financial, political, and implementation constraints.

> **Important:** Results reported in this repository are model outputs under stated assumptions. They are not legal, financial, statutory, or implementation advice.

---

## At a Glance

| Component | Implementation |
|---|---|
| Study corridor | Highway 427 → Humber River → Downtown Toronto |
| Network | Five-link bounded corridor |
| Traveller response | Eight route, mode, timing, occupancy, and trip-suppression actions |
| Choice model | Nested logit |
| Congestion solution | Stochastic user equilibrium via Method of Successive Averages |
| Policy framework | Stackelberg leader–follower optimization |
| Equity analysis | Income burden, Suits index, credits, geographic and modal equity, STEPS |
| Policy search | Price × timing × coverage × credit structure |
| Robustness | Weight sensitivity, tornado analysis, Monte Carlo, convergence checks |
| Backend | Python + FastAPI |
| Frontend | React + Vite |
| Mapping | MapLibre GL + OpenFreeMap |
| Deployment | Vercel |
| Test suite | 193 tests, including 45 slow tests |

**Live application:** <https://uttan-congestion.vercel.app>

---

## Contents

- [Quick Start](#quick-start)
- [How the Model Works](#how-the-model-works)
- [Network Design](#network-design)
- [Link Performance and Calibration](#link-performance-and-calibration)
- [3D Corridor View](#3d-corridor-view)
- [Repository Structure](#repository-structure)
- [Game-Theoretic Results](#game-theoretic-results)
- [Key Model Findings](#key-model-findings)
- [Equity and Political-Economy Grounding](#equity-and-political-economy-grounding)
- [Data Provenance and Model Transparency](#data-provenance-and-model-transparency)
- [Deployment](#deployment)
- [Scope and Limitations](#scope-and-limitations)

---

## Quick Start

The application runs as two local processes. Start the backend first.

### 1. Start the backend

```bash
cd backend
pip install -r requirements-local.txt
python run.py
```

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Open the application

- Frontend: <http://localhost:5178>
- API: <http://127.0.0.1:8088>
- Interactive API documentation: <http://127.0.0.1:8088/docs>

The first request calibrates the model and may take a few seconds. Subsequent requests use the calibration cache.

### 4. Run the test suite

```bash
cd backend
python -m pytest tests/ -q
```

---

## How the Model Works

The corridor is solved to a **stochastic user equilibrium**. Travellers select the action with the lowest perceived generalized cost, but the cost of driving itself depends on how many other travellers choose to drive. The resulting fixed point is solved using the **Method of Successive Averages (MSA)**.

The model includes eight follower actions spanning route choice, travel mode, departure time, vehicle occupancy, and whether the trip occurs at all.

| Action | Interpretation |
|---|---|
| `drive_gardiner` | Pay the charge and remain on the expressway |
| `drive_lakeshore` | Exit before the gantry, use Lake Shore Blvd W, and re-enter beyond it |
| `drive_queensway` | Use the secondary bypass through The Queensway |
| `carpool_gardiner` | Travel HOV2+, splitting the per-vehicle charge |
| `shift_offpeak` | Shift departure into the shoulder period |
| `go_rail` | Use Lakeshore West GO from Long Branch, Mimico, or Park Lawn |
| `ttc` | Use streetcar and Kipling subway feeder services |
| `forgo_remote` | Work remotely or suppress the trip |

### Why nested logit?

Traveller choice is represented using **nested logit**, rather than plain multinomial logit (MNL).

Plain MNL imposes independence of irrelevant alternatives. In this context, that can imply that a driver priced off the Gardiner is as likely to board a train as to divert onto Lake Shore. That would systematically understate diversion, which is one of the central risks the study is designed to measure.

Setting every nest scale to `1.0` recovers MNL, and those scales remain exposed for sensitivity testing.

---

## Network Design

### Why the corridor is split at the Humber

```text
gardiner_west    Hwy 427 → Humber River        ← charged segment, 8.2 km
gardiner_east    Humber River → downtown       ← shared downstream segment, 10.3 km
lakeshore_west   City-road bypass of the charged segment
lakeshore_east   Lake Shore into downtown
queensway_west   secondary bypass
```

The charged section represents only **8.2 km of an approximately 18.5 km trip**. For many drivers, the lowest-cost response to a gateway charge is therefore not to stop driving, but to **leave the expressway before the gantry, travel on an arterial, and re-enter beyond the priced segment**.

A single-link corridor cannot represent this behaviour and consequently produces an implausibly small diversion effect.

The split network also captures an important endogenous effect: bypassing drivers eventually rejoin the corridor, so diversion can partly defeat itself by increasing traffic on the common downstream section. That outcome emerges from the network structure rather than being imposed as an assumption.

---

## Link Performance and Calibration

Link travel time is represented as:

```text
t(v) = t_free + d_signal + t_free · α · (v/c)^β
```

Where:

- `t_free` is free-flow travel time,
- `d_signal` is fixed control delay,
- `v` is traffic volume,
- `c` is capacity,
- `α` controls congestion sensitivity, and
- `β` governs the curvature of the congestion response.

### Why fixed control delay is separated

`d_signal` captures delay that exists even at low traffic volumes, including arterial signals and freeway ramp friction. Separating this term from the BPR congestion function avoids forcing a slow-but-uncongested arterial to use an unrealistically large `α`, which would otherwise exaggerate the effect of diverted traffic.

### Calibration strategy

`β` is held at a literature value so that it cannot trade off against `α` during fitting.

`α` is **calibrated** so the base model reproduces observed peak travel times on:

- `gardiner_west`
- `gardiner_east`
- `lakeshore_west`

The remaining two links inherit the fitted arterial value and are **held out**, making their predicted-versus-observed error a genuine out-of-sample validation check.

---

## 3D Corridor View

The **Corridor & gantries** page renders the study area in 3D using [MapLibre GL](https://maplibre.org) over [OpenFreeMap](https://openfreemap.org) vector tiles. Both are open-source and require **no API key, token, or account**.

Network links are drawn on their real alignments and coloured according to modelled **volume-to-capacity ratios** under the selected policy. The visualization therefore displays model output directly rather than placing simple pins on a basemap.

Switching between **expressway-only** and **full-screenline** pricing makes the diversion mechanism visible: arterial links intensify as traffic bypasses the gantry and then cool when the bypass itself is included in the pricing screenline.

### Map troubleshooting

If the map is blank, open:

```text
/mapcheck
```

The diagnostic checks, in order:

1. WebGL support,
2. the three OpenFreeMap endpoints, and
3. the MapLibre lifecycle.

It reports the first failure it encounters.

A common cause is a background browser tab. Browsers can suspend animation frames for inactive tabs, while MapLibre depends on those frames for style loading, tile requests, and rendering. The application detects that condition and reports it instead of silently displaying an empty map.

The **basemap requires an internet connection**. The rest of the page does not.

---

## Repository Structure

```text
uttan-congestion/
├── backend/
│   ├── uttan/                    core model
│   │   ├── config.py             every parameter in one place
│   │   ├── datasets.py           public-data loading with provenance
│   │   ├── network.py            BPR links, route composition, calibration
│   │   ├── demand.py             70 traveller segments, value of time
│   │   ├── generalized_cost.py   GC[i,a] term from the proposal
│   │   ├── choice_model.py       nested logit + constant calibration
│   │   ├── congestion.py         MSA fixed point → stochastic user equilibrium
│   │   ├── toll_policy.py        leader instrument set
│   │   ├── equity.py             burden, Suits index, credits, equity score
│   │   ├── incidence.py          welfare components + STEPS
│   │   ├── geographic.py         burden by sub-area
│   │   ├── political.py          acceptability, trust, ride-hail follower
│   │   ├── finance.py            revenue under three cost cases
│   │   ├── metrics.py            congestion, mobility, diversion, emissions
│   │   ├── simulate.py           scenario execution + calibration cache
│   │   ├── game.py               Stackelberg search, Pigouvian, Pareto frontier
│   │   ├── phasing.py            dynamic leader timing decision
│   │   ├── bargaining.py         City ↔ Province Nash bargaining + side payments
│   │   ├── joint_game.py         joint gate and price × timing solution
│   │   ├── reversion.py          persistence of delay reduction
│   │   ├── rejoin_validation.py  rejoin-fraction validation
│   │   ├── comparators.py        nine operating schemes used as evidence
│   │   ├── site_selection.py     gateway screening + weight sensitivity
│   │   ├── sensitivity.py        tornado, Monte Carlo, convergence study
│   │   ├── precomputed.py        cache + configuration-hash guard
│   │   └── scenarios.py          23-scenario library
│   ├── api/main.py               FastAPI HTTP layer, 36 endpoints
│   ├── data/                     14 public-data files + provenance table
│   │   └── precomputed/          six hash-guarded cached responses
│   ├── scripts/precompute.py     regenerates the cache
│   └── tests/                    193 tests, 45 marked slow
├── frontend/                     React + Vite, 18 pages, hand-built SVG charts
├── api/index.py                  FastAPI export for Vercel
└── docs/
    ├── METHODS.md                modelling decisions and justification
    └── DATA-REQUESTS.md          four remaining data requests
```

---

## Game-Theoretic Results

### 1. Pigouvian benchmark

An entering vehicle experiences its own travel time but also imposes `v · dt/dv` minutes of delay on travellers already using the link.

When that external delay is valued at the average value of time of corridor users, the first-best charge on the tolled segment is approximately **$9.73**.

The untolled downstream section carries a still larger externality of roughly **$18 per vehicle**, which a western gateway charge cannot directly internalize. This is the clearest reason the policy answer is not simply “charge the Pigouvian toll.”

### 2. Price of anarchy ≈ 1.14

Self-interested traveller choice produces approximately **14% more total corridor travel cost** than the least-cost allocation attainable with a uniform screenline charge, equivalent to roughly **$55 million per year**.

That result provides an upper bound on the improvement available to a pricing policy within this corridor model.

### 3. Constrained Stackelberg leader search

The authority searches across:

- charge level,
- charging window,
- geographic coverage, and
- credit structure.

The search is constrained by:

- a local-diversion cap,
- an equity floor,
- a minimum congestion-improvement requirement, and
- transit capacity.

Both the unconstrained and constrained winners are reported. The difference between them represents the cost of protecting local streets and lower-income travellers rather than treating those safeguards as invisible assumptions.

### Enactment gates are interdependent

A simple formulation of enactment as

```text
P(enacted) = P(voters) × P(deal)
```

assumes public support and intergovernmental authorization are independent. The model relaxes that assumption: a scheme with stronger public support is also politically cheaper for the Province to authorize.

At the assumed political cost, the distinction barely changes the result because the deal gate is not binding. At **$3.50 per charged trip**, however, just below the **$3.91** implied by the 2017 refusal, coupling the gates makes waiting for public support **5.7× more valuable**.

The ranking does not reverse. Instead, the independence assumption understates the value of building support before implementation.

### Price and timing solved jointly

The sequencing game fixes the charge and asks *when* to introduce it. Solving price and timing jointly yields **$12 starting in year 1**.

The optimal price is constrained by the **equity floor**, not by public acceptability. Modelled support declines by only about six percentage points across the **$2–$25** range because larger charges also generate more revenue for recycling.

Under these assumptions, a policy debate focused primarily on price acceptability would therefore be targeting the wrong binding constraint.

---

## Key Model Findings

> These are model outputs under the stated assumptions, not policy advice.

### Gateway selection is robust

**Etobicoke–Gardiner ranks first in approximately 96% of 6,000 alternative criterion weightings**, and TOPSIS agrees with the weighted-sum ranking.

Importantly, the gateway also scores **worst of the five candidates on governance**. The screening framework reports that weakness explicitly rather than allowing a strong aggregate score to conceal it.

### Freeway-only pricing creates substantial diversion

At a **$4 charge**, expressway-only pricing increases traffic on **The Queensway by roughly 12%**, exceeding the model’s **10% local-diversion cap**.

Pricing the full screenline removes the free bypass and turns the modelled diversion effect negative.

### Pricing does not automatically outperform strong operations

The no-charge operational package, consisting of **adaptive signals, ramp management, transit priority, parking pricing, and increased GO frequency**, removes **45.2% of peak delay**.

By comparison:

- the recommended pricing design removes **39.4%**,
- a **$5 screenline charge** removes **35.5%**, and
- a **$10 means-tested charge** reaches **54.7%**.

The **combined pricing + operations package reaches 64.4%**.

The implication is central to the project: **pricing and operational improvements are complements rather than substitutes**. In this model, the strongest case for pricing rests on revenue generation, durability, and demand management, not on an assumption that pricing always wins on delay reduction alone.

> **Model correction:** An earlier version had pricing outperforming the operational package by approximately two percentage points. The operational package had been understated by **11.2 percentage points** because the baseline was scored on the improved network. See `metrics.compute`.

### Delay reduction is not automatically permanent

Under background demand growth, the recommended design’s initial **39.4% delay reduction falls to 34.7% over ten years** without any further policy change.

The London comparator eventually lost its initial delay benefit, but only after freed roadway capacity was reallocated to buses and footway. Reproducing that mechanism in the model requires reallocating approximately **28% of charged-link capacity**. At that point, traffic remains lower than at the start.

**Pricing converts congestion into road space. What happens to the delay benefit depends on what is subsequently done with that road space.**

### A single-corridor pilot is financially marginal

Fixed collection costs do not scale down proportionally with the size of the program. At modest charge levels, particularly after credits are paid, the pilot can spend more collecting revenue than it raises.

### Flat charges are regressive, and targeted credits materially reduce the burden

The lowest-income quintile bears roughly **4.7× the burden of the highest-income quintile as a share of income**.

The targeted credit package reduces that ratio to approximately **2.2×**, though at the cost of some congestion relief and a substantial share of gross revenue.

### Governance branch B is the most regressive option

If provincial authorization never arrives, the fallback is to charge only City-controlled arterials.

That approach prices the route used by lower-income Lake Shore residents while leaving the expressway free, making it the most regressive governance branch evaluated by the model.

---

## Equity and Political-Economy Grounding

The equity and political-economy framework follows five sources supplied as mentor material. The model implements their methods rather than merely citing them.

| Source | Contribution to the model |
|---|---|
| Eliasson (2016), *Is Congestion Pricing Fair?* (ITF DP 2016-13) | Four welfare components, Suits index and benchmarks, consumer/citizen distinction, and the warning that averages can conceal harmed subgroups |
| FHWA, *Income-Based Equity Impacts of Congestion Pricing* | Income, geographic, and modal equity as distinct dimensions; toll-account access barriers |
| Greenlining Institute (2020), *An Equity-First Approach* | Means-tested fees, revenue targeting toward underinvested communities, and charging the ride-hail platform rather than the driver |
| Shaheen et al. (2019), UC Berkeley TSRC | STEPS framework: Spatial, Temporal, Economic, Physiological, Social |
| SFCTA (2020) case studies; RPA (2019) | London, Stockholm, and New York outcomes; implementation sequencing and public-support anchors |

Three findings follow directly from that framework:

1. **A flat charge is 17× more burdensome for the lowest-income quintile than the highest-income quintile as a share of income**, even though the highest-income quintile pays more dollars in absolute terms. Both statements are true, and reporting only the latter can materially misrepresent equity.
2. **The corridor’s flat design is more regressive than every operating congestion charge** against the Suits benchmarks used in the model.
3. **Equity design is what makes the scheme politically passable.** The means-tested and equity-first packages are the only designs that would win a vote today under the model assumptions.

---

## Data Provenance and Model Transparency

Every model input is assigned a provenance tier, visible in the application and recorded in:

```text
backend/data/sources.csv
```

### Provenance tiers

- **PUBLISHED** — taken directly from a named public source, including City of Toronto counts, Metrolinx business-case guidance, TTS occupancy, GO/TTC fares, and CANCEA.
- **DERIVED** — calculated from published values using a documented rule.
- **ESTIMATED** — introduced as a planning assumption and explicitly targeted by sensitivity analysis.

The most consequential **ESTIMATED** inputs are:

- western screenline demand,
- observed travel times used as calibration targets, and
- the fraction of bypassing drivers who later rejoin the expressway.

The **Data & provenance** page lists the full set of known limitations. Those limitations should be reviewed before quoting any model result outside its intended context.

Working sources and modelling decisions are documented in:

```text
docs/METHODS.md
```

---

## Deployment

The project deploys to Vercel as a **static single-page application plus one Python serverless function**.

`vercel.json` builds the frontend, serves `frontend/dist`, and rewrites `/api/*` to `api/index.py`. That module re-exports the same FastAPI application used locally, so there is no second API implementation to maintain.

### Deploy to Vercel

```bash
npm i -g vercel
vercel            # preview deployment
vercel --prod     # production deployment
```

There are **no environment variables and no database**. Every model input is stored in `backend/data/`, and the model is deterministic, reducing the risk that the deployed application silently drifts from the local model.

### Precomputed endpoints

Six computationally expensive endpoints are served from disk rather than recomputed on each request:

- rejoin validation,
- phasing game,
- bargaining sweep,
- joint game,
- joint price-and-timing solution, and
- gate-dependence sweep.

Vercel imposes hard execution ceilings of **60 seconds on Pro** and **10 seconds on the free tier**. The two heaviest calculations were originally measured at approximately **100 seconds** and **70 seconds**.

The implementation is now substantially faster: full regeneration takes about **20 seconds on an M-series Mac**, with bargaining accounting for roughly **10 seconds**. Serverless CPU remains slower than a development laptop, however, leaving insufficient margin for free-tier runtime execution.

The six responses are therefore generated once and committed to:

```text
backend/data/precomputed/
```

Regenerate them with:

```bash
cd backend
python scripts/precompute.py
```

### Cache integrity

The precomputed files are a cache, not a second source of model truth.

Two safeguards prevent stale results:

1. Every cached response stores a hash of the full model configuration. If the runtime configuration differs, the file is rejected. A parameter change therefore makes the API slower rather than silently wrong.
2. `test_precomputed.py` recomputes each cached entry and compares the result, which also detects changes to the solver itself.

Run the integrity test before deployment:

```bash
cd backend
python -m pytest tests/test_precomputed.py -q
```

`/api/meta` reports which cached entries are valid, and every affected response includes:

```text
_source: "precomputed" | "computed"
```

This makes the execution source visible to the reader.

Regenerate cached outputs after changes to `config.py` or to the cached model modules. The fingerprint guard is intentionally designed so that forgetting to regenerate makes the application **slower, not wrong**.

### Cold-start behaviour

A serverless process does not persist indefinitely between requests. A cold instance therefore pays approximately **3 seconds** for imports and calibration on its first request.

A non-default charge sent to one of the six cached endpoints falls through to live computation. That works locally but may time out on Vercel. No current frontend page requests such a case.

### Python bundle size

The Vercel Python bundle is capped at **250 MB unzipped**. The current deployment is approximately **117 MB**.

`scipy` had remained in the dependency list despite being unused and accounted for approximately **123 MB** by itself. If it becomes necessary again, it should be added deliberately and the deployment size re-checked.

### Requirements-file naming

The serverless function installs:

```text
api/requirements.txt
```

Local execution uses:

```text
backend/requirements-local.txt
```

Development and test tooling use:

```text
backend/requirements-dev.txt
```

The backend file is intentionally **not** named `requirements.txt`. The Vercel CLI can interpret a `requirements.txt` beside a FastAPI application as a separate deployable service and then reject top-level `buildCommand`, `functions`, or `outputDirectory` settings because ownership becomes ambiguous.

Keeping the backend dependency file under its current name allows the project to remain a single deployment.

---

## Scope and Limitations

This is a **bounded-corridor planning model**, not a full GTHA network assignment and not a microsimulation.

The model does **not** represent individual vehicles, explicit queues, detailed signal operations, or incidents.

Emissions are represented using a transparent proxy that varies with vehicle-kilometres travelled and time spent in stop-start conditions. That is sufficient for relative policy ranking within this framework, but not for reporting a formal emissions inventory.

Ride-hailing and freight are assigned policy instruments but are not separately calibrated.

Results should therefore be interpreted as structured planning evidence within the modelled corridor and assumptions, not as a substitute for network-scale forecasting, microsimulation, detailed engineering design, statutory review, or implementation analysis.

---

**Live application:** <https://uttan-congestion.vercel.app>

---

<p align="center">
  <strong>© 2026. All Rights Reserved.</strong>
</p>
