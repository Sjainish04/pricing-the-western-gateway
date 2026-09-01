"""The City and the Province, bargaining over a road neither fully controls.

`game.py` treats governance as two scenarios -- Branch A assumes provincial
authorisation arrives, Branch B assumes it never does.  That is not a game, it
is a pair of assumptions about how a negotiation turns out.

The negotiation is real and it has been played once already.  In December 2016
Toronto Council voted 32-9 to toll the Gardiner and the DVP.  In January 2017
the Province refused, and offered instead a doubled municipal share of the
provincial gas tax, worth about $170M a year to Toronto -- roughly 0.85 of what
the City estimated the tolls would have raised.  A disagreement outcome, a side
payment, and an observed price for the disputed prize.

What each side actually holds
-----------------------------
The instrument set and the ownership are about to come apart, which is what
makes the timing sharp:

  Before fall 2027   The City owns the Gardiner and carries its
                     state-of-good-repair liability, but cannot toll it without
                     provincial authorisation.  The City holds the asset; the
                     Province holds the veto.  This is exactly the 2016-17
                     configuration.

  After fall 2027    The Province owns the road AND holds the veto.  The City's
                     only unilateral instrument is a charge on its own
                     arterials -- Branch B, which this study finds is the most
                     regressive design of all.  In exchange the City is
                     relieved of up to $7.6B of capital liability, which is why
                     it wanted the transfer.

The asymmetry that drives the result
------------------------------------
Forty per cent of AM-peak corridor demand originates outside Toronto, in
Mississauga and the west GTA.  That share is derived from the segment table,
not assumed.  Those travellers are not the City's voters and they are the
Province's -- disproportionately so, since 905 seats are where provincial
majorities are decided.  So the same charge imposes materially more political
cost on the Province than on the City, while the congestion benefit lands
mostly inside Toronto.  A charge can therefore be jointly worth having and
still be refused, which is not a failure of analysis; it is what happened.

Solution concepts
-----------------
Payoffs are in annual dollars so the Nash product means something.  Both
players' payoffs are linear in the revenue split, so the Nash and
Kalai-Smorodinsky solutions have closed forms and no search is needed -- the
same preference for a closed form as `network.fit_alpha` and
`rejoin_validation.implied_volume_ratio`.

Nash is reported alongside Kalai-Smorodinsky rather than instead of it, because
the two disagree exactly when the players' stakes are lopsided, which is the
case here.  Reporting one alone would hide that the answer depends on which
axiom set you accept.

The most important output is not either solution.  It is `bargaining_set`: the
range of revenue splits on which both sides do better than walking away.  When
that range is empty there is no deal at any price, and no amount of goodwill
produces one.
"""
from __future__ import annotations

import functools
import json
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import datasets, game
from .config import Config
from .demand import Segments, load_segments
from .toll_policy import TollPolicy

REGIMES = ("pre_transfer", "post_transfer")


def constituencies(segs: Optional[Segments] = None) -> dict:
    """Who the corridor's travellers vote for, derived from the segment table.

    The City's electorate is its residents; the Province's is everybody, but
    the seats that decide provincial majorities are the 905 ones.  That is why
    `province_marginal_weight` exists and why it is greater than one.
    """
    segs = segs if segs is not None else load_segments()
    outside = float(
        sum(s for a, s in zip(segs.subarea, segs.share) if "Mississauga" in a or "west GTA" in a)
    )
    return {
        "toronto_share": round(1.0 - outside, 4),
        "non_toronto_share": round(outside, 4),
        "note": (
            "Derived from data/segments.csv, not assumed. A charge at the "
            "western gateway falls on a population 40% of whom cannot vote in "
            "the city collecting it."
        ),
    }


