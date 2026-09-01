"""Who actually wins and loses, beyond who pays.

The equity module in `equity.py` answers "who pays the charge".  That is the
traditional analysis and it is not enough.  Eliasson (2016) sets out four
components of the welfare effect of a congestion charge, and tolls paid is only
the first:

    1. tolls paid                  a transfer out of the traveller's pocket
    2. adaptation cost             the cost of retiming, rerouting, switching
                                   mode, or giving up the trip
    3. travel-time gain            the road is quieter for whoever stays
    4. recycled revenue            what the traveller gets back

Components 1-3 are captured exactly by the change in the nested-logit logsum,
which is the compensating variation: what a traveller would have to be paid to
be indifferent between the charged world and the uncharged one.  Component 4 is
added separately because it depends on a spending decision, not on behaviour.

This module also implements three things the source material insists on and a
toll-incidence table cannot show:

  * **Concentration, not just averages.**  Eliasson's central point is that a
    scheme can look mildly regressive on average while a non-negligible
    subgroup is hurt badly.  He reports the share of each income group paying
    more than a threshold; the same is done here against income.

  * **Modal and geographic equity.**  FHWA distinguishes three equity types --
    income, geographic, modal -- and warns that most analyses only do the
    first.

  * **Payment access.**  FHWA estimates 10-20% of the population cannot hold a
    toll account for want of a bank account, credit card or deposit.  They do
    not avoid the charge; they pay it through a costlier channel.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from . import choice_model, datasets
from .config import ALTERNATIVES, Config
from .congestion import Equilibrium
from .demand import Segments

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}
QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"]

# Eliasson reports the share of each income group paying above a fixed monthly
# amount.  Expressed against income instead, so it transfers across currencies
# and income levels: a charge costing more than this share of household income
# is treated as a material burden.
BURDEN_THRESHOLDS = (0.005, 0.01, 0.02)


def welfare_incidence(
    eq: Equilibrium,
    base: Equilibrium,
    segs: Segments,
    cfg: Config,
    constants: np.ndarray,
    net_revenue_annual: float = 0.0,
) -> dict:
    """Full welfare position per segment, decomposed into Eliasson's components."""
    from . import equity as equity_mod

    charges = equity_mod.per_segment_charges(eq, segs, cfg)
    trips = charges["trips"]
    days = cfg.working_days_per_year

    # Components 1-3 together, per trip. Negative = worse off.
    surplus = choice_model.consumer_surplus_change(eq.gc, base.gc, constants, cfg)

    # Component 1 alone, so the transfer can be separated from the resource cost.
    tolls = charges["net_per_trip"]

    # What is left once the transfer is removed is the real resource effect:
    # the adaptation cost the traveller bears, netted against the time they
    # save on a quieter road. A positive number here means the corridor got
    # better for them in kind, before any money changed hands.
    resource = surplus + tolls

    # Component 4. Revenue is spent on station access, first/last mile, bus
    # priority and credits, so it is allocated the same way `equity.recycling_benefit`
    # allocates it: toward transit use and away from good existing access.
    weight = segs.share * (0.45 + 0.55 * (1.0 - segs.transit_access))
    weight = weight / weight.sum() if weight.sum() > 0 else weight
    captured = max(net_revenue_annual, 0.0) * cfg.recycling_capture_share
    recycled_annual = captured * weight
    recycled_per_trip = np.divide(
        recycled_annual, np.maximum(trips * days, 1e-9),
        out=np.zeros_like(recycled_annual), where=trips > 0,
    )

    net_per_trip = surplus + recycled_per_trip
    net_annual = net_per_trip * days

    return {
        "surplus_per_trip": surplus,
        "tolls_per_trip": tolls,
        "resource_per_trip": resource,
        "recycled_per_trip": recycled_per_trip,
        "net_per_trip": net_per_trip,
        "net_annual": net_annual,
        "net_share_income": np.divide(
            net_annual, segs.income, out=np.zeros_like(net_annual), where=segs.income > 0
        ),
        "trips": trips,
        # Reported both ways on purpose. Before recycling is what the charge
        # does to travellers; after recycling depends entirely on a spending
        # decision that has not been made yet, and on revenue actually
        # reaching this corridor. Eliasson treats revenue use as a separate
        # question for exactly this reason.
        "winners_share": float(trips[net_per_trip > 0].sum() / max(trips.sum(), 1e-9)),
        "winners_share_before_recycling": float(
            trips[surplus > 0].sum() / max(trips.sum(), 1e-9)
        ),
        "captured_revenue_annual": round(captured, 0),
        "capture_share": cfg.recycling_capture_share,
    }


