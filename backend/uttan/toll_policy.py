"""The leader's instrument set.

A policy is not just a price.  It is a price, a window, a coverage decision
(does the charge apply to the diversion arterial as well as the freeway?), a
discount structure, a credit structure, and a governance branch.  This module
turns one of those bundles into the per-segment toll and credit matrices that
the generalized cost consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List

import numpy as np

from .config import ALTERNATIVES, OCCUPANCY, Config
from .demand import Segments

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}

# Which alternatives can physically be charged under each coverage option.
COVERAGE_LINKS: Dict[str, List[str]] = {
    # Charge the freeway only.  Simple, but Lake Shore is left as a free bypass.
    "gardiner_only": ["drive_gardiner", "carpool_gardiner"],
    # Charge every inbound crossing of the western screenline.  Closes the
    # bypass, but needs gantries on City arterials as well.
    "screenline": [
        "drive_gardiner",
        "carpool_gardiner",
        "drive_lakeshore",
        "drive_queensway",
    ],
    # Branch B of the governance analysis: the Province has not authorised a
    # toll on the expressway, so only City-controlled roads can be charged.
    "city_roads_only": ["drive_lakeshore", "drive_queensway"],
}

CREDIT_MECHANISMS = [
    "none",
    "low_income",
    "low_income_transit_poor",
    "shift_worker",
    "hov_discount",
    "monthly_cap",
    "mobility_credit",
    "means_tested",
    "targeted_package",
    "equity_first",
]

CHARGING_WINDOWS: Dict[str, tuple] = {
    "0630_0930": (6.5, 9.5),
    "0700_1000": (7.0, 10.0),
    "0630_1000": (6.5, 10.0),
    "0700_0900": (7.0, 9.0),
    "peak_plus_shoulder": (6.0, 10.5),
}


@dataclass
class TollPolicy:
    """One point in the leader's strategy space."""

    peak_toll: float = 0.0
    shoulder_toll: float = 0.0
    window: str = "0630_0930"
    coverage: str = "gardiner_only"
    credit: str = "none"
    hov_discount: float = 0.0           # extra share waived for HOV2+, a policy lever
    freight_multiplier: float = 1.0     # reserved for the commercial-vehicle class
    monthly_cap_trips: int = 20         # trips per month before the cap binds
    low_income_rebate: float = 0.75     # share of toll rebated to Q1/Q2
    transit_poor_rebate: float = 0.60   # share rebated where transit is not viable
    shift_worker_rebate: float = 0.70
    mobility_credit_value: float = 2.40 # transit credit funded from revenue
    # Means-tested pricing, after the San Francisco design: the lowest income
    # band is exempt outright and the next band pays half. Every congestion
    # charge operating anywhere today is a flat fee regardless of income, so
    # this is the instrument the equity literature actually asks for and no
    # scheme has yet delivered.
    means_test_exempt_quintiles: tuple = ("Q1",)
    means_test_half_quintiles: tuple = ("Q2",)
    # Share of drivers who cannot hold a toll account -- no bank account, no
    # credit card, or no capacity for a deposit. FHWA puts this at 10-20% of
    # the population. They do not escape the charge; they pay it through a more
    # expensive channel, which is itself a regressive design feature.
    unbanked_surcharge: float = 0.0
    label: str = "custom"

    # Non-price complements, tested against and alongside the charge.
    adaptive_signals: bool = False      # signal retiming on the diversion corridors
    ramp_metering: bool = False
    transit_priority: bool = False
    parking_surcharge: float = 0.0      # added to downtown peak parking
    go_frequency_uplift: float = 0.0    # 0.25 = a quarter more peak capacity

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def window_hours(self) -> tuple:
        return CHARGING_WINDOWS.get(self.window, (6.5, 9.5))

    def window_coverage(self, cfg: Config) -> float:
        """Share of the modelled peak period that the charge actually covers."""
        start, end = self.window_hours
        overlap = max(0.0, min(end, cfg.peak_end_h) - max(start, cfg.peak_start_h))
        span = cfg.peak_end_h - cfg.peak_start_h
        return 0.0 if span <= 0 else overlap / span

    def is_priced(self) -> bool:
        return self.peak_toll > 0 or self.shoulder_toll > 0


