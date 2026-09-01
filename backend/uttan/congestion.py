"""The follower equilibrium.

Travellers choose the action with the lowest perceived generalized cost, but
the cost of driving depends on how many other people drive.  The fixed point of
that loop is a stochastic user equilibrium, and we reach it with the Method of
Successive Averages: at pass k, move the current allocation a 1/k step toward
the freshly computed choice probabilities.  The declining step is what makes
the iteration converge instead of oscillating between an empty road and a
jammed one.

Convergence uses the rule from the simulation plan,

    sum_e |v_e(k) - v_e(k-1)|  /  sum_e v_e(k-1)  <  epsilon

evaluated on link volumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from . import choice_model, generalized_cost, network
from .config import ALTERNATIVES, Config
from .demand import Segments, vehicles_by_link
from .network import Link
from .toll_policy import TollPolicy, credit_matrix, surcharge_matrix, toll_matrix

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}


@dataclass
class Equilibrium:
    """The converged state of the follower game."""

    shares: np.ndarray                    # (N, A) segment choice probabilities
    market_shares: np.ndarray             # (A,)
    peak_volumes: Dict[str, float]        # vehicles per link, peak period
    shoulder_volumes: Dict[str, float]    # added vehicles per link, shoulder
    transit_loads: Dict[str, float]
    route_times: Dict[str, float]         # minutes, door to door by route
    link_times: Dict[str, float]          # minutes per link
    gc: np.ndarray                        # (N, A) generalized cost at equilibrium
    components: dict
    iterations: int
    gap: float
    converged: bool
    gap_history: List[float] = field(default_factory=list)

    def share_of(self, alternative: str) -> float:
        return float(self.market_shares[IDX[alternative]])

    def person_trips(self, cfg: Config) -> Dict[str, float]:
        return {
            a: float(self.market_shares[i] * cfg.total_person_trips)
            for i, a in enumerate(ALTERNATIVES)
        }


def _transit_loads(shares: np.ndarray, segs: Segments, cfg: Config) -> Dict[str, float]:
    per_alt = (segs.trips(cfg)[:, None] * shares).sum(axis=0)
    return {
        "go_rail": float(per_alt[IDX["go_rail"]]),
        "ttc": float(per_alt[IDX["ttc"]]),
    }


def solve(
    policy: TollPolicy,
    segs: Segments,
    cfg: Config,
    links: Optional[Dict[str, Link]] = None,
    constants: Optional[np.ndarray] = None,
    start: Optional[np.ndarray] = None,
) -> Equilibrium:
    """Iterate to a stochastic user equilibrium under `policy`."""
    from copy import deepcopy

    from .toll_policy import apply_complements

    hours = cfg.peak_end_h - cfg.peak_start_h
    # Deep-copied because the non-price complements mutate link attributes, and
    # a scenario must not leak capacity changes into the next one.
    links = (
        deepcopy(links)
        if links is not None
        else network.load_links(hours, rejoin_fraction=cfg.rejoin_fraction)
    )
    cfg = apply_complements(policy, links, cfg)

    weights = segs.trips(cfg)
    constants = np.zeros(len(ALTERNATIVES)) if constants is None else constants
    tolls = toll_matrix(policy, segs, cfg)
    credits = credit_matrix(policy, segs, cfg)
    surcharges = surcharge_matrix(policy, segs, cfg)
    coverage = policy.window_coverage(cfg)

    shares = (
        start.copy()
        if start is not None
        else np.full((segs.n, len(ALTERNATIVES)), 1.0 / len(ALTERNATIVES))
    )

    link_order = sorted(links.keys())
    prev_volumes = None
    gap_history: List[float] = []
    gap = float("inf")
    it = 0

    for it in range(1, cfg.max_iterations + 1):
        veh = vehicles_by_link(shares, segs, cfg)
        peak, shoulder = veh["peak"], veh["shoulder"]
        loads = _transit_loads(shares, segs, cfg)
        carpool_share = float(
            np.average(shares[:, IDX["carpool_gardiner"]], weights=weights)
        )

        bundle = generalized_cost.assemble(
            links, peak, shoulder, loads, tolls, credits, segs, cfg,
            coverage, carpool_share,
        )
        probs = choice_model.probabilities(bundle["gc"], constants, cfg)

        # Method of successive averages, with a short warm-up at a fixed step so
        # the early passes can move away from a poor starting allocation.
        step = 0.5 if it <= cfg.msa_warmup else 1.0 / (it - cfg.msa_warmup)
        shares = shares + step * (probs - shares)

        current = np.array([peak.get(k, 0.0) for k in link_order])
        if prev_volumes is not None:
            gap = network.relative_gap(current, prev_volumes)
            gap_history.append(gap)
            if gap < cfg.convergence_epsilon and it > cfg.msa_warmup + 2:
                break
        prev_volumes = current

    # Final consistent evaluation at the converged allocation.
    veh = vehicles_by_link(shares, segs, cfg)
    peak, shoulder = veh["peak"], veh["shoulder"]
    loads = _transit_loads(shares, segs, cfg)
    carpool_share = float(np.average(shares[:, IDX["carpool_gardiner"]], weights=weights))
    bundle = generalized_cost.assemble(
        links, peak, shoulder, loads, tolls, credits, segs, cfg, coverage, carpool_share
    )
    # The surcharge is already inside the parking cost that drove the choice;
    # it is recorded separately so equity and revenue can account for it.
    bundle["surcharge"] = surcharges

    routes = network.route_composition(cfg.rejoin_fraction)
    shoulder_total = {
        lid: link.base_volume_veh * cfg.shoulder_capacity_ratio + shoulder.get(lid, 0.0)
        for lid, link in links.items()
    }
    route_times = {
        alt: network.route_time(alt, links, peak, hours, routes)
        for alt in ("drive_gardiner", "drive_lakeshore", "drive_queensway")
    }
    route_times["shift_offpeak"] = network.route_time(
        "shift_offpeak", links, shoulder_total, hours, routes
    )
    link_times = {
        lid: link.travel_time(peak.get(lid, 0.0), hours) for lid, link in links.items()
    }

    return Equilibrium(
        shares=shares,
        market_shares=choice_model.aggregate_shares(shares, weights),
        peak_volumes={k: float(v) for k, v in peak.items()},
        shoulder_volumes={k: float(v) for k, v in shoulder.items()},
        transit_loads=loads,
        route_times={k: float(v) for k, v in route_times.items()},
        link_times={k: float(v) for k, v in link_times.items()},
        gc=bundle["gc"],
        components=bundle,
        iterations=it,
        gap=float(gap),
        converged=bool(gap < cfg.convergence_epsilon),
        gap_history=[float(g) for g in gap_history],
    )


def calibrate(cfg: Config, segs: Optional[Segments] = None) -> dict:
    """Fit the alternative-specific constants against the observed base split.

    The constants are fitted at the *equilibrium* implied by each trial value,
    not at a frozen set of travel times, so the calibration stays consistent
    with the congestion feedback the model will later rely on.
    """
    from .config import BASE_SHARES
    from .demand import load_segments

    segs = segs or load_segments(cfg)
    weights = segs.trips(cfg)
    links = network.load_links(
        cfg.peak_end_h - cfg.peak_start_h, rejoin_fraction=cfg.rejoin_fraction
    )
    baseline = TollPolicy(peak_toll=0.0, label="baseline")

    def gc_fn(constants: np.ndarray) -> np.ndarray:
        return solve(baseline, segs, cfg, links=links, constants=constants).gc

    constants, info = choice_model.calibrate_constants(gc_fn, weights, BASE_SHARES, cfg)
    eq = solve(baseline, segs, cfg, links=links, constants=constants)
    info["constants"] = {a: float(c) for a, c in zip(ALTERNATIVES, constants)}
    info["fitted_shares"] = {a: float(s) for a, s in zip(ALTERNATIVES, eq.market_shares)}
    info["target_shares"] = dict(BASE_SHARES)

    # Report the error of the shares we actually publish, not the error the
    # fitting loop reached.  The final equilibrium is solved to the SUE
    # tolerance, which leaves a slightly larger residual than the fit itself;
    # quoting the fit error would overstate how well the baseline is reproduced.
    info["fit_loop_error"] = info["max_abs_share_error"]
    info["max_abs_share_error"] = max(
        abs(info["fitted_shares"][a] - BASE_SHARES[a]) for a in ALTERNATIVES
    )
    info["converged"] = info["max_abs_share_error"] < 1e-3
    info["base_link_volumes"] = {k: round(v, 1) for k, v in eq.peak_volumes.items()}
    return {"constants": constants, "equilibrium": eq, "info": info}
