"""Model parameters.

Everything the simulation can be argued about lives here, so a reviewer can
find and change an assumption without reading the solver.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List

# The eight follower actions from the proposal (route, mode, time, occupancy,
# and trip-frequency responses).
ALTERNATIVES: List[str] = [
    "drive_gardiner",
    "drive_lakeshore",
    "drive_queensway",
    "carpool_gardiner",
    "shift_offpeak",
    "go_rail",
    "ttc",
    "forgo_remote",
]

# Nested-logit structure.  Alternatives inside a nest are closer substitutes
# than alternatives across nests -- rerouting is a smaller change than
# abandoning the car.
NESTS: Dict[str, List[str]] = {
    "auto": [
        "drive_gardiner",
        "drive_lakeshore",
        "drive_queensway",
        "carpool_gardiner",
        "shift_offpeak",
    ],
    "transit": ["go_rail", "ttc"],
    "none": ["forgo_remote"],
}

# Observed base (no-toll) split of AM-peak inbound person-trips crossing the
# western screenline.  Reconciled exactly against the vehicle counts in
# data/network.csv -- see docs/CALIBRATION.md.  The model's alternative-specific
# constants are calibrated to reproduce these; see choice_model.calibrate_constants.
BASE_SHARES: Dict[str, float] = {
    "drive_gardiner": 0.314569,
    "drive_lakeshore": 0.118794,
    "drive_queensway": 0.072754,
    "carpool_gardiner": 0.090572,
    "shift_offpeak": 0.056839,
    "go_rail": 0.192759,
    "ttc": 0.138391,
    "forgo_remote": 0.015322,
}

# Vehicle occupancy by alternative.  drive_gardiner is the solo/near-solo
# movement that the HOV instrument is meant to convert; carpool_gardiner is the
# HOV2+ movement.  The diversion arterials carry the corridor-average
# occupancy because no HOV instrument is applied there.  Together these
# reproduce the TTS work-trip average of 1.15 persons per vehicle.
OCCUPANCY: Dict[str, float] = {
    "drive_gardiner": 1.00,
    "drive_lakeshore": 1.15,
    "drive_queensway": 1.15,
    "carpool_gardiner": 2.40,
    "shift_offpeak": 1.15,
    "go_rail": 0.0,
    "ttc": 0.0,
    "forgo_remote": 0.0,
}

# Which alternatives put vehicles on which link, and in which period.
LINK_OF_ALTERNATIVE: Dict[str, str] = {
    "drive_gardiner": "gardiner",
    "drive_lakeshore": "lakeshore",
    "drive_queensway": "queensway",
    "carpool_gardiner": "gardiner",
    "shift_offpeak": "gardiner",
}
PEAK_AUTO_ALTERNATIVES = [
    "drive_gardiner", "drive_lakeshore", "drive_queensway", "carpool_gardiner",
]


@dataclass
class Config:
    """Simulation parameters for one model run."""

    # --- study period -------------------------------------------------------
    peak_start_h: float = 6.5          # 06:30
    peak_end_h: float = 9.5            # 09:30
    shoulder_capacity_ratio: float = 0.62   # shoulder volume as a share of peak
    working_days_per_year: int = 244

    # --- demand -------------------------------------------------------------
    total_person_trips: float = 40_465.0   # AM-peak inbound across the screenline
    auto_occupancy: float = 1.15           # solo/base commute occupancy (TTS)
    carpool_occupancy: float = 2.40        # occupancy of an HOV-eligible trip

    # --- network composition ------------------------------------------------
    # Share of bypassing drivers who re-enter the expressway past the gantry
    # rather than staying on the arterial all the way downtown.  This governs
    # how much of the diverted traffic lands back on the shared untolled
    # section, so it drives both the measured diversion onto local streets and
    # the downstream congestion the charge cannot touch.
    #
    # It lives here rather than in routes.csv because it is a behavioural
    # assumption, not a fact about the road network, and because a parameter
    # this consequential has to be reachable by the tornado and Monte Carlo
    # sweeps.  It was previously hard-coded in the CSV, which meant the one
    # number the handover called the driver of the diversion result was the
    # one number robustness analysis could not touch.  See
    # rejoin_validation.py for what the public record does and does not say
    # about its value.
    rejoin_fraction: float = 0.55

    # --- value of time ------------------------------------------------------
    vot_base_per_hour: float = 24.00       # Metrolinx peak auto commuter, $/h
    vot_income_elasticity: float = 0.60    # VOT scales with income^0.60
    median_household_income: float = 84_000.0
    vot_floor_per_hour: float = 9.50       # nobody is valued below this
    transit_ivt_multiplier: float = 1.00
    transit_wait_multiplier: float = 2.10  # waiting hurts ~2x in-vehicle time
    transit_access_multiplier: float = 1.80

    # --- monetary costs -----------------------------------------------------
    auto_cost_per_km: float = 0.22
    parking_cost_peak: float = 26.00
    # Share of corridor auto trips that actually pay for parking in the
    # surcharged area.  The rest are through-trips, drop-offs, deliveries,
    # employer-provided spaces or free on-street parking, and a destination
    # levy cannot reach them.  Applying a surcharge to every driver would
    # overstate the reach of the parking instrument against the road charge.
    parking_surcharge_applicable: float = 0.70
    go_fare: float = 6.05
    ttc_fare: float = 3.35
    go_ttc_integration_fare: float = 0.00  # Ontario One Fare: no double charge

    # --- schedule delay and reliability ------------------------------------
    schedule_penalty_per_min: float = 0.55     # $ per minute of retiming
    offpeak_shift_minutes: float = 55.0        # how far a shifter must move
    fixed_schedule_multiplier: float = 3.20    # shift workers cannot retime cheaply
    carpool_coordination_cost: float = 5.75    # $ to arrange a shared ride
    carpool_matching_friction: float = 11.00   # convex cost of thinner matches
    forgo_base_penalty: float = 34.00          # value of a suppressed trip
    forgo_wfh_discount: float = 0.62           # remote-capable workers lose less
    reliability_weight: float = 0.85           # $ per min of buffer time
    buffer_time_factor: float = 0.45           # buffer as a share of BPR delay
    crowding_onset_load: float = 0.85          # transit load factor where crowding bites
    crowding_penalty_max: float = 9.50         # $ at a badly overloaded train

    # --- transit supply -----------------------------------------------------
    go_peak_capacity: float = 12_500.0     # inbound AM-peak places at these stations
    ttc_peak_capacity: float = 9_000.0

    # --- choice model -------------------------------------------------------
    logit_scale: float = 0.115             # theta, per dollar of generalized cost
    nest_lambda: Dict[str, float] = field(
        default_factory=lambda: {"auto": 0.65, "transit": 0.75, "none": 1.0}
    )

    # --- equilibrium --------------------------------------------------------
    max_iterations: int = 250
    convergence_epsilon: float = 1e-5
    msa_warmup: int = 3

    # --- emissions ----------------------------------------------------------
    fuel_l_per_100km: float = 11.5
    co2_kg_per_litre: float = 2.31
    idle_penalty_l_per_hour: float = 1.6

    # --- finance ------------------------------------------------------------
    admin_cost_scenario: str = "medium"    # low | medium | high
    admin_cost_per_transaction: Dict[str, float] = field(
        default_factory=lambda: {"low": 0.18, "medium": 0.35, "high": 0.62}
    )
    fixed_annual_cost: Dict[str, float] = field(
        default_factory=lambda: {"low": 8.0e6, "medium": 14.0e6, "high": 22.0e6}
    )
    enforcement_rate: float = 0.045        # share of gross lost to evasion/enforcement

    # Share of net revenue whose benefit lands on corridor travellers rather
    # than the wider region. Station access, bus priority and traffic
    # management serve far more people than the 40,000 who cross this
    # screenline in the peak, so crediting the whole sum back to them would
    # turn every priced scenario into a Pareto improvement on paper.
    recycling_capture_share: float = 0.5

    # --- equity index weights (kept visible and sensitivity-tested) ---------
    equity_weight_burden: float = 0.45
    equity_weight_access: float = 0.35
    equity_weight_spatial: float = 0.20

    # --- leader objective weights ------------------------------------------
    w_delay: float = 0.30
    w_revenue: float = 0.20
    w_reliability: float = 0.10
    w_emissions: float = 0.08
    w_equity: float = 0.20
    w_diversion: float = 0.08
    w_implementation: float = 0.04

    # --- policy constraints -------------------------------------------------
    max_diversion_increase: float = 0.10   # protected-corridor volume cap
    min_equity_score: float = 0.55
    min_delay_reduction: float = 0.08

    # --- City/Province bargaining (see bargaining.py) ------------------------
    # Relative bargaining power in the asymmetric Nash solution.  Not
    # observable, so the reported result is the whole curve over this
    # (`power_sensitivity`) rather than one point on it.
    bargaining_power_city: float = 0.50
    # Political cost of one charged trip, per year, in dollars.  A stated
    # stance, not an estimate.  Its LEVEL is arbitrary; what the bargaining
    # result rests on is the ratio between the two players, and that comes from
    # the derived share of corridor demand originating outside Toronto.
    political_cost_per_charged_trip: float = 0.90
    # How much more heavily the Province weights a 905 traveller than a Toronto
    # one, because provincial majorities are decided in those seats.  Set to
    # 1.0 to remove the asymmetry entirely and see what it was doing.
    province_marginal_weight: float = 1.60
    # The Province counts the whole corridor's time saving, not just the share
    # accruing to its own residents, because goods movement and regional
    # economic cost do not stop at the city boundary.
    province_benefit_weight: float = 1.00
    # Years from the study date (August 2026) to the Gardiner transfer in
    # fall 2027.  The joint game needs this because the phased game's advice to
    # wait for transit delivery runs into a hard change in who holds the
    # authorisation -- the deadline is what makes the two games one problem.
    years_until_transfer: float = 1.15
    # Scale and steepness for the probability that the City and the Province
    # actually strike a deal, given the surplus available to the weaker party.
    # Logistic rather than a step for the same reason as the voter gate: a
    # cliff at exactly zero surplus would make the timing answer an artefact of
    # which side of it a year landed on.  The reference is the order of
    # magnitude of an annual corridor surplus, not a measured quantity.
    deal_surplus_reference: float = 5.0e6
    deal_steepness: float = 3.0

    # The freeway-only charge the Province could levy alone once it owns the
    # road, used as its post-transfer fallback.  Set at the level this study
    # finds breaches the local-street diversion cap, because that is precisely
    # the option the City would have no standing to object to.
    province_unilateral_charge: float = 4.00
    # Period over which the Province's interim operating support is spread:
    # the New Deal announcement (November 2023) to the transfer (fall 2027).
    # A fixed sum for a fixed job, so it is annualised over the whole job and
    # not over the months still to run.
    interim_support_years: float = 4.0

    # --- sequencing (the phased game, see phasing.py) ------------------------
    horizon_years: int = 10
    discount_rate: float = 0.03            # real social discount rate
    # A charge is enacted only if it clears a political gate at the moment it
    # is proposed.  Modelled as a probability rather than a hard threshold,
    # because 49% support is not certain failure and 51% is not certain
    # success -- and a hard cliff would make the timing result an artefact of
    # exactly where the cliff sat.
    enactment_threshold: float = 0.50
    enactment_steepness: float = 14.0
    # Years between committing to a transit uplift and it carrying passengers.
    # Stockholm ran 197 extra buses on 16 new routes before its pilot; rolling
    # stock and service changes are quick, and this is deliberately optimistic
    # -- a longer lag only strengthens the case for starting transit early.
    transit_delivery_lag_years: int = 2
    # How much a *delivered and visible* alternative adds to the support
    # utility, over and above the improvement it makes to people's own net
    # position (which the incidence model already captures).  This is the
    # sequencing effect the case studies describe and it is a calibrated
    # stance, not an estimate -- exposed here so it can be swept.
    delivered_alternative_bonus: float = 0.45
    # ...and how much of that alternative has actually been built and is
    # carrying passengers at the moment the charge is proposed, scored 0-1.
    # This is scenario STATE rather than a parameter -- `phasing.py` sets it
    # per stage, the same way `apply_complements` rewrites parking cost per
    # scenario.  Zero everywhere else, so a single-shot run is unaffected.
    delivered_alternative: float = 0.0

    # --- Trust in the revenue promise -------------------------------------
    # Share of the promised revenue recycling that voters actually believe
    # will reach them.  Edinburgh rejected its charge 74.4-25.6 and the
    # research found the driver was TRUST rather than economics: only one in
    # four believed the revenue would reach transport.  Manchester attached a
    # GBP 3bn package and still lost.  Without this term, recycling enters
    # only through each traveller's net position, so a large enough package
    # always buys support -- which is precisely what the record denies.
    #
    # Defaults to 1.0 (the promise fully believed), which reproduces every
    # result computed before this term existed.  It is unobservable for
    # Toronto, so it is INVERTED rather than tuned: `political.trust_sensitivity`
    # reports the level the recommendation requires and sets it against
    # Edinburgh's measured 0.25.  The same discipline `bargaining.py` applies
    # to the political-cost rate.
    revenue_trust: float = 1.0
    # Trust gained once the scheme runs and the money is observably spent --
    # the promise stops being a promise.  Inert at the 1.0 default because
    # trust is capped at 1.
    revenue_trust_operating_gain: float = 0.20
    # ...and gained from an alternative that has already been built, which is
    # the mechanism behind Stockholm's pilot: a delivered thing is evidence
    # about the next promised thing.  Scales with `delivered_alternative`.
    revenue_trust_delivery_gain: float = 0.25

    # How much public support reduces the political cost of AUTHORISING a
    # charge, 0 = the two enactment gates are independent.
    #
    # `joint_game` multiplies P(voters) by P(deal) and has so far treated them
    # as independent, which is its most questionable simplification: a scheme
    # the public wants is cheaper for a government to authorise, so the two
    # gates move together. The channel is the political cost rate itself --
    # backing an unpopular policy costs a politician more -- rather than a
    # correlation bolted onto the probabilities, because a mechanism can be
    # argued with and a correlation coefficient cannot.
    #
    #     rate(support) = base * (1 + gate_dependence * (1 - 2 * support))
    #
    # At support = 0.5, the referendum threshold, the rate is the stated base
    # whatever the dependence, so the calibration is anchored where it was.
    # Defaults to 0 so every result computed under independence still holds.
    gate_dependence: float = 0.0

    # Belief that the charge will actually relieve congestion, 0-1. Distinct
    # from `revenue_trust`, which is belief that the MONEY arrives. Manchester
    # is the case that separates them: a GBP 3bn package was attached and the
    # referendum was still lost, and the package was never the doubted part.
    #
    # It applies only BEFORE operation. Once the scheme runs the traffic effect
    # is visible, and that is exactly what the `experience` coefficient in
    # SUPPORT already represents -- discounting after operation as well would
    # count the same phenomenon twice and the Stockholm anchors the
    # coefficients were set against would no longer hold.
    #
    # Defaults to 1.0, so every result computed before this term existed is
    # unchanged, and the level is inverted rather than tuned like the others.
    charge_efficacy_belief: float = 1.0

    # --- Does the delay reduction last? -----------------------------------
    # London's traffic reduction was permanent; its DELAY reduction was gone
    # within about five years. A static equilibrium cannot produce that, so a
    # first-year effect was reading as a steady state. See `reversion.py`.
    #
    # Background growth in corridor demand. A planning assumption, not a
    # forecast -- ESTIMATED, and swept, because the trajectory is sensitive to
    # it and nothing in this study measures it.
    background_demand_growth: float = 0.015
    # Share of the charged links' capacity handed to something other than
    # general traffic once the charge has freed it -- bus lanes, footway,
    # public realm. This is the London mechanism and it is a POLICY CHOICE, not
    # a physical law, which is why it defaults to zero: the model should not
    # assume Toronto gives the space away. `reversion.reallocation_matching_london`
    # inverts it against the one case in the record instead.
    space_reallocation_share: float = 0.0
    # Years over which that reallocation is reached, linearly.
    reallocation_ramp_years: float = 3.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Config":
        """Build a Config from a partial override dict, ignoring unknown keys."""
        cfg = cls()
        if not data:
            return cfg
        valid = set(asdict(cfg).keys())
        for key, value in data.items():
            if key in valid and value is not None:
                setattr(cfg, key, value)
        return cfg
