"""The third level of the game: will anyone let you do this?

The Stackelberg model in `game.py` has two levels -- the authority sets a
price, travellers respond.  That is incomplete in a way the case studies make
unavoidable.  Stockholm's charge was opposed by two-thirds of residents before
its pilot and supported by two-thirds afterwards.  New York lost its federal
Urban Partnership funding in 2008 precisely because it could not obtain the
legislative authority.  A policy that maximises welfare and cannot be enacted
is not a policy; it is a proposal.

So acceptability is modelled as a third stage, with the structure Eliasson
(2016) sets out:

  **Consumer perspective** -- how the individual is affected personally: tolls
  paid, time saved, revenue returned.  This is the net welfare position already
  computed in `incidence.py`.

  **Citizen perspective** -- what the individual thinks is fair or desirable
  for society, setting self-interest aside.  Eliasson's central finding is that
  this is *not* reducible to self-interest, and that it varies systematically:
  support for pricing as an allocation mechanism rises with income and
  education, which makes congestion pricing partly "an elite project" whatever
  its distributional profile.

Two further mechanisms come straight from the case studies:

  **Experience.**  Support rises sharply once a scheme operates and the traffic
  effect becomes visible.  Gothenburg's support curve shifted upward by almost
  the same amount at every level of toll payment after one year of operation.

  **Sequencing.**  Stockholm expanded transit first -- 197 buses, 16 new routes
  -- and ran the charge as a pilot.  New York's plan is explicitly phased:
  transit investment, then a ride-hail surcharge, then the cordon.  Whether the
  charge is introduced before or after the alternative exists changes whether
  it can pass, independently of the price.

  **Trust.**  A traveller votes on the position they BELIEVE they will be in,
  not the one a spreadsheet says they will be in, and those differ wherever the
  benefit is a promise.  Edinburgh rejected its charge 74.4-25.6 and the
  research found the driver was trust rather than economics: only one in four
  believed the revenue would actually reach transport.  Manchester attached a
  GBP 3bn transport package and still lost.  Both are unreachable by a model in
  which recycling enters only through net position, because in such a model a
  large enough package always buys consent.

  So the promised part of a traveller's net position -- the recycled revenue --
  is discounted by `cfg.revenue_trust` before it enters the vote.  You do not
  need to trust that you paid ten dollars.

  **Belief that the charge works.**  Trust in the money is not the only thing
  that can be doubted, and on the record it is not the important one.
  Manchester's package was never what people disbelieved; the charge was.  So
  the time saving is discounted too, by `cfg.charge_efficacy_belief` -- because
  before a scheme runs the saving is a FORECAST that depends on other people
  changing their behaviour, while the toll is a certainty.  Only the toll is
  undiscounted.

  The two levers are not the same size.  On this corridor the revenue promise is
  worth $0.28 a trip and the forecast time saving $1.68, so disbelief in the
  charge moves support roughly six times as far as disbelief in the money.  That
  is the quantitative form of Manchester's lesson.

  Efficacy belief applies only BEFORE operation.  Afterwards the traffic effect
  is visible, which is precisely what the `experience` coefficient already
  represents; discounting there as well would count one phenomenon twice and
  break the Stockholm anchors the coefficients were set against.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .config import ALTERNATIVES, Config
from .demand import Segments

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}

# Coefficients of the support model. These are a calibrated stance, not
# estimates: Eliasson estimates an ordered logit on survey data this project
# does not have. They are set so the model reproduces the two anchors the case
# studies give us -- roughly a third support before operation and roughly two
# thirds after -- and they are exposed for sensitivity testing.
SUPPORT = {
    "intercept": -0.35,
    # Per dollar per trip of net personal position. The dominant term, and the
    # reason revenue recycling changes politics as much as it changes equity.
    "self_interest": 0.42,
    # The citizen term: agreement that pricing is a fair way to allocate a
    # scarce road, which Eliasson finds rises with income.
    "citizen": 1.15,
    # The shift observed once a scheme is running and its effects are visible.
    "experience": 0.95,
    # Having a usable alternative is itself a reason to accept the charge,
    # separately from what it costs you.
    "alternative": 0.55,
}


def citizen_alignment(segs: Segments) -> np.ndarray:
    """(N,) how far each segment's social preferences favour pricing, 0-1.

    Rises with income, following Eliasson's finding that pricing-as-allocation
    is more congenial to higher-income and better-educated groups, and rises
    with transit access, since a traveller who already has an alternative is
    likelier to regard charging for road space as reasonable.

    This term is why a scheme can be distributionally defensible and still
    unpopular with the people it protects.
    """
    income_rank = {"Q1": 0.30, "Q2": 0.38, "Q3": 0.48, "Q4": 0.58, "Q5": 0.68}
    base = np.array([income_rank.get(q, 0.5) for q in segs.quintile])
    return np.clip(base + 0.22 * (segs.transit_access - 0.6), 0.05, 0.95)


def revenue_trust(cfg: Config, operating: bool = False) -> float:
    """Share of the promised recycling that enters the vote, 0-1.

    Three sources, in the order the record puts them:

      * a baseline belief about whether revenue reaches what it was promised
        to (`cfg.revenue_trust`);
      * whether the scheme is running, because once it runs the spending is
        observable and stops being a promise at all;
      * whether the alternative was actually delivered first, which is the
        mechanism behind Stockholm's pilot -- a government that built the
        buses it said it would build is evidence about the next promise.

    The last two are additive gains capped at 1.0, so at the default baseline
    of 1.0 they are inert and nothing outside a trust sweep moves.  They become
    live exactly when the baseline is swept below full belief, which is the
    only regime in which they mean anything.
    """
    trust = float(cfg.revenue_trust)
    if operating:
        trust += float(cfg.revenue_trust_operating_gain)
    trust += float(cfg.revenue_trust_delivery_gain) * float(cfg.delivered_alternative)
    return float(np.clip(trust, 0.0, 1.0))


def support(
    incidence: dict,
    segs: Segments,
    cfg: Config,
    operating: bool = False,
    coefficients: Optional[Dict[str, float]] = None,
) -> dict:
    """Predicted share of corridor travellers who would vote for the scheme.

    A binary-logit vote over the two perspectives, plus experience.  Reported
    both before operation (a referendum held today, on a proposal) and after
    (a referendum held once the traffic effect is visible), because the case
    studies show those are very different questions.

    `cfg.delivered_alternative` is the sequencing term used by the phased
    game: a transit improvement that has actually been built and is carrying
    people, scored 0-1.  It is separate from the improvement that shows up in
    a traveller's own net position, which the incidence model already counts.
    The claim it encodes is the one the case studies make -- that a charge
    introduced after a visible alternative exists is a different proposition
    from the same charge introduced before it, at the same price.  Zero for a
    single-shot analysis, so nothing outside `phasing.py` changes.
    """
    c = {**SUPPORT, **(coefficients or {})}
    trips = incidence["trips"]
    trust = revenue_trust(cfg, operating)
    # Indexed, not `.get`: a caller that cannot say how much of the position is
    # a promise cannot have this term applied to it, and should fail loudly
    # rather than silently vote on the undiscounted number.  A missing key
    # defaulting to zero is how this codebase has hidden a whole mechanism
    # before.
    promised = incidence["recycled_per_trip"]
    # The time saving is a FORECAST before the scheme runs, not an experience:
    # you know what you will be charged, but whether the road gets faster
    # depends on other people changing their behaviour. `resource_per_trip` is
    # exactly that in-kind benefit, net of the transfer, so it is the part
    # belief in the charge attaches to -- and on this corridor it is worth
    # $1.68 a trip against $0.28 for the revenue promise, which is why
    # Manchester's package could not save it.
    #
    # Applied only before operation: afterwards the effect is visible, and the
    # `experience` coefficient below already carries that shift.
    efficacy = 1.0 if operating else float(np.clip(cfg.charge_efficacy_belief, 0.0, 1.0))
    forecast = incidence["resource_per_trip"]
    # What the traveller believes they will get, which is what they vote on.
    net = (
        incidence["net_per_trip"]
        - (1.0 - trust) * promised
        - (1.0 - efficacy) * forecast
    )
    alignment = citizen_alignment(segs)
    has_alternative = (segs.transit_access >= 0.5).astype(float)

    utility = (
        c["intercept"]
        + c["self_interest"] * net
        + c["citizen"] * (alignment - 0.5)
        + c["alternative"] * (has_alternative - 0.5)
        + cfg.delivered_alternative_bonus * float(cfg.delivered_alternative)
        + (c["experience"] if operating else 0.0)
    )
    probability = 1.0 / (1.0 + np.exp(-utility))
    overall = float(np.average(probability, weights=trips))

    by_q = []
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
        m = segs.quintile == q
        if trips[m].sum() <= 0:
            continue
        by_q.append({
            "quintile": q,
            "support": round(float(np.average(probability[m], weights=trips[m])), 4),
            "net_per_trip": round(float(np.average(net[m], weights=trips[m])), 3),
            "citizen_alignment": round(float(np.average(alignment[m], weights=trips[m])), 3),
        })

    return {
        "support_share": round(overall, 4),
        "passes_referendum": bool(overall > 0.5),
        "operating": operating,
        "revenue_trust": round(trust, 4),
        "charge_efficacy_belief": round(efficacy, 4),
        "forecast_per_trip": round(float(np.average(forecast, weights=trips)), 3),
        "promised_per_trip": round(float(np.average(promised, weights=trips)), 3),
        "believed_net_per_trip": round(float(np.average(net, weights=trips)), 3),
        "by_quintile": by_q,
        "coefficients": c,
        "note": "A vote of corridor travellers only. It excludes residents who never "
                "use the corridor and would neither pay nor benefit directly, and who "
                "in Stockholm made up much of the eventual majority.",
    }


def acceptability(
    incidence: dict, segs: Segments, cfg: Config,
    coefficients: Optional[Dict[str, float]] = None,
) -> dict:
    """Support before and after operation, and what the gap implies."""
    before = support(incidence, segs, cfg, operating=False, coefficients=coefficients)
    after = support(incidence, segs, cfg, operating=True, coefficients=coefficients)
    return {
        "before_operation": before,
        "after_operation": after,
        "experience_gain_pp": round(
            100 * (after["support_share"] - before["support_share"]), 2
        ),
        "implementable_now": before["passes_referendum"],
        "implementable_after_pilot": after["passes_referendum"],
        "verdict": (
            "Would pass a vote today."
            if before["passes_referendum"] else
            "Would fail a vote today but pass once operating — the Stockholm pattern, "
            "which is the case for a time-limited pilot with a review."
            if after["passes_referendum"] else
            "Would fail a vote both before and after operation. Either the design or "
            "the compensation has to change, not the communications strategy."
        ),
        "benchmark": "Stockholm: about a third in favour before the pilot, about two "
                     "thirds voting to keep it afterwards. Gothenburg's support curve "
                     "shifted up by a similar amount at every level of toll paid.",
    }


# --------------------------------------------------------------------------
# Trust: what the recommendation needs people to believe
# --------------------------------------------------------------------------

# Edinburgh is the only scheme in the comparison set with a MEASURED trust
# figure attached to a vote: it lost 74.4-25.6, and the research found that
# only about one in four believed the revenue would reach transport.  It is
# used here as a reference point, not as Toronto's value -- the point of
# reporting a breakeven is that Toronto's value is unknown.
EDINBURGH_TRUST = 0.25


def _readable_list(items: List[str]) -> str:
    """'25% and 50%' rather than '25%, 50%' -- the reading is prose, not a CSV."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def trust_sensitivity(
    incidence: dict, segs: Segments, cfg: Config,
    levels: Optional[List[float]] = None,
) -> dict:
    """Support as a function of how much of the revenue promise is believed.

    The level itself is not observable for this corridor, so it is inverted
    rather than tuned: the useful output is the trust the recommendation
    REQUIRES, set against the one number the record actually measured.  This is
    the same move `bargaining.py` makes with the political-cost rate, and for
    the same reason -- a parameter nobody can measure should be reported as a
    threshold, not asserted as a value.
    """
    grid = levels if levels is not None else [round(0.05 * i, 2) for i in range(21)]
    rows = []
    for t in grid:
        trial = Config.from_dict({**cfg.to_dict(), "revenue_trust": float(t)})
        before = support(incidence, segs, trial, operating=False)
        after = support(incidence, segs, trial, operating=True)
        rows.append({
            "revenue_trust": float(t),
            "support_before": before["support_share"],
            "support_after": after["support_share"],
            "passes_before": before["passes_referendum"],
            "passes_after": after["passes_referendum"],
            "believed_net_per_trip": before["believed_net_per_trip"],
        })

    def breakeven(key_pass: str, key_support: str) -> Optional[float]:
        """Lowest trust at which the vote is carried, linearly interpolated."""
        for prev, row in zip(rows, rows[1:]):
            if not prev[key_pass] and row[key_pass]:
                lo, hi = prev[key_support], row[key_support]
                if hi == lo:
                    return row["revenue_trust"]
                span = row["revenue_trust"] - prev["revenue_trust"]
                return round(prev["revenue_trust"] + span * (0.5 - lo) / (hi - lo), 4)
        return None if not rows[0][key_pass] else 0.0

    before_be = breakeven("passes_before", "support_before")
    after_be = breakeven("passes_after", "support_after")

    def verdict(be: Optional[float], when: str) -> str:
        if be is None:
            return (f"No level of trust carries the vote {when}: the resistance is "
                    "to paying, not to the revenue promise. Belief that the charge "
                    "WORKS is the larger doubt and is reported separately.")
        if be <= 0.0:
            return (f"The vote is carried {when} even if nobody believes the "
                    "revenue promise, so the result does not rest on trust.")
        margin = "above" if EDINBURGH_TRUST >= be else "below"
        return (
            f"The vote is carried {when} only if more than {be:.0%} of the "
            f"revenue promise is believed. Edinburgh's measured figure was "
            f"{EDINBURGH_TRUST:.0%}, which is {margin} that threshold."
        )

    return {
        "levels": rows,
        "breakeven_before_operation": before_be,
        "breakeven_after_operation": after_be,
        "edinburgh_trust": EDINBURGH_TRUST,
        "edinburgh_note": (
            "Edinburgh rejected its charge 74.4% to 25.6%. The research found the "
            "driver was trust rather than economics: about one in four believed the "
            "revenue would actually reach transport, and car ownership predicted the "
            "vote better than income did."
        ),
        "verdict_before": verdict(before_be, "before operation"),
        "verdict_after": verdict(after_be, "once operating"),
        "note": (
            "Trust discounts only the PROMISED part of a traveller's position \u2014 the "
            "recycled revenue. The toll they pay and the time they save are "
            "experienced, not promised, and are not discounted. A scheme that "
            "recycles nothing is therefore unaffected by this term, which is the "
            "test that it is doing what it claims to."
        ),
    }


