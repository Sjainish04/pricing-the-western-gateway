"""Distributional analysis.

The proposal is explicit that equity is a design constraint and a simulation
output, not a claim.  So this module reports the raw components first -- who
pays, how much, as what share of income, with what alternative available -- and
only then folds them into an index whose weights stay visible.

The headline index is

    EquityScore = 1 - [ a*BurdenInequality + b*TransitAccessGap + c*SpatialConcentration ]

Burden inequality is measured with the Suits index, the progressivity measure
normally used for taxes.  It compares the cumulative share of the charge paid
against the cumulative share of income earned: +1 is perfectly progressive,
0 proportional, -1 perfectly regressive.  A flat per-trip charge is regressive
by construction, so the interesting question is how far credits move it.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .config import ALTERNATIVES, Config
from .congestion import Equilibrium
from .demand import Segments

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}
QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"]


def per_segment_charges(eq: Equilibrium, segs: Segments, cfg: Config) -> dict:
    """Toll paid and credit received, per segment, per trip and per year."""
    tolls = eq.components["toll"]
    credits = eq.components["credit"]
    # A parking surcharge is a charge on the traveller just as a toll is, so it
    # belongs in the burden analysis. Omitting it would make a parking levy
    # appear to deliver congestion relief at nobody's expense.
    surcharge = eq.components.get("surcharge")
    probs = eq.shares                                   # (N, A)

    charged = tolls if surcharge is None else tolls + surcharge
    gross_per_trip = (probs * charged).sum(axis=1)      # $ per person-trip

    # Two different things live in the credit matrix and must not be added
    # together.  A rebate against the charge reduces what a traveller pays; a
    # transit mobility credit is a separate benefit paid to somebody who may not
    # be paying the charge at all.  Netting the mobility credit off the burden
    # would let a large enough transit subsidy drive measured burden to zero and
    # report a charge as costless -- and it would make the Suits index
    # meaningless, since it would then describe a subsidy rather than a charge.
    paid_mask = (charged > 0).astype(float)
    rebate_per_trip = (probs * credits * paid_mask).sum(axis=1)
    transit_credit_per_trip = (probs * credits * (1.0 - paid_mask)).sum(axis=1)

    credit_per_trip = rebate_per_trip
    net_per_trip = np.maximum(gross_per_trip - rebate_per_trip, 0.0)

    trips = segs.trips(cfg)                             # people per peak
    days = cfg.working_days_per_year
    return {
        "gross_per_trip": gross_per_trip,
        "credit_per_trip": credit_per_trip,
        "net_per_trip": net_per_trip,
        "gross_annual": gross_per_trip * days,
        "net_annual": net_per_trip * days,
        "burden_share_income": np.divide(
            net_per_trip * days, segs.income, out=np.zeros_like(net_per_trip), where=segs.income > 0
        ),
        "transit_credit_per_trip": transit_credit_per_trip,
        "trips": trips,
        "gross_total": float((gross_per_trip * trips).sum()),
        # Finance must carry BOTH kinds of credit, because both are money out.
        "credit_total": float(
            ((rebate_per_trip + transit_credit_per_trip) * trips).sum()
        ),
        "rebate_total": float((rebate_per_trip * trips).sum()),
        "transit_credit_total": float((transit_credit_per_trip * trips).sum()),
    }


def _concentration_points(burden: np.ndarray, income: np.ndarray,
                          weights: np.ndarray, total_burden: float,
                          total_income: float):
    """Points of the concentration curve, aggregated at each distinct income.

    Both the index and the curve are built from this, so they cannot disagree.

    The aggregation is the whole point, and it is a correctness fix rather than
    a tidy-up.  This was `np.argsort(income)`, walking one segment at a time.
    But income here takes only FIVE distinct values -- it is a quintile, not a
    measured income -- so all 70 segments arrive in 14-way ties, and segments
    tied on income carry very different burdens (a Q1 traveller in Alderwood
    and a Q1 traveller in Mississauga are not the same row).  The cumulative
    burden therefore depended on the order numpy happened to put ties in, and
    `argsort` defaults to an UNSTABLE quicksort, so the answer was not even
    reproducible across numpy versions.

    The size of that ambiguity is not academic.  Sweeping the tie order over
    the real segments moves the index by 0.045 to 0.089 depending on the
    design -- wider than the gaps between the published benchmarks this study
    ranks itself against (Stockholm -0.09, Gothenburg -0.13, Lyon -0.16).  It
    also reordered the equity packages against each other: targeted_package
    reads as less regressive than equity_first under one tie order and more
    regressive under another.

    Segments tied on income are exchangeable -- nothing in the data says which
    should be counted first -- so the honest curve treats each income level as
    a single point and joins them with a chord.  That is also how the Suits
    index is classically computed on income brackets.  The result is invariant
    to segment order by construction, which `test_suits_index_is_tie_order_invariant`
    pins.
    """
    levels, inverse = np.unique(income, return_inverse=True)
    income_at_level = np.bincount(inverse, weights=income * weights, minlength=levels.size)
    burden_at_level = np.bincount(inverse, weights=burden * weights, minlength=levels.size)

    x = np.concatenate([[0.0], np.cumsum(income_at_level) / total_income])
    y = np.concatenate([[0.0], np.cumsum(burden_at_level) / total_burden])
    return x, y


def suits_index(burden: np.ndarray, income: np.ndarray, weights: np.ndarray) -> float:
    """Suits progressivity index of a charge.

    Order travellers from lowest to highest income, then compare the cumulative
    share of the charge paid against the cumulative share of income.  Returns
    +1 for perfectly progressive, 0 for proportional, -1 for the reverse.
    """
    total_burden = float((burden * weights).sum())
    total_income = float((income * weights).sum())
    if total_burden <= 0 or total_income <= 0:
        return 0.0

    x, y = _concentration_points(burden, income, weights, total_burden, total_income)
    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    area = float(trapz(y, x))          # L, area under the concentration curve

    # Suits: S = 1 - L/K with K = 0.5 the area under the diagonal.  A
    # progressive charge puts the curve BELOW the diagonal (L < 0.5, S > 0);
    # a regressive one puts it above.  Returning 2L-1 instead would invert the
    # sign and report a regressive charge as progressive.
    return float(1.0 - 2.0 * area)


def suits_curve(burden: np.ndarray, income: np.ndarray,
                weights: np.ndarray) -> List[dict]:
    """The concentration curve the Suits index is the area between.

    The index is a single number standing for a whole curve, and a number
    cannot show WHERE a charge is regressive -- a scheme that is hard on the
    bottom quintile and one that is hard on the middle can share an index.
    Returning the curve lets that be seen rather than asserted.

    Read it against the diagonal: a point above the diagonal means travellers up
    to that share of income have paid MORE than that share of the charge, which
    is the regressive direction.
    """
    total_burden = float((burden * weights).sum())
    total_income = float((income * weights).sum())
    if total_burden <= 0 or total_income <= 0:
        return []

    x, y = _concentration_points(burden, income, weights, total_burden, total_income)
    # The knots themselves, not a resampling of them.  This used to interpolate
    # onto a 24-point grid to keep a 70-point payload readable, but the curve
    # now has one point per distinct income -- five -- and the curve between
    # them is a straight chord, so a grid cannot add information and can only
    # lose it: resampling moved the reported widest gap from the fourth-quintile
    # boundary (54.2% of income, 68.3% of the charge) to a neighbouring grid
    # point at 52%/66%, and put a 2-point error into a figure quoted in the
    # write-up.  Returning the knots also lets the curve integrate back to the
    # reported index exactly rather than within a tolerance.
    return [
        {"cumulative_income_share": round(float(gx), 4),
         "cumulative_charge_share": round(float(gy), 4),
         "gap": round(float(gy - gx), 4)}
        for gx, gy in zip(x, y)
    ]


def transit_access_gap(eq: Equilibrium, segs: Segments, cfg: Config) -> float:
    """Share of the charge paid by travellers with no realistic transit option.

    Paying a charge is one thing; paying it with no alternative is another, and
    this is the number that decides whether a credit is a nicety or a
    necessity.
    """
    charges = per_segment_charges(eq, segs, cfg)
    weights = charges["trips"]
    paid = charges["net_per_trip"] * weights
    total = float(paid.sum())
    if total <= 0:
        return 0.0
    stranded = segs.transit_access < 0.50
    return float(paid[stranded].sum() / total)


def spatial_concentration(eq: Equilibrium, segs: Segments, cfg: Config) -> float:
    """How unevenly the charge lands across sub-areas.

    Compares each sub-area's share of the charge with its share of trips.  Zero
    means the charge falls exactly in proportion to travel; higher means it is
    concentrated on particular communities.
    """
    charges = per_segment_charges(eq, segs, cfg)
    weights = charges["trips"]
    paid = charges["net_per_trip"] * weights
    total_paid, total_trips = float(paid.sum()), float(weights.sum())
    if total_paid <= 0 or total_trips <= 0:
        return 0.0

    excess = 0.0
    for area in np.unique(segs.subarea):
        m = segs.subarea == area
        excess += abs(paid[m].sum() / total_paid - weights[m].sum() / total_trips)
    return float(excess / 2.0)      # a normalised dissimilarity index, 0 to 1


def by_quintile(eq: Equilibrium, base: Equilibrium, segs: Segments, cfg: Config) -> List[dict]:
    """The raw distributional table, before any index is built."""
    charges = per_segment_charges(eq, segs, cfg)
    weights = charges["trips"]
    base_time = base.components["time_minutes"]
    time_now = eq.components["time_minutes"]

    rows = []
    for q in QUINTILES:
        m = segs.quintile == q
        w = weights[m]
        wsum = float(w.sum())
        if wsum <= 0:
            continue

        # Time saved is only meaningful for the people still driving.
        drive_cols = [IDX["drive_gardiner"], IDX["carpool_gardiner"]]
        drive_prob = eq.shares[m][:, drive_cols].sum(axis=1)
        time_saved = (
            (base_time[m][:, IDX["drive_gardiner"]] - time_now[m][:, IDX["drive_gardiner"]])
            * drive_prob
        )

        transit_now = eq.shares[m][:, [IDX["go_rail"], IDX["ttc"]]].sum(axis=1)
        transit_base = base.shares[m][:, [IDX["go_rail"], IDX["ttc"]]].sum(axis=1)

        rows.append(
            {
                "quintile": q,
                "household_income": float(segs.income[m][0]),
                "trips": round(wsum, 1),
                "share_of_travellers": round(wsum / float(weights.sum()), 4),
                "gross_toll_per_trip": round(float(np.average(charges["gross_per_trip"][m], weights=w)), 3),
                "credit_per_trip": round(float(np.average(charges["credit_per_trip"][m], weights=w)), 3),
                "net_toll_per_trip": round(float(np.average(charges["net_per_trip"][m], weights=w)), 3),
                "net_annual_toll": round(float(np.average(charges["net_annual"][m], weights=w)), 2),
                "burden_pct_income": round(
                    100.0 * float(np.average(charges["burden_share_income"][m], weights=w)), 4
                ),
                "time_saved_min": round(float(np.average(time_saved, weights=w)), 3),
                "transit_share": round(float(np.average(transit_now, weights=w)), 4),
                "transit_shift_pp": round(
                    100.0 * float(np.average(transit_now - transit_base, weights=w)), 3
                ),
                "no_transit_alternative": round(
                    float(np.average((segs.transit_access[m] < 0.50).astype(float), weights=w)), 4
                ),
                "value_of_time_hourly": round(float(segs.vot_per_min[m][0] * 60), 2),
            }
        )
    return rows


def by_subarea(eq: Equilibrium, segs: Segments, cfg: Config) -> List[dict]:
    """Where the charge lands geographically."""
    charges = per_segment_charges(eq, segs, cfg)
    weights = charges["trips"]
    total_paid = float((charges["net_per_trip"] * weights).sum())

    rows = []
    for area in sorted(np.unique(segs.subarea)):
        m = segs.subarea == area
        w = weights[m]
        paid = float((charges["net_per_trip"][m] * w).sum())
        rows.append(
            {
                "subarea": str(area),
                "trips": round(float(w.sum()), 1),
                "trip_share": round(float(w.sum() / weights.sum()), 4),
                "charge_share": round(paid / total_paid, 4) if total_paid > 0 else 0.0,
                "net_toll_per_trip": round(float(np.average(charges["net_per_trip"][m], weights=w)), 3),
                "burden_pct_income": round(
                    100.0 * float(np.average(charges["burden_share_income"][m], weights=w)), 4
                ),
                "transit_access": round(float(segs.transit_access[m][0]), 3),
            }
        )
    return rows


def recycling_benefit(net_revenue_annual: float, segs: Segments, cfg: Config) -> List[dict]:
    """Who gains from spending the net revenue on the corridor.

    Reinvestment is directed at Lakeshore West station access, first and last
    mile connections, bus priority and mobility credits.  Benefit is allocated
    to sub-areas in proportion to transit ridership and inversely to current
    access quality, since the improvements are worth most where access is
    currently worst.
    """
    weight = segs.share * (0.45 + 0.55 * (1.0 - segs.transit_access))
    weight = weight / weight.sum() if weight.sum() > 0 else weight

    rows = []
    for area in sorted(np.unique(segs.subarea)):
        m = segs.subarea == area
        w = float(weight[m].sum())
        rows.append(
            {
                "subarea": str(area),
                "benefit_share": round(w, 4),
                "annual_benefit": round(net_revenue_annual * w, 0),
                "transit_access": round(float(segs.transit_access[m][0]), 3),
            }
        )
    return rows


def compute(
    eq: Equilibrium,
    base: Equilibrium,
    segs: Segments,
    cfg: Config,
    net_revenue_annual: float = 0.0,
) -> dict:
    """Full equity assessment: components first, index second."""
    charges = per_segment_charges(eq, segs, cfg)
    weights = charges["trips"]

    # With no charge in force there is no burden to distribute, so the index
    # is 1 by definition. Falling through to the general path would instead
    # score an untolled baseline at 0.775, because a Suits index of zero maps
    # to a mid-range penalty rather than to "nothing to be unequal about".
    if float((charges["net_per_trip"] * weights).sum()) <= 1e-9:
        return {
            "equity_score": 1.0,
            "components": {"burden_inequality": 0.0, "transit_access_gap": 0.0,
                           "spatial_concentration": 0.0, "suits_index": 0.0},
            "weights": {"burden": cfg.equity_weight_burden,
                        "access": cfg.equity_weight_access,
                        "spatial": cfg.equity_weight_spatial},
            "regressive": False,
            "by_quintile": by_quintile(eq, base, segs, cfg),
            "by_subarea": by_subarea(eq, segs, cfg),
            "recycling": recycling_benefit(net_revenue_annual, segs, cfg),
            "burden_ratio_q1_q5": 0.0,
            "total_credits_peak": 0.0,
            "share_paid_by_transit_poor": 0.0,
            "no_charge": True,
        }

    suits = suits_index(charges["net_annual"], segs.income, weights)
    # Map Suits (+1 progressive .. -1 regressive) onto a 0-1 penalty.
    burden_inequality = float(np.clip(0.5 - suits / 2.0, 0.0, 1.0))
    access_gap = transit_access_gap(eq, segs, cfg)
    spatial = spatial_concentration(eq, segs, cfg)

    score = 1.0 - (
        cfg.equity_weight_burden * burden_inequality
        + cfg.equity_weight_access * access_gap
        + cfg.equity_weight_spatial * spatial
    )

    quintiles = by_quintile(eq, base, segs, cfg)
    q1 = next((r for r in quintiles if r["quintile"] == "Q1"), None)
    q5 = next((r for r in quintiles if r["quintile"] == "Q5"), None)

    return {
        "equity_score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "components": {
            "burden_inequality": round(burden_inequality, 4),
            "transit_access_gap": round(access_gap, 4),
            "spatial_concentration": round(spatial, 4),
            "suits_index": round(suits, 4),
        },
        # The curve the index is derived from. A single number cannot show
        # WHERE a charge is regressive; two schemes with the same index can hurt
        # different people.
        "suits_curve": suits_curve(charges["net_annual"], segs.income, weights),
        "weights": {
            "burden": cfg.equity_weight_burden,
            "access": cfg.equity_weight_access,
            "spatial": cfg.equity_weight_spatial,
        },
        "regressive": bool(suits < 0),
        "by_quintile": quintiles,
        "by_subarea": by_subarea(eq, segs, cfg),
        "recycling": recycling_benefit(net_revenue_annual, segs, cfg),
        "burden_ratio_q1_q5": round(
            q1["burden_pct_income"] / q5["burden_pct_income"], 3
        ) if q1 and q5 and q5["burden_pct_income"] > 0 else 0.0,
        "total_credits_peak": round(charges["credit_total"], 2),
        "share_paid_by_transit_poor": round(access_gap, 4),
    }
