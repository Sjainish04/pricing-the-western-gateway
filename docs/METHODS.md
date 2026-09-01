# Methods

Modelling decisions, and why each was made the way it was. The intent is that a
reviewer can disagree with a choice here rather than having to reverse-engineer
it from the code.

---

## 1. Study area and period

AM peak, 06:30–09:30, inbound, across a screenline at the western Gardiner
gateway. The corridor is the City's own Section 3 rehabilitation segment —
Highway 427 to the Humber River — which gives the study a boundary that already
exists in policy rather than one invented for modelling convenience.

The network is split at the Humber into a charged western segment and an
untolled eastern segment shared by every route. This is the single most
consequential structural decision in the model; see §3.

---

## 2. Demand and segmentation

**Total demand.** 40,465 AM-peak inbound person-trips. This is derived, not
counted: a 120,000 two-way weekday screenline volume is interpolated between the
published 140,000 system average and the 164,000 downtown count, then reduced to
the AM peak period and the inbound direction.

**Reconciliation.** Person-trip shares are set so that the implied vehicle counts
reproduce the link volumes exactly — 14,256 on the charged segment, 4,180 on Lake
Shore, 2,560 on The Queensway — and so that the implied overall auto occupancy is
exactly the TTS work-trip figure of 1.15. Link volumes are then *derived* from the
mode shares rather than tabulated separately, so the two cannot drift apart.

**Segments.** 70 segments: seven sub-areas × five income quintiles × fixed or
flexible schedule. Transit accessibility is attached to the sub-area rather than
drawn as an independent attribute, because whether Lakeshore West GO is a
realistic option is a fact about where somebody lives.

The sub-areas include **Mississauga / west GTA**, carrying 40% of demand. A large
share of western-gateway users are not Toronto residents, which is a real
political and distributional fact that a Toronto-only segmentation would hide.

**Value of time.** Scaled from the Metrolinx peak auto figure of $24/hour by
household income with an elasticity of 0.6. A **floor of $9.50/hour** is applied.
Without it, the constant-elasticity form implies that delay to a low-income
traveller is nearly free, which would quietly bias every equity result in the
study toward finding that pricing helps the poor.

---

## 3. Network and link performance

```
t(v) = t_free + d_signal + t_free · α · (v/c)^β
```

**Why fixed control delay is separated out.** An arterial can be slow because it
is congested or because it has thirty signals. A pure BPR curve has to explain
both with `α`, so a slow-but-uncongested arterial gets a large fitted `α` — and
that `α` then governs how much worse the arterial gets when tolled traffic
diverts onto it. Since diversion onto exactly those arterials is the central risk
the study measures, conflating the two would corrupt the headline result.

**Why β is not fitted.** With both `α` and `β` free, many pairs reproduce one
observed travel time equally well and the fit becomes meaningless. `β` is held at
4.5 and only `α` is solved, in closed form.

**Effective capacity.** The freeway uses the queue-discharge rate of 1,600
veh/h/lane rather than the HCM design rate of 1,900, because the AM peak operates
in breakdown and the discharge rate is what governs throughput. Arterials use 800
veh/h/lane for a signalised approach.

**Calibration and validation.** `α` is fitted on `gardiner_west`,
`gardiner_east` and `lakeshore_west`. `lakeshore_east` and `queensway_west`
inherit the fitted arterial value and are held out. Their errors —
about −6% and −3% — are an out-of-sample check, and the strongest evidence
available here that the curve captures something real rather than absorbing error
into a free parameter.

**Route composition and gantry-hopping.** `drive_lakeshore` is not "use Lake Shore
for the whole trip". It is *bypass the charging point on the arterial, then
rejoin the expressway past it* — 55% rejoin at the Humber, the rest continue on
Lake Shore. This is what a gateway charge actually invites, and it is why the
network had to be split. The rejoin fraction is ESTIMATED and materially drives
the diversion result. It is a behavioural assumption, so it lives in `Config`
and is swept by the robustness analysis; `routes.csv` carries only the network
structure and marks the two branches with a `role` column. See §3a.

---

## 3a. Confronting the rejoin fraction with the Gardiner record

The rejoin fraction is the model's most consequential unmeasured input, so it
gets its own confrontation with the evidence rather than a caveat. The module
is `rejoin_validation.py`; `/api/validation/rejoin` returns the whole thing.

**The experiment we want is running now, and nobody has published a number
from it.** Section 3 — Highway 427 to the Humber, the charged segment itself —
has had Islington and Kipling reduced from three lanes to two in each
direction since April and May 2025, running to December 2026, and the
westbound Park Lawn on-ramp fully closed from August 2026. A ramp closure is
the closest physical analogue to a gantry anywhere in the record. No travel
times or counts have been published for any of it.

The episode that *was* measured is Section 2, downtown, about 8 km east of the
screenline: three lanes to two between Dufferin and Strachan from April 2024,
measured by Altitude by Geotab from commercial-vehicle telematics against a
clean two-and-a-half-month pre-period.

**Everything published is a travel time. No before/after volume count exists
for either episode.** A rejoin fraction is a claim about where vehicles go, so
the times have to be inverted through the link performance curves before they
say anything about volumes at all:

```
(t' − t_u) / (t − t_u) = (v' / (κ·v))^β
```

which solves for `v'/v` in closed form. A regression test inverts a ratio the
curve itself produced and requires the original volume back, so the figures
below are falsifiable rather than merely plausible.

**Three results survive that inversion.**

*The arterial absorbed part, never all.* Lake Shore's 30% travel-time rise
implies a volume increase of 30–43%, not 30% — the performance curve is convex,
and reading a time change as a volume change would overstate absorption
several times over. Against what the expressway lost, the parallel arterial
took between about a sixth and two thirds, depending on which stretch of
expressway the published figure refers to. The rest retimed, changed mode, was
suppressed, or used arterials outside the two modelled here.

*The travel-time record independently implies the announced lane closure.* With
capacity unchanged, a travel time that rose that much could only be produced by
*more* traffic on a corridor everyone was avoiding. The largest capacity ratio
consistent with the expressway losing traffic is 0.74, against the announced
three-lanes-to-two of 0.667. That is the closest thing to an external check the
module has.

*The inversion is fragile on one link and the output says so.* `lakeshore_east`
carries about a minute of queueing delay at base, so the two defensible
baselines — the fitted curve and the observed time — disagree by 47% in the
answer from a 6% disagreement in the input. `conditioning()` reports this and
the decomposition carries a low/high pair rather than a mean.

**What none of it identifies is the rejoin fraction.** That parameter splits
bypassers *at the Humber*, and separating re-entering from continuing requires
a count downstream of the split. None exists. The inversion bounds the total
diversion the model should reproduce and says nothing directly about the split.
The fraction stays ESTIMATED, and no result in this study should be presented
as though this changed that.

One directional argument does carry. Under construction the degraded facility
*is* the downstream expressway, so a driver who leaves it has little reason to
return — rejoining buys a share of the queue they left. Under a gateway charge
the opposite holds: past the gantry the road is untolled and, because the
charge removed traffic, faster than before. So a construction episode is a
**lower bound** on the toll-era rejoin fraction. That cuts against convenience,
because a higher fraction puts more diverted traffic back onto the shared
untolled section — the externality a gateway charge cannot price, and this
study's own central objection to the design it recommends.