def efficacy_sensitivity(
    incidence: dict, segs: Segments, cfg: Config,
    levels: Optional[List[float]] = None,
) -> dict:
    """Support against belief that the charge will actually relieve congestion.

    The companion to `trust_sensitivity`, and the larger of the two effects.
    Reported as a threshold for the same reason: nobody has measured what share
    of Etobicoke commuters would believe a gantry makes their trip faster.
    """
    grid = levels if levels is not None else [round(0.05 * i, 2) for i in range(21)]
    rows = []
    for e in grid:
        trial = Config.from_dict({**cfg.to_dict(), "charge_efficacy_belief": float(e)})
        before = support(incidence, segs, trial, operating=False)
        rows.append({
            "charge_efficacy_belief": float(e),
            "support_before": before["support_share"],
            "passes_before": before["passes_referendum"],
            "believed_net_per_trip": before["believed_net_per_trip"],
        })

    passing = [r["charge_efficacy_belief"] for r in rows if r["passes_before"]]
    return {
        "levels": rows,
        "breakeven_before_operation": min(passing) if passing else None,
        "forecast_per_trip": support(incidence, segs, cfg)["forecast_per_trip"],
        "promised_per_trip": support(incidence, segs, cfg)["promised_per_trip"],
        "note": (
            "Only the toll is certain. The time saving is a forecast that depends "
            "on other people changing their behaviour, so it is discounted by "
            "belief that the charge works; the recycled revenue is discounted "
            "separately by belief that the money arrives. On this corridor the "
            "forecast is the larger of the two by roughly six times."
        ),
    }