def by_quintile(inc: dict, segs: Segments) -> List[dict]:
    """The welfare table: who wins, who loses, and by how much."""
    trips = inc["trips"]
    rows = []
    for q in QUINTILES:
        m = segs.quintile == q
        w = trips[m]
        if w.sum() <= 0:
            continue
        avg = lambda key: float(np.average(inc[key][m], weights=w))  # noqa: E731
        rows.append({
            "quintile": q,
            "household_income": float(segs.income[m][0]),
            "trips": round(float(w.sum()), 1),
            "tolls_per_trip": round(avg("tolls_per_trip"), 3),
            "resource_per_trip": round(avg("resource_per_trip"), 3),
            "surplus_per_trip": round(avg("surplus_per_trip"), 3),
            "recycled_per_trip": round(avg("recycled_per_trip"), 3),
            "net_per_trip": round(avg("net_per_trip"), 3),
            "net_annual": round(avg("net_annual"), 2),
            "net_pct_income": round(100 * avg("net_share_income"), 4),
            "share_better_off": round(
                float(w[inc["net_per_trip"][m] > 0].sum() / w.sum()), 4
            ),
            "surplus_pct_income": round(
                100 * float(np.average(
                    inc["surplus_per_trip"][m], weights=w
                )) * 244 / float(segs.income[m][0]), 4
            ),
        })
    return rows


def burden_concentration(eq: Equilibrium, segs: Segments, cfg: Config) -> dict:
    """How many people are hurt badly, not just how much the average person pays.

    Eliasson's key warning: a scheme can be only mildly regressive on average
    while a non-negligible subgroup faces a large cost increase, and that
    subgroup is usually the political and moral problem.  Averages hide it.
    """
    from . import equity as equity_mod

    charges = equity_mod.per_segment_charges(eq, segs, cfg)
    trips = charges["trips"]
    burden = charges["net_annual"] / np.maximum(segs.income, 1.0)

    rows = []
    for q in QUINTILES:
        m = segs.quintile == q
        w = trips[m]
        if w.sum() <= 0:
            continue
        row = {"quintile": q, "household_income": float(segs.income[m][0])}
        for t in BURDEN_THRESHOLDS:
            row[f"share_above_{t:g}"] = round(
                float(w[burden[m] > t].sum() / w.sum()), 4
            )
        row["max_burden_pct"] = round(100 * float(burden[m].max()), 4)
        rows.append(row)

    total = trips.sum()
    return {
        "thresholds": list(BURDEN_THRESHOLDS),
        "by_quintile": rows,
        "share_above_1pct_income": round(
            float(trips[burden > 0.01].sum() / max(total, 1e-9)), 4
        ),
        "note": "Share of travellers in each income group whose annual charge exceeds "
                "the stated fraction of household income. Eliasson (2016) reports the "
                "same statistic against a fixed monthly amount and argues it matters "
                "more than the average, because averages conceal the subgroup that is "
                "actually harmed.",
    }


def modal_equity(eq: Equilibrium, base: Equilibrium, cfg: Config) -> dict:
    """Does the scheme reward the travellers who were already not driving?

    FHWA's third equity type. The complaint it captures is specific: it is not
    obviously fair to hand the same travel-time saving to someone who paid to
    keep driving as to someone who had already switched to the bus.
    """
    T = cfg.total_person_trips
    share = lambda e, a: float(e.market_shares[IDX[a]])  # noqa: E731

    transit_before = share(base, "go_rail") + share(base, "ttc")
    transit_after = share(eq, "go_rail") + share(eq, "ttc")
    drive_before = share(base, "drive_gardiner") + share(base, "carpool_gardiner")
    drive_after = share(eq, "drive_gardiner") + share(eq, "carpool_gardiner")

    time_saved = base.route_times["drive_gardiner"] - eq.route_times["drive_gardiner"]
    return {
        "transit_share_before": round(transit_before, 5),
        "transit_share_after": round(transit_after, 5),
        "transit_riders_gained": round((transit_after - transit_before) * T, 1),
        "drivers_retained": round(drive_after * T, 1),
        "time_saved_for_drivers_min": round(time_saved, 2),
        "time_saved_for_transit_min": 0.0,
        "reward_ratio": round(time_saved, 2),
        "note": "Travel-time savings accrue to whoever keeps driving. Transit riders "
                "gain only what recycled revenue buys them, which is why the "
                "recycling plan is doing the modal-equity work, not the charge.",
    }


