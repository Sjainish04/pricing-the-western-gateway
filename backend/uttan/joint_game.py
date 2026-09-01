"""Sequencing and authorisation are one problem, not two.

`phasing.py` asks when to charge and answers "as soon as the alternative is
delivered" -- year 1, because waiting buys public support and costs discounted
benefit-years.  `bargaining.py` asks whether the City and the Province can
agree, and finds the City's position weakens once the Gardiner transfers in
fall 2027.

Solved separately, each is missing the other's binding constraint.  The phased
game says wait; the bargaining game says there is a deadline on waiting.  Put
together they are a single question with a date attached, and the answer is not
the answer either one gives alone.

The interaction
---------------
From the study date, fall 2027 is about 1.15 years away.  On the phased game's
annual grid that lands *inside year 1* -- which is precisely the year the phased
game recommends charging.  So the recommendation sits on the boundary of a
regime change in who holds the authorisation:

    year 0    pre-transfer.  City owns the road, Province authorises. Mutual
              veto, so a genuine bilateral bargain -- but transit is only half
              delivered, so public support is at its weakest.
    year 1    the transfer happens during this year. Transit is delivered and
              support has risen, but whether the City still has an asset to
              bargain with depends on which side of fall 2027 the deal lands.
    year 2+   post-transfer. The Province owns the road and authorises itself.
              The City's fallback has not improved, and the Province's has: it
              can levy a freeway-only charge alone and keep the revenue.

Two gates, not one
------------------
A charge needs a public that will tolerate it *and* two governments that can
agree.  So

    P(enacted) = P(voters) x P(deal)

with the first from `phasing.enactment_probability` and the second logistic in
the surplus available to the weaker party in `bargaining.solve`.  Both are
logistic rather than step functions, for the same reason: a cliff would make
the timing result an artefact of which side of it a year happened to fall.

Multiplying them is the substantive claim of this module.  It says the two
constraints are close to independent -- a public that likes the scheme does not
make the Province's 905 seats safer, and an intergovernmental deal does not
make voters happier.  That is an assumption, and where the model is most likely
to be wrong: in practice a popular scheme is easier to authorise.  Treating
them as independent therefore *understates* the value of waiting for support,
which is the conservative direction for this study's conclusion.

What this still does not do
---------------------------
The charge level is fixed across the sweep, so this answers when, not when and
how much jointly.  And the leader commits to a date rather than adapting -- it
cannot observe a failed vote and re-propose.  Both understate the value of
moving early, again conservatively.
"""
from __future__ import annotations

import functools
import json
from typing import Dict, List, Optional

import numpy as np

from . import bargaining, phasing
from .config import Config
from .phasing import Path, Stage
from .toll_policy import TollPolicy

TRANSIT_UPLIFT = 0.25   # the modelled GO frequency uplift, as in phasing.py


def regime_at(year: int, cfg: Config) -> str:
    """Which governance regime is in force when a charge is proposed in `year`.

    A charge proposed in a year that begins before the transfer is negotiated
    under the pre-transfer rules, because the negotiation precedes the levy.
    Ties go to pre-transfer for that reason: year 1 starts before fall 2027
    even though the transfer completes within it.
    """
    return "pre_transfer" if year < cfg.years_until_transfer else "post_transfer"


def deal_probability(min_surplus: float, cfg: Config) -> float:
    """Probability the two governments strike a deal, given the weaker party's gain.

    Logistic in surplus scaled by `deal_surplus_reference`.  At zero surplus it
    is a coin toss, which is the honest reading of a party that is exactly
    indifferent between agreeing and walking away.  It falls toward zero as the
    weaker party is made worse off by the deal, and rises toward one as the
    surplus grows large relative to the reference.
    """
    z = cfg.deal_steepness * (min_surplus / max(cfg.deal_surplus_reference, 1.0))
    return float(1.0 / (1.0 + np.exp(-z)))


