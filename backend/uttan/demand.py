"""Traveller segments and base demand.

A segment is (sub-area, income quintile, schedule flexibility).  Transit
accessibility is attached to the sub-area rather than drawn independently,
because whether Lakeshore West GO is a realistic option is a fact about where
somebody lives, not a separate personal attribute.

Everything downstream works on numpy arrays indexed [segment, alternative].
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import datasets
from .config import ALTERNATIVES, Config


@dataclass
class Segments:
    ids: np.ndarray            # (N,) segment labels
    subarea: np.ndarray        # (N,)
    quintile: np.ndarray       # (N,)
    income: np.ndarray         # (N,) household income, $/yr
    schedule: np.ndarray       # (N,) 'fixed' | 'flexible'
    transit_access: np.ndarray # (N,) 0-1 accessibility score
    wfh_capable: np.ndarray    # (N,) 0-1
    share: np.ndarray          # (N,) share of total person-trips, sums to 1
    vot_per_min: np.ndarray    # (N,) $/minute of travel time

    @property
    def n(self) -> int:
        return len(self.ids)

    def trips(self, cfg: Config) -> np.ndarray:
        """Person-trips per segment in the AM peak."""
        return self.share * cfg.total_person_trips

    @property
    def is_fixed(self) -> np.ndarray:
        return (self.schedule == "fixed").astype(float)


def value_of_time(income: np.ndarray, cfg: Config) -> np.ndarray:
    """Value of travel time, $/minute.

    Scales the Metrolinx peak auto figure with household income, using the
    usual constant-elasticity form.  A floor is applied so that the model never
    concludes that delay to a low-income traveller is nearly free -- an
    artefact that would quietly bias every equity result in the study.
    """
    scaled = cfg.vot_base_per_hour * (income / cfg.median_household_income) ** cfg.vot_income_elasticity
    hourly = np.maximum(scaled, cfg.vot_floor_per_hour)
    return hourly / 60.0


def load_segments(cfg: Config | None = None) -> Segments:
    cfg = cfg or Config()
    df = datasets.segments()
    income = df["household_income"].to_numpy(dtype=float)
    return Segments(
        ids=df["segment_id"].to_numpy(),
        subarea=df["subarea"].to_numpy(),
        quintile=df["quintile"].to_numpy(),
        income=income,
        schedule=df["schedule"].to_numpy(),
        transit_access=df["transit_access"].to_numpy(dtype=float),
        wfh_capable=df["wfh_capable"].to_numpy(dtype=float),
        share=df["share"].to_numpy(dtype=float),
        vot_per_min=value_of_time(income, cfg),
    )


def base_share_matrix(cfg: Config) -> np.ndarray:
    """(N, A) starting point for the equilibrium: every segment at base shares."""
    from .config import BASE_SHARES

    segs = load_segments(cfg)
    row = np.array([BASE_SHARES[a] for a in ALTERNATIVES], dtype=float)
    return np.tile(row, (segs.n, 1))


def vehicles_by_link(shares: np.ndarray, segs: Segments, cfg: Config) -> dict:
    """Convert (N, A) person-trip shares into vehicles on each link.

    `shift_offpeak` travels the same physical route but in the shoulder period,
    so it is assigned to a separate shoulder volume rather than added to the
    peak.
    """
    from . import network

    trips = segs.trips(cfg)[:, None] * shares          # (N, A) person-trips
    per_alt = trips.sum(axis=0)                        # (A,)
    by_alt = {a: float(per_alt[i]) for i, a in enumerate(ALTERNATIVES)}

    peak_trips = {a: v for a, v in by_alt.items() if a != "shift_offpeak"}
    peak = network.assign(peak_trips, rejoin_fraction=cfg.rejoin_fraction)
    shoulder = network.assign(
        {"shift_offpeak": by_alt["shift_offpeak"]}, rejoin_fraction=cfg.rejoin_fraction
    )

    return {
        "peak": peak,
        "shoulder": shoulder,
        "person_trips_by_alternative": by_alt,
    }
