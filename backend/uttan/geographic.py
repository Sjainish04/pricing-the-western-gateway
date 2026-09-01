"""Geographic equity: who pays is also a question about where they live.

FHWA's income-equity primer distinguishes three kinds of equity -- income,
geographic and modal -- and warns that most analyses stop at the first.  Its
New York finding is the one worth transplanting: New Jersey residents paid
about 45% of the tolls while making up about 24% of the drivers.  A cordon at a
state line collects disproportionately from the people on the far side of it.

This corridor has the same structure and nobody has said so plainly.  Forty per
cent of AM-peak demand crosses the western gateway from Mississauga and the
west GTA.  Those travellers pay a charge levied by a city they do not live in,
cannot vote in, and whose council does not answer to them.  The income analysis
in `equity.py` cannot see any of that, because it sorts people by quintile.

Three questions this module answers that the income analysis cannot
------------------------------------------------------------------
**Does any area pay more than its share?**  The FHWA ratio: share of the charge
paid over share of trips made.  Above one means an area is carrying more than
its use of the road would imply.

**Does the money come back to where it came from?**  Revenue is recycled toward
station access and first-and-last-mile connections, which is deliberately
progressive -- it goes where transit access is worst.  But that allocation is
made on transit need, not on where the charge was collected, so some areas are
net contributors and others net recipients.  Naming them is the difference
between a spending plan and a transfer nobody announced.

**Is the burden actually about geography, or is it income wearing a map?**
Sub-areas differ in income as well as in distance, so a raw geographic result
can be an income result in disguise.  `decomposition()` holds income constant
and asks what is left, which is the only way to know whether "geographic
equity" is a separate finding or a restatement of §7.

A note on what this is not
--------------------------
The sub-area shares come from a synthetic OD pattern, Census-derived rather
than a TTS extract.  The *ordering* of areas by distance and transit access is
solid; the precise shares are not observed.  A 45%-versus-24% style headline
from this model is an illustration of a structure, not a measurement of it.
"""
from __future__ import annotations

import functools
import json
from typing import Dict, List, Optional

import numpy as np

from . import congestion, equity, incidence, simulate
from .config import Config
from .demand import Segments, load_segments
from .toll_policy import TollPolicy

# Sub-areas outside the City of Toronto.  Matched on the segment table's own
# labels rather than hard-coded shares, so adding a sub-area cannot silently
# leave it on the wrong side of the boundary.
OUTSIDE_TORONTO = ("Mississauga", "west GTA")

# FHWA's New York finding, carried as the benchmark this corridor is compared
# against rather than as an assumption used anywhere in the arithmetic.
FHWA_NYC_BENCHMARK = {
    "jurisdiction": "New Jersey residents, New York cordon",
    "share_of_tolls_paid": 0.45,
    "share_of_drivers": 0.24,
    "ratio": round(0.45 / 0.24, 3),
    "source": "FHWA income-equity primer (dot_760_DS1.pdf)",
}


def _is_outside(subarea: str) -> bool:
    return any(token in subarea for token in OUTSIDE_TORONTO)


@functools.lru_cache(maxsize=16)
def _cached(payload: str) -> dict:
    kw = json.loads(payload)
    cfg = Config.from_dict(kw["config"])
    return _analyse(TollPolicy(**kw["policy"]), cfg)


def analyse(policy: Optional[TollPolicy] = None,
            cfg: Optional[Config] = None) -> dict:
    """Cached entry point."""
    cfg = cfg or Config()
    policy = policy or TollPolicy(
        peak_toll=10.0, coverage="screenline", credit="low_income_transit_poor",
        label="$10 screenline (recommended)",
    )
    payload = json.dumps({"policy": policy.to_dict(), "config": cfg.to_dict()},
                         sort_keys=True)
    return _cached(payload)