**The question that actually matters is whether it changes any conclusion.**
Sweeping the fraction from 0.20 to 0.90:

| Conclusion | Robust? |
|---|---|
| \$10 screenline recommendation — diversion, revenue, equity, feasibility | Yes, across the whole range |
| \$5 screenline turns diversion negative | Yes |
| **\$4 freeway-only breaches the 10% local-street cap** | **No — flips at 0.49** |

The study's second headline finding rests on a parameter nobody has measured,
sitting 0.06 above its switching point. Below a rejoin fraction of about 0.49
a freeway-only charge stays inside the cap; above it, it breaches. The
recommendation does not depend on it, which is the more important half of the
result — but the leakage finding must be reported with that dependence
attached, and `breakeven_rejoin_fraction()` computes the crossing so the margin
can be quoted rather than assumed.

---

## 4. Generalized cost

```
GC[i,a] = β_t[i]·T[a] + C[a] + τ[a] + S[i,a] + R[i,a] − D[i,a]
```

**Per-vehicle charges, per-person costs.** The charge is levied per vehicle but
generalized cost is per person, so every charged alternative's per-person toll is
the vehicle rate divided by its occupancy. Dividing only for carpools
over-collects 15% on the 1.15-occupancy arterial routes, inflating revenue and
making bypassing look dearer than it is — which then understates diversion. A
regression test pins revenue-per-charged-vehicle to the posted rate.

**Carpool matching friction.** A carpool of 2.4 people splits one charge 2.4
ways, so without a countervailing friction the model answers almost any toll by
inventing carpools. The easy matches — households already travelling together,
colleagues on one schedule — form first, so the coordination cost rises convexly
with carpool growth. A test bounds occupancy growth under a $10 charge.

**Transit crowding.** Flat until an 85% load factor, then steeply rising. This is
what stops the model from "solving" congestion by moving an impossible number of
drivers onto trains with no room to take them.

**Charging window.** A window narrower than the peak is easy to dodge, because a
traveller only has to shift to the edge of the peak rather than out of it, so the
retiming penalty scales with window coverage. This is the mechanism that makes a
narrow window leak rather than merely reshuffle arrivals inside it.

---

## 5. Choice model and calibration

Nested logit — auto / transit / not travelling — with nest scales exposed. A test
asserts that within-nest substitution exceeds cross-nest substitution, which is
precisely the property plain MNL lacks.

**Alternative-specific constants** are fitted so the base run reproduces the
observed split. They are fitted *at the equilibrium implied by each trial value*,
not at frozen travel times, so the calibration stays consistent with the
congestion feedback the model later relies on. The constants come out large; that
is expected, since a corridor where driving is slower and dearer than the train
yet still carries a third of trips can only be reproduced by admitting unmodelled
preferences explicitly.

**Reported calibration error is the error of the published shares**, not the error
the fitting loop reached. The final equilibrium is solved to the SUE tolerance,
which leaves a slightly larger residual than the fit itself; quoting the fit error
would overstate how well the baseline is reproduced.

**Constants are held fixed when parameters are varied.** In a tornado sweep or a
Monte Carlo draw, only the baseline is re-solved. Re-fitting the constants per
draw would be circular — they would move to whatever reproduces the observed
shares under the new parameter, so the model would match the base data no matter
what and the parameter's influence would vanish into the constants. A test asserts
that a perturbed value-of-time actually moves the base split.

---

## 6. Equilibrium

Method of Successive Averages with a short fixed-step warm-up. Convergence uses
the rule from the simulation plan, `Σ|v_k − v_{k−1}| / Σ v_{k−1} < ε`, on link
volumes. A convergence study across five tolerances confirms results are not an
artefact of stopping early, and a test confirms the fixed point is independent of
the starting allocation (the solver is warm-started from the baseline for speed).

Links are deep-copied per scenario, because the non-price complements mutate link
capacity and a scenario must not leak into the next. A test pins this.

---

## 7. Equity

Components are reported before any index is built.

**Suits index** for progressivity: cumulative share of the charge paid against
cumulative share of income, with `S = 1 − L/K`. The sign convention is
deliberately pinned by a test against four known cases, because getting it
backwards flips the study's central distributional claim from "regressive" to
"progressive".

**Two measures that disagree, both reported.** In absolute dollars a charge here
falls mainly on higher-income travellers, because they drive more. As a share of
income it lands several times harder on the lowest quintile. Reporting only one
would be misleading, so the interface shows them side by side.

**Rebates and transit credits are not the same thing.** A rebate against the
charge reduces what a traveller pays; a transit mobility credit is a benefit paid
to somebody who may not be paying the charge at all. Netting the mobility credit
off the burden would let a large enough transit subsidy drive measured burden to
zero and report a charge as costless. They are separated in the burden account
and combined only in the revenue account, where both are money out.

**A parking surcharge is a charge.** It changes behaviour through the parking cost
inside generalized cost, but it is also paid by somebody and raises revenue.
Leaving it out of the equity and revenue accounts made a parking levy appear to
deliver congestion relief at nobody's expense, and the model recommended it for
that wrong reason. It now enters both accounts, and reaches only the 70% of
drivers who actually pay for parking in the surcharged area — through-trips,
drop-offs, deliveries and employer-provided spaces are outside a destination levy.

---

## 7a. Welfare incidence: who wins, not just who pays

Counting tolls paid is the traditional equity analysis and it is incomplete.
Eliasson (2016) separates four components of the welfare effect of a charge:
tolls paid, adaptation cost, travel-time gain, and recycled revenue. Only the
first appears on an incidence table.

Components 1-3 are computed exactly, as the change in the nested-logit
**logsum** — the compensating variation, or what a traveller would need to be
paid to be indifferent between the charged world and the uncharged one. This is
verified against a case with an analytic answer: raising the cost of every
alternative by $5 must cost exactly $5 of surplus, and it does.

Component 4 is added separately and **capped**. Crediting the whole of net
revenue back to the 40,000 people who cross this screenline would make any
revenue-positive scheme a Pareto improvement on paper; station access and bus
priority serve far more people than that. `recycling_capture_share` (default
0.5) sets how much lands on corridor travellers, and the result is reported
both before and after recycling, because the second number depends on a
spending decision nobody has made yet.

**The two numbers that disagree.** Under a flat $10 screenline charge, the top
quintile loses more dollars than the bottom — which is how a scheme gets called
progressive — while the bottom quintile loses about **17 times more of its
income**. Both are true; reporting only the first is the most common way an
equity analysis misleads.

**Concentration, not averages.** Eliasson's sharpest warning is that a scheme
can look mildly regressive on average while a real subgroup is badly hurt, and
that subgroup is the political problem. The model reports the share of each
quintile whose annual charge exceeds 0.5%, 1% and 2% of household income.

