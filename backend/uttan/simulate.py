"""One scenario, end to end.

Also owns the calibration cache.  Fitting the alternative-specific constants
means solving a full equilibrium at every trial value, which takes a few
seconds; every scenario afterwards reuses that result, so the grid searches and
Monte Carlo runs stay fast.
"""
from __future__ import annotations

import functools
import json
from typing import Dict, Optional

import numpy as np

from . import congestion, equity, finance, incidence, metrics, network, political
from .config import Config
from .congestion import Equilibrium
from .demand import Segments, load_segments
from .toll_policy import TollPolicy


def _config_key(cfg: Config) -> str:
    """Only the parameters that can move the calibration belong in the key."""
    keep = (
        "total_person_trips", "vot_base_per_hour", "vot_income_elasticity",
        "median_household_income", "vot_floor_per_hour", "auto_cost_per_km",
        "parking_cost_peak", "go_fare", "ttc_fare", "logit_scale",
        "nest_lambda", "schedule_penalty_per_min", "offpeak_shift_minutes",
        "fixed_schedule_multiplier", "forgo_base_penalty", "forgo_wfh_discount",
        "reliability_weight", "buffer_time_factor", "transit_ivt_multiplier",
        "transit_wait_multiplier", "transit_access_multiplier",
        "carpool_coordination_cost", "carpool_matching_friction",
        "carpool_occupancy", "shoulder_capacity_ratio", "peak_start_h",
        "peak_end_h", "go_peak_capacity", "ttc_peak_capacity",
        "crowding_onset_load", "crowding_penalty_max",
    )
    d = cfg.to_dict()
    return json.dumps({k: d[k] for k in keep}, sort_keys=True)


@functools.lru_cache(maxsize=32)
def _calibrated(key: str, cfg_json: str) -> dict:
    cfg = Config.from_dict(json.loads(cfg_json))
    segs = load_segments(cfg)
    return congestion.calibrate(cfg, segs)


def calibrated(cfg: Config) -> dict:
    """Calibration result for this configuration, cached across calls."""
    return _calibrated(_config_key(cfg), json.dumps(cfg.to_dict(), sort_keys=True))


def baseline(cfg: Config) -> Equilibrium:
    return calibrated(cfg)["equilibrium"]


def context(cfg: Config, reference: Optional[Config] = None) -> tuple:
    """The (constants, baseline) pair a run should be scored against.

    The alternative-specific constants are estimated once, against the observed
    base split.  When a behavioural or demand parameter is being *varied* -- in a
    tornado sweep or a Monte Carlo draw -- those constants stay at their fitted
    values and only the baseline is re-solved under the new parameter.

    Re-fitting the constants for every draw would be circular: they would move to
    whatever value reproduces the observed shares under the new parameter, so the
    model would match the base data no matter what, and the parameter's influence
    would disappear into the constants.  A sensitivity analysis built that way
    reports far less sensitivity than really exists.
    """
    if reference is None:
        cal = calibrated(cfg)
        return cal["constants"], cal["equilibrium"]

    constants = calibrated(reference)["constants"]
    segs = load_segments(cfg)
    links = network.load_links(
        cfg.peak_end_h - cfg.peak_start_h, rejoin_fraction=cfg.rejoin_fraction
    )
    base = congestion.solve(
        TollPolicy(peak_toll=0.0, label="baseline"), segs, cfg,
        links=links, constants=constants,
    )
    return constants, base


