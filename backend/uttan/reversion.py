"""Does the delay reduction last?  London says it does not.

The study's most quotable number is that the recommended design removes about
39% of peak delay.  The operating record contradicts it directly: **London's
traffic reduction was permanent, and its delay reduction was not.**  Congestion
returned to roughly pre-charging levels within about five years, while the
traffic itself stayed down.  A static equilibrium cannot produce that at any
parameter value -- it solves one point in time, so whatever it finds is
permanent by construction.

That made a first-year effect read as a steady state, which is the single
highest-severity disagreement between this model and the record.

Two mechanisms close the gap, and they are very different in kind.

  **Background demand growth.**  The region keeps growing.  Every year the same
  network carries more trips, so the delay a charge removed is progressively
  re-occupied.  This is exogenous and happens to the charged and uncharged
  corridor alike.

  **Reallocation of the freed road space.**  This is the London mechanism, and
  the important thing about it is that it is a *choice*, not a physical law.
  The charge freed capacity; the authority spent it on bus lanes, wider
  footways and public realm rather than banking it as speed.  Delay came back
  because the space stopped being available to cars -- not because the charge
  stopped working.

Separating them matters more than either number.  Growth erodes the benefit
whatever anybody does.  Reallocation erodes it because somebody decided to
spend it, and that decision buys something this model does not value.  A study
that reported reversion without saying which was which would be telling a
Toronto reader that pricing wears off, when what London actually shows is that
pricing converts congestion into road space you can then give away.

The trajectory is measured against a no-charge counterfactual that grows the
same way, because the alternative -- comparing a future charged year against
today's baseline -- would attribute ordinary demand growth to the charge.
"""
from __future__ import annotations

import functools
import json
from copy import deepcopy
from typing import Dict, List, Optional

from . import congestion, metrics, network
from .config import Config
from .demand import load_segments
from .simulate import calibrated
from .toll_policy import TollPolicy, apply_complements

# London is the only scheme with a published before/after on BOTH quantities
# over enough years to see a reversion, which is why it is the anchor.  Traffic
# stayed down; delay did not.
LONDON = {
    "city": "London",
    "years_to_revert": 5,
    "traffic_change_permanent": True,
    "note": (
        "Traffic entering the charging zone stayed down permanently, but the "
        "delay reduction was gone within about five years as road space was "
        "reallocated to buses, cycling and public realm and background demand "
        "grew."
    ),
    "source": "SFCTA (2020) case studies; city_schemes.csv lesson for London",
}


def recommended_policy() -> TollPolicy:
    """The design the study actually recommends, so the trajectory starts at the
    number the write-up quotes rather than at a neighbouring scenario's."""
    return TollPolicy(
        peak_toll=10.0, coverage="screenline", credit="low_income_transit_poor",
        window="0630_0930", label="recommended",
    )


def _solve_year(
    policy: TollPolicy,
    cfg: Config,
    reference: Config,
    growth_factor: float,
    reallocation: float,
) -> dict:
    """One year: demand grown, space possibly reallocated, equilibrium re-solved.

    `reference` is the configuration the choice constants were fitted at, and it
    is never the grown one.  Re-fitting them per year would be the same
    circularity `sensitivity.py` documents: the constants would absorb the
    growth and the trajectory would flatten into nothing.
    """
    grown = Config.from_dict(
        {**cfg.to_dict(), "total_person_trips": cfg.total_person_trips * growth_factor}
    )
    segs = load_segments(grown)
    constants = calibrated(reference)["constants"]
    hours = grown.peak_end_h - grown.peak_start_h

    def links_for(reallocate: bool) -> Dict[str, network.Link]:
        links = network.load_links(hours, rejoin_fraction=grown.rejoin_fraction)
        if reallocate and reallocation > 0:
            # Only the links the charge actually relieves can have space taken
            # back from them. Reallocating capacity on a road the charge never
            # emptied would be inventing a capacity cut and calling it a
            # consequence of pricing.
            for link in links.values():
                if link.tollable_city or link.tollable_province:
                    link.lane_capacity *= 1.0 - reallocation
        return links

    base_links = links_for(False)
    base = congestion.solve(
        TollPolicy(peak_toll=0.0, label="baseline"), segs, grown,
        links=base_links, constants=constants,
    )
    charged_links = links_for(True)
    eq = congestion.solve(
        policy, segs, grown, links=charged_links, constants=constants,
        start=base.shares,
    )

    scen_links = deepcopy(charged_links)
    apply_complements(policy, scen_links, grown)
    # The baseline is scored on the network WITHOUT the reallocation: with no
    # charge there is no freed space to hand over, so a reallocated baseline
    # would be a capacity cut nobody made.
    m = metrics.compute(eq, base, scen_links, grown, base_links=base_links)
    return {
        "delay_reduction_pct": m["delay_reduction_pct"],
        "peak_vehicle_change_pct": m["peak_vehicle_change_pct"],
        "vehicle_hours_delay": m["vehicle_hours_delay"],
        "vehicle_hours_delay_base": m["vehicle_hours_delay_base"],
    }