def manchester_test(
    incidence: dict, segs: Segments, cfg: Config,
    multipliers: Optional[List[float]] = None,
    efficacy_levels: Optional[List[float]] = None,
) -> dict:
    """Can a package rescue a charge nobody believes will work?

    Manchester's GBP 3bn was real and was never the doubted part, so this holds
    the money FULLY believed and varies only belief in the charge.  If the
    package can still not carry the vote, the study has reproduced the actual
    Manchester failure rather than a monetary one -- and the earlier
    `package_credibility` result, which got there by disbelieving the money, was
    telling the right story for the wrong reason.
    """
    mults = multipliers if multipliers is not None else [0.0, 1.0, 2.0, 4.0, 8.0]
    effs = efficacy_levels if efficacy_levels is not None else [0.0, 0.25, 0.5, 0.75, 1.0]

    series = []
    for e in effs:
        trial = Config.from_dict({
            **cfg.to_dict(),
            "charge_efficacy_belief": float(e),
            "revenue_trust": 1.0,          # the money is believed; the charge is not
        })
        points = []
        for m in mults:
            scaled = {**incidence}
            promised = incidence["recycled_per_trip"] * float(m)
            scaled["recycled_per_trip"] = promised
            scaled["net_per_trip"] = (
                incidence["net_per_trip"] - incidence["recycled_per_trip"] + promised
            )
            s = support(scaled, segs, trial, operating=False)
            points.append({
                "package_multiplier": float(m),
                "support": s["support_share"],
                "passes": s["passes_referendum"],
            })
        series.append({
            "charge_efficacy_belief": float(e),
            "points": points,
            "ceiling": round(max(p["support"] for p in points), 4),
            "any_package_passes": any(p["passes"] for p in points),
        })

    blocked = [s["charge_efficacy_belief"] for s in series if not s["any_package_passes"]]
    return {
        "revenue_trust_held_at": 1.0,
        "series": series,
        "efficacy_levels_no_package_can_carry": blocked,
        "reading": (
            "With the money fully believed, no multiple of the package in the "
            "range tested carries the vote at %s belief that the charge works. "
            "Manchester's GBP 3bn was credible; the charge was not, and that is "
            "the failure this reproduces."
            % _readable_list([f"{e:.0%}" for e in blocked])
            if blocked else
            "At every level of belief tested some package carries the vote, so on "
            "these parameters generosity can substitute for credibility about the "
            "charge itself."
        ),
    }


