"""The sequential game: not how much to charge, but when.

`game.py` has the leader move once.  Every operating scheme in the record moved
more than once, and the order is what decided whether they survived.

  Stockholm expanded transit *first* -- 197 buses on 16 new routes -- then ran
  the charge as a time-limited pilot, then held the referendum.  Support went
  from roughly a third before to roughly two thirds after.

  New York's plan is explicitly phased: transit investment, then a ride-hail
  surcharge, then the cordon.

  New York in 2008 tried to move once, and lost its federal Urban Partnership
  funding because it could not get the legislative authority in time.

A single-shot model cannot represent any of that.  It reports the welfare of a
charge as though enacting it were free, which quietly assumes away the
constraint that actually killed the 2008 attempt.

The structure here
------------------
The leader chooses a *path*: a sequence of stages, each with a transit uplift,
a ride-hail surcharge and possibly a road charge in force.  At the stage where
the charge is first proposed it must clear a political gate, and the
probability of clearing it depends on the state the earlier stages have built:
what has been delivered, whether people have experienced a pilot, and what the
charge does to their own net position.

If the gate fails, the charge never happens and the path continues on whatever
non-price measures it had.  So the payoff is

    E[W] = sum over years of  discount^t * [ p * W(with charge) +
                                             (1 - p) * W(without charge) ]

with `p` the enactment probability at the gate, and 1 before it.  That product
is the whole point.  A charge introduced immediately has the highest annual
welfare and the lowest probability of existing at all; one introduced after
transit is delivered earns less per year, for fewer years inside the horizon,
but is far likelier to be there.  The optimum is interior, and finding it is
the answer to "when".

What this does NOT model
------------------------
The charge level is optimised at the stage it is introduced, but the leader
cannot revise it later in response to what it learns -- there is no adaptive
policy here, only a committed sequence evaluated under uncertainty about
enactment.  Nor is there a rival player: `bargaining.py` handles the City and
Province, and the two are not solved jointly.  Both are simplifications that
make the timing question tractable, and both cut in the direction of
understating the value of sequencing rather than overstating it.
"""
from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np

from . import game
from .config import Config
from .demand import Segments, load_segments
from .toll_policy import TollPolicy


@dataclass
class Stage:
    """One period of a sequencing path, and the state in force during it."""

    year: int
    label: str
    transit_uplift: float = 0.0       # go_frequency_uplift committed by now
    transit_delivered: float = 0.0    # ...and actually carrying passengers
    ptc_surcharge: float = 0.0        # ride-hail per-trip surcharge in force
    charge: float = 0.0               # road charge in force, $/trip
    coverage: str = "screenline"
    credit: str = "low_income_transit_poor"
    pilot: bool = False               # a time-limited trial, not a permanent scheme
    gate: bool = False                # the enactment decision is taken this year

    def policy(self, label: str) -> TollPolicy:
        return TollPolicy(
            peak_toll=self.charge,
            coverage=self.coverage,
            credit=self.credit if self.charge > 0 else "none",
            go_frequency_uplift=self.transit_delivered,
            label=label,
        )

    def policy_without_charge(self, label: str) -> TollPolicy:
        """The counterfactual if the gate fails: the non-price measures survive."""
        return TollPolicy(
            peak_toll=0.0,
            coverage=self.coverage,
            credit="none",
            go_frequency_uplift=self.transit_delivered,
            label=label,
        )


@dataclass
class Path:
    key: str
    name: str
    precedent: str
    rationale: str
    stages: List[Stage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "name": self.name, "precedent": self.precedent,
            "rationale": self.rationale,
            "stages": [asdict(s) for s in self.stages],
        }


def _ramp(commit_year: Optional[int], year: int, size: float, lag: int) -> float:
    """How much of a transit commitment is carrying passengers in `year`.

    Linear delivery over the lag rather than a step, because service uplifts
    arrive in tranches -- and a step would make the timing answer sensitive to
    whether the charge landed one year either side of a cliff.
    """
    if commit_year is None or year < commit_year:
        return 0.0
    if lag <= 0:
        return size
    return float(size * min(1.0, (year - commit_year + 1) / lag))