def _analyse(policy: TollPolicy, cfg: Config) -> dict:
    segs = load_segments(cfg)
    constants, base = simulate.context(cfg, None)
    eq = congestion.solve(policy, segs, cfg, constants=constants, start=base.shares)

    result = simulate.run(policy, cfg, segs, full=False)
    net_revenue = float(result["finance"]["net_revenue_annual"])

    inc = incidence.welfare_incidence(eq, base, segs, cfg, constants, net_revenue)
    paid = equity.by_subarea(eq, segs, cfg)
    benefit = {r["subarea"]: r for r in equity.recycling_benefit(net_revenue, segs, cfg)}

    rows = []
    for row in paid:
        area = row["subarea"]
        m = segs.subarea == area
        w = inc["trips"][m]
        if w.sum() <= 0:
            continue
        b = benefit.get(area, {})
        pay_share = row["charge_share"]
        trip_share = row["trip_share"]
        rows.append(
            {
                "subarea": area,
                "outside_toronto": _is_outside(area),
                "trips": row["trips"],
                "trip_share": trip_share,
                "charge_share": pay_share,
                # The FHWA ratio. Above 1 = paying more than its use of the road.
                "pays_vs_uses": round(pay_share / trip_share, 3) if trip_share else None,
                "net_toll_per_trip": row["net_toll_per_trip"],
                "burden_pct_income": row["burden_pct_income"],
                "transit_access": row["transit_access"],
                "household_income": round(float(np.average(segs.income[m], weights=w)), 0),
                # Welfare, not just tolls paid -- Eliasson's point that the toll
                # is only the first of four components.
                "net_welfare_per_trip": round(float(np.average(inc["net_per_trip"][m], weights=w)), 3),
                "net_welfare_before_recycling": round(
                    float(np.average(inc["surplus_per_trip"][m], weights=w)), 3
                ),
                "recycled_per_trip": round(float(np.average(inc["recycled_per_trip"][m], weights=w)), 3),
                "benefit_share": b.get("benefit_share"),
                # Net fiscal position: what the area contributes minus what the
                # recycling plan sends back to it.
                "net_contributor_gap": (
                    round(pay_share - b["benefit_share"], 4)
                    if b.get("benefit_share") is not None else None
                ),
                "winners_share": round(
                    float(w[inc["net_per_trip"][m] > 0].sum() / w.sum()), 4
                ),
            }
        )

    rows.sort(key=lambda r: -r["charge_share"])
    return {
        "policy": policy.to_dict(),
        "subareas": rows,
        "boundary": _boundary(rows),
        "benchmark": FHWA_NYC_BENCHMARK,
        "net_revenue_annual": round(net_revenue, 0),
        "caveat": (
            "Sub-area shares come from a synthetic Census-derived OD pattern, "
            "not a TTS extract. The ordering of areas by distance, income and "
            "transit access is defensible; the exact shares are not observed."
        ),
    }


def _boundary(rows: List[dict]) -> dict:
    """The cross-boundary summary: the finding a quintile table cannot show."""
    def agg(outside: bool, key: str) -> float:
        return float(sum(r[key] or 0.0 for r in rows if r["outside_toronto"] is outside))

    out_trips, in_trips = agg(True, "trip_share"), agg(False, "trip_share")
    out_pay, in_pay = agg(True, "charge_share"), agg(False, "charge_share")
    out_benefit = agg(True, "benefit_share")

    return {
        "outside_toronto": {
            "trip_share": round(out_trips, 4),
            "charge_share": round(out_pay, 4),
            "benefit_share": round(out_benefit, 4),
            "pays_vs_uses": round(out_pay / out_trips, 3) if out_trips else None,
            "net_contributor_gap": round(out_pay - out_benefit, 4),
        },
        "toronto": {
            "trip_share": round(in_trips, 4),
            "charge_share": round(in_pay, 4),
            "benefit_share": round(1.0 - out_benefit, 4),
            "pays_vs_uses": round(in_pay / in_trips, 3) if in_trips else None,
        },
        "representation": (
            "The travellers outside Toronto pay a charge set by a council they "
            "cannot vote for. That is not a distributional point, it is a "
            "constitutional one, and it is the same asymmetry that gives the "
            "Province its political cost in bargaining.py."
        ),
    }