def toll_matrix(policy: TollPolicy, segs: Segments, cfg: Config) -> np.ndarray:
    """(N, A) toll actually charged, in dollars per trip.

    A traveller arriving inside the charging window pays the full rate; one
    arriving in the untolled part of the peak pays nothing.  Charging the
    expected value over the window is the aggregate-model equivalent, and it is
    what makes a narrow window raise less revenue rather than merely shuffling
    arrival times inside it.
    """
    n = segs.n
    tolls = np.zeros((n, len(ALTERNATIVES)))
    coverage = policy.window_coverage(cfg)
    charged = COVERAGE_LINKS.get(policy.coverage, [])

    # The charge is levied per VEHICLE, but generalized cost is per person, so
    # every charged movement splits it across its occupants.  Only dividing for
    # carpools would over-collect on the 1.15-occupancy arterial routes by 15%,
    # overstating both revenue and the price of bypassing -- which would then
    # understate diversion, the very risk the study exists to measure.
    for alt in charged:
        rate = policy.peak_toll * coverage
        if alt == "carpool_gardiner":
            rate *= 1.0 - policy.hov_discount
        tolls[:, IDX[alt]] = rate / max(OCCUPANCY[alt], 1e-9)

    # Retiming into the shoulder is charged at the shoulder rate, if any, and
    # only for the movements that the coverage option actually prices.
    if any(a in charged for a in ("drive_gardiner", "carpool_gardiner")):
        tolls[:, IDX["shift_offpeak"]] = policy.shoulder_toll / max(
            OCCUPANCY["shift_offpeak"], 1e-9
        )

    return tolls


def surcharge_matrix(policy: TollPolicy, segs: Segments, cfg: Config) -> np.ndarray:
    """(N, A) parking surcharge borne by the traveller, in dollars per trip.

    The surcharge already changes behaviour through `apply_complements`, which
    raises the parking cost inside the generalized cost.  It is pulled out
    separately here because it is also a *charge*: somebody pays it, and it
    raises public revenue.  Leaving it out of those two accounts would let a
    parking levy look as though it delivered congestion relief for free, and
    the model would then recommend it for the wrong reason.

    Unlike a gateway toll it cannot be dodged by rerouting, because it is levied
    at the destination -- which is exactly why it performs well here.
    """
    surcharge = np.zeros((segs.n, len(ALTERNATIVES)))
    if not policy.parking_surcharge:
        return surcharge
    effective = policy.parking_surcharge * cfg.parking_surcharge_applicable
    for alt in ("drive_gardiner", "drive_lakeshore", "drive_queensway",
                "carpool_gardiner", "shift_offpeak"):
        # Parking is paid per vehicle and shared among its occupants.
        surcharge[:, IDX[alt]] = effective / max(OCCUPANCY[alt], 1.0)
    return surcharge


