"""Robustness: how much of the answer is the data, and how much is the guesses?

Two complementary tests.

`tornado` moves one uncertain parameter at a time and records how far the
headline outcomes move.  It says which assumptions matter.

`monte_carlo` moves everything at once, drawing from ranges around each
parameter, and reports the distribution of outcomes plus how often the
recommended policy still beats its rivals.  It says whether the *recommendation*
survives, which is the question a reviewer actually cares about.  A policy that
wins on the point estimate but only ranks first in half the draws is not a
finding, it is a coin toss.
"""
from __future__ import annotations

import functools
import json
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import game, simulate
from .config import Config
from .demand import load_segments
from .toll_policy import TollPolicy

# Parameter, plus or minus fraction, and why it is uncertain.
UNCERTAIN: Dict[str, Tuple[float, str]] = {
    "vot_base_per_hour": (0.30, "Value of time is guidance, not measurement."),
    "logit_scale": (0.35, "Sets how strongly travellers respond to price."),
    "total_person_trips": (0.15, "Screenline demand is derived, not counted."),
    "parking_cost_peak": (0.30, "Downtown parking prices vary widely by lot."),
    "auto_cost_per_km": (0.35, "Perceived driving cost is not the full cost."),
    "go_fare": (0.20, "Fare policy can change independently of the charge."),
    "go_peak_capacity": (0.25, "Depends on GO Expansion delivery."),
    "schedule_penalty_per_min": (0.40, "Retiming cost is hard to observe."),
    "carpool_matching_friction": (0.50, "Carpool formation is poorly measured."),
    "forgo_base_penalty": (0.30, "Value of a suppressed trip is uncertain."),
    "buffer_time_factor": (0.35, "Reliability valuation is contested."),
    "shoulder_capacity_ratio": (0.20, "Shoulder traffic profile is derived."),
    "enforcement_rate": (0.50, "Evasion rates are unknown before operation."),
    "crowding_onset_load": (0.15, "Crowding tolerance is a behavioural guess."),
    # Added after the rejoin fraction was promoted out of routes.csv. It was
    # described as the driver of the diversion result while being the one
    # parameter this sweep could not reach, because it was hard-coded in a data
    # file rather than held in Config. The spread is wide because nothing local
    # has ever measured it -- see rejoin_validation.py.
    "rejoin_fraction": (0.35, "Gantry-hopping behaviour has never been observed here."),
}

OUTCOMES = (
    "delay_reduction_pct",
    "peak_vehicle_change_pct",
    "net_revenue_annual",
    "equity_score",
    "worst_diversion_pct",
)


def _evaluate(policy: TollPolicy, cfg: Config, reference: Optional[Config] = None) -> dict:
    """Score a policy under `cfg`, with the choice constants fixed at `reference`.

    Holding the constants fixed is what makes a sensitivity result meaningful --
    see `simulate.context`.  It is also what makes it fast, because the
    expensive calibration runs once rather than once per draw.
    """
    segs = load_segments(cfg)
    return game.summarise(game.evaluate(policy, cfg, segs, reference=reference))


@functools.lru_cache(maxsize=16)
def _cached_tornado(payload: str) -> dict:
    kwargs = json.loads(payload)
    return _tornado(
        policy=TollPolicy(**kwargs["policy"]),
        cfg=Config.from_dict(kwargs["config"]),
        parameters=kwargs["parameters"],
    )


def tornado(
    policy: Optional[TollPolicy] = None,
    cfg: Optional[Config] = None,
    parameters: Optional[List[str]] = None,
) -> dict:
    """Cached entry point for the one-at-a-time sweep."""
    policy = policy or TollPolicy(peak_toll=5.0, coverage="screenline",
                                  credit="targeted_package", label="central")
    cfg = cfg or Config()
    payload = json.dumps(
        {"policy": policy.to_dict(), "config": cfg.to_dict(), "parameters": parameters},
        sort_keys=True,
    )
    return _cached_tornado(payload)