def _outcome(policy: TollPolicy, cfg: Config, segs: Segments, reference: Config) -> dict:
    """The corridor consequences of a policy, in the units the bargain needs."""
    result = game.evaluate(policy, cfg, segs, reference=reference)
    vot_hour = float(np.average(segs.vot_per_min, weights=segs.trips(cfg)) * 60.0)
    delay_hours = float(result["delay_hours_saved_peak"])
    # Indexed, not .get(): a missing key here would zero the political-cost
    # term, which is the asymmetry the whole bargaining result rests on, and
    # the model would still return a complete and entirely wrong answer.
    # Already annual -- do not multiply by working days again.
    charged = float(result["finance"]["charged_vehicles_annual"])
    return {
        "label": policy.label,
        "congestion_benefit_annual": delay_hours * vot_hour * cfg.working_days_per_year,
        "net_revenue_annual": float(result["finance"]["net_revenue_annual"]),
        "charged_trips_annual": charged,
        "delay_reduction_pct": result["metrics"]["delay_reduction_pct"],
        "equity_score": result["equity"]["equity_score"],
        "worst_diversion_pct": result["metrics"]["worst_diversion_pct"],
    }


def _liabilities(regime: str, cfg: Config) -> Tuple[float, float]:
    """(city, province) annual Gardiner liability in dollars, by regime.

    Signed as a cost.  The New Deal unlocked about $1.9B for the City over ten
    years by moving this liability to the Province, so $190M/yr is the annual
    value of the obligation being handed over -- a published figure rather than
    an assumed one.

    Before the transfer the Province is already contributing interim operating
    support, so the City's net burden is that much lighter and the Province is
    already carrying part of the road.  The support is annualised over the
    whole New-Deal-to-transfer period (November 2023 to fall 2027), not over
    the months still to run: it is a fixed sum for a fixed job, and dividing it
    by a shrinking remainder would make the Province's position look worse the
    closer the transfer got, which is backwards.
    """
    annual = datasets.governance_value("new_deal_unlocked_decade") / 10.0
    interim = datasets.governance_value("interim_om_support") / max(
        cfg.interim_support_years, 1.0
    )
    if regime == "pre_transfer":
        return max(annual - interim, 0.0), interim
    return 0.0, annual


def political_cost_given_support(cfg: Config, support: Optional[float]) -> float:
    """The political cost rate, adjusted for how popular the scheme is.

    Authorising a charge the public wants is cheaper for a government than
    authorising one it does not, which is the channel by which the two
    enactment gates in `joint_game` stop being independent.  Anchored at the
    referendum threshold: at 50% support the rate is exactly the stated base,
    so the existing calibration is untouched and `gate_dependence` rotates the
    line about that point rather than shifting it.

    Returned as a rate rather than applied here because `payoffs` is reached
    through a dozen call sites; the caller puts it on a Config instead, the
    same way `phasing.py` carries `delivered_alternative`.
    """
    base = float(cfg.political_cost_per_charged_trip)
    if support is None or cfg.gate_dependence == 0.0:
        return base
    adjusted = base * (1.0 + cfg.gate_dependence * (1.0 - 2.0 * float(support)))
    # A wildly popular scheme makes authorisation free, not profitable: there
    # is no evidence for a government being PAID to authorise, and a negative
    # cost would flip the sign of the term that drives the whole bargain.
    return max(adjusted, 0.0)


