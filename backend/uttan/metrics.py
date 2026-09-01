"""Congestion, mobility, diversion and emissions indicators.

Every measure is reported against the calibrated no-toll baseline, because an
absolute vehicle-hour count means little on its own -- the question is always
what the policy changed.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from . import network
from .config import ALTERNATIVES, OCCUPANCY, Config
from .congestion import Equilibrium
from .network import Link

# Corridors the diversion constraint protects.  These carry residential
# frontage and neighbourhood access, so a volume increase here is a real
# local impact rather than an accounting transfer.
PROTECTED_LINKS = ("lakeshore_west", "lakeshore_east", "queensway_west")


def vehicle_hours_of_delay(
    volumes: Dict[str, float], links: Dict[str, Link], hours: float
) -> float:
    """Total vehicle-hours of congestion delay across the corridor."""
    return sum(
        volumes.get(lid, 0.0) * link.congestion_delay(volumes.get(lid, 0.0), hours) / 60.0
        for lid, link in links.items()
    )


def vehicle_km(volumes: Dict[str, float], links: Dict[str, Link]) -> float:
    return sum(volumes.get(lid, 0.0) * link.length_km for lid, link in links.items())


def reliability_index(
    volumes: Dict[str, float], links: Dict[str, Link], hours: float
) -> float:
    """Planning-time proxy: the buffer a traveller must add to arrive on time.

    Delay variance rises faster than mean delay as a link approaches capacity,
    so the buffer is scaled by the volume/capacity ratio.  Reported as minutes
    on the Gardiner route; lower is better.
    """
    total = 0.0
    for alt_link in ("gardiner_west", "gardiner_east"):
        link = links[alt_link]
        v = volumes.get(alt_link, 0.0)
        delay = link.congestion_delay(v, hours)
        total += delay * (0.7 + 0.9 * min(link.vc_ratio(v, hours), 1.2))
    return total


def emissions(
    volumes: Dict[str, float],
    links: Dict[str, Link],
    hours: float,
    cfg: Config,
) -> Dict[str, float]:
    """Transparent CO2e proxy: running emissions plus congestion idling.

    This is deliberately a proxy, not a calibrated emissions model.  It moves
    with vehicle-kilometres and with time spent in stop-start conditions, which
    is enough to rank policies, and is not precise enough to quote as an
    absolute inventory.
    """
    vkm = vehicle_km(volumes, links)
    vhd = vehicle_hours_of_delay(volumes, links, hours)
    running_l = vkm * cfg.fuel_l_per_100km / 100.0
    idling_l = vhd * cfg.idle_penalty_l_per_hour
    litres = running_l + idling_l
    return {
        "vehicle_km": vkm,
        "litres_peak": litres,
        "co2e_kg_peak": litres * cfg.co2_kg_per_litre,
        "co2e_tonnes_year": litres * cfg.co2_kg_per_litre * cfg.working_days_per_year / 1000.0,
    }


def compute(
    eq: Equilibrium,
    base: Equilibrium,
    links: Dict[str, Link],
    cfg: Config,
    base_links: Optional[Dict[str, Link]] = None,
) -> dict:
    """Full indicator set for one scenario against the baseline.

    `links` is the network the SCENARIO ran on; `base_links` is the network the
    BASELINE ran on, and they are not the same object whenever a scenario
    changes capacity -- an operational package, or road space reallocated after
    a charge frees it.

    Passing one set for both is wrong in a way that does not look wrong. Every
    "against baseline" figure below is a ratio, and evaluating the baseline
    volumes on an improved network shrinks the denominator, so a scenario is
    charged for the improvement it made and credited with none of it. On the
    no-charge operational package that understated the delay reduction by
    **11.2 percentage points** -- enough to reverse this study's finding that
    pricing beats good operations. Pure-price scenarios were unaffected,
    because for them the two networks are identical, which is exactly why the
    error survived: it was invisible on most of the library.

    Defaults to `links` for backwards compatibility with callers that do not
    change capacity, where the two are the same network anyway.
    """
    hours = cfg.peak_end_h - cfg.peak_start_h
    T = cfg.total_person_trips
    base_links = links if base_links is None else base_links

    vhd = vehicle_hours_of_delay(eq.peak_volumes, links, hours)
    vhd_base = vehicle_hours_of_delay(base.peak_volumes, base_links, hours)
    vkm = vehicle_km(eq.peak_volumes, links)
    vkm_base = vehicle_km(base.peak_volumes, base_links)

    em = emissions(eq.peak_volumes, links, hours, cfg)
    em_base = emissions(base.peak_volumes, base_links, hours, cfg)

    rel = reliability_index(eq.peak_volumes, links, hours)
    rel_base = reliability_index(base.peak_volumes, base_links, hours)

    gw, gw_base = eq.peak_volumes["gardiner_west"], base.peak_volumes["gardiner_west"]

    diversion = {}
    for lid in PROTECTED_LINKS:
        v, v0 = eq.peak_volumes.get(lid, 0.0), base.peak_volumes.get(lid, 0.0)
        diversion[lid] = {
            "name": links[lid].name,
            "base_veh": round(v0, 1),
            "scenario_veh": round(v, 1),
            "change_veh": round(v - v0, 1),
            "change_pct": round(100.0 * (v / v0 - 1.0), 2) if v0 else 0.0,
            "vc_ratio": round(links[lid].vc_ratio(v, hours), 3),
        }
    worst = max(diversion.values(), key=lambda d: d["change_pct"]) if diversion else None

    shares = {a: float(eq.market_shares[i]) for i, a in enumerate(ALTERNATIVES)}
    base_shares = {a: float(base.market_shares[i]) for i, a in enumerate(ALTERNATIVES)}
    auto_person = sum(
        shares[a] * T for a in ALTERNATIVES if OCCUPANCY[a] > 0 and a != "shift_offpeak"
    )
    auto_veh = sum(
        shares[a] * T / OCCUPANCY[a]
        for a in ALTERNATIVES
        if OCCUPANCY[a] > 0 and a != "shift_offpeak"
    )

    transit_share = shares["go_rail"] + shares["ttc"]
    transit_share_base = base_shares["go_rail"] + base_shares["ttc"]

    return {
        "peak_entering_vehicles": round(gw, 1),
        "peak_entering_vehicles_base": round(gw_base, 1),
        "peak_vehicle_change": round(gw - gw_base, 1),
        "peak_vehicle_change_pct": round(100.0 * (gw / gw_base - 1.0), 2),
        "gardiner_travel_time_min": round(eq.route_times["drive_gardiner"], 2),
        "gardiner_travel_time_base_min": round(base.route_times["drive_gardiner"], 2),
        "travel_time_saved_min": round(
            base.route_times["drive_gardiner"] - eq.route_times["drive_gardiner"], 2
        ),
        "gardiner_speed_kmh": round(
            60.0
            * sum(links[l].length_km for l in ("gardiner_west", "gardiner_east"))
            / max(eq.route_times["drive_gardiner"] - 8.0, 1e-6),
            1,
        ),
        "vehicle_hours_delay": round(vhd, 1),
        "vehicle_hours_delay_base": round(vhd_base, 1),
        "delay_reduction_pct": round(100.0 * (1.0 - vhd / vhd_base), 2) if vhd_base else 0.0,
        "vehicle_km": round(vkm, 1),
        "vehicle_km_change_pct": round(100.0 * (vkm / vkm_base - 1.0), 2) if vkm_base else 0.0,
        "reliability_buffer_min": round(rel, 2),
        "reliability_improvement_pct": round(100.0 * (1.0 - rel / rel_base), 2) if rel_base else 0.0,
        "mode_shares": {k: round(v, 5) for k, v in shares.items()},
        "mode_share_change": {k: round(shares[k] - base_shares[k], 5) for k in shares},
        "person_trips": {k: round(v * T, 1) for k, v in shares.items()},
        "transit_share": round(transit_share, 5),
        "transit_share_change_pp": round(100.0 * (transit_share - transit_share_base), 2),
        "transit_riders": round(transit_share * T, 1),
        "carpool_share": round(shares["carpool_gardiner"], 5),
        "auto_occupancy": round(auto_person / auto_veh, 4) if auto_veh else 0.0,
        "trips_suppressed": round((shares["forgo_remote"] - base_shares["forgo_remote"]) * T, 1),
        "retimed_trips": round((shares["shift_offpeak"] - base_shares["shift_offpeak"]) * T, 1),
        "diversion": diversion,
        "worst_diversion_pct": round(worst["change_pct"], 2) if worst else 0.0,
        "worst_diversion_link": worst["name"] if worst else None,
        "go_load_factor": round(eq.transit_loads["go_rail"] / cfg.go_peak_capacity, 3),
        "ttc_load_factor": round(eq.transit_loads["ttc"] / cfg.ttc_peak_capacity, 3),
        "transit_capacity_breached": bool(
            eq.transit_loads["go_rail"] > cfg.go_peak_capacity
            or eq.transit_loads["ttc"] > cfg.ttc_peak_capacity
        ),
        "emissions": {k: round(v, 2) for k, v in em.items()},
        "co2e_change_pct": round(
            100.0 * (em["co2e_kg_peak"] / em_base["co2e_kg_peak"] - 1.0), 2
        ) if em_base["co2e_kg_peak"] else 0.0,
        "link_volumes": {k: round(v, 1) for k, v in eq.peak_volumes.items()},
        "link_times": {k: round(v, 2) for k, v in eq.link_times.items()},
        "link_vc": {
            lid: round(link.vc_ratio(eq.peak_volumes.get(lid, 0.0), hours), 3)
            for lid, link in links.items()
        },
    }