def build_paths(cfg: Config, charge: float = 10.0) -> List[Path]:
    """The sequencing strategies worth comparing, each with a real precedent.

    The charge level is held the same across paths so that the comparison is
    about *order*, not price.  `timing_frontier` varies the start year with the
    price re-optimised, which is the other half of the question.
    """
    horizon = cfg.horizon_years
    lag = cfg.transit_delivery_lag_years
    uplift = 0.25   # a quarter more GO peak capacity, the modelled uplift

    def stages(charge_year: Optional[int], transit_year: Optional[int],
               ptc_year: Optional[int] = None, pilot_years: tuple = ()) -> List[Stage]:
        out = []
        for y in range(horizon):
            delivered = _ramp(transit_year, y, uplift, lag)
            charging = charge_year is not None and y >= charge_year
            out.append(
                Stage(
                    year=y,
                    label=f"year {y}",
                    transit_uplift=uplift if transit_year is not None and y >= transit_year else 0.0,
                    transit_delivered=delivered,
                    ptc_surcharge=2.75 if ptc_year is not None and y >= ptc_year else 0.0,
                    charge=charge if charging else 0.0,
                    pilot=y in pilot_years,
                    gate=charge_year is not None and y == charge_year,
                )
            )
        return out

    return [
        Path(
            key="charge_now",
            name="Charge immediately",
            precedent="New York 2008",
            rationale=(
                "Maximum annual benefit, taken as early as possible. It is also "
                "what New York attempted in 2008, and it failed to obtain the "
                "authority before the funding lapsed."
            ),
            stages=stages(charge_year=0, transit_year=None),
        ),
        Path(
            key="transit_first",
            name="Transit first, then charge",
            precedent="Stockholm 2005-06",
            rationale=(
                "Deliver the alternative, let it become visible, then charge. "
                "Costs two years of congestion benefit to buy a materially "
                "better chance the charge exists at all."
            ),
            stages=stages(charge_year=lag, transit_year=0),
        ),
        Path(
            key="pilot_then_vote",
            name="Transit, pilot, then referendum",
            precedent="Stockholm exactly",
            rationale=(
                "The only sequence in the record that converted a two-to-one "
                "majority against into a majority for. The pilot is what moves "
                "support, because it replaces a forecast with an experience."
            ),
            stages=stages(charge_year=lag, transit_year=0,
                          pilot_years=tuple(range(lag, lag + 2))),
        ),
        Path(
            key="nyc_phased",
            name="Transit, ride-hail surcharge, then cordon",
            precedent="New York 2019-2025",
            rationale=(
                "Phases the politics as well as the engineering: the surcharge "
                "establishes the charging principle and the collection "
                "machinery on a small and unsympathetic base first."
            ),
            stages=stages(charge_year=lag + 1, transit_year=0, ptc_year=1),
        ),
        Path(
            key="operations_only",
            name="Operations, never charge",
            precedent="Toronto Congestion Management Plan",
            rationale=(
                "The serious non-priced alternative. It needs no authorisation "
                "and no referendum, so its enactment probability is one -- "
                "which is exactly why it is hard to beat."
            ),
            stages=stages(charge_year=None, transit_year=0),
        ),
    ]


def enactment_probability(support_share: float, cfg: Config) -> float:
    """Probability a charge with this level of support is actually enacted.

    Logistic in the distance from the threshold rather than a step. A hard cut
    at 50% would make the whole timing result an artefact of which side of the
    line a path happened to land on, and would claim a precision about
    political processes that nobody has.
    """
    z = cfg.enactment_steepness * (support_share - cfg.enactment_threshold)
    return float(1.0 / (1.0 + np.exp(-z)))


def _evaluate_state(
    policy: TollPolicy,
    cfg: Config,
    segs: Segments,
    reference: Config,
    delivered_alternative: float,
    operating: bool,
) -> dict:
    """Score one (policy, state) combination, with support re-computed for it.

    The delivered-alternative state rides on the Config rather than being
    passed to `political.support` directly, because the acceptability
    calculation happens inside `simulate.run` and needs the state to reach it
    without every intermediate signature growing an argument.  `reference` is
    left untouched, so the choice constants stay fitted at the central
    configuration exactly as in every other sweep.
    """
    cfg = Config.from_dict(
        {**cfg.to_dict(), "delivered_alternative": float(delivered_alternative)}
    )
    segs = load_segments(cfg)
    result = game.evaluate(policy, cfg, segs, reference=reference)
    accept = result["acceptability"]
    phase = "after_operation" if operating else "before_operation"
    return {
        "welfare": result["objective"]["welfare"],
        "delay_reduction_pct": result["metrics"]["delay_reduction_pct"],
        "net_revenue_annual": result["finance"]["net_revenue_annual"],
        "equity_score": result["equity"]["equity_score"],
        "support_share": accept[phase]["support_share"],
        "feasible": result["feasible"]["passes"],
    }


@functools.lru_cache(maxsize=64)
def _cached_state(payload: str) -> dict:
    kwargs = json.loads(payload)
    cfg = Config.from_dict(kwargs["config"])
    return _evaluate_state(
        TollPolicy(**kwargs["policy"]), cfg, load_segments(cfg),
        Config.from_dict(kwargs["reference"]),
        kwargs["delivered"], kwargs["operating"],
    )