**Benchmarking.** The model's Suits index is placed against schemes that
actually operate: Stockholm -0.09, Helsinki -0.09, Gothenburg -0.13, Lyon
-0.16. For scale, a US sales tax is about -0.11 and the Texas fuel tax about
-0.25. A flat charge on this corridor comes out more regressive than any
operating scheme, which is a finding, not a rounding error.

**Beyond income.** FHWA distinguishes income, geographic and modal equity, and
warns most analyses stop at the first. Modal equity is reported explicitly:
travel-time savings accrue to whoever keeps driving, so the recycling plan is
doing the modal-equity work, not the charge. Payment access is modelled too —
FHWA puts the share unable to hold a toll account at 10-20%, falling with
income, and they do not escape the charge, they pay it through a costlier
channel.

**STEPS.** Shaheen's Spatial-Temporal-Economic-Physiological-Social framework
is scored on the three dimensions the model can see. Physiological and Social
are reported as *not modelled*, with the reason, rather than scored as passes.

**Means-tested pricing.** Every congestion charge operating anywhere today is a
flat fee regardless of income. San Francisco's proposal would be the first that
is not: exempt the lowest income band, half price for the next. That design is
implemented as the `means_tested` and `equity_first` credit mechanisms, and a
means test is the only **instrument** in the library that reverses the burden
ordering: exactly two designs manage it, and both contain one. Stated as "the
only design" this was simply false — two designs reverse it — and the
distinction matters, because Stockholm reverses nothing and is still not
regressive. `test_means_test_claim_matches_the_library` recomputes which designs
reverse the ordering and requires every one of them to carry a means test, so
the sentence cannot drift from the scenario library again.

---

## 7b. Geographic equity

FHWA distinguishes income, geographic and modal equity, and warns that most
analyses stop at the first. `geographic.py` and the **Geographic equity** page
do the second, because the income analysis sorts people by quintile and so
cannot see any of it.

The benchmark worth transplanting is FHWA's New York finding: New Jersey
residents paid about 45% of the tolls while making about 24% of the trips, a
ratio of 1.88. A charge at a boundary collects from the people on the far side
of it, and this corridor has the same shape — 40% of demand crosses the western
gateway from outside Toronto.

**It does not have the same result.** Under the recommended \$10 screenline with
income and transit-poor credits, travellers from outside Toronto pay **36.2%**
of the charge on **40.0%** of the trips — a ratio of **0.904**, against 1.88 for
New Jersey. They also receive **44.4%** of the recycled benefit, making them net
recipients by 8 percentage points. The reason is Lakeshore West GO: west-GTA
travellers have a way out of the charge and enough of them take it. The finding
holds under a freeway-only design too (0.986).

The handover assumed this corridor reproduced the New Jersey case. It does not,
and a test pins the direction so that if it ever flips the page has to say so.

**Where the burden actually lands is inside Toronto.** Alderwood carries
**0.81%** of household income against a corridor average nearer 0.6%, and pays
1.33 times its share of trips. Inner Etobicoke, not the 905, is the group a
geographic mitigation would have to protect.

**Is it geography, or income wearing a map?** Sub-areas differ in income as well
as in location, so the geographic result has to be separated from the income one
before it counts as a finding. Regressing burden on log income and taking the
residual, **54% of the variation is not explained by income** — which is what
justifies reading this separately from §7 rather than as a restatement of it.
The residual runs against transit access (r = −0.35): an area with a usable
alternative escapes the charge, an area without one pays it. With seven
sub-areas that correlation is moderate rather than decisive, and it is reported
as consistent with the mechanism rather than as evidence for it. If it holds,
the remedy for geographic inequity here is service, not rebates.

**Representation is a separate question from burden.** Travellers from outside
Toronto pay a charge set by a council they cannot vote for, whatever the ratio
says. That is the same asymmetry that gives the Province its political cost in
§11a, and it is an argument about consent rather than about incidence.

**Caveat.** Sub-area shares come from a synthetic Census-derived OD pattern, not
a TTS extract. The ordering of areas by distance, income and transit access is
defensible; the exact shares are not observed, so the headline ratios illustrate
a structure rather than measure one.

---

## 7c. Acceptability: the third level of the game

A policy that maximises welfare and cannot be enacted is a proposal, not a
policy. New York lost its federal Urban Partnership funding in 2008 because it
could not obtain the legislative authority.

Support is modelled as a third stage, over the two perspectives Eliasson
separates: the **consumer** perspective (the traveller's own net position, from
the incidence module) and the **citizen** perspective (whether they think
pricing is a fair way to allocate road space at all, which rises with income —
which is why congestion pricing is partly an elite project regardless of how
the money is spent).

Two mechanisms come from the case studies. **Experience**: Stockholm was opposed
two to one before its pilot and kept by the same margin afterwards, and
Gothenburg's support curve shifted up by a similar amount at every level of toll
paid. **Sequencing**: Stockholm expanded transit first — 197 buses, 16 new
routes — and New York's plan is explicitly phased.

The coefficients are a calibrated stance, not estimates: Eliasson fits an
ordered logit to survey data this project does not have. They are set to
reproduce the two anchors the record gives us (roughly a third support before,
roughly two thirds after) and are exposed for sensitivity testing.

Acceptability enters the leader's search as a constraint, tested **after**
operation rather than before — requiring majority support up front would rule
out every charge ever built.

---

## 7c-i. Trust: the vote is taken on the promise, not the spreadsheet

Two entries in the comparative record (§7g) contradicted this model, and both
were the same missing mechanism.

**Edinburgh** rejected its charge **74.4% to 25.6%**, and the research found the
driver was *trust* rather than economics: only about **one in four** believed the
revenue would actually reach transport. **Manchester** attached a **£3bn**
transport package and lost anyway. Neither outcome was reachable here at any
parameter value, because recycling entered the vote at face value — so support
was increasing and unbounded in the size of the package, and there was always a
package that won.

The fix follows the structure already in the model. A traveller's net position
has two parts with quite different epistemic status:

| Component | Status | Discounted? |
|---|---|---|
| Toll paid, time saved (`surplus_per_trip`) | **Experienced** | No |
| Recycled revenue (`recycled_per_trip`) | **Promised** | Yes, by `revenue_trust` |

You do not need to trust that you paid ten dollars. So only the promise is
discounted:

```
believed_net = surplus + revenue_trust · recycled
```

Trust itself has three sources: a baseline belief; a gain once the scheme is
**operating**, because the spending becomes observable and stops being a promise
at all; and a gain from an alternative that was actually **delivered** first —
the mechanism behind Stockholm's pilot, where a government that built the buses
it said it would build is evidence about the next promise. The last two are
capped at certainty.

**The level is inverted, not tuned.** `revenue_trust` defaults to **1.0** — full
belief — which reproduces every result computed before the term existed,
bit-identically, and a test pins that by making the gains absurd and requiring
the answer not to move. Toronto's actual level is unobservable, so
`political.trust_sensitivity` reports the level the recommendation *requires* and
sets it against Edinburgh's measured 25%. This is the same discipline
`bargaining.py` applies to the political-cost rate, and for the same reason: a
parameter nobody can measure should be reported as a threshold, not asserted as
a value.

### What it finds, including against interest