def payoffs(
    outcome: dict, split: float, regime: str, cfg: Config, cons: dict
) -> dict:
    """Each player's annual dollar payoff at a given revenue split.

    `split` is the City's share of net revenue.  Both payoffs are linear in it,
    which is what makes the solution concepts closed-form.

    The political cost term converts charged trips into dollars at a rate that
    is a stated stance, not an estimate (`political_cost_per_charged_trip`).
    Its *level* is arbitrary; what the model rests on is the *ratio* between the
    two players, and that comes from the derived geography rather than from the
    rate.
    """
    city_liab, prov_liab = _liabilities(regime, cfg)
    c = cfg.political_cost_per_charged_trip * outcome["charged_trips_annual"]

    # The City answers to Toronto residents only. The Province answers to all of
    # them plus the 905 travellers, weighted up because those are the marginal
    # seats.
    political_city = c * cons["toronto_share"]
    political_prov = c * (
        cons["toronto_share"]
        + cfg.province_marginal_weight * cons["non_toronto_share"]
    )

    # Time saved on the corridor accrues to whoever travels on it, so the City's
    # share of the congestion benefit is its residents' share of demand. The
    # Province counts all of it: goods movement and regional economic cost do
    # not stop at the city boundary.
    benefit_city = outcome["congestion_benefit_annual"] * cons["toronto_share"]
    benefit_prov = outcome["congestion_benefit_annual"] * cfg.province_benefit_weight

    revenue = outcome["net_revenue_annual"]
    return {
        "split": round(split, 4),
        "city": round(
            benefit_city + split * revenue - political_city - city_liab, 1
        ),
        "province": round(
            benefit_prov + (1.0 - split) * revenue - political_prov - prov_liab, 1
        ),
        "terms": {
            "city_congestion_benefit": round(benefit_city, 1),
            "province_congestion_benefit": round(benefit_prov, 1),
            "city_political_cost": round(political_city, 1),
            "province_political_cost": round(political_prov, 1),
            "city_liability": round(city_liab, 1),
            "province_liability": round(prov_liab, 1),
            "net_revenue": round(revenue, 1),
        },
    }


def disagreement(regime: str, cfg: Config, segs: Segments, reference: Config) -> dict:
    """What each side gets if no deal is struck.  The BATNA, and the whole game.

    The City's fallback is the same in both regimes: Branch B, a charge on its
    own arterials, which it can enact alone and whose revenue nobody else has a
    claim on.  This study finds Branch B is the most regressive design in the
    library.  A credible threat and a bad outcome are not incompatible -- that
    is what makes it a threat.

    The Province's fallback is what changes, and it is the whole point of the
    2027 date:

      Before the transfer the City owns the Gardiner and the Province holds the
      authorisation.  Neither can charge on it alone.  A mutual veto, which is
      what makes this a genuine bilateral bargain.

      After the transfer the Province owns the road *and* holds the
      authorisation, so it can levy a freeway charge unilaterally and keep all
      of the revenue.  It no longer needs the City's agreement for anything.

    Note what that unilateral option is: `gardiner_only`, because the arterials
    stay with the City.  This study's own finding is that a freeway-only charge
    pushes traffic onto exactly those arterials.  So after 2027 the Province can
    impose a charge whose diversion lands on City streets, and the City has no
    standing to object.

    An earlier version put the repair liability in this term.  It cancels: a
    lump sum shifts a player's deal and no-deal payoffs equally, so it changes
    each side's welfare level but not its incentive to agree.  The liability is
    still carried in `payoffs` because it belongs in the reported levels, but it
    is not what the 2027 transfer does to the bargain.
    """
    cons = constituencies(segs)
    branch_b = _outcome(
        TollPolicy(peak_toll=5.0, coverage="city_roads_only", credit="none",
                   label="Branch B: City arterials only"),
        cfg, segs, reference,
    )
    city_alone = payoffs(branch_b, 1.0, regime, cfg, cons)["city"]

    if regime == "pre_transfer":
        fallback = _outcome(
            TollPolicy(peak_toll=0.0, label="no charge"), cfg, segs, reference
        )
        # No charge, so the split is irrelevant; evaluated at 0 for clarity.
        prov_alone = payoffs(fallback, 0.0, regime, cfg, cons)["province"]
    else:
        fallback = _outcome(
            TollPolicy(peak_toll=cfg.province_unilateral_charge,
                       coverage="gardiner_only", credit="none",
                       label="Province charges the freeway alone"),
            cfg, segs, reference,
        )
        # It owns the road and authorises itself, so it keeps everything.
        prov_alone = payoffs(fallback, 0.0, regime, cfg, cons)["province"]

    return {
        "regime": regime,
        "city": city_alone,
        "province": prov_alone,
        "city_fallback": branch_b["label"],
        "province_fallback": fallback["label"],
        "city_fallback_equity_score": branch_b["equity_score"],
        "province_fallback_diversion_pct": fallback["worst_diversion_pct"],
        "note": (
            "The Province's fallback improves at the transfer, from having no "
            "option at all to having a unilateral one. The City's does not "
            "change. That is an unambiguous loss of leverage with a date on it."
        ),
    }