def _tornado(
    policy: Optional[TollPolicy] = None,
    cfg: Optional[Config] = None,
    parameters: Optional[List[str]] = None,
) -> dict:
    """One-at-a-time sensitivity around the central case."""
    cfg = cfg or Config()
    policy = policy or TollPolicy(peak_toll=5.0, coverage="screenline",
                                  credit="targeted_package", label="central")
    parameters = parameters or list(UNCERTAIN.keys())

    central = _evaluate(policy, cfg, reference=cfg)
    base_cfg = cfg.to_dict()

    rows = []
    for name in parameters:
        spread, reason = UNCERTAIN.get(name, (0.25, ""))
        nominal = base_cfg.get(name)
        if not isinstance(nominal, (int, float)):
            continue

        variants = {}
        for direction, mult in (("low", 1.0 - spread), ("high", 1.0 + spread)):
            trial = Config.from_dict({**base_cfg, name: nominal * mult})
            variants[direction] = _evaluate(policy, trial, reference=cfg)

        rows.append(
            {
                "parameter": name,
                "reason": reason,
                "nominal": nominal,
                "low_value": round(nominal * (1.0 - spread), 4),
                "high_value": round(nominal * (1.0 + spread), 4),
                "spread_pct": round(100 * spread, 1),
                "effects": {
                    o: {
                        "low": variants["low"][o],
                        "central": central[o],
                        "high": variants["high"][o],
                        "swing": round(abs(variants["high"][o] - variants["low"][o]), 4),
                    }
                    for o in OUTCOMES
                },
                "swing_delay": round(
                    abs(variants["high"]["delay_reduction_pct"] - variants["low"]["delay_reduction_pct"]), 4
                ),
            }
        )

    rows.sort(key=lambda r: -r["swing_delay"])
    return {
        "policy": policy.to_dict(),
        "central": central,
        "parameters": rows,
        "note": (
            "The choice constants are held at their central fitted values while "
            "each parameter moves. Re-fitting them per draw would force the model "
            "to reproduce the observed base split whatever the parameter value, "
            "hiding the very sensitivity being measured."
        ),
    }


@functools.lru_cache(maxsize=8)
def _cached_monte_carlo(payload: str) -> dict:
    kwargs = json.loads(payload)
    return _monte_carlo(cfg=Config.from_dict(kwargs.pop("config")), **kwargs)


def monte_carlo(
    policies: Optional[List[TollPolicy]] = None,
    cfg: Optional[Config] = None,
    draws: int = 150,
    seed: int = 11,
) -> dict:
    """Cached entry point.

    A run costs several hundred equilibria.  The sampling is seeded and the
    model is deterministic, so an identical request cannot produce a different
    answer and there is no reason to pay for it twice.  Only the default policy
    set is cacheable; a custom set falls through to a direct run.
    """
    if policies is not None:
        return _monte_carlo(policies, cfg, draws, seed)
    cfg = cfg or Config()
    payload = json.dumps({"config": cfg.to_dict(), "draws": draws, "seed": seed},
                         sort_keys=True)
    return _cached_monte_carlo(payload)