On the recommended design, **trust is not the binding constraint** — and the
reason is a finding in itself. The promise is worth about **$0.28 per trip**
against a **$2.35** toll, so believing none of it moves support only from 38.0%
to 35.3%. The scheme fails a vote today for reasons that have nothing to do with
the revenue promise, and passes once operating whether or not anyone believes it.
**A single-corridor scheme cannot raise enough to make its own revenue promise
politically decisive**, which is the acceptability counterpart of §8's finding
that it cannot raise enough to be financially comfortable.

Where trust does bind is at Manchester's scale. Scaling the package while holding
trust fixed:

| Trust | Support at 1× package | at 8× | Any package carries the vote? |
|---|---|---|---|
| 25% | 36.0% | 40.8% | **No** |
| 50% | 36.7% | 46.4% | **No** |
| 75% | 37.3% | 52.1% | Yes |
| 100% | 38.0% | 57.8% | Yes |

At 25% and 50% trust no multiple up to eight times the modelled package carries
the vote: the constraint is credibility, not generosity. That is the Manchester
result, and a model without this term cannot produce it.

### The second doubt, which is the larger one

The paragraph above covered trust in the **money**. On the record that is not
the doubt that decides votes. Manchester's £3bn was real and credible; what
nobody believed was that the charge would work.

So the time saving is discounted too, by `charge_efficacy_belief`, and the split
is not arbitrary — it follows what a traveller can actually know before the
scheme runs:

| Component | Before operation | Discounted by |
|---|---|---|
| Toll paid | **Certain** — you know the rate | nothing |
| Time saved (`resource_per_trip`) | **A forecast** — depends on others changing behaviour | `charge_efficacy_belief` |
| Recycled revenue | **A promise** | `revenue_trust` |

**The two doubts are not the same size.** On this corridor the revenue promise
is worth **$0.28** a trip and the forecast time saving **$1.68** — six times
larger. Disbelieving the money moves support 38.0% → 35.3%; disbelieving the
charge moves it 38.0% → **23.6%**.

That difference is the quantitative form of Manchester's lesson, and it lets the
model reproduce the actual failure rather than a monetary substitute for it.
Holding the money **fully believed** and varying only belief in the charge:

| Belief the charge works | Support at 1× package | at 8× | Any package carries it? |
|---|---|---|---|
| 0% | 23.6% | 40.7% | **No** |
| 25% | 26.7% | 45.0% | **No** |
| 50% | 30.2% | 49.3% | **No** |
| 75% | 34.0% | 53.6% | Yes |
| 100% | 38.0% | 57.8% | Yes |

A credible package cannot rescue an incredible charge. The earlier result
reached the same conclusion by disbelieving the £3bn, which was the right story
for the wrong reason.

**Efficacy belief applies only before operation.** Afterwards the traffic effect
is visible, which is exactly what the `experience` coefficient already
represents; discounting there as well would count one phenomenon twice and break
the Stockholm anchors the coefficients were set against. A test pins that
support after operation is invariant to it.

### What is still missing

Edinburgh's finding that **car ownership predicted the vote better than income
did** is not reproduced; this model's segments carry transit access, which is
related but not the same thing. Recorded in `comparators.contradictions` rather
than quietly closed.

---

## 7d. Ride-hailing as a second follower

London removed its ride-hail exemption once more than 18,000 such vehicles were
entering the zone daily. New York charges $2.75 for a solo ride-hail trip and
$0.75 per rider on a shared one — an explicit occupancy incentive. Greenlining
notes that ride-hail generates up to 14% of vehicle-kilometres in some cities
and that a ride-hail trip produces roughly 70% more emissions than the same trip
in a private car, because of empty repositioning kilometres.

The operator is modelled as a genuine second follower choosing how much of the
charge to pass to riders. Pass-through is interior — it neither absorbs nor
forwards all of it — which is why a charge levied on the platform is not
equivalent to one levied on the rider, and why Greenlining's argument that the
platform should absorb it is a real design choice rather than a slogan.

---

## 7e. Sequencing: the leader moves more than once

`game.py` has the leader move once. Every scheme in the record moved more than
once, and the order decided whether it survived. Stockholm expanded transit
first, then ran a pilot, then held the referendum, and turned a two-to-one
majority against into a majority for. New York's plan is explicitly phased.
New York in 2008 moved once, and lost its federal funding because it could not
obtain the legislative authority in time.

A single-shot model reports the welfare of a charge as though enacting it were
free, which assumes away the constraint that killed the 2008 attempt.

**Structure.** The leader chooses a *path*: a sequence of years, each with a
transit uplift, a ride-hail surcharge and possibly a charge in force. At the
year the charge is first proposed it faces a gate, and the payoff is

```
E[W] = Σ_t  δ^t · [ p · W(with charge) + (1−p) · W(without charge) ]
```

with `p` the enactment probability. That product is the whole model. Charging
immediately has the highest annual welfare and the lowest probability of
existing at all; charging after transit is delivered earns less, for fewer
discounted years, but is far likelier to be there.

Enactment is a logistic in the distance from the threshold, not a step. A hard
cut at 50% would make the entire ranking an artefact of which side of the line
a path happened to land on.

**The sequencing term is a calibrated stance.** `delivered_alternative_bonus`
says how much a *built and visible* alternative adds to support, over and above
the improvement it makes to people's own net position, which the incidence
model already counts. The whole sequencing result rests on it. It defaults to
inert (`delivered_alternative = 0`), so nothing outside the phased game moves,
and a test makes the coefficient absurd to prove the term cannot reach a
single-shot run.

**Result — order, at an identical \$10 price:**

| Path | Precedent | Support at gate | P(enact) | E[discounted W] |
|---|---|---|---|---|
| Transit, pilot, then referendum | Stockholm | 73% | 0.96 | **0.429** |
| Transit first, then charge | Stockholm (no pilot) | 52% | 0.56 | 0.168 |
| Transit, ride-hail surcharge, cordon | New York 2019–25 | 52% | 0.56 | 0.118 |
| Charge immediately | New York 2008 | 38% | 0.16 | −0.131 |
| Operations, never charge | Toronto CMP | — | 1.00 | −0.197 |

Sequencing is worth **0.56 welfare points** against charging immediately, on an
identical charge. None of that is a better policy; all of it is a better chance
the policy exists. The pilot does most of the work, because it replaces a
forecast with an experience — which is exactly the mechanism Stockholm and
Gothenburg document.

**Result — timing.** Sweeping the start year with transit committed at year 0
gives an **interior optimum at year 1**, the year the uplift is fully
delivered. Charging a year earlier costs 0.145 welfare points to enactment
risk; waiting to year 6 costs 0.246 to discounting. The answer to "when" is
*as soon as the alternative lands, and not a year later* — waiting past
delivery buys no further support and is pure discounted loss.

**What this does not model.** The leader commits to a sequence and cannot
revise the charge in response to what it learns, so there is no adaptive
policy. Enactment is one-shot: a leader who fails cannot re-propose, which
understates the value of trying early. Transit capital cost is not netted off —
the paths differ in *when* the uplift arrives, not whether it is affordable.
And the City–Province game in §11a is solved separately rather than jointly
with this one.