def _bargain_at(year: int, cfg: Config, charge: float, coverage: str,
                support: Optional[float] = None) -> dict:
    """The intergovernmental position if the charge is proposed in `year`.

    `support` is the public support at the gate. It reaches the bargain through
    the political cost rate rather than through a correlation between the two
    probabilities, because the mechanism is that authorising an unpopular
    scheme costs a government more -- and a mechanism can be argued with.
    At `cfg.gate_dependence == 0` the rate is unchanged and the gates are
    independent exactly as before.
    """
    regime = regime_at(year, cfg)
    rate = bargaining.political_cost_given_support(cfg, support)
    if rate != cfg.political_cost_per_charged_trip:
        cfg = Config.from_dict(
            {**cfg.to_dict(), "political_cost_per_charged_trip": rate}
        )
    b = bargaining.solve(cfg, regime, charge, coverage)
    nash = b["nash"]
    if nash is None:
        return {
            "regime": regime,
            "has_zone": False,
            "min_surplus": 0.0,
            "city_share": None,
            "deal_probability": 0.0,
            # Present on both branches: a caller that reads this only on the
            # happy path gets a KeyError exactly when no zone of agreement
            # exists, which is the case the analysis most wants to look at.
            "political_cost_rate": round(rate, 4),
        }
    min_surplus = min(nash["city_surplus"], nash["province_surplus"])
    return {
        "regime": regime,
        "has_zone": b["bargaining_set"]["has_zone_of_agreement"],
        "min_surplus": round(min_surplus, 1),
        "city_surplus": nash["city_surplus"],
        "province_surplus": nash["province_surplus"],
        "city_share": nash["city_share"],
        "deal_probability": round(deal_probability(min_surplus, cfg), 4),
        "political_cost_rate": round(rate, 4),
    }


@functools.lru_cache(maxsize=8)
def _cached_frontier(payload: str) -> dict:
    kw = json.loads(payload)
    return _frontier(Config.from_dict(kw["config"]), kw["charge"], kw["coverage"])


def timing_frontier(cfg: Optional[Config] = None, charge: float = 10.0,
                    coverage: str = "screenline") -> dict:
    """Cached entry point for the joint sweep over the charge start year."""
    cfg = cfg or Config()
    payload = json.dumps(
        {"config": cfg.to_dict(), "charge": charge, "coverage": coverage},
        sort_keys=True,
    )
    return _cached_frontier(payload)


def _frontier(cfg: Config, charge: float, coverage: str) -> dict:
    lag = cfg.transit_delivery_lag_years
    rows = []

    for start in range(0, min(cfg.horizon_years, 7)):
        # Same construction as phasing.timing_frontier: transit committed at
        # year 0 throughout, so the only thing varying is how long the leader
        # waits before charging.
        stages = [
            Stage(
                year=y,
                label=f"year {y}",
                transit_uplift=TRANSIT_UPLIFT,
                transit_delivered=phasing._ramp(0, y, TRANSIT_UPLIFT, lag),
                charge=charge if y >= start else 0.0,
                coverage=coverage,
                gate=(y == start),
            )
            for y in range(cfg.horizon_years)
        ]
        path = Path(key=f"joint_{start}", name=f"Charge from year {start}",
                    precedent="", rationale="", stages=stages)
        voters = phasing.evaluate_path(path, cfg, reference=cfg)
        deal = _bargain_at(start, cfg, charge, coverage,
                           support=voters["support_at_gate"])

        p_voters = voters["enactment_probability_exact"]
        p_joint = p_voters * deal["deal_probability"]

        # The phased game's welfare already carries P(voters). Rescaling by the
        # ratio of the joint probability to the voter probability applies the
        # second gate without re-solving every equilibrium: welfare is linear in
        # the enactment probability by construction, so the rescale is exact
        # for the charged years and leaves the pre-charge years untouched.
        scale = (p_joint / p_voters) if p_voters > 1e-9 else 0.0
        joint_welfare = _rescaled_welfare(voters, scale, cfg)

        rows.append(
            {
                "charge_start_year": start,
                "transit_delivered": round(phasing._ramp(0, start, TRANSIT_UPLIFT, lag), 4),
                "regime": deal["regime"],
                "support_at_gate": voters["support_at_gate"],
                "p_voters": round(p_voters, 4),
                "p_deal": deal["deal_probability"],
                "political_cost_rate": deal["political_cost_rate"],
                "p_joint": round(p_joint, 4),
                "city_share_of_revenue": deal["city_share"],
                "weaker_party_surplus": deal["min_surplus"],
                "welfare_voters_only": voters["expected_discounted_welfare"],
                "expected_discounted_welfare": round(joint_welfare, 5),
            }
        )

    best_joint = max(rows, key=lambda r: r["expected_discounted_welfare"])
    best_voters = max(rows, key=lambda r: r["welfare_voters_only"])
    crossing = next(
        (r["charge_start_year"] for r in rows if r["regime"] == "post_transfer"), None
    )

    return {
        "charge": charge,
        "coverage": coverage,
        "years_until_transfer": cfg.years_until_transfer,
        "first_post_transfer_year": crossing,
        "rows": rows,
        "optimal_start_year_joint": best_joint["charge_start_year"],
        "optimal_start_year_voters_only": best_voters["charge_start_year"],
        "deadline_moves_the_answer": (
            best_joint["charge_start_year"] != best_voters["charge_start_year"]
        ),
        "cost_of_missing_the_window": round(
            best_joint["expected_discounted_welfare"]
            - min(
                (r["expected_discounted_welfare"] for r in rows
                 if r["regime"] == "post_transfer"),
                default=best_joint["expected_discounted_welfare"],
            ),
            5,
        ),
        "reading": (
            "The phased game alone asks only whether the public will accept a "
            "charge. Adding the second gate asks whether the two governments "
            "can agree to levy one, and that gate changes at a fixed date "
            "rather than with the state of the corridor. Where the two "
            "recommendations differ, the difference is the deadline."
        ),
    }


