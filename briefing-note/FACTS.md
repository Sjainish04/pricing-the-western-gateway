# Facts pack — every figure, with its provenance and its caveat

Regenerated from the model on 2026-08-31. Every number below is reproducible:
`cd backend && python -m pytest tests/ -q` (193 tests), then read the endpoint
named beside each block.

**Read this before quoting anything.** Three tiers of confidence run through the
whole study, and they are not interchangeable:

| Tier | Meaning | How to talk about it |
|---|---|---|
| PUBLISHED | From a named public source | State it plainly |
| DERIVED | Computed from published values by a documented rule | "Our analysis implies…" |
| ESTIMATED | A planning assumption | "Under an assumption of…" — and give the sweep |

The three inputs that matter most are all ESTIMATED: the western screenline
demand, the observed travel times α is fitted to, and the rejoin fraction.

---

## 1. Where to price — site screening

| Figure | Value | Tier | Notes |
|---|---|---|---|
| Etobicoke–Gardiner wins | **95.8%** of 6,000 randomly weighted criterion sets | DERIVED | Dirichlet draws around the nominal weights |
| TOPSIS agreement | Agrees with the weighted sum | DERIVED | Two methods, same winner |
| Governance score | **Worst of the five** candidates | DERIVED | Say this out loud — it is the whole problem |
| Charged segment | Hwy 427 → Humber, **8.2 km of an 18.5 km trip** | PUBLISHED | The geometry that drives diversion |
| Screenline demand | ~120,000 two-way weekday | **ESTIMATED** | Interpolated between a published 140k system average and a 164k downtown count |

`/api/site/screening?draws=6000`

---

## 2. The benchmarks

| Figure | Value | Notes |
|---|---|---|
| Pigouvian first-best, charged segment | **$9.73** | The externality a gateway charge can reach |
| Pigouvian, untolled downstream section | **$18.34** | Larger — and a gateway charge cannot touch it |
| Welfare-maximising uniform screenline charge | $15.50 | Unconstrained |
| Price of anarchy | **1.140** | ≈ **$55.9M/yr** wasted to selfish choice |

The $9.73 / $18.34 gap is the cleanest statement of why the answer is not simply
"charge the Pigouvian toll." `/api/game/analysis`

---

## 3. Coverage — the diversion result

| Design | Worst local diversion | Verdict |
|---|---|---|
| $4, **freeway only** | **+11.6%** on The Queensway | Breaches the 10% cap |
| $10, **full screenline** | **−8.2%** on Lake Shore W | Diversion reversed |

**The fragility you must disclose.** This depends on an assumed **55%** of
bypassing drivers rejoining the expressway past the gantry. The finding
**reverses below 49%** — a margin of 0.06 in a quantity nothing local has ever
measured. The recommendation itself does not depend on it; the freeway-only
warning does. Quote the breakeven, not the certainty.

---

## 4. Delay — the finding that reversed

| Option | Peak delay removed |
|---|---|
| $5 screenline charge alone | 35.5% |
| **Recommended $10 charge with credits** | **39.4%** |
| **No-charge operational package** | **45.2%** |
| Charge **and** operational package | **64.4%** |
| $10 screenline, means-tested (hard price, thin credits) | 54.7% |

A charge only beats good operations on delay if it is priced hard and
compensated sparingly — the opposite of an equitable design. **If any earlier
draft says pricing beats operations, it is now wrong.** The honest framing is
that they are complements and pricing earns its place on revenue, durability and
demand management.

---

## 5. Equity — who pays

| Figure | Value |
|---|---|
| Burden ratio Q1:Q5, **flat $5 screenline** | **4.7×** |
| Burden ratio Q1:Q5, **targeted credit package** | **2.2×** |
| Welfare loss as share of income, flat $10: Q1 vs Q5 | −1.82% vs −0.11% (**17×**) |
| Toll paid per trip, Q1 vs Q5 | $2.43 vs $5.48 |
| Suits index, recommended design | **−0.16** |
| Suits index, flat $10 | −0.20 |

**Both of the first two rows are true and they point opposite ways**: Q5 pays
more than twice the dollars, Q1 loses 17× more of its income. Reporting only the
first is how equity analyses mislead — say both.

**Against the operating record:** Stockholm −0.09, Helsinki −0.09, Gothenburg
−0.13, Lyon −0.16. Even credited, this corridor is at the regressive end of
every charge in operation. Report it.

Concentration curve: the gap is widest at the **fourth-quintile boundary** — the
bottom 80% hold 54.2% of corridor income and pay 68.3% of the charge.

---

## 6. Equity — where they live

| Sub-area | Share of trips | Share of charge | Ratio |
|---|---|---|---|
| Mississauga / west GTA (**905**) | 40.0% | **36.2%** | **0.90** |
| Islington–City Centre W | 14.5% | 17.2% | 1.18 |
| **Alderwood** | 6.5% | **8.6%** | **1.33** |
| Long Branch | 7.0% | 6.3% | 0.90 |

**Do not tell the New Jersey story.** FHWA found NJ residents paying 45% of NYC
tolls on 24% of trips (ratio 1.88). This corridor is the opposite: the 905 pays
*less* than its share and receives 44.4% of recycled benefit — a net recipient,
because Lakeshore West GO gives it a way out. A judge with the FHWA paper open
will catch the wrong version.