---

## 7f. Joining the two games: when, given who must agree

§7e asks when to charge and answers *year 1*, as soon as the transit uplift is
delivered. §11a asks whether the City and the Province can agree, and finds the
City's hand changes at a fixed date. Solved separately, each is missing the
other's binding constraint: the phased game says wait, the bargaining game says
there is a deadline on waiting.

**Two gates.** A charge needs a public that will tolerate it *and* two
governments that can agree:

```
P(enacted) = P(voters) × P(deal)
```

The first is the phased game's logistic in support. The second is logistic in
the surplus available to the *weaker* party in the bargain — at zero surplus a
coin toss, which is the honest reading of a party exactly indifferent between
agreeing and walking away. Both are logistic rather than steps, so no result
here is an artefact of which side of a cliff a year fell on.

Multiplying them assumes the gates are independent. In practice a popular
scheme is easier to authorise, so this **understates** the value of waiting for
support — the conservative direction for a study that recommends charging
early.

**The timing grid meets the transfer date.** Fall 2027 is about 1.15 years from
the study date, so on an annual grid years 0 and 1 begin before it and year 2
does not. Year 1 — the phased game's recommendation — sits on the boundary.

**At the assumed political cost, the second gate does not bind.** The bargained
surplus is comfortably positive in both regimes, P(deal) ≈ 0.99, and the joint
recommendation is the phased one: charge in year 1. That is the honest
baseline, and on its own the joint model would add nothing.

**But the Province refused in 2017.** §11a inverts that into a revealed bound:
a refusal implies a political cost above about **\$3.91** per charged trip,
four times the assumed rate. Sweeping the rate:

| \$/charged trip | P(deal) pre-transfer | P(deal) post-transfer | Optimal start | Before the transfer? |
|---|---|---|---|---|
| 0.90 *(assumed)* | 1.00 | 1.00 | year 1 | yes |
| 2.00 | 0.96 | 0.99 | year 1 | yes |
| **3.50** | **0.13** | **0.93** | **year 2** | **no** |
| 5.00 | 0.00 | 0.72 | year 2 | no |
| 8.00 | 0.00 | 0.08 | year 2 | no |
| 10.00 | 0.00 | 0.00 | — | no charge at all |

**The recommendation reverses at \$3.50 — just below the \$3.91 the 2017
refusal implies.** On the model's own revealed bound, the advice is to wait
until *after* the transfer, not to rush a deal before it.

**Why, and why it is counterintuitive.** A zone of agreement survives to a
*higher* political cost after the transfer than before. Once the Province owns
the road, its fallback is a unilateral freeway charge that carries political
cost of its own — it is exposed either way, so the political cost of *agreeing*
is smaller in difference terms. The leverage argument (§11a: the City's
position weakens in 2027) and the political-cost argument point in opposite
directions, and which dominates is an empirical question about a rate this
study cannot measure. Both are reported.

**A trap worth recording.** At \$10 no deal is reachable in any year, so every
year returns the same no-charge welfare and `argmax` picks year 0 — which reads
as the recommendation swinging back to "charge immediately". It is not a
recommendation to charge early; it is a recommendation not to charge at all.
Degenerate rows now report a null start year, and a test pins it.

**Still not modelled.** The charge level is fixed across the sweep, so this
answers *when*, not when and how much jointly. The leader commits to a date and
cannot re-propose after a failed vote. And the transfer date is treated as
certain, though it has slipped before.

---

## 7g. The comparative record, used as evidence

Six cities run a full-scale congestion charge — Singapore (1975), London
(2003), Stockholm (2007), Milan (2008), Gothenburg (2013) and New York
(January 2025). Three more tried and failed. `comparators.py` and the **Other
cities** page use them to test this study rather than to decorate it.

**The table is complete and the units are not the same.** All six operating
schemes now carry a charge and a measured traffic response. Two things stop
that being a single comparable series, and both are recorded as columns rather
than as a footnote:

- `charge_basis` — London, Milan and New York levy **once per day** however many
  times you cross; Singapore, Stockholm and Gothenburg charge **every passage**.
  A daily \$19 and a per-passage \$2 can be the same annual cost to a
  twice-a-day commuter and wildly different for anyone else. The charge/response
  chart plots them as two series and fits nothing.
- `traffic_metric` — each percentage names exactly what was counted, because
  they are not the same quantity. Milan's headline is often quoted as a 28%
  *congestion* reduction; the figure used here is the **31.1%** fall in daily
  cordon **entries** (131,898 → 90,849 in 2012), which has counts behind it.
  Putting a congestion figure in a traffic column would have been a category
  error of exactly the kind this codebase keeps catching.

| City | Charge | Basis | Traffic | What was measured |
|---|---|---|---|---|
| Gothenburg | \$2.10 | per passage | −10.0% | area volume, charged hours, year one |
| Stockholm | \$4.30 | per passage | −20.0% | cordon crossings; the reduction *grew* over a decade |
| Singapore | \$4.45 | per passage | −15.0% | expressway volume during ERP hours |
| Milan | \$5.40 | daily | −31.1% | daily cordon entries, 2012 vs 2011 |
| New York | \$9.00 | daily | −11.0% | zone entries, year one |
| London | \$19.00 | daily | −16.0% | traffic within the zone, year one |

**Price does not order the response.** In the daily group the *cheapest* scheme
produced the largest reduction and the dearest less than half of it — Milan at
\$5.40 cut entries 31%, London at \$19 cut traffic 16%. Network geometry and
the quality of the alternatives evidently matter more than the rate. That is the
same conclusion the model reached internally, where **coverage** moved the
diversion result far more than the **rate** did.

Three points per basis, so nothing is fitted and no elasticity is estimated
from other people's cities. The prose describing this pattern is *generated
from the computed table* rather than written beside it — an earlier draft
asserted the ordering failed in both bases when it fails in one, which is how a
caption stops matching its figure. A test pins the two together.

**An out-of-sample check.** New York is the only North American scheme and the
closest comparator available. It charges \$9 and observed an **11%** fall in
vehicles entering the zone in its first year. Running this model at \$9 gives
a **13.1%** fall in AM-peak vehicles — *larger*, which is the wrong direction:
a suburban gateway with weaker alternatives should shed less traffic than a
Manhattan cordon at the same price.

The leading explanation is that the two are not the same quantity. New York's
figure is zone entries averaged over a whole year and a whole day; this is
AM-peak vehicles across a screenline, and a peak-only response is normally the
larger, because peak travellers can retime and off-peak ones have no charge to
avoid. That plausibly accounts for the 2.1 pp gap and it is **not established
that it does**, so the module reports `verdict: unresolved` rather than
claiming either a passed test or a refuted model. The MTA publishes CRZ entries
by hour, so this is settleable — and if the gap survives a like-for-like
comparison, the logit scale is too responsive and this study's demand response
is too strong.

**Where the record contradicts this study.** Kept as a first-class output,
because a comparison that only finds corroboration is not being used as
evidence:

| This study says | The record says | Why the model cannot see it |
|---|---|---|
| The design removes 39.4% of peak delay | London's traffic reduction was permanent but its **delay** reduction was not — congestion returned to roughly pre-charging levels within five years | Static equilibrium: no background demand growth, no reallocation of freed road space, no induced demand. The delay figure is a first-year effect, not a steady state |
| Acceptability runs on net position and a citizen view rising with income | Edinburgh rejected its charge **74.4% to 25.6%** on *trust* — only one in four believed the revenue would reach transport, and car ownership predicted the vote better than income | There is no trust term. Toronto's own 2016–17 episode is the local reason to take that seriously |
| A revenue package improves acceptability | Manchester attached a **£3bn** transport package and still lost | Recycling enters through net position, so a large enough package always helps. The record says it is not sufficient when the charge is not believed to work |

**And one place it corroborates.** Stockholm has **no income-based discount of
any kind** and is still not regressive, because wealthy inner-city residents pay
the most and the revenue funds transit that low-income riders use
disproportionately. That is the same mechanism as §7b's finding that the 905
pays *less* than its share here. Geography can do the distributional work a
means test would otherwise have to — but only where the geography cooperates,
which is a fact about a city rather than a design principle.

**Exemptions are a distributional instrument, not administration.** Gothenburg's
company-car exemption moves its Suits index from −0.06 to **−0.13** — an
exemption granted for convenience roughly doubled the scheme's regressivity,
doing more damage than the rate ever did.

---

## 7g-i. How the comparison charts were built

Recorded because the choices were made against a validator rather than by eye,
and one of them is a deliberate deviation.

**Every label position is checked, not eyeballed.** Measuring the rendered SVG
found four collisions across the three charts: the timeline staggered markers by
array index rather than by horizontal position, so whether two labels overlapped
depended on their order in the list rather than on their years; and the bar
chart's value labels ran left past the axis gutter onto the category names, with
the axis title clipping the zero tick. All four are fixed and the measured count
is now zero in both light and dark.

**The scatter had no identity at all.** Seven points carried their city only in
colour and a hover tooltip — unreadable on a printed page or in a screenshot,
which is how a competition submission is actually read. Every point is now
directly labelled, placed by a small greedy solver that tries right, left, above,
then below and takes the first slot that misses everything already placed.

**The palette was validated, and it failed twice before it passed.**

- The first attempt used grey for the taxes. It failed the chroma floor (it *is*
  grey) and, worse, sat at ΔE 14.5 from the green "This corridor" bar — below the
  15 normal-vision floor, for two adjacent bars one of which is the whole point
  of the chart.
- The obvious replacement, blue and purple, passes in light and **collapses to
  ΔE 1.9 in dark**. Dark mode had to be selected against the dark surface, not
  flipped.

The trio that passes both is blue (operating) / green (proposed) / orange (this
corridor), with one WARN in light on the green's 2.74 contrast — relieved, as the
method allows, by direct labels on every mark and a full table below. The same
three slots are used on every chart on the page, so this study is orange
everywhere; an entity that changes colour between two charts is two entities to
a reader. The scatter's previous amber failed the same normal-vision floor
against the orange (ΔE 13.7).

**The one deliberate departure.** The other taxes are no longer plotted. Grey
said what they are — a yardstick, not a comparator — and no colour that passed
validation could say it. Rather than give them a categorical hue that claims they
are peers, they are rendered as a labelled reference strip beneath the chart.
That is what a yardstick is, and it removes the failing adjacency entirely. A
congestion charge is not made acceptable by being less regressive than a fuel
tax, and the chart should not imply otherwise.

---

## 7h. The curve behind the Suits index

The Suits index is a single number standing for a whole curve, and two schemes
with the same index can hurt different people. `equity.suits_curve` returns the
concentration curve the index is integrated from — cumulative share of the
charge paid against cumulative share of income, poorest to richest — so *where*
a charge is regressive can be seen rather than asserted. Above the diagonal is
the regressive direction.

The curve has one point per distinct income — five, because income here is a
quintile rather than a measured value — joined by chords. On the recommended
design the gap is widest at the **fourth-quintile boundary**: the bottom 80% of
travellers hold **54.2%** of corridor income and pay **68.3%** of the charge.
Per knot:

| Cumulative through | Share of income | Share of charge | Gap |
|---|---|---|---|
| Q1 | 2.1% | 3.9% | 0.018 |
| Q2 | 9.3% | 11.7% | 0.025 |
| Q3 | 25.0% | 35.7% | 0.107 |
| **Q4** | **54.2%** | **68.3%** | **0.141** |

So the charge bites hardest across the whole span *below* the top quintile, not
at the very bottom — which the income credits reach first. A design tuned only
on the bottom quintile would leave that untouched and still report an improved
index.

Two corrections were made here, and both are worth stating because they changed
published numbers.

**The index was not tie-order invariant.** It was built by walking segments in
`np.argsort(income)` order, but income takes only five distinct values, so all
70 segments arrive in 14-way ties — and segments tied on income carry very
different burdens. The cumulative charge therefore depended on the order numpy
happened to return, and `argsort` defaults to an *unstable* quicksort, so the
answer was not reproducible across numpy versions. Sweeping the tie order over
the real segments moves the index by **0.045 to 0.089** depending on the design
— wider than the gaps between the published benchmarks in §7 that this study
ranks itself against, and enough to reorder the equity packages against each
other. Aggregating each income level into one point is the only tie-order-free
reading, is what the classical Suits index does on income brackets, and is
pinned by a test that permutes the segments. Correcting it moved the reported
indices by +0.002 to +0.006; the §7 conclusion is unaffected.

**The curve was resampled onto a 24-point grid**, a holdover from when it had 70
points. With five knots and straight chords between them a grid cannot add
information, and it cost accuracy: it reported the widest gap at 52%/66%, a
neighbouring grid point rather than the actual knot at 54.2%/68.3%. The curve
now returns its knots.

A test integrates the reported curve and requires it to return the reported
index — now to 1e-4 rather than the 0.01 that was absorbing the interpolation
error. Two further tests pin the sign against constructed cases — a flat charge
on unequal incomes must sit above the diagonal *and* return a negative index —
because these disagreeing in sign is precisely the bug that once reported this
charge as progressive.

---

## 7i. Does the delay reduction last?

London's traffic reduction was permanent and its **delay** reduction was not:
congestion returned to roughly pre-charging levels within about five years. A
static equilibrium cannot produce that at any parameter value — it solves one
point in time, so whatever it finds is permanent by construction. The study's
most quotable number was therefore a first-year effect being read as a steady
state, and it was the highest-severity disagreement in §7g.

`reversion.py` re-solves the equilibrium year by year against a no-charge
counterfactual that grows the same way. Comparing a future charged year against
*today's* baseline would attribute ordinary demand growth to the charge.

Two mechanisms, and separating them matters more than either number:

| | Mechanism | Kind |
|---|---|---|
| **Background growth** | More trips on the same network progressively re-occupy the delay the charge removed | Exogenous — happens either way |
| **Reallocation** | Freed capacity handed to bus lanes, footway, public realm | **A choice.** The space stopped being available to cars; the charge did not stop working |