def _state(policy: TollPolicy, cfg: Config, reference: Config,
           delivered: float, operating: bool) -> dict:
    """Cached wrapper.  Paths share most of their states, so this matters.

    Five paths over a ten-year horizon is fifty stage evaluations, but they
    collapse to a handful of distinct (policy, delivered, operating) triples --
    a path is mostly the same state repeated. Without the cache the sweep costs
    about ten times what it needs to.
    """
    payload = json.dumps(
        {"policy": policy.to_dict(), "config": cfg.to_dict(),
         "reference": reference.to_dict(), "delivered": round(delivered, 6),
         "operating": operating},
        sort_keys=True,
    )
    return _cached_state(payload)


def evaluate_path(
    path: Path, cfg: Optional[Config] = None, reference: Optional[Config] = None
) -> dict:
    """Expected discounted welfare of one sequencing strategy."""
    cfg = cfg or Config()
    reference = reference or cfg

    gate_prob = 1.0
    gate_support = None
    gate_year = None
    rows = []
    total = 0.0

    for stage in path.stages:
        discount = 1.0 / (1.0 + cfg.discount_rate) ** stage.year
        # Normalise the delivered uplift to 0-1 for the support term: what the
        # voter registers is that an improvement arrived, not its magnitude in
        # capacity units.
        delivered = min(stage.transit_delivered / 0.25, 1.0) if stage.transit_delivered else 0.0

        with_charge = _state(
            stage.policy(f"{path.key} y{stage.year}"), cfg, reference,
            delivered, operating=stage.year > (gate_year if gate_year is not None else -1),
        )
        without_charge = _state(
            stage.policy_without_charge(f"{path.key} y{stage.year} (failed)"),
            cfg, reference, delivered, operating=False,
        )

        if stage.gate:
            gate_year = stage.year
            # The vote is taken on the state as it stands when the charge is
            # proposed.  A pilot is the exception: it is voted on after people
            # have lived with it, which is the whole Stockholm mechanism.
            gate_support = _state(
                stage.policy(f"{path.key} gate"), cfg, reference,
                delivered, operating=stage.pilot,
            )["support_share"]
            gate_prob = enactment_probability(gate_support, cfg)

        if stage.charge > 0:
            expected = gate_prob * with_charge["welfare"] + (1 - gate_prob) * without_charge["welfare"]
            expected_delay = (
                gate_prob * with_charge["delay_reduction_pct"]
                + (1 - gate_prob) * without_charge["delay_reduction_pct"]
            )
            expected_revenue = gate_prob * with_charge["net_revenue_annual"]
        else:
            expected = without_charge["welfare"]
            expected_delay = without_charge["delay_reduction_pct"]
            expected_revenue = 0.0

        total += discount * expected
        rows.append(
            {
                "year": stage.year,
                "transit_delivered": round(stage.transit_delivered, 4),
                "ptc_surcharge": stage.ptc_surcharge,
                "charge": stage.charge,
                "pilot": stage.pilot,
                "gate": stage.gate,
                "discount": round(discount, 4),
                "welfare_with_charge": with_charge["welfare"],
                "welfare_without_charge": without_charge["welfare"],
                "expected_welfare": round(expected, 5),
                "expected_delay_reduction_pct": round(expected_delay, 3),
                "expected_net_revenue_annual": round(expected_revenue, 0),
            }
        )

    return {
        "path": path.to_dict(),
        "years": rows,
        "charge_year": gate_year,
        "support_at_gate": None if gate_support is None else round(gate_support, 4),
        "enactment_probability": round(gate_prob, 4) if gate_year is not None else 1.0,
        # The same number unrounded. `joint_game` multiplies this by a second
        # gate and re-derives the path's welfare from the per-year with/without
        # pair; at 4 decimal places the rounding alone shifts the total by a few
        # times 1e-5, which is small against the welfare differences being
        # compared but is pure arithmetic, and it would show up as the joint
        # frontier disagreeing with the phased one for no reason.
        "enactment_probability_exact": float(gate_prob) if gate_year is not None else 1.0,
        "expected_discounted_welfare": round(total, 5),
        "undiscounted_final_year_delay_pct": rows[-1]["expected_delay_reduction_pct"],
    }


@functools.lru_cache(maxsize=8)
def _cached_compare(payload: str) -> dict:
    kwargs = json.loads(payload)
    cfg = Config.from_dict(kwargs["config"])
    return _compare_paths(cfg, kwargs["charge"])


