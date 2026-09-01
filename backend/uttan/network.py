"""Link performance, route composition, and calibration.

The corridor is split at the Humber River, because that is where the study
segment ends and therefore where a gateway charge would be collected:

    gardiner_west    Hwy 427 - Humber River      <- the charged segment
    gardiner_east    Humber River - downtown     <- shared by everybody
    lakeshore_west   the City-road bypass of the charged segment
    lakeshore_east   Lake Shore into downtown
    queensway_west   the secondary bypass

That split is not cosmetic.  The charged segment is only 8.2 km of a roughly
19 km trip, so the cheapest way to avoid the charge is not to stop driving but
to leave the expressway before the gantry, run the arterial, and re-enter past
it.  A single-link corridor cannot represent that behaviour and would report an
implausibly small diversion effect -- the exact risk the study exists to test.
Because bypassers rejoin, diversion also partly defeats itself: the shared
downstream section gets busier, which is an emergent result rather than an
assumption.

Link performance is

    t(v) = t_free + d_signal + t_free * alpha * (v / c) ** beta

with beta fixed at a literature value and alpha fitted so that the base run
reproduces observed peak travel times.  Splitting fixed control delay
(d_signal) out of the BPR term keeps a slow-but-uncongested arterial from
requiring a huge alpha, which would then overstate how much worse that arterial
gets when traffic diverts onto it.

alpha is fitted on gardiner_west, gardiner_east and lakeshore_west.  The other
two links inherit the fitted arterial value and are held out, so their
predicted-versus-observed error is a genuine out-of-sample check.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from . import datasets


@dataclass
class Link:
    link_id: str
    name: str
    kind: str
    segment: str
    length_km: float
    free_flow_kmh: float
    lanes: int
    lane_capacity: float
    alpha: float
    beta: float
    signal_delay_min: float
    observed_peak_min: float
    calibrate_alpha: bool
    tollable_city: bool
    tollable_province: bool
    base_volume_veh: float = 0.0

    @property
    def free_flow_minutes(self) -> float:
        if self.free_flow_kmh <= 0:
            return 0.0
        return 60.0 * self.length_km / self.free_flow_kmh

    @property
    def uncongested_minutes(self) -> float:
        """Running time plus fixed control delay, with no queueing."""
        return self.free_flow_minutes + self.signal_delay_min

    def capacity(self, hours: float) -> float:
        return self.lanes * self.lane_capacity * hours

    def vc_ratio(self, volume: float, hours: float) -> float:
        cap = self.capacity(hours)
        return 0.0 if cap <= 0 else max(volume, 0.0) / cap

    def travel_time(self, volume: float, hours: float) -> float:
        cap = self.capacity(hours)
        if cap <= 0:
            return self.uncongested_minutes
        vc = max(volume, 0.0) / cap
        return self.uncongested_minutes + self.free_flow_minutes * self.alpha * vc**self.beta

    def congestion_delay(self, volume: float, hours: float) -> float:
        """The queueing component alone -- what pricing can actually remove."""
        return self.travel_time(volume, hours) - self.uncongested_minutes

    def marginal_time(self, volume: float, hours: float) -> float:
        """d t / d v, minutes of delay per additional vehicle.

        The term that separates a user equilibrium from a social optimum: an
        entering driver feels t(v) but imposes v * dt/dv on everyone already
        there.
        """
        cap = self.capacity(hours)
        if cap <= 0 or volume <= 0:
            return 0.0
        return (
            self.free_flow_minutes
            * self.alpha
            * self.beta
            * volume ** (self.beta - 1.0)
            / cap**self.beta
        )

    def speed_kmh(self, volume: float, hours: float) -> float:
        t = self.travel_time(volume, hours)
        return 0.0 if t <= 0 else 60.0 * self.length_km / t


@functools.lru_cache(maxsize=1)
def _route_template() -> tuple:
    """routes.csv parsed once, as ((alternative, link_id, fraction, role), ...).

    Split out from `route_composition` because the rejoin fraction is now swept
    by the Monte Carlo, which draws a different value on every sample.  With
    the DataFrame parse inside the cached function, every draw was a cache miss
    that re-ran `iterrows()` inside the equilibrium solver's hot loop -- the
    exact pandas-row-iteration cost that caching this was introduced to remove.
    It put the test suite from 30 seconds to just under four hours.

    Parsing once and rebuilding the small dict per fraction keeps the miss path
    at dict arithmetic over twelve rows.
    """
    df = datasets.routes()
    return tuple(
        (str(row["alternative"]), str(row["link_id"]), float(row["fraction"]),
         str(row.get("role", "fixed")))
        for _, row in df.iterrows()
    )


@functools.lru_cache(maxsize=32)
def route_composition(rejoin_fraction: float | None = None) -> Dict[str, Dict[str, float]]:
    """{alternative: {link_id: fraction of that route's vehicles}}.

    The `role` column in routes.csv marks the two rows of each bypass route
    that split at the Humber: `rejoin` re-enters the expressway past the
    gantry, `continue` stays on the arterial.  Those two are overwritten with
    `rejoin_fraction` and its complement, so the behavioural assumption lives
    in Config and the CSV describes only the network structure.  Passing None
    keeps whatever the CSV holds, which is what the data-provenance endpoint
    reports.

    Cached on the fraction: the equilibrium solver asks for this on every
    iteration, and re-parsing the table each time dominated the run cost (a
    scenario went 1160ms -> 9ms when this was first cached).  A sweep over
    rejoin_fraction touches a handful of distinct values, so a small cache
    keeps that win.  Callers treat the result as read-only.
    """
    out: Dict[str, Dict[str, float]] = {}
    for alt, link_id, csv_fraction, role in _route_template():
        if rejoin_fraction is None or role == "fixed":
            frac = csv_fraction
        elif role == "rejoin":
            frac = float(rejoin_fraction)
        elif role == "continue":
            frac = 1.0 - float(rejoin_fraction)
        else:
            raise ValueError(f"unknown route role {role!r} in routes.csv")
        out.setdefault(alt, {})[link_id] = frac
    return out


def base_link_volumes(rejoin_fraction: float | None = None) -> Dict[str, float]:
    """Base link volumes implied by the observed mode split.

    Derived rather than tabulated, so the link counts and the mode shares
    cannot drift apart.

    Note that this depends on the rejoin fraction, and alpha is then fitted to
    these volumes against fixed observed travel times -- so changing the
    fraction moves the base split between gardiner_east and lakeshore_east and
    alpha absorbs it.  That is the intended treatment: the fraction's influence
    should show up in the *response* to a charge, not in a baseline that is
    pinned to observation either way.
    """
    from .config import BASE_SHARES, OCCUPANCY, Config

    cfg = Config()
    routes = route_composition(rejoin_fraction)
    volumes: Dict[str, float] = {}
    for alt, links in routes.items():
        if alt == "shift_offpeak":
            continue  # travels in the shoulder, not the peak
        occ = OCCUPANCY[alt]
        if occ <= 0:
            continue
        veh = BASE_SHARES[alt] * cfg.total_person_trips / occ
        for link_id, frac in links.items():
            volumes[link_id] = volumes.get(link_id, 0.0) + veh * frac
    return volumes


def fit_alpha(link: Link, hours: float) -> float:
    """Solve t(v_base) = observed for alpha.  Closed form, no search needed."""
    vc = link.vc_ratio(link.base_volume_veh, hours)
    denom = link.free_flow_minutes * vc**link.beta
    if denom <= 0:
        return 0.0
    return max((link.observed_peak_min - link.uncongested_minutes) / denom, 0.0)


def load_links(
    hours: float = 3.0,
    recalibrate: bool = True,
    rejoin_fraction: float | None = None,
) -> Dict[str, Link]:
    df = datasets.network()
    base = base_link_volumes(rejoin_fraction)
    links: Dict[str, Link] = {}
    for link_id, row in df.iterrows():
        lid = str(link_id)
        links[lid] = Link(
            link_id=lid,
            name=str(row["name"]),
            kind=str(row["kind"]),
            segment=str(row["segment"]),
            length_km=float(row["length_km"]),
            free_flow_kmh=float(row["free_flow_kmh"]),
            lanes=int(row["lanes"]),
            lane_capacity=float(row["lane_capacity"]),
            alpha=float(row["alpha"]),
            beta=float(row["beta"]),
            signal_delay_min=float(row["signal_delay_min"]),
            observed_peak_min=float(row["observed_peak_min"]),
            calibrate_alpha=bool(row["calibrate_alpha"]),
            tollable_city=bool(row["tollable_city"]),
            tollable_province=bool(row["tollable_province"]),
            base_volume_veh=float(base.get(lid, 0.0)),
        )

    if recalibrate:
        for link in links.values():
            if link.calibrate_alpha:
                link.alpha = fit_alpha(link, hours)
        fitted = [l.alpha for l in links.values() if l.kind == "arterial" and l.calibrate_alpha]
        if fitted:
            transferred = float(np.mean(fitted))
            for link in links.values():
                if link.kind == "arterial" and not link.calibrate_alpha:
                    link.alpha = transferred
    return links


def route_time(
    alternative: str,
    links: Dict[str, Link],
    volumes: Dict[str, float],
    hours: float,
    routes: Dict[str, Dict[str, float]] | None = None,
) -> float:
    """Travel time along a composed route, in minutes."""
    routes = routes or route_composition()
    total = 0.0
    for link_id, frac in routes.get(alternative, {}).items():
        total += frac * links[link_id].travel_time(volumes.get(link_id, 0.0), hours)
    return total


def route_length(
    alternative: str,
    links: Dict[str, Link],
    routes: Dict[str, Dict[str, float]] | None = None,
) -> float:
    routes = routes or route_composition()
    return sum(frac * links[lid].length_km for lid, frac in routes.get(alternative, {}).items())


def assign(
    person_trips: Dict[str, float],
    hours: float = 3.0,
    rejoin_fraction: float | None = None,
) -> Dict[str, float]:
    """Turn person-trips by alternative into vehicles on each link."""
    from .config import OCCUPANCY

    routes = route_composition(rejoin_fraction)
    volumes: Dict[str, float] = {}
    for alt, trips in person_trips.items():
        occ = OCCUPANCY.get(alt, 0.0)
        if occ <= 0 or alt not in routes:
            continue
        veh = trips / occ
        for link_id, frac in routes[alt].items():
            volumes[link_id] = volumes.get(link_id, 0.0) + veh * frac
    return volumes


def validate(hours: float = 3.0, rejoin_fraction: float | None = None) -> List[dict]:
    """Modelled vs observed base travel times -- the Step 4 validation table."""
    links = load_links(hours, rejoin_fraction=rejoin_fraction)
    rows = []
    for link in links.values():
        modelled = link.travel_time(link.base_volume_veh, hours)
        observed = link.observed_peak_min
        rows.append(
            {
                "link_id": link.link_id,
                "name": link.name,
                "role": "calibrated" if link.calibrate_alpha else "held out",
                "alpha": round(link.alpha, 4),
                "beta": link.beta,
                "vc_ratio": round(link.vc_ratio(link.base_volume_veh, hours), 4),
                "base_volume_veh": round(link.base_volume_veh, 1),
                "capacity_veh": round(link.capacity(hours), 0),
                "modelled_min": round(modelled, 2),
                "observed_min": round(observed, 2),
                "error_pct": round(100.0 * (modelled - observed) / observed, 2),
                "modelled_speed_kmh": round(link.speed_kmh(link.base_volume_veh, hours), 1),
            }
        )
    return rows


def relative_gap(current: np.ndarray, previous: np.ndarray) -> float:
    """Convergence measure from the plan: sum|v_k - v_(k-1)| / sum v_(k-1)."""
    denom = float(np.sum(np.abs(previous)))
    if denom <= 0:
        return 0.0
    return float(np.sum(np.abs(current - previous)) / denom)