def run(
    policy: TollPolicy,
    cfg: Optional[Config] = None,
    segs: Optional[Segments] = None,
    full: bool = True,
    reference: Optional[Config] = None,
    with_raw_incidence: bool = False,
) -> dict:
    """Run one policy to equilibrium and score it on every dimension.

    `reference` names the configuration the choice constants were fitted at.
    Pass it when `cfg` perturbs a parameter, so the constants stay fixed and the
    perturbation is allowed to move the results.  See `context`.
    """
    cfg = cfg or Config()
    segs = segs or load_segments(cfg)
    constants, base = context(cfg, reference)

    hours = cfg.peak_end_h - cfg.peak_start_h
    links = network.load_links(hours, rejoin_fraction=cfg.rejoin_fraction)
    # Warm-started from the calibrated baseline. Most policies land near it, so
    # the iteration has far less ground to cover than from a flat start, and the
    # fixed point is the same either way.
    eq = congestion.solve(
        policy, segs, cfg, links=links, constants=constants, start=base.shares
    )

    # Complements can change capacity, so score the scenario on the network it
    # actually ran with, not on the pristine one.
    from copy import deepcopy

    from .toll_policy import apply_complements

    scen_links = deepcopy(links)
    apply_complements(policy, scen_links, cfg)

    # `links` is what the baseline ran on; `scen_links` carries the complements'
    # capacity changes. Scoring both against `scen_links` credits the baseline
    # with improvements it never had -- see metrics.compute.
    m = metrics.compute(eq, base, scen_links, cfg, base_links=links)
    delay_saved = m["vehicle_hours_delay_base"] - m["vehicle_hours_delay"]
    vehicles_removed = max(-m["peak_vehicle_change"], 0.0)

    fin = finance.compute(
        eq, base, policy, segs, cfg,
        delay_saved_vehicle_hours=delay_saved,
        vehicles_removed=vehicles_removed,
    )
    eqty = equity.compute(eq, base, segs, cfg, fin["net_revenue_annual"])

    raw_incidence = incidence.welfare_incidence(
        eq, base, segs, cfg, constants, fin["net_revenue_annual"]
    )
    accept = political.acceptability(raw_incidence, segs, cfg)

    result = {
        "policy": policy.to_dict(),
        "label": policy.label,
        "metrics": m,
        "finance": fin,
        "equity": eqty,
        "convergence": {
            "iterations": eq.iterations,
            "gap": eq.gap,
            "converged": eq.converged,
            "epsilon": cfg.convergence_epsilon,
            "history": eq.gap_history[:80],
        },
        "delay_hours_saved_peak": round(delay_saved, 1),
        "acceptability": accept,
        "winners_share": round(raw_incidence["winners_share"], 4),
        "feasible": feasibility(m, eqty, cfg, accept),
    }
    if full:
        result["revenue_recycling"] = finance.recycling_plan(fin["net_revenue_annual"])
        result["sankey"] = sankey(eq, base, cfg)
        # Who wins and loses, as distinct from who pays. See incidence.py.
        inc = incidence.compute(
            eq, base, segs, cfg, constants, policy, m, eqty,
            fin["net_revenue_annual"],
        )
        result["incidence"] = inc
        result["ride_hailing"] = political.ride_hailing_response(
            policy.peak_toll, getattr(policy, "ptc_surcharge", 0.0), cfg
        )
    # Per-segment arrays, opt-in because they are numpy and 70 long: not JSON
    # and not wanted in any API payload. `political.trust_report` needs the
    # promised/experienced split, and rebuilding it outside would duplicate this
    # function's setup and then drift from it.
    if with_raw_incidence:
        result["_raw_incidence"] = raw_incidence

    return result


def feasibility(m: dict, eqty: dict, cfg: Config, accept: Optional[dict] = None) -> dict:
    """Test a scenario against the policy constraints the leader must respect."""
    checks = {
        "diversion": {
            "limit_pct": round(100 * cfg.max_diversion_increase, 1),
            "value_pct": m["worst_diversion_pct"],
            "link": m["worst_diversion_link"],
            "passes": m["worst_diversion_pct"] <= 100 * cfg.max_diversion_increase,
        },
        "equity": {
            "minimum": cfg.min_equity_score,
            "value": eqty["equity_score"],
            "passes": eqty["equity_score"] >= cfg.min_equity_score,
        },
        "congestion": {
            "minimum_pct": round(100 * cfg.min_delay_reduction, 1),
            "value_pct": m["delay_reduction_pct"],
            "passes": m["delay_reduction_pct"] >= 100 * cfg.min_delay_reduction,
        },
        "transit_capacity": {
            "go_load_factor": m["go_load_factor"],
            "ttc_load_factor": m["ttc_load_factor"],
            "passes": not m["transit_capacity_breached"],
        },
    }
    if accept is not None:
        # A scheme that cannot survive its own politics is not a policy option.
        # The test is support once operating rather than support today, because
        # every scheme in the record was unpopular before it ran: Stockholm was
        # opposed two to one and then kept by the same margin. Requiring
        # majority support up front would rule out every charge ever built.
        checks["acceptability"] = {
            "minimum": 0.5,
            "support_before": accept["before_operation"]["support_share"],
            "support_after": accept["after_operation"]["support_share"],
            "passes": accept["implementable_after_pilot"],
        }
    return {
        "passes": all(c["passes"] for c in checks.values()),
        "checks": checks,
        "failed": [k for k, c in checks.items() if not c["passes"]],
    }