**Income explains only 46%** of burden variation across sub-areas, which is why
geographic equity needs its own treatment.

---

## 7. Money

| Figure | Value |
|---|---|
| Net revenue, recommended design | **$5.55M/yr** |
| Travellers better off | 63.1% |
| Travellers better off **before** recycling, flat $10 | **0%** |

Fixed collection costs do not scale down, so at modest charges a single-corridor
scheme can spend more collecting than it raises. Revenue is an argument for
pricing a **network**, not this corridor alone.

---

## 8. Sequencing — the biggest lever

| Path | Precedent | Support at gate | E[discounted welfare] |
|---|---|---|---|
| **Transit, pilot, then referendum** | Stockholm | **73%** | **0.434** |
| Transit first, then charge | Stockholm, no pilot | 52% | 0.171 |
| Transit, ride-hail surcharge, cordon | NYC 2019–25 | 52% | 0.120 |
| Charge immediately | NYC 2008 | 38% | −0.130 |
| Operations, never charge | Toronto CMP | — | −0.197 |

**0.56 welfare points** separate the best ordering from charging now, at the same
price. The pilot does most of the work: it replaces a forecast with an
experience. Optimum start is **year 1**, when the transit uplift lands.

---

## 9. Governance and the 2027 transfer

| Figure | Value |
|---|---|
| Zone of agreement closes at | **$3.91**/charged trip pre-transfer, **$8.75** post |
| 2017 settlement side payment | ~$170M/yr gas tax — **30.6×** corridor net revenue |
| Joint price-and-timing optimum | **$12, year 1** — binding on the **equity floor** |
| Value of waiting, at $3.50 with dependent gates | **5.7× larger** than under independence |

The Province refused in 2017, which places its valuation **above $3.91** — a
revealed bound from a real decision, not an assumption. The repair liability
moving City → Province **cancels out of the bargain**; what changes is the
Province's *fallback*, since after the transfer it could levy a freeway-only
charge on its own — the design that pushes traffic onto City streets.

**Support barely disciplines the price**: it falls only ~6 points across a
$2–$25 range. The equity floor is what sets the rate.

---

## 10. What the record says we have wrong

Use these. A comparison that only finds corroboration is not being used as
evidence, and judges reward the team that says so first.

| Case | What it says | Our position |
|---|---|---|
| **London** | Traffic reduction permanent; **delay reduction was not** — gone in ~5 years | Our 39.4% is a **first-year** figure. Growth alone erodes it to 34.7% over ten years; reproducing London needs ~28% of freed capacity reallocated to buses and public realm |
| **Edinburgh** | Lost **74.4–25.6 on trust**, not economics — 1 in 4 believed revenue would reach transport | Belief in the money is worth $0.28/trip here |
| **Manchester** | **£3bn** package attached, still lost | Belief the charge *works* is worth **$1.68**/trip — 6× larger. A credible package cannot rescue an incredible charge |
| **Stockholm** | No income discount, still not regressive | Geography can do the work a means test would — but that is a fact about a city, not a design principle |
| **New York** | Observed **−11%** entries in year one at $9 | We predict **−13.1%** — *larger*, which is the wrong direction for a corridor with weaker alternatives. **Unresolved**, not explained away |

The NYC gap is the single highest-value open item: MTA publishes CRZ entries by
hour, so a like-for-like weekday AM-peak comparison would settle it. If the gap
survives, our demand response is too strong and the headline numbers move.

---

## 11. Limitations to state, not bury

- Screenline demand is **derived, not counted**.
- Observed travel times are **estimates**, and α is fitted to them — error
  propagates into every delay figure.
- The OD pattern is **synthetic** (Census-derived, not a TTS extract).
- The **55% rejoin fraction** drives the diversion result and reverses at 49%.
- **Collection costs are assumed** and change the *sign* of the financial answer.
- Acceptability coefficients are a **calibrated stance**, not estimates.
- Emissions are a **proxy**, not an inventory.
- **No microsimulation** — no queues, signals or incidents.
- STEPS physiological and social equity are **not modelled at all**, and we say so.

---

## 12. Two things to settle before Sep 4

1. **Interviews.** The brief requires **at least two** with professionals, and
   only with industry stakeholders — not the public. `docs/DATA-REQUESTS.md` has
   specified asks for UTTRI (behavioural parameters, the rejoin fraction),
   Metrolinx (Lakeshore West peak capacity, which sets the transit constraint)
   and City Transportation Services (Section 3 counts and screenline data).

2. **The AI disclosure.** The brief requires you to indicate **where and how**
   AI tools were used. In this project that is substantial — the simulation code
   was AI-assisted throughout. An under-stated disclosure is a far bigger risk
   to you than a thorough one. Write it in your own words, and be specific about
   what was assisted (code, debugging, structuring the comparator review) and
   what was not (assumptions, source selection, interpretation, the note itself).

**The live Gardiner natural experiment worth one phone call:** Islington and
Kipling went 3 lanes → 2 in April 2025, and the Park Lawn westbound on-ramp has
been closed since August 2026. Nobody has published a number from it. A ramp
closure is the closest physical analogue to a gantry in the entire record, and
it would move the rejoin fraction off ESTIMATED.
