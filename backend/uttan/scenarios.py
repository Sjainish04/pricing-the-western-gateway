"""The scenario library.

Covers the ten designs the proposal commits to comparing, plus the governance
branches.  The no-toll operational package matters most of all: without a
serious non-pricing counterfactual, the study would be assuming its own
conclusion.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import Config
from .toll_policy import TollPolicy

LIBRARY: Dict[str, dict] = {
    "baseline": dict(
        peak_toll=0.0, label="Baseline - no charge",
        description="Current policy. Every other scenario is measured against this.",
        group="reference",
    ),
    "flat_2": dict(peak_toll=2.0, label="$2 flat peak charge",
                   description="Freeway only, no credits.", group="price ladder"),
    "flat_4": dict(peak_toll=4.0, label="$4 flat peak charge",
                   description="Freeway only, no credits.", group="price ladder"),
    "flat_6": dict(peak_toll=6.0, label="$6 flat peak charge",
                   description="Freeway only, no credits.", group="price ladder"),
    "flat_8": dict(peak_toll=8.0, label="$8 flat peak charge",
                   description="Freeway only, no credits.", group="price ladder"),
    "time_of_day": dict(
        peak_toll=6.0, shoulder_toll=2.5, window="0630_1000",
        label="Time-of-day charge",
        description="Higher core rate with a cheaper shoulder rate, to spread the peak "
                    "rather than simply suppress it.",
        group="design",
    ),
    "screenline_5": dict(
        peak_toll=5.0, coverage="screenline", label="$5 screenline charge",
        description="Charges every inbound crossing of the western screenline, so "
                    "Lake Shore and The Queensway stop being a free bypass.",
        group="design",
    ),
    "equity_low_income": dict(
        peak_toll=5.0, coverage="screenline", credit="low_income",
        label="$5 screenline + low-income credit",
        description="Rebates most of the charge for the bottom two income quintiles.",
        group="equity",
    ),
    "equity_transit_poor": dict(
        peak_toll=5.0, coverage="screenline", credit="low_income_transit_poor",
        label="$5 screenline + income and transit-poor credits",
        description="Adds a partial rebate where no realistic transit alternative exists.",
        group="equity",
    ),
    "equity_shift_worker": dict(
        peak_toll=5.0, coverage="screenline", credit="shift_worker",
        label="$5 screenline + shift-worker credit",
        description="Protects travellers who cannot retime their trip.",
        group="equity",
    ),
    "hov_discount": dict(
        peak_toll=5.0, coverage="screenline", credit="hov_discount", hov_discount=0.5,
        label="$5 screenline + HOV discount",
        description="Halves the charge for vehicles carrying two or more people.",
        group="equity",
    ),
    "monthly_cap": dict(
        peak_toll=5.0, coverage="screenline", credit="monthly_cap", monthly_cap_trips=16,
        label="$5 screenline + monthly cap",
        description="Caps the number of charged trips per month for frequent users.",
        group="equity",
    ),
    "mobility_credit": dict(
        peak_toll=5.0, coverage="screenline", credit="mobility_credit",
        label="$5 screenline + GO/TTC mobility credit",
        description="Spends revenue on cutting the transit fare instead of rebating the charge.",
        group="equity",
    ),
    "targeted_package": dict(
        peak_toll=5.0, coverage="screenline", credit="targeted_package",
        label="$5 screenline + targeted package",
        description="Income credit, transit-poor credit and a transit fare credit together. "
                    "The design the proposal expects to prefer over broad exemptions.",
        group="equity",
    ),
    "means_tested": dict(
        peak_toll=10.0, coverage="screenline", credit="means_tested",
        label="$10 screenline, means-tested (San Francisco design)",
        description="Lowest income quintile exempt, second quintile pays half. Every "
                    "congestion charge operating today is a flat fee regardless of "
                    "income; San Francisco's proposal would be the first that is not.",
        group="equity",
    ),
    "equity_first": dict(
        peak_toll=10.0, coverage="screenline", credit="equity_first",
        label="$10 screenline, equity-first package",
        description="Means-tested fees, a transit credit funded from the same revenue, "
                    "and a partial rebate where no realistic transit alternative exists. "
                    "The Greenlining/San Francisco design applied to this corridor.",
        group="equity",
    ),
    "toll_plus_signals": dict(
        peak_toll=5.0, coverage="screenline", credit="targeted_package",
        adaptive_signals=True,
        label="$5 screenline + targeted package + adaptive signals",
        description="Adds signal coordination on the diversion corridors.",
        group="package",
    ),
    "toll_plus_transit": dict(
        peak_toll=5.0, coverage="screenline", credit="targeted_package",
        go_frequency_uplift=0.25, transit_priority=True,
        label="$5 screenline + targeted package + transit investment",
        description="Recycles revenue into Lakeshore West frequency and bus priority.",
        group="package",
    ),
    "toll_plus_parking": dict(
        peak_toll=5.0, coverage="screenline", credit="targeted_package",
        parking_surcharge=8.0,
        label="$5 screenline + targeted package + parking surcharge",
        description="Coordinates the road charge with downtown parking pricing.",
        group="package",
    ),
    "full_package": dict(
        peak_toll=5.0, coverage="screenline", credit="targeted_package",
        adaptive_signals=True, ramp_metering=True, transit_priority=True,
        parking_surcharge=6.0, go_frequency_uplift=0.25,
        label="Full package - charge plus every complement",
        description="Everything at once, to show what the charge adds over operations alone.",
        group="package",
    ),
    "no_toll_package": dict(
        peak_toll=0.0, adaptive_signals=True, ramp_metering=True, transit_priority=True,
        parking_surcharge=8.0, go_frequency_uplift=0.25,
        label="No-toll operational package",
        description="Adaptive signals, ramp management, transit priority, parking pricing and "
                    "GO frequency, with no charge at all. The serious counterfactual: if this "
                    "matches the priced scenarios, pricing is not worth its political cost.",
        group="counterfactual",
    ),
    "branch_b_city_roads": dict(
        peak_toll=5.0, coverage="city_roads_only", credit="targeted_package",
        label="Governance branch B - City roads only",
        description="If the Province does not authorise a toll on the expressway, only the "
                    "City-controlled arterials can be charged. Tests whether that is a "
                    "substitute or a perverse outcome.",
        group="governance",
    ),
    "branch_b_parking": dict(
        peak_toll=0.0, parking_surcharge=14.0, adaptive_signals=True, transit_priority=True,
        label="Governance branch B - parking levy substitute",
        description="A City-controlled demand-management package built on parking pricing "
                    "instead of a road charge.",
        group="governance",
    ),
}


def build(name: str, overrides: Optional[dict] = None) -> TollPolicy:
    """Instantiate a named scenario, with optional overrides."""
    if name not in LIBRARY:
        raise KeyError(f"unknown scenario {name!r}; available: {sorted(LIBRARY)}")
    spec = {k: v for k, v in LIBRARY[name].items() if k not in ("description", "group")}
    spec.update(overrides or {})
    return TollPolicy(**spec)


def catalogue() -> List[dict]:
    """Scenario metadata for the interface."""
    return [
        {
            "id": name,
            "label": spec["label"],
            "description": spec["description"],
            "group": spec["group"],
            "peak_toll": spec.get("peak_toll", 0.0),
            "coverage": spec.get("coverage", "gardiner_only"),
            "credit": spec.get("credit", "none"),
            "window": spec.get("window", "0630_0930"),
        }
        for name, spec in LIBRARY.items()
    ]


def compare(names: Optional[List[str]] = None, cfg: Optional[Config] = None) -> dict:
    """Run a set of scenarios and return comparable summary rows."""
    from . import game
    from .demand import load_segments

    cfg = cfg or Config()
    segs = load_segments(cfg)
    names = names or list(LIBRARY.keys())

    rows = []
    for name in names:
        policy = build(name)
        row = game.summarise(game.evaluate(policy, cfg, segs))
        row["id"] = name
        row["group"] = LIBRARY[name]["group"]
        row["description"] = LIBRARY[name]["description"]
        rows.append(row)

    priced = [r for r in rows if r["peak_toll"] > 0]
    no_toll = next((r for r in rows if r["id"] == "no_toll_package"), None)
    best_priced = max(priced, key=lambda r: r["delay_reduction_pct"]) if priced else None

    # A charge on its own, with none of the operational measures bolted on.
    # Without this the only "priced" comparator is `full_package`, which is a
    # charge PLUS every complement -- so the headline read as pricing beating
    # operations when it was really operations-plus-pricing beating operations.
    # Two different questions, and the interesting one is asked below.
    # Read off the POLICY, not the summary row: `game.summarise` reports the
    # priced instruments and drops the complement flags, so testing the row
    # silently classified every scenario as unaccompanied.
    complements = ("adaptive_signals", "ramp_metering", "transit_priority",
                   "parking_surcharge", "go_frequency_uplift")

    def unaccompanied(row: dict) -> bool:
        policy = build(row["id"])
        return not any(getattr(policy, c, None) for c in complements)

    alone = [r for r in priced if unaccompanied(r)]
    best_alone = max(alone, key=lambda r: r["delay_reduction_pct"]) if alone else None

    def gap(a, b):
        if not a or not b:
            return None
        return round(a["delay_reduction_pct"] - b["delay_reduction_pct"], 2)

    return {
        "scenarios": rows,
        "pareto_frontier": game.pareto_frontier(rows),
        "counterfactual": {
            "no_toll_package": no_toll,
            "best_priced": best_priced,
            "best_priced_alone": best_alone,
            # What a charge adds ON TOP of the operational package. This is the
            # decision actually in front of an authority that could do either.
            "combined_advantage_pp": gap(best_priced, no_toll),
            # And the like-for-like one: a charge by itself against operations
            # by themselves. Negative means operations win on delay.
            "charge_only_advantage_pp": gap(best_alone, no_toll),
            "note": "`combined_advantage_pp` compares the strongest priced scenario "
                    "-- which includes every operational complement -- against the "
                    "operational package alone, so it measures what the CHARGE adds "
                    "to good operations. `charge_only_advantage_pp` is the "
                    "like-for-like comparison of a charge by itself against "
                    "operations by themselves; a negative value means operations "
                    "remove more delay than pricing does.",
        },
    }