def credit_matrix(policy: TollPolicy, segs: Segments, cfg: Config) -> np.ndarray:
    """(N, A) credit, rebate or discount, in dollars per trip.

    Credits are attached to the alternatives that are charged, so a rebate
    lowers the price of driving.  The mobility credit is the exception: it is
    attached to transit, so it pulls travellers toward the alternative rather
    than refunding the behaviour the charge is meant to discourage.
    """
    n = segs.n
    credits = np.zeros((n, len(ALTERNATIVES)))
    tolls = toll_matrix(policy, segs, cfg)
    charged_cols = [IDX[a] for a in COVERAGE_LINKS.get(policy.coverage, [])]
    if not charged_cols:
        return credits

    low_income = np.isin(segs.quintile, ["Q1", "Q2"]).astype(float)
    transit_poor = (segs.transit_access < 0.50).astype(float)
    shift_worker = segs.is_fixed

    def rebate(eligibility: np.ndarray, rate: float) -> None:
        for col in charged_cols:
            credits[:, col] += eligibility * rate * tolls[:, col]

    mechanism = policy.credit
    if mechanism == "low_income":
        rebate(low_income, policy.low_income_rebate)
    elif mechanism == "low_income_transit_poor":
        rebate(low_income, policy.low_income_rebate)
        rebate(np.clip(transit_poor - low_income, 0, 1), policy.transit_poor_rebate)
    elif mechanism == "shift_worker":
        rebate(shift_worker, policy.shift_worker_rebate)
    elif mechanism == "hov_discount":
        pass  # already applied inside toll_matrix
    elif mechanism == "monthly_cap":
        # With a cap of K trips a month against about 21 commuting days, the
        # expected share of trips charged falls to K/21.
        capped = min(1.0, policy.monthly_cap_trips / 21.0)
        for col in charged_cols:
            credits[:, col] += (1.0 - capped) * tolls[:, col]
    elif mechanism == "mobility_credit":
        credits[:, IDX["go_rail"]] += policy.mobility_credit_value
        credits[:, IDX["ttc"]] += policy.mobility_credit_value
    elif mechanism == "means_tested":
        rebate(np.isin(segs.quintile, list(policy.means_test_exempt_quintiles)).astype(float), 1.0)
        rebate(np.isin(segs.quintile, list(policy.means_test_half_quintiles)).astype(float), 0.5)
    elif mechanism == "equity_first":
        # The full Greenlining/San Francisco package: means-tested fees, a
        # transit credit funded from the same revenue, and a partial rebate
        # where no realistic transit alternative exists.
        rebate(np.isin(segs.quintile, list(policy.means_test_exempt_quintiles)).astype(float), 1.0)
        rebate(np.isin(segs.quintile, list(policy.means_test_half_quintiles)).astype(float), 0.5)
        rebate(np.clip(transit_poor - low_income, 0, 1), policy.transit_poor_rebate)
        credits[:, IDX["go_rail"]] += policy.mobility_credit_value
        credits[:, IDX["ttc"]] += policy.mobility_credit_value
    elif mechanism == "targeted_package":
        # The combination the proposal expects to prefer: a deep rebate where
        # income is low, a partial one where transit genuinely is not an
        # option, and a transit credit funded from the same revenue.
        rebate(low_income, policy.low_income_rebate)
        rebate(np.clip(transit_poor - low_income, 0, 1), policy.transit_poor_rebate)
        credits[:, IDX["go_rail"]] += policy.mobility_credit_value
        credits[:, IDX["ttc"]] += policy.mobility_credit_value

    # A credit can never exceed the charge it offsets.
    for col in charged_cols:
        credits[:, col] = np.minimum(credits[:, col], tolls[:, col])
    return credits


def apply_complements(policy: TollPolicy, links: dict, cfg: Config) -> Config:
    """Apply the non-price measures to the network and the configuration.

    These are the operational alternatives the proposal insists on testing
    against the charge: adaptive signals, ramp metering, transit priority,
    parking pricing and GO frequency.  Each is a modest, defensible adjustment
    rather than a claim of large effect.
    """
    cfg = Config.from_dict(cfg.to_dict())

    if policy.adaptive_signals:
        # Coordinated signals recover roughly a tenth of fixed control delay and
        # a little effective capacity on the arterials.
        for link in links.values():
            if link.kind == "arterial":
                link.signal_delay_min *= 0.88
                link.lane_capacity *= 1.06
    if policy.ramp_metering:
        # Metered entry protects mainline discharge, at the cost of ramp queues.
        for lid, link in links.items():
            if link.kind == "freeway":
                link.lane_capacity *= 1.04
                link.signal_delay_min += 0.6
    if policy.transit_priority:
        cfg.transit_ivt_multiplier *= 0.94
    if policy.parking_surcharge:
        cfg.parking_cost_peak += policy.parking_surcharge * cfg.parking_surcharge_applicable
    if policy.go_frequency_uplift:
        cfg.go_peak_capacity *= 1.0 + policy.go_frequency_uplift
        cfg.transit_wait_multiplier *= 1.0 - min(policy.go_frequency_uplift, 0.5) * 0.4
    return cfg