def _monte_carlo(
    policies: Optional[List[TollPolicy]] = None,
    cfg: Optional[Config] = None,
    draws: int = 150,
    seed: int = 11,
) -> dict:
    """Joint uncertainty, using Latin hypercube sampling over the ranges.

    Latin hypercube rather than plain random draws because it covers each
    parameter's range evenly with far fewer samples, which matters when a
    single draw costs a full equilibrium solve for every policy.
    """
    cfg = cfg or Config()
    policies = policies or [
        TollPolicy(peak_toll=0.0, label="no toll"),
        TollPolicy(peak_toll=4.0, coverage="gardiner_only", credit="none", label="$4 freeway only"),
        TollPolicy(peak_toll=5.0, coverage="screenline", credit="targeted_package",
                   label="$5 screenline + targeted credits"),
        TollPolicy(peak_toll=7.0, coverage="screenline", credit="low_income_transit_poor",
                   label="$7 screenline + income credits"),
        TollPolicy(peak_toll=0.0, adaptive_signals=True, ramp_metering=True,
                   transit_priority=True, parking_surcharge=8.0, go_frequency_uplift=0.25,
                   label="no-toll package"),
    ]

    names = list(UNCERTAIN.keys())
    base_cfg = cfg.to_dict()
    rng = np.random.default_rng(seed)

    # Latin hypercube: stratify each parameter, then shuffle the strata apart.
    lhs = np.zeros((draws, len(names)))
    for j in range(len(names)):
        strata = (np.arange(draws) + rng.random(draws)) / draws
        lhs[:, j] = rng.permutation(strata)

    samples = []
    records: Dict[str, List[dict]] = {p.label: [] for p in policies}

    for d in range(draws):
        overrides = dict(base_cfg)
        drawn = {}
        for j, name in enumerate(names):
            spread, _ = UNCERTAIN[name]
            nominal = base_cfg[name]
            value = nominal * (1.0 - spread + 2.0 * spread * lhs[d, j])
            overrides[name] = value
            drawn[name] = round(float(value), 5)
        trial = Config.from_dict(overrides)
        samples.append(drawn)

        scored = []
        for p in policies:
            row = _evaluate(p, trial, reference=cfg)
            records[p.label].append(row)
            scored.append((p.label, row["welfare"], row["feasible"]))

        # Rank only the policies that satisfy the constraints in this draw.
        feasible = [s for s in scored if s[2]]
        winner = max(feasible or scored, key=lambda s: s[1])[0]
        for label in records:
            records[label][-1]["_won"] = label == winner

    summary = []
    for p in policies:
        rows = records[p.label]
        entry = {"label": p.label, "policy": p.to_dict(),
                 "win_probability": round(float(np.mean([r["_won"] for r in rows])), 4),
                 "feasible_probability": round(float(np.mean([r["feasible"] for r in rows])), 4)}
        for o in OUTCOMES:
            vals = np.array([r[o] for r in rows], dtype=float)
            entry[o] = {
                "mean": round(float(vals.mean()), 4),
                "p05": round(float(np.percentile(vals, 5)), 4),
                "p50": round(float(np.percentile(vals, 50)), 4),
                "p95": round(float(np.percentile(vals, 95)), 4),
            }
        summary.append(entry)

    summary.sort(key=lambda e: -e["win_probability"])
    return {
        "draws": draws,
        "method": "Latin hypercube over 14 uncertain parameters",
        "parameters": {
            k: {"spread_pct": round(100 * v[0], 1), "reason": v[1]} for k, v in UNCERTAIN.items()
        },
        "policies": summary,
        "most_robust": summary[0]["label"] if summary else None,
        "note": (
            "Win probability is the share of draws in which a policy has the "
            "highest welfare among those still satisfying the diversion, equity "
            "and congestion constraints in that draw."
        ),
    }


def convergence_study(
    cfg: Optional[Config] = None,
    epsilons: Optional[List[float]] = None,
    policy: Optional[TollPolicy] = None,
) -> dict:
    """Confirm results are stable across convergence tolerances.

    The plan asks for several epsilon values rather than one, so that a result
    cannot be an artefact of stopping the iteration early.
    """
    cfg = cfg or Config()
    policy = policy or TollPolicy(peak_toll=5.0, coverage="screenline", label="central")
    epsilons = epsilons or [1e-3, 1e-4, 1e-5, 1e-6, 1e-7]

    rows = []
    for eps in epsilons:
        trial = Config.from_dict({**cfg.to_dict(), "convergence_epsilon": eps})
        segs = load_segments(trial)
        result = simulate.run(policy, trial, segs, full=False, reference=cfg)
        rows.append(
            {
                "epsilon": eps,
                "iterations": result["convergence"]["iterations"],
                "gap": result["convergence"]["gap"],
                "converged": result["convergence"]["converged"],
                "peak_vehicles": result["metrics"]["peak_entering_vehicles"],
                "delay_reduction_pct": result["metrics"]["delay_reduction_pct"],
                "net_revenue_annual": result["finance"]["net_revenue_annual"],
            }
        )

    tightest = rows[-1]
    for r in rows:
        r["vehicles_vs_tightest_pct"] = round(
            100 * (r["peak_vehicles"] / tightest["peak_vehicles"] - 1.0), 5
        )
    return {"policy": policy.to_dict(), "results": rows,
            "stable": all(abs(r["vehicles_vs_tightest_pct"]) < 0.1 for r in rows)}