def sankey(eq: Equilibrium, base: Equilibrium, cfg: Config) -> dict:
    """Where the baseline Gardiner drivers ended up.

    An aggregate model tracks shares, not individuals, so this is a
    proportional attribution: the drivers who left the Gardiner are allocated
    across the alternatives that grew, in proportion to how much each grew.  It
    is a presentation of the net change, not a claim about who moved where.
    """
    from .config import ALTERNATIVES

    T = cfg.total_person_trips
    idx = {a: i for i, a in enumerate(ALTERNATIVES)}
    lost = (base.market_shares[idx["drive_gardiner"]] - eq.market_shares[idx["drive_gardiner"]]) * T
    if lost <= 0:
        return {"source": "drive_gardiner", "total": 0.0, "flows": [], "note": "no reduction"}

    gains = {
        a: (eq.market_shares[idx[a]] - base.market_shares[idx[a]]) * T
        for a in ALTERNATIVES
        if a != "drive_gardiner"
    }
    positive = {a: g for a, g in gains.items() if g > 0}
    total_gain = sum(positive.values())

    flows = [
        {"target": a, "value": round(lost * g / total_gain, 1), "share": round(g / total_gain, 4)}
        for a, g in sorted(positive.items(), key=lambda kv: -kv[1])
    ] if total_gain > 0 else []

    return {
        "source": "drive_gardiner",
        "total": round(float(lost), 1),
        "flows": flows,
        "note": "Net change attributed proportionally across the alternatives that grew.",
    }


def validation_report(cfg: Optional[Config] = None) -> dict:
    """The Step 4 evidence that the baseline is credible before any toll is set."""
    cfg = cfg or Config()
    cal = calibrated(cfg)
    info = cal["info"]
    segs = load_segments(cfg)
    base = cal["equilibrium"]

    links = network.load_links(
        cfg.peak_end_h - cfg.peak_start_h, rejoin_fraction=cfg.rejoin_fraction
    )
    elasticity = _toll_elasticity(cfg, segs, cal["constants"])

    share_rows = [
        {
            "alternative": a,
            "observed": round(info["target_shares"][a], 5),
            "modelled": round(info["fitted_shares"][a], 5),
            "error_pp": round(100 * (info["fitted_shares"][a] - info["target_shares"][a]), 4),
            "constant_dollars": round(info["constants"][a], 3),
        }
        for a in info["target_shares"]
    ]

    return {
        "link_validation": network.validate(cfg.peak_end_h - cfg.peak_start_h),
        "share_validation": share_rows,
        "max_share_error_pp": round(100 * info["max_abs_share_error"], 6),
        "calibration_iterations": info["iterations"],
        "calibration_converged": info["converged"],
        "base_link_volumes": info["base_link_volumes"],
        "toll_elasticity": elasticity,
        "transit_headroom": {
            "go_load_factor": round(base.transit_loads["go_rail"] / cfg.go_peak_capacity, 4),
            "go_capacity": cfg.go_peak_capacity,
            "ttc_load_factor": round(base.transit_loads["ttc"] / cfg.ttc_peak_capacity, 4),
            "ttc_capacity": cfg.ttc_peak_capacity,
        },
        "notes": [
            "Alpha is fitted on gardiner_west, gardiner_east and lakeshore_west; "
            "lakeshore_east and queensway_west are held out and their error is "
            "an out-of-sample check.",
            "Alternative-specific constants are fitted at the equilibrium "
            "implied by each trial value, so the calibration is consistent with "
            "the congestion feedback used later.",
            "Beta is held at a literature value rather than fitted, so it "
            "cannot trade off against alpha.",
        ],
    }


def _toll_elasticity(cfg: Config, segs: Segments, constants: np.ndarray) -> dict:
    """Arc elasticity of charged-link volume with respect to the toll.

    Reported so the implied behavioural response can be compared against
    observed schemes rather than taken on trust from the logit scale.
    """
    out = []
    base_eq = congestion.solve(TollPolicy(peak_toll=0.0), segs, cfg, constants=constants)
    v0 = base_eq.peak_volumes["gardiner_west"]
    for toll in (2.0, 4.0, 6.0):
        eq = congestion.solve(TollPolicy(peak_toll=toll), segs, cfg, constants=constants)
        v = eq.peak_volumes["gardiner_west"]
        out.append(
            {
                "toll": toll,
                "volume": round(v, 1),
                "change_pct": round(100 * (v / v0 - 1), 2),
                "arc_elasticity_vs_generalized_cost": round(
                    ((v - v0) / v0) / (toll / 50.0), 3
                ),
            }
        )
    return {
        "base_volume": round(v0, 1),
        "points": out,
        "note": "Elasticity is expressed against a roughly $50 base generalized "
                "cost per peak auto trip, so it is comparable with published "
                "toll-elasticity ranges of about -0.1 to -0.4.",
    }
