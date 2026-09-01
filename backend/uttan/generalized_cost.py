"""The generalized cost from the proposal:

    GC[i,a] = beta_t[i] * T[a] + C[a] + tau[a] + S[i,a] + R[i,a] - D[i,a]

    beta_t  value of travel time, $/min, scaled by household income
    T       door-to-door travel time including access, wait and egress
    C       base monetary cost (operating cost, parking, fare)
    tau     the congestion charge
    S       schedule-delay / inconvenience penalty
    R       reliability buffer (auto) or crowding (transit)
    D       credit, rebate or discount

Everything is returned in dollars per person-trip as an (N segments,
A alternatives) matrix, together with the components so the interface can show
where the cost actually sits.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from .config import ALTERNATIVES, Config
from .demand import Segments
from .network import Link

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}

# Fixed door-to-door add-ons, in minutes, that sit outside the link model.
AUTO_TERMINAL_MIN = 8.0        # parking search plus the walk to the workplace
CARPOOL_DETOUR_MIN = 8.0       # collecting and dropping the other occupant
GO_EGRESS_MIN = 8.0            # Union Station to the workplace
TTC_EGRESS_MIN = 6.0
GO_HEADWAY_MIN = 15.0          # Lakeshore West peak headway
TTC_HEADWAY_MIN = 6.0
GO_IVT_MIN = 18.0
TTC_IVT_MIN = 32.0

AUTO_ALTERNATIVES = (
    "drive_gardiner",
    "drive_lakeshore",
    "drive_queensway",
    "carpool_gardiner",
)


def _shoulder_totals(
    links: Dict[str, Link], shoulder_volumes: Dict[str, float], cfg: Config
) -> Dict[str, float]:
    """Shoulder-period link volumes: background traffic plus anyone who retimed."""
    return {
        lid: link.base_volume_veh * cfg.shoulder_capacity_ratio
        + shoulder_volumes.get(lid, 0.0)
        for lid, link in links.items()
    }


def travel_times(
    links: Dict[str, Link],
    peak_volumes: Dict[str, float],
    shoulder_volumes: Dict[str, float],
    segs: Segments,
    cfg: Config,
) -> np.ndarray:
    """(N, A) door-to-door travel time in minutes."""
    from . import network

    hours = cfg.peak_end_h - cfg.peak_start_h
    routes = network.route_composition(cfg.rejoin_fraction)
    T = np.zeros((segs.n, len(ALTERNATIVES)))

    def rt(alt: str, volumes: Dict[str, float]) -> float:
        return network.route_time(alt, links, volumes, hours, routes)

    shoulder_total = _shoulder_totals(links, shoulder_volumes, cfg)

    T[:, IDX["drive_gardiner"]] = rt("drive_gardiner", peak_volumes) + AUTO_TERMINAL_MIN
    T[:, IDX["drive_lakeshore"]] = rt("drive_lakeshore", peak_volumes) + AUTO_TERMINAL_MIN
    T[:, IDX["drive_queensway"]] = rt("drive_queensway", peak_volumes) + AUTO_TERMINAL_MIN
    T[:, IDX["carpool_gardiner"]] = (
        rt("carpool_gardiner", peak_volumes) + AUTO_TERMINAL_MIN + CARPOOL_DETOUR_MIN
    )
    T[:, IDX["shift_offpeak"]] = rt("shift_offpeak", shoulder_total) + AUTO_TERMINAL_MIN

    # Transit access time falls as the sub-area accessibility score rises.
    go_access = 6.0 + 22.0 * (1.0 - segs.transit_access)
    ttc_access = 5.0 + 24.0 * (1.0 - segs.transit_access)

    T[:, IDX["go_rail"]] = (
        cfg.transit_access_multiplier * go_access
        + cfg.transit_wait_multiplier * (GO_HEADWAY_MIN / 2.0)
        + cfg.transit_ivt_multiplier * GO_IVT_MIN
        + GO_EGRESS_MIN
    )
    T[:, IDX["ttc"]] = (
        cfg.transit_access_multiplier * ttc_access
        + cfg.transit_wait_multiplier * (TTC_HEADWAY_MIN / 2.0)
        + cfg.transit_ivt_multiplier * TTC_IVT_MIN
        + TTC_EGRESS_MIN
    )
    # Not travelling costs no travel time; its whole cost sits in S.
    T[:, IDX["forgo_remote"]] = 0.0
    return T


def monetary_costs(links: Dict[str, Link], segs: Segments, cfg: Config) -> np.ndarray:
    """(N, A) out-of-pocket cost in dollars, excluding the toll."""
    from . import network

    routes = network.route_composition(cfg.rejoin_fraction)
    C = np.zeros((segs.n, len(ALTERNATIVES)))

    def drive_cost(alt: str) -> float:
        km = network.route_length(alt, links, routes)
        return cfg.auto_cost_per_km * km + cfg.parking_cost_peak

    C[:, IDX["drive_gardiner"]] = drive_cost("drive_gardiner")
    C[:, IDX["drive_lakeshore"]] = drive_cost("drive_lakeshore")
    C[:, IDX["drive_queensway"]] = drive_cost("drive_queensway")
    # A carpooler splits fuel and parking with the other occupants.
    C[:, IDX["carpool_gardiner"]] = (
        drive_cost("carpool_gardiner") / cfg.carpool_occupancy
    )
    C[:, IDX["shift_offpeak"]] = drive_cost("shift_offpeak")
    # Ontario One Fare removes the second fare on a GO-to-TTC transfer.
    C[:, IDX["go_rail"]] = cfg.go_fare + cfg.go_ttc_integration_fare
    C[:, IDX["ttc"]] = cfg.ttc_fare
    C[:, IDX["forgo_remote"]] = 0.0
    return C


def schedule_penalties(
    segs: Segments,
    cfg: Config,
    window_coverage: float = 1.0,
    carpool_share: float | None = None,
) -> np.ndarray:
    """(N, A) schedule-delay and inconvenience penalties, S[i,a].

    `window_coverage` is the share of the peak period actually charged.  A short
    charging window is easy to dodge, because a traveller only has to shift to
    the edge of the peak rather than out of it, so the retiming penalty scales
    with coverage.  That is the mechanism which makes a narrow window leak.
    """
    S = np.zeros((segs.n, len(ALTERNATIVES)))
    fixed = segs.is_fixed
    rigidity = np.where(fixed > 0, cfg.fixed_schedule_multiplier, 1.0)

    shift_minutes = cfg.offpeak_shift_minutes * max(window_coverage, 0.15)
    S[:, IDX["shift_offpeak"]] = cfg.schedule_penalty_per_min * shift_minutes * rigidity

    # Carpooling costs coordination time, and much more if you cannot flex.  It
    # also gets harder at the margin: the easy matches -- households already
    # travelling together, colleagues on one schedule -- form first, and every
    # additional carpool has to be assembled from a thinner pool.  Without this
    # friction the model answers almost any toll by inventing carpools, because
    # one vehicle carrying 2.4 people splits the charge 2.4 ways.
    friction = 0.0
    if carpool_share is not None:
        from .config import BASE_SHARES

        growth = max(carpool_share / BASE_SHARES["carpool_gardiner"] - 1.0, 0.0)
        friction = cfg.carpool_matching_friction * growth**1.5
    S[:, IDX["carpool_gardiner"]] = cfg.carpool_coordination_cost * rigidity + friction

    # Giving up the trip costs its full value, less whatever remote work recovers.
    forgo = cfg.forgo_base_penalty * (1.0 - cfg.forgo_wfh_discount * segs.wfh_capable)
    S[:, IDX["forgo_remote"]] = np.where(
        fixed > 0, cfg.forgo_base_penalty * 1.6, forgo
    )
    return S


def crowding_cost(load: float, capacity: float, cfg: Config) -> float:
    """Discomfort cost of a crowded transit vehicle, in dollars.

    Flat until the load factor passes `crowding_onset_load`, then rising
    steeply.  This is what stops the model from solving congestion by moving an
    impossible number of drivers onto trains with no room to take them, which
    is validation item 5 in the simulation plan.
    """
    if capacity <= 0:
        return 0.0
    lf = load / capacity
    if lf <= cfg.crowding_onset_load:
        return 0.0
    over = (lf - cfg.crowding_onset_load) / (1.0 - cfg.crowding_onset_load)
    return float(cfg.crowding_penalty_max * min(over, 3.0) ** 1.6)


def reliability_penalties(
    links: Dict[str, Link],
    peak_volumes: Dict[str, float],
    shoulder_volumes: Dict[str, float],
    loads: Dict[str, float],
    segs: Segments,
    cfg: Config,
) -> np.ndarray:
    """(N, A) reliability buffer for drivers, crowding discomfort for riders."""
    from . import network

    hours = cfg.peak_end_h - cfg.peak_start_h
    routes = network.route_composition(cfg.rejoin_fraction)
    R = np.zeros((segs.n, len(ALTERNATIVES)))

    def buffer_cost(alt: str, volumes: Dict[str, float]) -> float:
        delay = sum(
            frac * links[lid].congestion_delay(volumes.get(lid, 0.0), hours)
            for lid, frac in routes.get(alt, {}).items()
        )
        return cfg.reliability_weight * cfg.buffer_time_factor * delay

    for alt in AUTO_ALTERNATIVES:
        R[:, IDX[alt]] = buffer_cost(alt, peak_volumes)
    R[:, IDX["shift_offpeak"]] = buffer_cost(
        "shift_offpeak", _shoulder_totals(links, shoulder_volumes, cfg)
    )

    R[:, IDX["go_rail"]] = crowding_cost(
        loads.get("go_rail", 0.0), cfg.go_peak_capacity, cfg
    )
    R[:, IDX["ttc"]] = crowding_cost(loads.get("ttc", 0.0), cfg.ttc_peak_capacity, cfg)
    return R


def assemble(
    links: Dict[str, Link],
    peak_volumes: Dict[str, float],
    shoulder_volumes: Dict[str, float],
    transit_loads: Dict[str, float],
    tolls: np.ndarray,
    credits: np.ndarray,
    segs: Segments,
    cfg: Config,
    window_coverage: float = 1.0,
    carpool_share: float | None = None,
) -> dict:
    """Assemble GC and return it alongside its components."""
    T = travel_times(links, peak_volumes, shoulder_volumes, segs, cfg)
    C = monetary_costs(links, segs, cfg)
    S = schedule_penalties(segs, cfg, window_coverage, carpool_share)
    R = reliability_penalties(
        links, peak_volumes, shoulder_volumes, transit_loads, segs, cfg
    )

    time_cost = segs.vot_per_min[:, None] * T
    gc = time_cost + C + tolls + S + R - credits
    return {
        "gc": gc,
        "time_minutes": T,
        "time_cost": time_cost,
        "money": C,
        "toll": tolls,
        "schedule": S,
        "reliability": R,
        "credit": credits,
    }