**Growth alone erodes; it does not revert.** The recommended design's delay
reduction falls from **39.4%** to **34.7%** over ten years at 1.5% annual demand
growth, with no policy change at all.

**Reproducing London takes a deliberate reallocation.** Inverted rather than
assumed, for the same reason §11a inverts the political-cost rate — nobody has
measured how much of a Toronto gantry's freed capacity would be handed to buses:

| Reallocation | Delay reduction at year 5 | Traffic change at year 5 |
|---|---|---|
| 0% | 37.7% | −7.1% |
| 12% | 28.7% | −14.9% |
| 20% | 16.4% | −19.8% |
| **28%** | **−0.2%** | **−24.7%** |

At 28% the delay benefit has gone by London's fifth year **while traffic is down
more than at the start**. That is London's asymmetry exactly, and it carries the
conclusion: *pricing converts congestion into road space, and whether the delay
benefit survives depends on what the authority then spends it on.* A study that
reported reversion without saying which mechanism caused it would be telling a
Toronto reader that pricing wears off.

`space_reallocation_share` defaults to **0** — the model must not assume Toronto
gives the space away — so nothing outside this section moves.

**Not modelled**: land-use change, trip generation outside the screenline, and
any authority response other than reallocating capacity. Background growth is a
planning assumption, not a forecast, and is swept.

### The bug this uncovered

Building it required the scenario network and the baseline network to be scored
separately, which exposed an error in `metrics.compute`: it evaluated **both**
sides on the scenario's network. Every "against baseline" figure is a ratio, so
evaluating baseline volumes on an improved network shrinks the denominator and a
scenario is charged for the improvement it made while credited with none of it.

The no-charge operational package was understated by **11.2 percentage points**
— 33.9% where it should have read 45.2% — which **reversed §9's finding that
pricing beats good operations**. Pure-price scenarios were unaffected, because
for them the two networks are the same object, which is exactly why it survived:
it was invisible on most of the scenario library.

---

## 7f-i. Choosing the price and the year together

§7f fixes the charge and sweeps the start year, so it answers *when* rather than
when and how much. The leader chooses both. `joint_game.joint_optimum` sweeps
the surface.

**The political gates barely discipline the price.** Support at the enactment
gate falls only from 54.7% to 48.2% across a $2–$25 range, because a larger
charge also recycles more and because travellers priced off the road stop paying
it. So expected welfare rises almost monotonically with the charge, and an
unconstrained joint solve simply runs the price to the top of whatever grid it
is given — a grid boundary, not a result.

**What disciplines the price is the constraint set.** Applying the same
constraints `game.stackelberg_search` uses, the highest admissible charge is
**$12**; **$14 fails the equity floor**. The joint answer is therefore:

| | Charge | Start year | E[discounted welfare] |
|---|---|---|---|
| Unconstrained | $16+ (grid edge) | 1 | 0.705 |
| **Constrained** | **$12** | **1** | **0.409** |

The gap, **0.296 welfare points**, is the price the corridor pays for its own
equity floor — the same quantity §9 reports against the unconstrained Stackelberg
optimum, now expressed jointly with timing.

**Is the problem separable?** Asymmetrically, which a single flag cannot say:

- The best **charge is the same at every start year** ($12 throughout).
- The best **year is not the same at every charge** — year 0 at $6, year 1 above it.

Because the price dimension is the invariant one, solving in sequence — price
first at the year the fixed-charge sweep recommends, then timing at that price —
reaches ($12, year 1), which *is* the joint optimum. So the joint machinery
confirms the sequential answer here rather than overturning it. That is a fact
about this corridor and not a general one: the asymmetry is precisely what makes
the order of solving matter, and a corridor where the best price moved with the
start year would need the two chosen together.

**The finding worth carrying:** the charge is set by the **equity floor**, not by
public acceptability. Acceptability is nearly flat in the price over the whole
plausible range, so a study that argued about the price on acceptability grounds
would be arguing about the wrong constraint.

---

## 7f-ii. The two gates are not independent

`P(enacted) = P(voters) × P(deal)` treats public acceptance and intergovernmental
agreement as unrelated events. They are not: **a scheme the public wants is
cheaper for a government to authorise**, so waiting for support should buy a
better bargain as well as a better vote. This was the joint model's most
questionable simplification.

The dependence is modelled through the **mechanism** rather than as a
correlation between the two probabilities — a mechanism can be argued with and a
correlation coefficient cannot. Authorising an unpopular policy costs a
politician more, so the political cost rate itself moves with support:

```
rate(support) = base · (1 + gate_dependence · (1 − 2 · support))
```

At **50% support** — the referendum threshold — the rate is exactly the stated
base whatever the dependence, so this rotates the line about the existing anchor
rather than shifting it, and `gate_dependence` defaults to **0**: every result
computed under independence still holds. The rate is floored at zero, because
there is no evidence for a government being *paid* to authorise and a negative
cost would invert the term the whole bargain turns on.

### Whether it matters depends entirely on whether the gate binds

| Political cost | Value of waiting, independent | …with dependence | Ratio | Deal gate binds? |
|---|---|---|---|---|
| $0.90 *(assumed)* | 0.145 | 0.146 | **1.01** | No |
| $2.00 | 0.139 | 0.170 | 1.22 | No |
| **$3.50** | **0.019** | **0.111** | **5.69** | **Yes** |
| $5.00 | 0.000 | 0.000 | — | Yes (no deal at all) |

At the assumed $0.90 the assumption is nearly harmless: P(deal) is about 0.997
either way, so independence costs under half a percent of the value of waiting.

**It matters exactly where the study's own revealed bound puts us.** The Province
refused in 2017, so its valuation sits above **$3.91** (§11a). At $3.50 — just
below that bound — allowing the gates to move together makes waiting for support
**5.7× more valuable**, because charging immediately now fails *both* gates while
waiting improves both.

### What this does and does not change

**The ranking is unaffected throughout.** Dependence changes how much waiting is
worth, not whether to wait, at every cost and dependence tested. So §7f's
sequencing recommendation stands — and stands more strongly than the independent
model claimed, because independence was systematically *understating* the case
for building support first.

The strength of the dependence is unobservable, so it is swept rather than set.

---

## 8. Finance

Three administrative cost cases throughout, because the *sign* of the financial
answer changes with an assumption nobody can pin down before procurement. No
charge means no scheme, so an untolled baseline is not charged the fixed
operating cost of a system that was never built.

---

## 9. The leader's problem

Weighted welfare across delay, revenue, reliability, emissions, equity, diversion
and deliverability, with an explicit implementation-difficulty score rather than
one buried in a weight. Constraints: local-diversion cap, equity floor, minimum
congestion improvement, transit capacity.

The **Pareto frontier** is presented alongside the weighted winner, because the
frontier shows the trade-off instead of hiding it inside a choice of weights.

Both the constrained and unconstrained optima are reported. The gap is the price
of protecting local streets and low-income travellers, and stating it explicitly
is more useful than quietly reporting only the constrained winner.

---

## 10. Robustness

**Tornado** — one parameter at a time across its plausible range, ranked by the
swing it produces.