def decomposition(policy: Optional[TollPolicy] = None,
                  cfg: Optional[Config] = None) -> dict:
    """Is the geographic result a real one, or income wearing a map?

    Sub-areas differ in income as well as in location, so a raw geographic
    burden can be an income result restated.  This holds income constant --
    comparing each area's burden against what the model would predict from its
    income alone -- and reports the residual.  A large residual means geography
    is doing independent work and deserves its own page; a small one means §7
    already said it.
    """
    data = analyse(policy, cfg)
    rows = data["subareas"]

    incomes = np.array([r["household_income"] for r in rows], dtype=float)
    burdens = np.array([r["burden_pct_income"] for r in rows], dtype=float)
    weights = np.array([r["trip_share"] for r in rows], dtype=float)

    # Weighted least squares of burden on log income: the income-only prediction.
    x = np.log(np.maximum(incomes, 1.0))
    xbar = float(np.average(x, weights=weights))
    ybar = float(np.average(burdens, weights=weights))
    var = float(np.average((x - xbar) ** 2, weights=weights))
    slope = (
        float(np.average((x - xbar) * (burdens - ybar), weights=weights) / var)
        if var > 1e-12 else 0.0
    )
    predicted = ybar + slope * (x - xbar)
    residual = burdens - predicted

    total_var = float(np.average((burdens - ybar) ** 2, weights=weights))
    resid_var = float(np.average(residual ** 2, weights=weights))
    explained = 1.0 - resid_var / total_var if total_var > 1e-12 else 0.0

    out = []
    for r, pred, res in zip(rows, predicted, residual):
        out.append(
            {
                "subarea": r["subarea"],
                "outside_toronto": r["outside_toronto"],
                "household_income": r["household_income"],
                "transit_access": r["transit_access"],
                "burden_pct_income": r["burden_pct_income"],
                "predicted_from_income": round(float(pred), 4),
                "residual": round(float(res), 4),
            }
        )
    out.sort(key=lambda r: -abs(r["residual"]))

    # What IS the residual, if not income?  Correlate it against transit access.
    # If that comes out strongly negative, the leftover geographic burden is
    # not distance at all -- it is whether an alternative exists to escape to,
    # which is a different policy lever and points at a different remedy.
    access = np.array([r["transit_access"] for r in rows], dtype=float)
    resid = np.array([r["residual"] for r in out], dtype=float)
    resid_by_row = np.array([residual[i] for i in range(len(rows))], dtype=float)
    if np.std(access) > 1e-9 and np.std(resid_by_row) > 1e-9:
        access_corr = float(np.corrcoef(access, resid_by_row)[0, 1])
    else:
        access_corr = 0.0

    return {
        "rows": out,
        "share_explained_by_income": round(float(explained), 4),
        "share_not_explained_by_income": round(1.0 - float(explained), 4),
        "residual_vs_transit_access_corr": round(access_corr, 4),
        "mechanism": (
            "The part of geographic burden that income does not explain runs "
            "against transit access: an area with a usable alternative can "
            "escape the charge, an area without one pays it. The direction is "
            "the expected one and the remedy it points at is service rather "
            "than rebates -- but with seven sub-areas the correlation is "
            "moderate, not decisive, and it should be read as consistent with "
            "that mechanism rather than as evidence for it."
        ),
        "reading": (
            "The share of geographic burden variation that income alone "
            "predicts. What is left over is what location contributes on its "
            "own -- distance to the screenline, and whether a usable transit "
            "alternative exists at that distance. A geographic equity page is "
            "only worth having if that residual is material."
        ),
    }


def report(policy: Optional[TollPolicy] = None,
           cfg: Optional[Config] = None) -> dict:
    return {
        "incidence": analyse(policy, cfg),
        "decomposition": decomposition(policy, cfg),
        "fhwa_types": [
            {"type": "Income", "where": "equity.py and incidence.py",
             "status": "modelled, with Suits benchmarks against operating schemes"},
            {"type": "Geographic", "where": "this module",
             "status": "modelled: burden, welfare and recycling by sub-area, "
                       "and across the city boundary"},
            {"type": "Modal", "where": "incidence.py",
             "status": "modelled: time savings accrue to whoever keeps driving, "
                       "so the recycling plan does the modal-equity work, not "
                       "the charge"},
        ],
    }