def package_credibility(
    incidence: dict, segs: Segments, cfg: Config,
    multipliers: Optional[List[float]] = None,
    trust_levels: Optional[List[float]] = None,
) -> dict:
    """Can a bigger package buy consent?  The Manchester question.

    Manchester attached a GBP 3bn transport package to its charge and lost the
    referendum anyway.  A model in which recycling enters only through net
    position cannot produce that: support is increasing and unbounded in the
    size of the package, so there is always a package that wins.

    Scaling the promised recycling while holding trust fixed shows why not.
    Each extra dollar of package reaches the vote multiplied by trust, so at
    low trust the support curve flattens far below the level the undiscounted
    model would predict, and no multiplier reaches it.  The package is not the
    binding constraint; belief in it is.
    """
    mults = multipliers if multipliers is not None else [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]
    trusts = trust_levels if trust_levels is not None else [0.25, 0.50, 0.75, 1.00]

    series = []
    for t in trusts:
        trial = Config.from_dict({**cfg.to_dict(), "revenue_trust": float(t)})
        points = []
        for m in mults:
            scaled = {**incidence}
            promised = incidence["recycled_per_trip"] * float(m)
            # Scale the promise and carry the same change into the total, so
            # the only thing varying across a row is the size of the package.
            scaled["recycled_per_trip"] = promised
            scaled["net_per_trip"] = (
                incidence["net_per_trip"] - incidence["recycled_per_trip"] + promised
            )
            s = support(scaled, segs, trial, operating=False)
            points.append({
                "package_multiplier": float(m),
                "support": s["support_share"],
                "passes": s["passes_referendum"],
                "promised_per_trip": s["promised_per_trip"],
            })
        best = max(p["support"] for p in points)
        series.append({
            "revenue_trust": float(t),
            "points": points,
            "ceiling": round(best, 4),
            "any_package_passes": any(p["passes"] for p in points),
        })

    blocked = [s["revenue_trust"] for s in series if not s["any_package_passes"]]
    return {
        "series": series,
        "trust_levels_no_package_can_carry": blocked,
        "reading": (
            "At trust levels of %s, no multiple of the package in the range tested "
            "carries the vote, so the constraint is credibility rather than "
            "generosity. That is the Manchester result, which a model without this "
            "term cannot produce."
            % _readable_list([f"{t:.0%}" for t in blocked])
            if blocked else
            "Every trust level tested has some package that carries the vote, so on "
            "these parameters generosity can still substitute for credibility."
        ),
        "manchester_note": (
            "Manchester attached a GBP 3bn transport package to its charge and still "
            "lost its referendum. Paying people in advance does not buy consent if "
            "they do not believe the charge will work."
        ),
    }