**Monte Carlo** — Latin hypercube over fourteen uncertain parameters, reporting
the probability each policy is the best *feasible* one. Win probability is
computed only among policies still satisfying the constraints in that draw,
because a policy that posts the highest median delay reduction but only clears the
constraints in a minority of draws is not a recommendation.

---

## 11. Governance

A toll cannot be levied on a highway where the Crown is the road authority unless
an Act permits it, and the Gardiner transfers to the Province in fall 2027. Two
branches are carried throughout rather than treated as a footnote:

- **Branch A** — direct charge on the expressway, assuming provincial authorisation.
- **Branch B** — City-controlled instruments only: an arterial charge, or a
  parking-linked demand-management package.

Branch B is not a variation on the recommendation. It is a different policy with
different economics and, as the model finds, a worse distributional profile.

---

## 11a. The City and the Province as players

§11 carries governance as two branches — A assumes provincial authorisation
arrives, B assumes it never does. That is not a game; it is a pair of
assumptions about how a negotiation turns out. `bargaining.py` models the
negotiation.

**It has been played once already.** In December 2016 Toronto Council voted
32–9 to toll the Gardiner and the DVP. In January 2017 the Province refused,
and offered instead a doubled municipal share of the gas tax, worth about
\$170M a year — roughly 0.85 of what the City estimated the tolls would raise.
A disagreement outcome, a side payment, and a revealed price for provincial
authorisation. It is one observation under a different government, so it
disciplines the model's sign rather than its magnitudes.

**The asymmetry.** 40% of AM-peak corridor demand originates outside Toronto,
in Mississauga and the west GTA — derived from the segment table, not assumed.
Those travellers are not the City's voters and they are the Province's,
disproportionately so, since 905 seats decide provincial majorities. The same
charge therefore imposes more political cost on the Province than on the City,
while the congestion benefit lands mostly inside Toronto. A charge can be
jointly worth having and still be refused. That is not a failure of analysis;
it is the record.

**Payoffs** are annual dollars, so the Nash product means something. Both sides
are linear in the revenue split, so Nash and Kalai–Smorodinsky have closed
forms. Both are reported, because they diverge exactly when stakes are
lopsided, and reporting one alone would hide that the answer depends on which
axioms you accept. The more important output is the **bargaining set** — the
splits on which both sides beat walking away. An empty set means no deal at any
price.

**What the 2027 transfer actually does.** Not what a first pass suggests. The
repair liability moving from City to Province *cancels out of the bargain*: a
lump sum shifts a player's deal and no-deal payoffs equally, changing welfare
levels but not the incentive to agree. A test pins this, because an earlier
version of the module put the transfer's whole effect in that term, where it
silently did nothing.

What changes is the **Province's fallback**:

| | City can charge Gardiner alone? | Province can? |
|---|---|---|
| Before fall 2027 | No (needs authorisation) | No (does not own it) |
| After fall 2027 | No | **Yes** |

Today the two hold a mutual veto, which is what makes this a genuine bilateral
bargain. After the transfer the Province owns the road and authorises itself.
The City's fallback does not improve — it still has only Branch B, a charge on
its own arterials, which this study finds is the most regressive design in the
library.

**The option the Province gains is a freeway-only charge**, and this study finds
that design pushes **+11.6%** onto The Queensway, breaching the local-street
cap. Those are City streets. After 2027 the Province can impose a charge whose
diversion lands on the City, and the City has no standing to object.

**Why the measured loss of leverage is small.** The City's bargained surplus
falls under 1%. The reason connects two other findings: the Province's new
unilateral option is financially marginal, because fixed collection costs do
not scale down and a \$4 freeway-only charge does not cover itself. A threat
that loses money is a weak threat. The City's exposure is not to the Province's
revenue — it is to the diversion.

**The unobservable, inverted.** The political-cost rate is the least defensible
number here, and at its assumed value a deal exists at any split, which sits
awkwardly beside the Province having actually refused. Rather than tune the rate
until the model reproduces 2017, `breakeven_political_cost` finds the rate at
which the zone of agreement closes: **\$3.91** per charged trip per year before
the transfer, **\$8.75** after. Because the Province did refuse, its true
valuation lies above the pre-transfer threshold — a revealed-preference lower
bound from a real decision, which is worth more than a fitted coefficient.

**Not modelled.** Revenue is the only transferable instrument; the actual New
Deal traded highways against transit capital, land and Ontario Place at once.
Bargaining is one-shot, with no reputation and with 2027 as a hard boundary
rather than a lever. And the sequencing game in §7e is solved separately from
this one rather than jointly.

---

## Working sources

- City of Toronto — [About the Gardiner Expressway](https://www.toronto.ca/services-payments/streets-parking-transportation/road-maintenance/bridges-and-expressways/expressways/gardiner-expressway/about-the-gardiner-expressway/)
- City of Toronto — [Gardiner Section 3: Highway 427 to Humber River](https://www.toronto.ca/services-payments/streets-parking-transportation/road-maintenance/bridges-and-expressways/expressways/gardiner-expressway/gardiner-expressway-rehabilitation-strategy/section-3-highway-427-to-humber-river/)
- City of Toronto — [2026 Congestion Management Plan](https://www.toronto.ca/news/city-of-torontos-congestion-plan-drives-co-ordinated-action-to-keep-people-moving/)
- City of Toronto / Province — [Gardiner and DVP transfer](https://www.toronto.ca/news/city-of-toronto-and-province-of-ontario-advancing-transfer-of-gardiner-expressway-and-don-valley-parkway/)
- CANCEA — [Impact of Congestion in the GTHA and Ontario](https://www.cancea.ca/index.php/2024/12/09/impact-of-congestion-in-the-gtha-and-ontario-economic-and-social-risks/)
- Metrolinx — [Business Case Manual Volume 2](https://assets.metrolinx.com/image/upload/v1663237565/Documents/Metrolinx/Metrolinx-Business-Case-Guidance-Volume-2.pdf)
- Metrolinx — [Lakeshore West Line GO Expansion](https://www.metrolinx.com/en/projects-and-programs/lakeshore-west-line-go-expansion)
- GO Transit — [Fare information](https://www.gotransit.com/en/ways-to-pay/fare-information) · [Mimico station](https://www.gotransit.com/en/find-a-station-or-stop/mi)
- TTC — [Fares and passes](https://www.ttc.ca/Fares-and-passes)
- DMG / TTS — [Auto Passenger Travel and Auto Occupancy in the GTA](https://dmg.utoronto.ca/wp-content/uploads/2023/03/auto_pass.pdf)
- [Transportation Tomorrow Survey](http://www.transportationtomorrow.on.ca/)
- U of T School of Cities — [Could Congestion Pricing Unlock a Better Toronto?](https://schoolofcities.utoronto.ca/could-congestion-pricing-unlock-a-better-toronto/)
- Build Canada — [Adaptive traffic intersections](https://www.buildcanada.com/toronto/memos/adaptive-traffic-intersections) · [Congestion pricing](https://www.buildcanada.com/toronto/memos/congestion-pricing)
- Ontario — [Public Transportation and Highway Improvement Act](https://www.ontario.ca/laws/statute/90p50)