def nash_split(a_city: float, a_prov: float, revenue: float,
               d_city: float, d_prov: float, alpha: float) -> Optional[float]:
    """Closed-form asymmetric Nash bargaining solution over the revenue split.

    With U_c(s) = a_c + s*R and U_p(s) = a_p + (1-s)*R, maximising
    (U_c - d_c)^alpha * (U_p - d_p)^(1-alpha) gives

        s* = alpha + [alpha*(a_p - d_p) - (1-alpha)*(a_c - d_c)] / R

    Returns None when there is no revenue to divide, or when no split leaves
    both sides above their fallback -- in which case there is nothing to solve
    and the honest answer is that no deal exists.
    """
    if abs(revenue) < 1e-9:
        return None
    x, y = a_city - d_city, a_prov - d_prov
    s = alpha + (alpha * y - (1.0 - alpha) * x) / revenue
    s = float(np.clip(s, 0.0, 1.0))
    if (x + s * revenue) <= 0 or (y + (1.0 - s) * revenue) <= 0:
        return None
    return s


def kalai_smorodinsky_split(a_city: float, a_prov: float, revenue: float,
                            d_city: float, d_prov: float) -> Optional[float]:
    """Equal proportional gains toward each side's best attainable outcome.

    Differs from Nash precisely when the stakes are lopsided, which they are
    here, so the two are reported together.  Linear payoffs again give a closed
    form: the ideal for each player is the split where the other is held exactly
    at its fallback.
    """
    if abs(revenue) < 1e-9:
        return None
    x, y = a_city - d_city, a_prov - d_prov
    # Split at which the Province is exactly indifferent to walking away.
    s_max = (y + revenue) / revenue
    # ...and at which the City is.
    s_min = -x / revenue
    lo, hi = max(0.0, s_min), min(1.0, s_max)
    if hi < lo:
        return None
    ideal_city, ideal_prov = x + hi * revenue, y + (1.0 - lo) * revenue
    if ideal_city <= 0 or ideal_prov <= 0:
        return None
    # Equal proportional gain: (x + sR)/ideal_c = (y + (1-s)R)/ideal_p
    denom = revenue * (1.0 / ideal_city + 1.0 / ideal_prov)
    if abs(denom) < 1e-12:
        return None
    s = ((y + revenue) / ideal_prov - x / ideal_city) / denom
    return float(np.clip(s, lo, hi))


@functools.lru_cache(maxsize=16)
def _cached_solve(payload: str) -> dict:
    kw = json.loads(payload)
    cfg = Config.from_dict(kw["config"])
    return _solve(cfg, kw["regime"], kw["charge"], kw["coverage"])


def solve(cfg: Optional[Config] = None, regime: str = "pre_transfer",
          charge: float = 10.0, coverage: str = "screenline") -> dict:
    cfg = cfg or Config()
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}")
    payload = json.dumps(
        {"config": cfg.to_dict(), "regime": regime, "charge": charge,
         "coverage": coverage}, sort_keys=True,
    )
    return _cached_solve(payload)


