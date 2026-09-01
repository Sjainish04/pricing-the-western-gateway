"""Nested logit over the eight follower actions, plus its calibration.

The proposal's MVP specifies a multinomial logit.  We use a nested logit
instead, because plain MNL imposes independence of irrelevant alternatives:
under MNL, a driver priced off the Gardiner is as likely to appear on a GO
train as on Lake Shore Boulevard.  That assumption would systematically
understate diversion, which is the single risk the study most needs to measure.
Setting every nest scale to 1.0 collapses this back to MNL, and `nest_lambda`
is exposed for sensitivity testing.

Nests
    auto      drive_gardiner, drive_lakeshore, drive_queensway,
              carpool_gardiner, shift_offpeak
    transit   go_rail, ttc
    none      forgo_remote

Formulation, with V[a] = -theta * GC[a] and nest scale lambda_n in (0, 1]:

    I_n     = ln  sum_{a in n} exp(V[a] / lambda_n)      (logsum of the nest)
    P(n)    = exp(lambda_n * I_n) / sum_m exp(lambda_m * I_m)
    P(a|n)  = exp(V[a] / lambda_n) / sum_{b in n} exp(V[b] / lambda_n)
    P(a)    = P(a|n) * P(n)
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .config import ALTERNATIVES, NESTS, Config

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}
NEST_MEMBERS: Dict[str, List[int]] = {
    nest: [IDX[a] for a in alts] for nest, alts in NESTS.items()
}


def probabilities(
    gc: np.ndarray, constants: np.ndarray, cfg: Config
) -> np.ndarray:
    """(N, A) choice probabilities from an (N, A) generalized-cost matrix.

    `constants` are the alternative-specific constants, in dollars, absorbing
    everything the observed attributes do not explain.
    """
    v = -cfg.logit_scale * (gc - constants[None, :])
    n_rows = v.shape[0]
    nest_names = list(NESTS.keys())

    conditional = np.zeros_like(v)
    nest_logsum = np.zeros((n_rows, len(nest_names)))

    for k, nest in enumerate(nest_names):
        cols = NEST_MEMBERS[nest]
        lam = max(float(cfg.nest_lambda.get(nest, 1.0)), 1e-3)
        scaled = v[:, cols] / lam
        # Shift before exponentiating so a large |V| cannot overflow.
        top = scaled.max(axis=1, keepdims=True)
        ex = np.exp(scaled - top)
        denom = ex.sum(axis=1, keepdims=True)
        conditional[:, cols] = ex / denom
        nest_logsum[:, k] = (top[:, 0] + np.log(denom[:, 0])) * lam

    top = nest_logsum.max(axis=1, keepdims=True)
    ex = np.exp(nest_logsum - top)
    nest_prob = ex / ex.sum(axis=1, keepdims=True)

    out = np.zeros_like(v)
    for k, nest in enumerate(nest_names):
        cols = NEST_MEMBERS[nest]
        out[:, cols] = conditional[:, cols] * nest_prob[:, [k]]
    return out


def logsum(gc: np.ndarray, constants: np.ndarray, cfg: Config) -> np.ndarray:
    """(N,) expected maximum utility per segment -- the nested-logit logsum.

    This is the quantity welfare economics uses to value a change in a choice
    set.  Divided by the logit scale it converts to dollars, giving the
    compensating variation: what each traveller would need to be paid to be
    indifferent between the world with the charge and the world without it.

    It is strictly better than counting tolls alone, because it also prices the
    two things a toll makes people do -- retime, reroute, switch mode, or stop
    travelling (adaptation cost), and drive on a road that is now quieter
    (travel-time gain).  Eliasson (2016) sets out exactly this decomposition.
    """
    v = -cfg.logit_scale * (gc - constants[None, :])
    nest_names = list(NESTS.keys())
    nest_ls = np.zeros((v.shape[0], len(nest_names)))

    for k, nest in enumerate(nest_names):
        cols = NEST_MEMBERS[nest]
        lam = max(float(cfg.nest_lambda.get(nest, 1.0)), 1e-3)
        scaled = v[:, cols] / lam
        top = scaled.max(axis=1, keepdims=True)
        nest_ls[:, k] = (top[:, 0] + np.log(np.exp(scaled - top).sum(axis=1))) * lam

    top = nest_ls.max(axis=1, keepdims=True)
    return top[:, 0] + np.log(np.exp(nest_ls - top).sum(axis=1))


def consumer_surplus_change(
    gc_after: np.ndarray,
    gc_before: np.ndarray,
    constants: np.ndarray,
    cfg: Config,
) -> np.ndarray:
    """(N,) change in consumer surplus, in dollars per trip.

    Negative means the traveller is worse off before any revenue is returned
    to them.  The toll itself is inside this figure, because the traveller does
    pay it; the transfer is added back separately when revenue is recycled.
    """
    return (logsum(gc_after, constants, cfg) - logsum(gc_before, constants, cfg)) / cfg.logit_scale


def aggregate_shares(probs: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Collapse (N, A) segment probabilities into an (A,) market share vector."""
    return np.asarray(probs * weights[:, None]).sum(axis=0) / weights.sum()


def calibrate_constants(
    gc_fn,
    weights: np.ndarray,
    target_shares: Dict[str, float],
    cfg: Config,
    max_iter: int = 400,
    tol: float = 1e-9,
) -> Tuple[np.ndarray, dict]:
    """Fit alternative-specific constants so the base run reproduces observed shares.

    The standard adjustment: at each pass, move each constant by the log ratio
    of observed to modelled share, then renormalise.  `gc_fn(constants)` must
    return the (N, A) generalized-cost matrix at the equilibrium implied by
    those constants, so the fit accounts for congestion feeding back on itself.

    Without this step every result would inherit whatever base-share error the
    raw utility specification happens to produce, and the toll response would be
    measured from the wrong starting point.
    """
    target = np.array([target_shares[a] for a in ALTERNATIVES], dtype=float)
    target = target / target.sum()
    constants = np.zeros(len(ALTERNATIVES))
    history = []

    for it in range(max_iter):
        gc = gc_fn(constants)
        probs = probabilities(gc, constants, cfg)
        modelled = aggregate_shares(probs, weights)
        err = float(np.abs(modelled - target).max())
        history.append(err)
        if err < tol:
            break
        # Damped so the update cannot overshoot on a near-zero modelled share.
        step = np.log(np.maximum(target, 1e-12) / np.maximum(modelled, 1e-12))
        constants = constants + 0.75 * step / cfg.logit_scale
        constants -= constants.mean()

    return constants, {
        "iterations": it + 1,
        "max_abs_share_error": history[-1],
        "converged": history[-1] < 1e-6,
        "history": [float(h) for h in history[:60]],
    }


def direct_elasticity(
    gc: np.ndarray,
    constants: np.ndarray,
    weights: np.ndarray,
    cfg: Config,
    alternative: str = "drive_gardiner",
    delta: float = 0.01,
) -> float:
    """Point elasticity of an alternative's share with respect to its own cost.

    Used to check that the logit scale implies a plausible toll response rather
    than whatever value happened to be typed into the config.
    """
    j = IDX[alternative]
    base = aggregate_shares(probabilities(gc, constants, cfg), weights)[j]
    bumped = gc.copy()
    mean_cost = float(np.average(gc[:, j], weights=weights))
    bumped[:, j] += mean_cost * delta
    after = aggregate_shares(probabilities(bumped, constants, cfg), weights)[j]
    return float(((after - base) / base) / delta)