def trajectory(
    policy: Optional[TollPolicy] = None,
    cfg: Optional[Config] = None,
    reallocation_share: Optional[float] = None,
    years: Optional[int] = None,
) -> dict:
    """Delay and traffic reduction year by year, against a growing counterfactual.

    `reallocation_share` is the fraction of the charged links' capacity handed
    to something other than general traffic once the charge has freed it,
    reached linearly over `cfg.reallocation_ramp_years`.
    """
    cfg = cfg or Config()
    policy = policy or recommended_policy()
    share = cfg.space_reallocation_share if reallocation_share is None else reallocation_share
    horizon = years or cfg.horizon_years

    rows = []
    for year in range(horizon + 1):
        growth = (1.0 + cfg.background_demand_growth) ** year
        ramp = min(1.0, year / max(cfg.reallocation_ramp_years, 1e-9))
        row = _solve_year(policy, cfg, cfg, growth, share * ramp)
        rows.append({
            "year": year,
            "demand_index": round(growth, 4),
            "reallocated_share": round(share * ramp, 4),
            **row,
        })

    first = rows[0]["delay_reduction_pct"]
    half = next((r["year"] for r in rows if r["delay_reduction_pct"] <= first / 2.0), None)
    gone = next((r["year"] for r in rows if r["delay_reduction_pct"] <= 0.0), None)
    return {
        "policy": policy.to_dict(),
        "reallocation_share": round(share, 4),
        "background_demand_growth": cfg.background_demand_growth,
        "years": rows,
        "delay_reduction_year_0": first,
        "delay_reduction_final": rows[-1]["delay_reduction_pct"],
        "half_life_years": half,
        "years_to_full_reversion": gone,
        # The half that London says survives, reported alongside, because the
        # whole point of the comparison is that the two quantities part company.
        "traffic_change_year_0": rows[0]["peak_vehicle_change_pct"],
        "traffic_change_final": rows[-1]["peak_vehicle_change_pct"],
    }


def reallocation_matching_london(
    policy: Optional[TollPolicy] = None,
    cfg: Optional[Config] = None,
    grid: Optional[List[float]] = None,
) -> dict:
    """What reallocation would reproduce London's five-year reversion here?

    Inverted rather than assumed, for the reason the rest of this study inverts
    unobservables: nobody has measured how much of a Toronto gantry's freed
    capacity would be handed to buses, and asserting a number would be the
    weakest link in the chain.  Reporting the number that reproduces the one
    case in the record puts the assumption where it can be argued with.
    """
    cfg = cfg or Config()
    policy = policy or recommended_policy()
    candidates = grid if grid is not None else [round(0.02 * i, 2) for i in range(16)]

    rows = []
    for share in candidates:
        t = trajectory(policy, cfg, reallocation_share=share, years=LONDON["years_to_revert"])
        rows.append({
            "reallocation_share": share,
            "delay_reduction_at_london_horizon": t["delay_reduction_final"],
            "traffic_change_at_london_horizon": t["traffic_change_final"],
        })

    # The share at which the delay benefit has gone by London's fifth year.
    reverted = [r for r in rows if r["delay_reduction_at_london_horizon"] <= 0.0]
    needed = reverted[0]["reallocation_share"] if reverted else None
    return {
        "london": LONDON,
        "candidates": rows,
        "reallocation_needed": needed,
        "reading": (
            "Reproducing London's five-year reversion on this corridor needs about "
            "%.0f%% of the charged links' capacity to be handed to something other "
            "than general traffic. Whether that is a lot or a little is a judgement "
            "about what Toronto would do with the space, not a modelling result."
            % (100 * needed)
            if needed is not None else
            "No reallocation share in the range tested reproduces London's "
            "five-year reversion on this corridor, so on these assumptions "
            "background growth alone does not take the delay benefit away and the "
            "reversion would have to be a deliberate reallocation larger than the "
            "range tested."
        ),
    }