def trust_report(cfg: Optional[Config] = None,
                 policy: Optional["TollPolicy"] = None) -> dict:
    """Both trust analyses for one design, plus what they mean together.

    Defaults to the recommended design, because the question the record puts to
    this study is about the design it actually proposes.
    """
    from .demand import load_segments
    from .simulate import run
    from .toll_policy import TollPolicy as _TollPolicy

    cfg = cfg or Config()
    policy = policy or _TollPolicy(
        peak_toll=10.0, coverage="screenline", credit="low_income_transit_poor",
        window="0630_0930", label="recommended",
    )
    segs = load_segments(cfg)
    result = run(policy, cfg, segs, with_raw_incidence=True)
    inc = result["_raw_incidence"]

    sens = trust_sensitivity(inc, segs, cfg)
    pkg = package_credibility(inc, segs, cfg)
    efficacy = efficacy_sensitivity(inc, segs, cfg)
    manchester = manchester_test(inc, segs, cfg)
    return {
        "policy": policy.to_dict(),
        "support_at_full_trust": result["acceptability"]["before_operation"]["support_share"],
        "sensitivity": sens,
        "package": pkg,
        "efficacy": efficacy,
        "manchester": manchester,
        "two_beliefs": (
            "Belief that the money arrives is worth $%.2f a trip here; belief that "
            "the charge works is worth $%.2f. They are separate doubts and the "
            "second is roughly %.0f times larger, which is why Manchester's "
            "credible package could not rescue a charge nobody believed in."
            % (
                efficacy["promised_per_trip"],
                efficacy["forecast_per_trip"],
                efficacy["forecast_per_trip"] / max(efficacy["promised_per_trip"], 1e-9),
            )
        ),
        "why_this_exists": (
            "Two entries in the comparative record contradict this model, and both "
            "are the same missing mechanism. Edinburgh lost 74.4-25.6 on trust "
            "rather than economics, and Manchester lost with a GBP 3bn package "
            "attached. Without a trust term, recycling reaches the vote at face "
            "value, so a large enough package always wins and neither outcome is "
            "reachable at any parameter value."
        ),
        "what_it_does_not_do": (
            "It does not estimate Toronto's trust level, and no attempt is made to. "
            "Both belief terms default to full, which reproduces every result "
            "computed before it existed, and the analysis reports the threshold the "
            "recommendation requires rather than asserting where the corridor sits. "
            "The one measured figure in the record \u2014 Edinburgh's 25% \u2014 is a "
            "reference point from a different city and a different decade."
        ),
    }