def payment_access(eq: Equilibrium, segs: Segments, cfg: Config, policy) -> dict:
    """Who cannot hold a toll account, and what it costs them.

    FHWA puts the share of the population unable to overcome the barriers to a
    transponder account -- no bank account, no credit card, no capacity for a
    deposit -- at 10 to 20 percent. They are not exempt from the charge; they
    pay it through video billing or a retail channel, usually at a premium.
    This is a regressive design feature that no toll-incidence table shows,
    because it lives in the payment system rather than in the price.
    """
    from . import equity as equity_mod

    charges = equity_mod.per_segment_charges(eq, segs, cfg)
    trips = charges["trips"]

    # Account access falls with income; the FHWA range is applied across the
    # income distribution rather than as a single population-wide figure.
    unbanked_rate = {"Q1": 0.20, "Q2": 0.13, "Q3": 0.07, "Q4": 0.03, "Q5": 0.01}
    rate = np.array([unbanked_rate.get(q, 0.05) for q in segs.quintile])
    surcharge = getattr(policy, "unbanked_surcharge", 0.0)

    exposed = float((trips * rate).sum())
    extra = float((trips * rate * charges["net_per_trip"] * surcharge).sum())
    return {
        "share_of_travellers_exposed": round(exposed / max(trips.sum(), 1e-9), 4),
        "travellers_exposed": round(exposed, 1),
        "assumed_rate_by_quintile": unbanked_rate,
        "surcharge_applied": surcharge,
        "extra_cost_peak": round(extra, 2),
        "extra_cost_annual": round(extra * cfg.working_days_per_year, 0),
        "note": "FHWA estimates 10-20% of the population cannot open a toll account. "
                "Rates here fall with income. A cash-accepting, account-free payment "
                "channel removes this barrier at no cost to the congestion effect; "
                "Puerto Rico and Texas both operate one.",
    }


def benchmark(suits_index: float) -> dict:
    """Place this scheme's regressivity against schemes that actually operate."""
    df = datasets.benchmarks()
    rows = []
    for _, r in df.iterrows():
        if r.get("suits_index") is None or (isinstance(r["suits_index"], float) and np.isnan(r["suits_index"])):
            continue
        rows.append({
            "scheme": str(r["scheme"]),
            "city": str(r["city"]),
            "suits_index": float(r["suits_index"]),
            "source": str(r["source"]),
            "note": str(r["note"]),
        })
    rows.sort(key=lambda x: x["suits_index"])

    charges = [r for r in rows if r["scheme"] in
               ("stockholm", "gothenburg", "helsinki", "lyon")]
    more_regressive = [r for r in charges if r["suits_index"] > suits_index]
    return {
        "model_suits_index": round(suits_index, 4),
        "comparisons": rows,
        "operating_charges": charges,
        "more_regressive_than_all_operating_schemes": len(more_regressive) == len(charges),
        "verdict": (
            "This design is more regressive than every congestion charge in the "
            "comparison set." if len(more_regressive) == len(charges) else
            "This design sits inside the range of operating congestion charges."
        ),
        "note": "Operating congestion charges cluster between -0.09 and -0.16. For "
                "scale, a US sales tax is about -0.11 and the Texas fuel tax about "
                "-0.25, so a mildly regressive road charge is less regressive than "
                "the fuel tax it partly displaces.",
    }


# The STEPS framework (Shaheen et al.), applied to the instruments this model
# can actually set. Physiological and Social barriers are included precisely
# because the model cannot quantify them -- leaving them out of the table would
# imply the analysis had covered them.
STEPS_DIMENSIONS = {
    "spatial": "Distance and the absence of a transit option within reach.",
    "temporal": "Time barriers: reliability, operating hours, congestion itself.",
    "economic": "Direct cost, plus indirect costs such as needing a bank account, "
                "a credit card or a smartphone to pay.",
    "physiological": "Physical and cognitive limits: disability, age, travelling "
                     "with infants.",
    "social": "Safety, language and cultural barriers to using a mode.",
}