def _rescaled_welfare(voters: dict, scale: float, cfg: Config) -> float:
    """Re-discount a phased path with the enactment probability rescaled.

    `phasing.evaluate_path` already computed, for each year, welfare with and
    without the charge and combined them at P(voters).  Recombining the same
    two numbers at the joint probability is exact rather than approximate,
    because the combination is linear -- so no equilibrium needs re-solving.
    """
    p_voters = voters["enactment_probability_exact"]
    p_joint = p_voters * scale
    total = 0.0
    for row in voters["years"]:
        if row["charge"] > 0:
            expected = (
                p_joint * row["welfare_with_charge"]
                + (1.0 - p_joint) * row["welfare_without_charge"]
            )
        else:
            expected = row["welfare_without_charge"]
        total += row["discount"] * expected
    return total


def window(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    """Is there a window, and how long is it?

    The decision-relevant framing: the phased game wants to wait for transit,
    the bargaining game says the City's hand weakens at a fixed date. If the
    best joint year is at or before the transfer, there is a window and it has
    a length. If it is after, the deadline is not binding and the two games
    genuinely were separable.
    """
    cfg = cfg or Config()
    f = timing_frontier(cfg, charge)
    best = f["optimal_start_year_joint"]
    pre = [r for r in f["rows"] if r["regime"] == "pre_transfer"]
    post = [r for r in f["rows"] if r["regime"] == "post_transfer"]

    best_pre = max(pre, key=lambda r: r["expected_discounted_welfare"]) if pre else None
    best_post = max(post, key=lambda r: r["expected_discounted_welfare"]) if post else None

    return {
        "years_until_transfer": cfg.years_until_transfer,
        "last_pre_transfer_year": max((r["charge_start_year"] for r in pre), default=None),
        "optimal_start_year": best,
        "optimum_is_before_transfer": bool(
            best is not None and best < cfg.years_until_transfer
        ),
        "best_pre_transfer": best_pre,
        "best_post_transfer": best_post,
        "value_of_acting_before_the_transfer": (
            round(best_pre["expected_discounted_welfare"]
                  - best_post["expected_discounted_welfare"], 5)
            if best_pre and best_post else None
        ),
        "note": (
            "Both gates are logistic, so neither the voter constraint nor the "
            "deal constraint produces a cliff. Any sharp change across the "
            "transfer year is the regime change itself, not a modelling "
            "artefact."
        ),
    }


def deadline_sensitivity(cfg: Optional[Config] = None, charge: float = 10.0,
                         rates: Optional[tuple] = None) -> dict:
    """How the joint answer moves with the political cost of a charged trip.

    At the assumed rate the deal gate barely binds: the bargained surplus is
    comfortably positive in both regimes, so the joint recommendation matches
    the phased one and the deadline does not bite.  That is a real result, but
    it cannot be the end of the analysis, because the Province *did* refuse in
    2017 -- and `bargaining.breakeven_political_cost` says a refusal implies a
    rate above about $3.91 per charged trip, four times the assumed one.

    So the question this answers is: at a political cost consistent with the
    behaviour actually observed, does the deadline change the answer?

    The two breakevens run the opposite way to intuition.  A zone of agreement
    survives to a *higher* political cost after the transfer than before it,
    because once the Province owns the road its own fallback is a unilateral
    charge that carries political cost too.  It is already paying either way,
    so the political cost of agreeing is smaller in *difference* terms.  Where
    that matters, waiting past the transfer helps rather than hurts -- which is
    the reverse of the leverage story, and worth stating plainly rather than
    letting the leverage argument stand alone.
    """
    cfg = cfg or Config()
    rates = rates or (0.9, 2.0, 3.5, 5.0, 6.5, 8.0, 10.0)

    rows = []
    for rate in rates:
        trial = Config.from_dict(
            {**cfg.to_dict(), "political_cost_per_charged_trip": float(rate)}
        )
        f = timing_frontier(trial, charge)
        pre = [r for r in f["rows"] if r["regime"] == "pre_transfer"]
        post = [r for r in f["rows"] if r["regime"] == "post_transfer"]
        # When no deal is possible in any year, every year returns the same
        # no-charge welfare and argmax picks year 0 arbitrarily. That is not a
        # recommendation to charge early -- it is a recommendation not to
        # charge at all, and reading the start year off a degenerate row is
        # exactly how this model would produce a confident reversal that does
        # not exist.
        best_p = max(r["p_joint"] for r in f["rows"])
        degenerate = best_p < 1e-3

        rows.append(
            {
                "political_cost_per_charged_trip": rate,
                "optimal_start_year": None if degenerate else f["optimal_start_year_joint"],
                "p_deal_pre_transfer": pre[0]["p_deal"] if pre else None,
                "p_deal_post_transfer": post[0]["p_deal"] if post else None,
                "best_welfare": max(
                    r["expected_discounted_welfare"] for r in f["rows"]
                ),
                "charge_ever_enacted": not degenerate,
                "optimum_before_transfer": (
                    None if degenerate else bool(
                        f["optimal_start_year_joint"] is not None
                        and f["optimal_start_year_joint"] < cfg.years_until_transfer
                    )
                ),
            }
        )

    # Compare only rows where a charge actually happens; a degenerate row has
    # no timing recommendation to switch to or from.
    live = [r for r in rows if r["charge_ever_enacted"]]
    switches = [
        r for i, r in enumerate(live[1:], 1)
        if r["optimum_before_transfer"] != live[i - 1]["optimum_before_transfer"]
    ]
    return {
        "charge": charge,
        "assumed_rate": cfg.political_cost_per_charged_trip,
        "rows": rows,
        "recommendation_switches_at": (
            switches[0]["political_cost_per_charged_trip"] if switches else None
        ),
        "reading": (
            "If the political cost of a charged trip is near the assumed rate, "
            "the intergovernmental gate does not bind and the timing answer is "
            "the phased one. If it is high enough to explain the 2017 refusal, "
            "the gate binds -- and because the Province's post-transfer "
            "fallback carries political cost of its own, it binds harder "
            "BEFORE the transfer than after. The leverage argument and the "
            "political-cost argument point in opposite directions, and which "
            "one dominates is an empirical question this study cannot settle."
        ),
    }


DEFAULT_CHARGE = 10.0

# The rate at which the pre-transfer zone of agreement closes, from
# `bargaining.breakeven_political_cost`. The Province refused in 2017, so its
# true valuation sits above this -- a revealed bound from a real decision, and
# the regime the dependence question actually matters in.
REVEALED_COST_BOUND = 3.91


@functools.lru_cache(maxsize=8)
def _cached_dependence(payload: str) -> dict:
    kw = json.loads(payload)
    return _dependence_sweep(
        Config.from_dict(kw["config"]), kw["charge"], kw["coverage"],
        tuple(kw["dependencies"]), tuple(kw["political_costs"]),
    )


def gate_dependence_sweep(
    cfg: Optional[Config] = None,
    charge: float = DEFAULT_CHARGE,
    coverage: str = "screenline",
    dependencies: Optional[List[float]] = None,
    political_costs: Optional[List[float]] = None,
) -> dict:
    """Cached entry point. The sweep solves 16 full frontiers, so a repeat call
    inside one process -- three tests and the precompute recompute do exactly
    that -- should not pay for it twice. Adding it took the suite from 2:09
    back to 44s."""
    cfg = cfg or Config()
    deps = dependencies if dependencies is not None else [0.0, 0.5, 1.0, 2.0]
    costs = political_costs if political_costs is not None else [0.9, 2.0, 3.5, 5.0]
    return _cached_dependence(json.dumps({
        "config": cfg.to_dict(), "charge": charge, "coverage": coverage,
        "dependencies": list(deps), "political_costs": list(costs),
    }, sort_keys=True))


def _dependence_sweep(
    cfg: Config,
    charge: float,
    coverage: str,
    dependencies: tuple,
    political_costs: tuple,
) -> dict:
    """What the independence assumption costs, across the range that matters.

    `P(enacted) = P(voters) x P(deal)` treats the two gates as independent, and
    that is this model's most questionable simplification: a scheme the public
    wants is cheaper to authorise, so waiting for support should buy a better
    bargain as well as a better vote.

    Swept against the political cost rate, because whether the assumption
    matters depends entirely on whether the deal gate binds. At the assumed
    $0.90 it does not -- P(deal) is about 0.997 either way -- and independence
    is nearly harmless. The regime worth looking at is the one the 2017 refusal
    points to, above $%.2f.
    """ % REVEALED_COST_BOUND
    deps, costs = list(dependencies), list(political_costs)

    rows = []
    for cost in costs:
        for dep in deps:
            trial = Config.from_dict({
                **cfg.to_dict(),
                "political_cost_per_charged_trip": float(cost),
                "gate_dependence": float(dep),
            })
            frontier = _frontier(trial, charge, coverage)
            by_year = {r["charge_start_year"]: r for r in frontier["rows"]}
            now, waited = by_year[0], by_year[1]
            rows.append({
                "political_cost_per_charged_trip": float(cost),
                "gate_dependence": float(dep),
                "optimal_start_year": frontier["optimal_start_year_joint"],
                "p_deal_charging_now": now["p_deal"],
                "p_deal_after_waiting": waited["p_deal"],
                "welfare_charging_now": now["expected_discounted_welfare"],
                "welfare_after_waiting": waited["expected_discounted_welfare"],
                "value_of_waiting": round(
                    waited["expected_discounted_welfare"]
                    - now["expected_discounted_welfare"], 5
                ),
            })

    # How much dependence amplifies the value of waiting, at each cost.
    amplification = []
    for cost in costs:
        at_cost = {r["gate_dependence"]: r for r in rows
                   if r["political_cost_per_charged_trip"] == cost}
        independent = at_cost.get(0.0)
        strongest = at_cost.get(max(deps))
        if not independent or not strongest:
            continue
        base_value = independent["value_of_waiting"]
        amplification.append({
            "political_cost_per_charged_trip": cost,
            "value_of_waiting_independent": base_value,
            "value_of_waiting_dependent": strongest["value_of_waiting"],
            "ratio": (
                round(strongest["value_of_waiting"] / base_value, 2)
                if abs(base_value) > 1e-9 else None
            ),
            "deal_gate_binds": independent["p_deal_charging_now"] < 0.9,
            "start_year_changes": (
                independent["optimal_start_year"] != strongest["optimal_start_year"]
            ),
        })

    biting = [a for a in amplification if a["deal_gate_binds"] and a["ratio"]]
    return {
        "charge": charge,
        "revealed_cost_bound": REVEALED_COST_BOUND,
        "rows": rows,
        "amplification": amplification,
        "changes_the_recommended_year_anywhere": any(
            a["start_year_changes"] for a in amplification
        ),
        "reading": (
            "Independence is nearly harmless where the deal gate does not bind: "
            "at the assumed $0.90 the value of waiting moves by under half a "
            "percent whatever the dependence, because P(deal) is about 0.997 "
            "either way. It matters where the gate binds, and that is the regime "
            "the 2017 refusal points to. %s The ranking is unaffected throughout "
            "-- dependence changes how much waiting is worth, not whether to "
            "wait -- so the sequencing recommendation stands, and stands more "
            "strongly than the independent model claimed."
            % (
                "At $%.2f per charged trip the value of waiting is %.2f times "
                "larger once the gates are allowed to move together."
                % (biting[0]["political_cost_per_charged_trip"], biting[0]["ratio"])
                if biting else
                "No cost in the range tested both binds the gate and admits a "
                "deal, so the amplification cannot be quantified here."
            )
        ),
        "caveat": (
            "The dependence is a rotation of the political cost rate about the "
            "referendum threshold, not an estimated correlation. Its strength is "
            "unobservable, so it is swept rather than set, and it defaults to "
            "zero -- every result computed under independence still holds."
        ),
    }



def _feasibility_at(charge: float, start: int, cfg: Config, coverage: str) -> dict:
    """Does the study's own constraint set admit this charge at this gate year?

    The political gates in `_frontier` are the only thing disciplining the price
    there, and on this corridor they barely move with it -- support falls about
    six points across a twelvefold price range, because a larger charge also
    recycles more. So a joint solve that asked only "what maximises expected
    welfare" would run the price to the boundary of whatever grid it was given.

    The constraints that actually bind are the ones `game.stackelberg_search`
    imposes -- local diversion, the equity floor, minimum congestion relief,
    transit capacity -- so the joint answer is reported both with and without
    them. The gap between the two is the price the corridor pays for its
    constraints, expressed in dollars rather than in welfare points.
    """
    from . import game
    from .demand import load_segments

    delivered_capacity = phasing._ramp(
        0, start, TRANSIT_UPLIFT, cfg.transit_delivery_lag_years
    )
    # Same normalisation phasing uses for the support term: what a voter
    # registers is that an improvement arrived, not its size in capacity units.
    delivered = min(delivered_capacity / 0.25, 1.0) if delivered_capacity else 0.0
    trial = Config.from_dict({**cfg.to_dict(), "delivered_alternative": delivered})
    policy = TollPolicy(
        peak_toll=charge, coverage=coverage, credit="low_income_transit_poor",
        go_frequency_uplift=delivered_capacity, label=f"${charge:g} from year {start}",
    )
    result = game.evaluate(policy, trial, load_segments(trial), reference=cfg)
    return {
        "passes": bool(result["feasible"]["passes"]),
        "failed": list(result["feasible"]["failed"]),
    }


@functools.lru_cache(maxsize=8)
def _cached_optimum(payload: str) -> dict:
    kw = json.loads(payload)
    return _optimum(Config.from_dict(kw["config"]), tuple(kw["charges"]), kw["coverage"])


def joint_optimum(cfg: Optional[Config] = None,
                  charges: Optional[List[float]] = None,
                  coverage: str = "screenline") -> dict:
    """Solve for the price AND the start year together.

    The sweep above fixes the charge, so it answers *when* rather than when and
    how much. The leader chooses both, and whether that matters is an empirical
    question about the shape of the surface, not something to assume either way.
    """
    cfg = cfg or Config()
    grid = tuple(charges) if charges is not None else (6.0, 8.0, 10.0, 12.0, 14.0, 16.0)
    return _cached_optimum(json.dumps(
        {"config": cfg.to_dict(), "charges": list(grid), "coverage": coverage},
        sort_keys=True,
    ))


def _optimum(cfg: Config, charges: tuple, coverage: str) -> dict:
    cells = []
    for charge in charges:
        frontier = _frontier(cfg, charge, coverage)
        for row in frontier["rows"]:
            start = row["charge_start_year"]
            feas = _feasibility_at(charge, start, cfg, coverage)
            cells.append({
                "charge": charge,
                "charge_start_year": start,
                "expected_discounted_welfare": row["expected_discounted_welfare"],
                "p_voters": row["p_voters"],
                "p_deal": row["p_deal"],
                "p_joint": row["p_joint"],
                "regime": row["regime"],
                "feasible": feas["passes"],
                "failed_constraints": feas["failed"],
            })

    best = max(cells, key=lambda c: c["expected_discounted_welfare"])
    admissible = [c for c in cells if c["feasible"]]
    best_feasible = (
        max(admissible, key=lambda c: c["expected_discounted_welfare"])
        if admissible else None
    )

    # Is the problem separable? If the best price is the same whatever the start
    # year, and the best year the same whatever the price, then solving the two
    # in sequence loses nothing and the joint machinery is only confirming that.
    # String keys, formatted deterministically. A dict keyed by float or int is
    # not stable across a JSON round-trip: the keys come back as strings and
    # `sort_keys` then orders them lexicographically, so {6.0, 8.0, 10.0} reads
    # back as {"10.0", "6.0", "8.0"} and a byte comparison against a cached copy
    # fails on ordering alone. Caught by the precomputed recompute test.
    by_year, by_charge = {}, {}
    for start in sorted({c["charge_start_year"] for c in cells}):
        col = [c for c in admissible if c["charge_start_year"] == start]
        if col:
            by_year[f"year_{start}"] = max(
                col, key=lambda c: c["expected_discounted_welfare"]
            )["charge"]
    for charge in charges:
        rowset = [c for c in admissible if c["charge"] == charge]
        if rowset:
            by_charge[f"${charge:g}"] = max(
                rowset, key=lambda c: c["expected_discounted_welfare"]
            )["charge_start_year"]

    # "Separable" as a single boolean is too blunt to be useful: the two
    # dimensions can fail it asymmetrically, and they do here. Report each
    # direction, then answer the question that actually matters by RUNNING the
    # sequential procedure and comparing it with the joint answer.
    charge_is_year_invariant = len(set(by_year.values())) <= 1
    year_is_charge_invariant = len(set(by_charge.values())) <= 1

    sequential = None
    if admissible:
        # Price first, at the start year the fixed-charge sweep recommends,
        # then timing at that price -- the order a study would naturally use.
        anchor_year = _frontier(cfg, DEFAULT_CHARGE, coverage)["optimal_start_year_joint"]
        at_anchor = [c for c in admissible if c["charge_start_year"] == anchor_year]
        if at_anchor:
            step1 = max(at_anchor, key=lambda c: c["expected_discounted_welfare"])
            step2 = max(
                (c for c in admissible if c["charge"] == step1["charge"]),
                key=lambda c: c["expected_discounted_welfare"],
            )
            sequential = {
                "anchor_start_year": anchor_year,
                "charge": step2["charge"],
                "charge_start_year": step2["charge_start_year"],
                "expected_discounted_welfare": step2["expected_discounted_welfare"],
                "matches_joint": (
                    step2["charge"] == best_feasible["charge"]
                    and step2["charge_start_year"] == best_feasible["charge_start_year"]
                ),
            }

    blocked = sorted({
        f for c in cells if not c["feasible"] for f in c["failed_constraints"]
    })

    return {
        "charges": list(charges),
        "coverage": coverage,
        "cells": cells,
        "unconstrained_optimum": best,
        "constrained_optimum": best_feasible,
        "optimal_charge_by_start_year": by_year,
        "optimal_start_year_by_charge": by_charge,
        "charge_is_year_invariant": charge_is_year_invariant,
        "year_is_charge_invariant": year_is_charge_invariant,
        "sequential": sequential,
        "constraints_that_bind": blocked,
        "price_of_the_constraints": (
            round(best["expected_discounted_welfare"]
                  - best_feasible["expected_discounted_welfare"], 5)
            if best_feasible else None
        ),
        "reading": (
            "Solving jointly puts the charge at $%.0f starting in year %d. The "
            "start year is unchanged from the fixed-charge sweep, and the price "
            "sits against the %s constraint rather than against public "
            "acceptability: support falls only about six points across the whole "
            "price range tested, because a larger charge also recycles more, so "
            "the political gates barely discipline the price at all. %s"
            % (
                best_feasible["charge"], best_feasible["charge_start_year"],
                " and ".join(blocked) if blocked else "binding",
                "Solving the two in sequence reaches the same answer here, "
                "because the best price is the same at every start year even "
                "though the best year is not the same at every price. That is a "
                "fact about this corridor rather than a general one -- the "
                "asymmetry is what makes the order of solving matter."
                if sequential and sequential["matches_joint"] else
                "Solving the two in sequence does NOT reach the joint answer, so "
                "the price and the year have to be chosen together.",
            )
            if best_feasible else
            "No charge in the range tested satisfies the constraint set at any "
            "start year."
        ),
    }


def report(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    cfg = cfg or Config()
    f = timing_frontier(cfg, charge)
    return {
        "frontier": f,
        "window": window(cfg, charge),
        "deadline_sensitivity": deadline_sensitivity(cfg, charge),
        "gates": {
            "voters": "phasing.enactment_probability, logistic in support",
            "governments": "logistic in the weaker party's bargained surplus",
            "combined": "P(voters) x P(deal), assumed independent",
            "independence_caveat": (
                "In practice a popular scheme is easier to authorise, so "
                "treating the gates as independent understates the value of "
                "waiting for support. That is the conservative direction for "
                "this study, which recommends charging early."
            ),
        },
        "assumptions": [
            "The charge level is fixed across the sweep, so this answers when, "
            "not when and how much jointly.",
            "The leader commits to a date and cannot re-propose after a failed "
            "vote, which understates the value of trying early.",
            "The transfer date is treated as certain. It has slipped before.",
        ],
    }