# --------------------------------------------------------------------------
# Ride-hailing as a strategic player
# --------------------------------------------------------------------------

# Ride-hailing accounts for up to 14% of vehicle-kilometres in some cities, and
# a ride-hail trip generates roughly 70% more emissions than the same trip in a
# private car because of the empty repositioning miles between fares
# (Greenlining, 2020). London removed its ride-hail exemption for this reason;
# New York charges $2.75 a solo trip and $0.75 a shared one.
PTC_SHARE_OF_AUTO = 0.09      # share of corridor auto trips that are ride-hail
PTC_DEADHEAD = 0.62           # extra vehicle-km per passenger-km, from repositioning


def ride_hailing_response(
    peak_toll: float,
    ptc_surcharge: float,
    cfg: Config,
    pass_through_cap: float = 1.0,
) -> dict:
    """The ride-hail operator's best response to being charged.

    The operator is a genuine second follower, not a passive one: it chooses how
    much of the charge to pass to riders.  Passing all of it protects margin but
    loses trips; absorbing it holds volume at the operator's expense.  With a
    linear demand response the profit-maximising pass-through is interior, which
    is why a charge levied on the operator is not equivalent to a charge levied
    on the rider.

    Greenlining's argument is that the charge should sit with the platform
    rather than the driver.  This function shows what the platform does when it
    can choose.
    """
    charge = peak_toll + ptc_surcharge
    if charge <= 0:
        return {
            "charge_per_trip": 0.0, "pass_through": 0.0, "rider_price_increase": 0.0,
            "trip_change_pct": 0.0, "deadhead_vehicle_trips": 0.0,
            "note": "No charge applies to ride-hail trips under this policy.",
        }

    # Rider demand falls with price; the operator trades margin against volume.
    # Optimal pass-through under a linear response is one half, adjusted for
    # how price-sensitive riders are relative to the operator's margin.
    elasticity = 0.9
    optimal = min(pass_through_cap, 1.0 / (1.0 + elasticity))
    rider_increase = charge * optimal
    trip_change = -elasticity * rider_increase / 24.0     # against a ~$24 trip

    trips = PTC_SHARE_OF_AUTO * cfg.total_person_trips * (1.0 + trip_change)
    return {
        "charge_per_trip": round(charge, 2),
        "pass_through": round(optimal, 3),
        "rider_price_increase": round(rider_increase, 2),
        "operator_absorbs": round(charge * (1 - optimal), 2),
        "trip_change_pct": round(100 * trip_change, 2),
        "ptc_trips": round(trips, 1),
        "deadhead_vehicle_trips": round(trips * PTC_DEADHEAD, 1),
        "note": "The operator passes roughly half the charge to riders and absorbs the "
                "rest. Because each passenger trip drags additional empty repositioning "
                "kilometres behind it, a ride-hail trip removed from the corridor takes "
                "more vehicle-kilometres with it than a private car trip does.",
    }


def ride_hailing_case(cfg: Config) -> dict:
    """Why ride-hail needs its own instrument, with the operating precedents."""
    return {
        "share_of_auto_trips": PTC_SHARE_OF_AUTO,
        "deadhead_factor": PTC_DEADHEAD,
        "precedents": [
            {"city": "London", "action": "Removed the ride-hail exemption while keeping "
                                         "the taxi exemption",
             "detail": "More than 18,000 ride-hail vehicles were entering the charging "
                       "zone daily; trips by taxi and ride-hail rose 29% since 2000."},
            {"city": "New York", "action": "Separate per-trip surcharge ahead of the cordon",
             "detail": "$2.50 taxi, $2.75 ride-hail, $0.75 per rider on a shared trip — "
                       "an explicit occupancy incentive."},
            {"city": "San Francisco", "action": "Charge the platform, not the driver",
             "detail": "Greenlining argues the fee should be absorbed as a cost of doing "
                       "business rather than passed to drivers already on low wages."},
        ],
        "recommendation": "Charge per trip with a lower rate for shared rides, levied on "
                          "the platform. A per-vehicle cordon charge alone under-prices "
                          "ride-hail, because the deadhead kilometres never cross the "
                          "screenline as a charged entry.",
    }