def compare_paths(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    cfg = cfg or Config()
    payload = json.dumps({"config": cfg.to_dict(), "charge": charge}, sort_keys=True)
    return _cached_compare(payload)


def _compare_paths(cfg: Config, charge: float) -> dict:
    results = [evaluate_path(p, cfg, reference=cfg) for p in build_paths(cfg, charge)]
    results.sort(key=lambda r: -r["expected_discounted_welfare"])

    best = results[0]
    charge_now = next(
        (r for r in results if r["path"]["key"] == "charge_now"), None
    )
    gain = (
        round(best["expected_discounted_welfare"]
              - charge_now["expected_discounted_welfare"], 5)
        if charge_now else None
    )

    return {
        "charge": charge,
        "horizon_years": cfg.horizon_years,
        "discount_rate": cfg.discount_rate,
        "enactment": {
            "threshold": cfg.enactment_threshold,
            "steepness": cfg.enactment_steepness,
            "note": (
                "Probability rather than a hard threshold. A step at 50% would "
                "make the ranking an artefact of which side of the line a path "
                "landed on."
            ),
        },
        "paths": results,
        "best": best["path"]["key"],
        "sequencing_value": gain,
        "reading": (
            "The value of sequencing is the gap between the best-ordered path "
            "and charging immediately, holding the price identical. It is "
            "entirely a political-feasibility effect: the charge is the same, "
            "and the difference is how likely it is to exist."
        ),
    }


@functools.lru_cache(maxsize=8)
def _cached_frontier(payload: str) -> dict:
    kwargs = json.loads(payload)
    return _timing_frontier(Config.from_dict(kwargs["config"]), kwargs["charge"])


def timing_frontier(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    cfg = cfg or Config()
    payload = json.dumps({"config": cfg.to_dict(), "charge": charge}, sort_keys=True)
    return _cached_frontier(payload)


def _timing_frontier(cfg: Config, charge: float) -> dict:
    """Expected discounted welfare against the year the charge starts.

    This is the direct answer to "when". Transit is committed at year 0
    throughout, so the only thing varying is how long the leader waits before
    charging. Waiting buys enactment probability and costs benefit-years, and
    the two run in opposite directions, so the curve has an interior maximum
    unless one effect dominates completely.
    """
    lag = cfg.transit_delivery_lag_years
    uplift = 0.25
    rows = []

    for start in range(0, min(cfg.horizon_years, 7)):
        stages = [
            Stage(
                year=y,
                label=f"year {y}",
                transit_uplift=uplift,
                transit_delivered=_ramp(0, y, uplift, lag),
                charge=charge if y >= start else 0.0,
                gate=(y == start),
            )
            for y in range(cfg.horizon_years)
        ]
        path = Path(key=f"start_{start}", name=f"Charge from year {start}",
                    precedent="", rationale="", stages=stages)
        r = evaluate_path(path, cfg, reference=cfg)
        rows.append(
            {
                "charge_start_year": start,
                "transit_delivered_at_start": round(_ramp(0, start, uplift, lag), 4),
                "support_at_gate": r["support_at_gate"],
                "enactment_probability": r["enactment_probability"],
                "expected_discounted_welfare": r["expected_discounted_welfare"],
            }
        )

    best = max(rows, key=lambda r: r["expected_discounted_welfare"])
    interior = 0 < best["charge_start_year"] < rows[-1]["charge_start_year"]
    return {
        "charge": charge,
        "rows": rows,
        "optimal_start_year": best["charge_start_year"],
        "interior_optimum": interior,
        "cost_of_charging_immediately": round(
            best["expected_discounted_welfare"] - rows[0]["expected_discounted_welfare"], 5
        ),
        "cost_of_waiting_too_long": round(
            best["expected_discounted_welfare"] - rows[-1]["expected_discounted_welfare"], 5
        ),
        "reading": (
            "Waiting raises the probability the charge is ever enacted and "
            "lowers the number of discounted years it operates. An interior "
            "optimum means both forces are real; a corner would mean one of "
            "them is doing all the work and the model is not saying much."
        ),
    }


def report(cfg: Optional[Config] = None, charge: float = 10.0) -> dict:
    cfg = cfg or Config()
    return {
        "comparison": compare_paths(cfg, charge),
        "frontier": timing_frontier(cfg, charge),
        "assumptions": [
            "The charge level is held constant across paths so the comparison "
            "is about order, not price.",
            "Enactment is a one-shot gate. A leader who fails cannot re-propose "
            "later, which understates the value of trying early.",
            "The delivered-alternative effect on support is a calibrated stance "
            "(cfg.delivered_alternative_bonus), not an estimate. It is the "
            "single assumption the sequencing result rests on.",
            "Transit capital cost is not netted off. The paths differ in when "
            "the uplift arrives, not whether it is affordable.",
        ],
    }