def steps_assessment(policy, metrics: dict, equity_result: dict) -> List[dict]:
    """Score the policy on the STEPS equity framework.

    Spatial, Temporal and Economic are read from model output. Physiological
    and Social are reported as not modelled, with the reason, because the
    honest answer is that this corridor model cannot see them.
    """
    credit = getattr(policy, "credit", "none")
    means_tested = credit in ("means_tested", "equity_first")
    priced = getattr(policy, "peak_toll", 0) > 0

    gap = equity_result["components"]["transit_access_gap"]
    delay = metrics["delay_reduction_pct"]
    diversion = metrics["worst_diversion_pct"]

    def verdict(good: bool, mixed: bool = False) -> str:
        if mixed:
            return "may eliminate or create barrier"
        return "reduces or eliminates barrier" if good else "exacerbates or creates barrier"

    return [
        {
            "dimension": "Spatial",
            "definition": STEPS_DIMENSIONS["spatial"],
            "verdict": verdict(gap < 0.25, mixed=0.25 <= gap < 0.4),
            "evidence": f"{gap:.0%} of the charge is paid by travellers with no "
                        f"realistic transit alternative.",
            "modelled": True,
        },
        {
            "dimension": "Temporal",
            "definition": STEPS_DIMENSIONS["temporal"],
            "verdict": verdict(delay > 5),
            "evidence": f"{delay:.1f}% of vehicle-hours of delay removed; "
                        f"worst protected-corridor change {diversion:+.1f}%.",
            "modelled": True,
        },
        {
            "dimension": "Economic",
            "definition": STEPS_DIMENSIONS["economic"],
            "verdict": verdict(means_tested and priced, mixed=priced and not means_tested),
            "evidence": ("Means-tested fees remove the direct cost for the lowest "
                         "income band." if means_tested else
                         "A flat fee is charged regardless of income, and payment "
                         "requires an account that 10-20% of the population cannot open."),
            "modelled": True,
        },
        {
            "dimension": "Physiological",
            "definition": STEPS_DIMENSIONS["physiological"],
            "verdict": "not modelled",
            "evidence": "This corridor model has no disability, age or accompanied-"
                        "travel dimension. London exempts blue-badge holders entirely; "
                        "whether that is sufficient is an empirical question this "
                        "model cannot answer.",
            "modelled": False,
        },
        {
            "dimension": "Social",
            "definition": STEPS_DIMENSIONS["social"],
            "verdict": "not modelled",
            "evidence": "Safety, language and cultural barriers to switching mode are "
                        "outside a generalized-cost model. They are listed here so the "
                        "omission is visible rather than implied to be a pass.",
            "modelled": False,
        },
    ]


def compute(
    eq: Equilibrium,
    base: Equilibrium,
    segs: Segments,
    cfg: Config,
    constants: np.ndarray,
    policy,
    metrics: dict,
    equity_result: dict,
    net_revenue_annual: float = 0.0,
) -> dict:
    """The full distributional picture, beyond who pays."""
    inc = welfare_incidence(eq, base, segs, cfg, constants, net_revenue_annual)
    rows = by_quintile(inc, segs)

    q1 = next((r for r in rows if r["quintile"] == "Q1"), None)
    q5 = next((r for r in rows if r["quintile"] == "Q5"), None)

    return {
        "welfare_by_quintile": rows,
        "winners_share": round(inc["winners_share"], 4),
        "winners_share_before_recycling": round(inc["winners_share_before_recycling"], 4),
        "captured_revenue_annual": inc["captured_revenue_annual"],
        "capture_share": inc["capture_share"],
        "net_position_q1": q1["net_per_trip"] if q1 else None,
        "net_position_q5": q5["net_per_trip"] if q5 else None,
        "regressive_in_welfare": bool(
            q1 and q5 and q1["net_pct_income"] < q5["net_pct_income"]
        ),
        # Before revenue is returned, which is the part of the picture the
        # charge itself determines.
        "regressive_before_recycling": bool(
            q1 and q5 and q1["surplus_pct_income"] < q5["surplus_pct_income"]
        ),
        "burden_concentration": burden_concentration(eq, segs, cfg),
        "modal_equity": modal_equity(eq, base, cfg),
        "payment_access": payment_access(eq, segs, cfg, policy),
        "benchmark": benchmark(equity_result["components"]["suits_index"]),
        "steps": steps_assessment(policy, metrics, equity_result),
        "components_explained": {
            "tolls_per_trip": "What the traveller hands over, net of any rebate.",
            "resource_per_trip": "Adaptation cost netted against travel-time gain. "
                                 "Positive means the corridor improved for them in kind.",
            "surplus_per_trip": "Components 1-3 together: the compensating variation.",
            "recycled_per_trip": "Their share of what the revenue buys.",
            "net_per_trip": "Surplus plus recycling. This is the bottom line.",
        },
    }