def _solve(cfg: Config, regime: str, charge: float, coverage: str) -> dict:
    segs = load_segments(cfg)
    cons = constituencies(segs)
    deal = _outcome(
        TollPolicy(peak_toll=charge, coverage=coverage,
                   credit="low_income_transit_poor",
                   label=f"${charge:g} {coverage}"),
        cfg, segs, cfg,
    )
    d = disagreement(regime, cfg, segs, cfg)

    # Payoffs are linear in the split, so evaluate at s=0 to get the intercepts.
    at_zero = payoffs(deal, 0.0, regime, cfg, cons)
    revenue = deal["net_revenue_annual"]
    a_city, a_prov = at_zero["city"], at_zero["province"]

    # The bargaining set: splits where BOTH beat their fallback.
    lo = (d["city"] - a_city) / revenue if revenue > 0 else None
    hi = (a_prov - d["province"]) / revenue + 1.0 if revenue > 0 else None
    if revenue > 0:
        lo, hi = max(0.0, float(lo)), min(1.0, float(hi))
        has_deal = hi >= lo
    else:
        lo = hi = None
        has_deal = False

    nash = nash_split(a_city, a_prov, revenue, d["city"], d["province"],
                      cfg.bargaining_power_city)
    ks = kalai_smorodinsky_split(a_city, a_prov, revenue, d["city"], d["province"])

    return {
        "regime": regime,
        "charge": charge,
        "coverage": coverage,
        "constituencies": cons,
        "outcome": {k: round(v, 1) if isinstance(v, float) else v
                    for k, v in deal.items()},
        "disagreement": d,
        "bargaining_set": {
            "city_share_min": None if lo is None else round(lo, 4),
            "city_share_max": None if hi is None else round(hi, 4),
            "has_zone_of_agreement": bool(has_deal),
            "width": None if not has_deal else round(hi - lo, 4),
        },
        "nash": None if nash is None else {
            "city_share": round(nash, 4),
            **{k: v for k, v in payoffs(deal, nash, regime, cfg, cons).items()
               if k in ("city", "province")},
            # Surplus over the fallback is the real measure of a bargaining
            # position. The payoff LEVELS move with the repair liability, which
            # cancels out of the bargain; the surpluses do not.
            "city_surplus": round(
                payoffs(deal, nash, regime, cfg, cons)["city"] - d["city"], 1
            ),
            "province_surplus": round(
                payoffs(deal, nash, regime, cfg, cons)["province"] - d["province"], 1
            ),
            "bargaining_power_city": cfg.bargaining_power_city,
        },
        "kalai_smorodinsky": None if ks is None else {
            "city_share": round(ks, 4),
            **{k: v for k, v in payoffs(deal, ks, regime, cfg, cons).items()
               if k in ("city", "province")},
        },
        "verdict": (
            "No zone of agreement: there is no revenue split at which both "
            "sides prefer the charge to walking away. This is the 2017 outcome, "
            "and it cannot be fixed by negotiating harder."
            if not has_deal else
            "A zone of agreement exists. The charge is jointly worth having, "
            "and what remains is a distributive fight over the split."
        ),
    }