def _verdict(cfg: Config, growth_only: dict, reallocated: Optional[dict],
             needed: Optional[float]) -> str:
    """State what the two trajectories actually show, separately.

    Written from the computed rows rather than beside them. A first draft
    asserted that growth alone reproduced London's asymmetry; it does not --
    under growth both quantities erode together, and the asymmetry appears only
    once the space is reallocated. The claim and the table have to be generated
    from the same place or they drift, which is the failure this study has
    already recorded once in its comparative section.
    """
    lines = [
        "The headline delay reduction is a FIRST-YEAR effect. Under background "
        "demand growth alone it erodes from %.1f%% to %.1f%% over %d years, and "
        "the traffic reduction erodes with it (%.1f%% to %.1f%%). Growth alone "
        "does not reproduce London: both quantities weaken together, and neither "
        "reverts."
        % (
            growth_only["delay_reduction_year_0"],
            growth_only["delay_reduction_final"],
            cfg.horizon_years,
            growth_only["traffic_change_year_0"],
            growth_only["traffic_change_final"],
        )
    ]
    if reallocated is not None and needed is not None:
        lines.append(
            "London's pattern needs the freed space to be given away. Handing "
            "over %.0f%% of the charged links' capacity reverts the delay benefit "
            "entirely by year %s -- to %.1f%% by year %d, meaning worse than no "
            "charge at all -- while the traffic reduction GROWS from %.1f%% to "
            "%.1f%%. Traffic down, delay gone: that is the asymmetry London "
            "recorded, and it is a consequence of spending the space, not of the "
            "charge failing."
            % (
                100 * needed,
                reallocated["years_to_full_reversion"],
                reallocated["delay_reduction_final"],
                cfg.horizon_years,
                reallocated["traffic_change_year_0"],
                reallocated["traffic_change_final"],
            )
        )
    return " ".join(lines)


@functools.lru_cache(maxsize=8)
def _cached_report(payload: str) -> dict:
    cfg = Config.from_dict(json.loads(payload)["config"])
    policy = recommended_policy()

    growth_only = trajectory(policy, cfg, reallocation_share=0.0)
    matched = reallocation_matching_london(policy, cfg)
    needed = matched["reallocation_needed"]
    with_reallocation = (
        trajectory(policy, cfg, reallocation_share=needed) if needed is not None else None
    )

    return {
        "growth_only": growth_only,
        "with_london_reallocation": with_reallocation,
        "london_match": matched,
        "verdict": _verdict(cfg, growth_only, with_reallocation, needed),
        "what_this_does_not_model": (
            "Land-use change, trip generation outside the modelled screenline, and "
            "any response by the authority other than reallocating capacity. "
            "Background growth is a planning assumption, not a forecast, and is "
            "swept. The reallocation share is inverted against London rather than "
            "assumed, and defaults to zero, so nothing here changes a headline "
            "unless it is asked to."
        ),
    }


def report(cfg: Optional[Config] = None) -> dict:
    """Both trajectories and the London comparison, for the API."""
    cfg = cfg or Config()
    return _cached_report(json.dumps({"config": cfg.to_dict()}, sort_keys=True))