def compare_regimes(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    """Does the fall 2027 transfer help or hurt the chance of a deal?

    This is the decision-relevant question, because it has a deadline attached.
    """
    cfg = cfg or Config()
    results = {r: solve(cfg, r, charge) for r in REGIMES}
    pre, post = results["pre_transfer"], results["post_transfer"]

    def width(r):
        w = r["bargaining_set"]["width"]
        return 0.0 if w is None else w

    def surplus(r, who):
        return 0.0 if r["nash"] is None else r["nash"][f"{who}_surplus"]

    city_change = surplus(post, "city") - surplus(pre, "city")

    return {
        "charge": charge,
        "regimes": results,
        "zone_width_change": round(width(post) - width(pre), 4),
        "city_surplus_change": round(city_change, 1),
        "city_surplus_change_pct": (
            None if surplus(pre, "city") == 0 else
            round(100.0 * city_change / abs(surplus(pre, "city")), 1)
        ),
        "province_unilateral_diversion_pct":
            post["disagreement"]["province_fallback_diversion_pct"],
        "deal_possible_before_transfer": pre["bargaining_set"]["has_zone_of_agreement"],
        "deal_possible_after_transfer": post["bargaining_set"]["has_zone_of_agreement"],
        "breakeven_political_cost": {
            r: breakeven_political_cost(cfg, charge, r) for r in REGIMES
        },
        "reading": (
            "The repair liability is not what the transfer does to the bargain "
            "-- a lump sum shifts a player's deal and no-deal payoffs equally "
            "and cancels out. What changes is the Province's fallback. Today "
            "neither side can charge on the Gardiner alone, so they hold a "
            "mutual veto. After fall 2027 the Province owns the road and "
            "authorises itself, so it can levy a freeway-only charge "
            "unilaterally and keep the revenue. The City's fallback does not "
            "improve, so its leverage falls. The option the Province gains is "
            "precisely the design this study finds breaches the local-street "
            "diversion cap -- and the diversion lands on City arterials, which "
            "the City would no longer have standing to object to."
        ),
        "why_the_loss_of_leverage_is_small": (
            "The City's bargained surplus falls only slightly, and the reason "
            "connects two of this study's other findings. The Province's new "
            "unilateral option is a freeway-only charge, and this model finds "
            "that design is financially marginal -- fixed collection costs do "
            "not scale down, so at $4 it does not cover itself. A threat that "
            "loses money is a weak threat, so the City keeps more leverage than "
            "the institutional picture alone suggests. The exposure is not to "
            "the Province's revenue, it is to the diversion: the Province can "
            "impose a charge that is bad for it financially and still worse for "
            "City streets, and after 2027 nothing stops it."
        ),
    }


def power_sensitivity(cfg: Optional[Config] = None, charge: float = 10.0,
                      regime: str = "pre_transfer") -> dict:
    """How the split moves with relative bargaining power.

    Nash's asymmetric weight is not observable, so the honest presentation is
    the whole curve rather than one point on it.
    """
    cfg = cfg or Config()
    rows = []
    for alpha in (0.2, 0.35, 0.5, 0.65, 0.8):
        trial = Config.from_dict({**cfg.to_dict(), "bargaining_power_city": alpha})
        r = solve(trial, regime, charge)
        rows.append({
            "bargaining_power_city": alpha,
            "city_share": None if r["nash"] is None else r["nash"]["city_share"],
            "has_zone_of_agreement": r["bargaining_set"]["has_zone_of_agreement"],
        })
    return {
        "regime": regime, "charge": charge, "rows": rows,
        "note": (
            "Whether a zone of agreement exists does not depend on bargaining "
            "power -- that is set by the fallbacks. Power only decides how a "
            "surplus is divided once there is one to divide."
        ),
    }


def breakeven_political_cost(
    cfg: Optional[Config] = None, charge: float = 10.0,
    regime: str = "pre_transfer", coverage: str = "screenline",
    lo: float = 0.0, hi: float = 60.0, tol: float = 0.05,
) -> dict:
    """How much must a charged trip cost politically before the deal dies?

    The political cost rate is the least observable number in this module, and
    at the default the zone of agreement is the whole range -- both sides want
    the charge at any split.  That is a real result, but on its own it sits
    awkwardly beside the record, in which the Province refused a charge Council
    supported 32-9.

    Rather than tune the rate until the model reproduces 2017, invert the
    question: find the rate at which the zone closes.  Below it the charge is
    jointly worth having; above it there is no split either side will accept.
    Because the Province did in fact refuse, its true valuation lies ABOVE this
    threshold -- a revealed-preference lower bound from an actual decision,
    which is worth more than a fitted coefficient.

    Bisection, because the zone's existence is monotone in the rate: political
    cost enters both payoffs negatively and is the only term moving.
    """
    cfg = cfg or Config()

    def has_zone(rate: float) -> bool:
        trial = Config.from_dict(
            {**cfg.to_dict(), "political_cost_per_charged_trip": float(rate)}
        )
        return solve(trial, regime, charge, coverage)["bargaining_set"][
            "has_zone_of_agreement"
        ]

    if not has_zone(lo):
        return {"regime": regime, "charge": charge, "threshold": None,
                "reason": "No zone of agreement even at zero political cost."}
    if has_zone(hi):
        return {"regime": regime, "charge": charge, "threshold": None,
                "reason": f"A zone survives even at ${hi:g} per charged trip."}

    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if has_zone(mid):
            lo = mid
        else:
            hi = mid

    threshold = round(0.5 * (lo + hi), 3)
    charged = solve(cfg, regime, charge, coverage)["outcome"]["charged_trips_annual"]
    return {
        "regime": regime,
        "charge": charge,
        "threshold_per_charged_trip": threshold,
        "assumed_per_charged_trip": cfg.political_cost_per_charged_trip,
        "implied_annual_political_cost": round(threshold * charged, 0),
        "reading": (
            "Below about $%.2f of political cost per charged trip a year, the "
            "charge is jointly worth having and the argument is only about the "
            "split. Above it, no split is acceptable to both. The Province "
            "refused in 2017, so on this model its valuation sits above the "
            "threshold for the regime of the day." % threshold
        ),
    }


def side_payment(cfg: Optional[Config] = None, regime: str = "pre_transfer",
                 charge: float = 10.0, coverage: str = "screenline",
                 political_cost: Optional[float] = None) -> dict:
    """What a deal costs once money can move outside the corridor's revenue.

    Everything above divides only the charge's own net revenue, which on this
    corridor is about \\$5.5M a year.  That is not how the 2016-17 negotiation
    was actually settled: the Province offered a doubled municipal share of the
    provincial gas tax, worth roughly \\$170M a year -- about thirty times the
    corridor's entire net revenue, and paid in the opposite direction to the
    one a revenue split can represent.

    So the revenue split is the wrong instrument to be arguing over.  With a
    transfer available the problem becomes transferable-utility: the *total*
    surplus is what decides whether a deal exists, and the split only decides
    who banks it.  A scheme that is jointly worth doing can always be made
    mutually acceptable by a payment; one that is not, cannot be rescued by any
    split.

    This reports the transfer needed to bring the weaker party exactly to its
    fallback, so the number can be set beside what was actually paid.
    """
    cfg = cfg or Config()
    if political_cost is not None:
        cfg = Config.from_dict(
            {**cfg.to_dict(), "political_cost_per_charged_trip": float(political_cost)}
        )
    r = solve(cfg, regime, charge, coverage)
    d = r["disagreement"]
    segs = load_segments(cfg)
    cons = constituencies(segs)
    deal = _outcome(
        TollPolicy(peak_toll=charge, coverage=coverage,
                   credit="low_income_transit_poor", label="deal"),
        cfg, segs, cfg,
    )

    # Total surplus is invariant to the split: a dollar moved between the two
    # leaves the sum unchanged. Evaluate at any split and it is the same number.
    at_half = payoffs(deal, 0.5, regime, cfg, cons)
    total_surplus = (at_half["city"] - d["city"]) + (at_half["province"] - d["province"])

    # With all revenue to the City, how far below its fallback is the Province?
    all_to_city = payoffs(deal, 1.0, regime, cfg, cons)
    province_shortfall = d["province"] - all_to_city["province"]
    # ...and the mirror case.
    all_to_province = payoffs(deal, 0.0, regime, cfg, cons)
    city_shortfall = d["city"] - all_to_province["city"]

    observed = datasets.governance_value("side_payment_accepted")
    return {
        "regime": regime,
        "charge": charge,
        "political_cost_per_charged_trip": cfg.political_cost_per_charged_trip,
        "corridor_net_revenue_annual": round(deal["net_revenue_annual"], 0),
        "total_surplus_annual": round(total_surplus, 0),
        "deal_exists_with_transfers": bool(total_surplus > 0),
        # Positive means the City must pay the Province to secure agreement even
        # after handing over none of the revenue; negative means no payment is
        # needed in that direction.
        "city_must_pay_province": round(max(province_shortfall, 0.0), 0),
        "province_must_pay_city": round(max(city_shortfall, 0.0), 0),
        "observed_2017_side_payment": observed,
        "observed_vs_corridor_revenue": (
            round(observed / deal["net_revenue_annual"], 1)
            if deal["net_revenue_annual"] > 0 else None
        ),
        "reading": (
            "With a transfer available, whether a deal exists depends on the "
            "TOTAL surplus, not on the revenue split. The split decides only "
            "who banks it. That reframes the negotiation: arguing over the "
            "corridor's revenue is arguing over a sum an order of magnitude "
            "smaller than the transfers these two governments already move "
            "between them."
        ),
    }


def side_payment_curve(cfg: Optional[Config] = None, charge: float = 10.0,
                       rates: Optional[tuple] = None) -> dict:
    """The transfer needed to secure agreement, as political cost rises.

    At the assumed rate no payment is needed at all -- the charge is jointly
    worth having.  As the political cost approaches the level implied by the
    2017 refusal, the payment required to bring the Province along climbs, and
    past some point no transfer suffices because the total surplus itself has
    gone negative.  Where that happens is the point at which the scheme is not
    worth doing rather than merely hard to agree on, and the two are worth
    distinguishing.
    """
    cfg = cfg or Config()
    rates = rates or (0.9, 2.0, 3.5, 5.0, 6.5, 8.0, 10.0)
    rows = []
    for rate in rates:
        for regime in REGIMES:
            sp = side_payment(cfg, regime, charge, political_cost=rate)
            rows.append({
                "political_cost_per_charged_trip": rate,
                "regime": regime,
                "total_surplus_annual": sp["total_surplus_annual"],
                "deal_exists_with_transfers": sp["deal_exists_with_transfers"],
                "city_must_pay_province": sp["city_must_pay_province"],
            })
    return {
        "charge": charge,
        "rows": rows,
        "note": (
            "A deal that needs a transfer is still a deal. A negative total "
            "surplus is not: no split and no payment can make both sides "
            "prefer the charge, and the honest conclusion there is that the "
            "scheme is not worth doing at that political cost."
        ),
    }


def precedent() -> dict:
    """The 2016-17 episode, as the one observed play of this game."""
    g = datasets.governance_value
    return {
        "council_vote": f"{int(g('council_toll_vote_for'))}-{int(g('council_toll_vote_against'))}"
                        " in favour, December 2016",
        "province_response": "Refused, January 2017",
        "side_payment_annual": g("side_payment_accepted"),
        "side_payment_vs_toll_estimate": g("side_payment_vs_toll_estimate"),
        "what_it_shows": [
            "The disagreement outcome is not hypothetical. It is what happened, "
            "on this road, with these two players.",
            "A side payment was accepted at roughly 0.85 of the disputed prize, "
            "which is a revealed price for provincial authorisation -- the "
            "closest thing to an observation this bargaining model has.",
            "The Province refused a charge that City Council supported 32-9. "
            "Any model in which the City's preferences alone decide the outcome "
            "is contradicted by the record.",
        ],
        "caveat": (
            "One observation, under a different government, before the New Deal "
            "moved the repair liability. It disciplines the model's sign, not "
            "its magnitudes."
        ),
    }


def report(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    cfg = cfg or Config()
    return {
        "precedent": precedent(),
        "comparison": compare_regimes(cfg, charge),
        "breakeven": breakeven_political_cost(cfg, charge),
        "side_payment": side_payment(cfg, "pre_transfer", charge),
        "side_payment_curve": side_payment_curve(cfg, charge),
        "power_sensitivity": power_sensitivity(cfg, charge),
        "assumptions": [
            "Payoffs are annual dollars. The political cost RATE is a stated "
            "stance; the model rests on the ratio between the two players, "
            "which is derived from where corridor demand comes from.",
            "Revenue is the only transferable instrument. Real bargains include "
            "transit capital, land, and Ontario Place -- the actual New Deal "
            "traded the highways against several of those at once.",
            "One-shot bargaining. Neither side builds a reputation, and the "
            "2027 deadline is a hard boundary rather than a bargaining lever.",
        ],
    }
