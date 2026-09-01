"""Stage 0: where should the charge be tested at all?

The proposal's own instruction is that the pilot corridor must be *screened*,
not assumed.  So this module scores the candidate gateways on the stated
criteria and then does the thing that actually decides whether the answer is
credible: it re-runs the ranking under thousands of alternative weightings.

A multi-criteria score is only ever as good as its weights, and weights are
subjective.  Reporting a single weighted total invites the obvious objection
that the answer was chosen by choosing the weights.  Reporting how often each
candidate wins across a wide spread of weightings answers that objection
directly.  A cross-check with TOPSIS, which aggregates by distance to the ideal
point rather than by weighted sum, tests whether the result survives a change
of aggregation method too.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from . import datasets

# Criterion -> whether a larger raw value is better for a pricing pilot.
DIRECTIONS = {
    "peak_delay_index": True,
    "traffic_base": True,
    "transit_substitute": True,
    "revenue_potential": True,
    "diversion_risk": False,
    "equity_exposure": False,
    "governance_feasibility": True,
}


def _matrix() -> tuple:
    """Build the normalised decision matrix, respecting criterion direction."""
    df = datasets.gateways().copy()
    df["traffic_base"] = df["daily_vehicles"]

    criteria = list(DIRECTIONS.keys())
    raw = df[criteria].to_numpy(dtype=float)

    # Min-max normalise each column onto 0-1, flipping the ones where less is
    # better, so every column reads "higher is a better pricing candidate".
    norm = np.zeros_like(raw)
    for j, c in enumerate(criteria):
        col = raw[:, j]
        lo, hi = col.min(), col.max()
        scaled = np.full_like(col, 0.5) if hi <= lo else (col - lo) / (hi - lo)
        norm[:, j] = scaled if DIRECTIONS[c] else 1.0 - scaled
    return df, criteria, raw, norm


def default_weights() -> Dict[str, float]:
    df = datasets.criteria()
    return {str(r["criterion"]): float(r["weight"]) for _, r in df.iterrows()}


def score(weights: Optional[Dict[str, float]] = None) -> dict:
    """Weighted-sum ranking of the candidate gateways."""
    df, criteria, raw, norm = _matrix()
    w = weights or default_weights()
    vec = np.array([w.get(c, 0.0) for c in criteria], dtype=float)
    vec = vec / vec.sum() if vec.sum() > 0 else vec

    totals = norm @ vec
    order = np.argsort(-totals)

    rows = []
    for rank, i in enumerate(order, start=1):
        rows.append(
            {
                "rank": rank,
                "gateway_id": str(df.iloc[i]["gateway_id"]),
                "name": str(df.iloc[i]["name"]),
                "score": round(float(totals[i]), 4),
                "lat": float(df.iloc[i]["lat"]),
                "lon": float(df.iloc[i]["lon"]),
                "daily_vehicles": int(df.iloc[i]["daily_vehicles"]),
                "note": str(df.iloc[i]["note"]),
                "criteria": {
                    c: {
                        "raw": float(raw[i, j]),
                        "normalised": round(float(norm[i, j]), 4),
                        "weighted": round(float(norm[i, j] * vec[j]), 4),
                        "direction": "higher is better" if DIRECTIONS[c] else "lower is better",
                    }
                    for j, c in enumerate(criteria)
                },
            }
        )
    return {"weights": {c: float(v) for c, v in zip(criteria, vec)}, "ranking": rows}


def topsis(weights: Optional[Dict[str, float]] = None) -> List[dict]:
    """Rank by closeness to the ideal point instead of by weighted sum.

    A different aggregation rule applied to the same evidence.  If the two
    methods disagree, the weighted-sum result was an artefact of the method.
    """
    df, criteria, _, norm = _matrix()
    w = weights or default_weights()
    vec = np.array([w.get(c, 0.0) for c in criteria], dtype=float)
    vec = vec / vec.sum() if vec.sum() > 0 else vec

    # Vector-normalise, then weight.
    denom = np.sqrt((norm**2).sum(axis=0))
    denom[denom == 0] = 1.0
    v = (norm / denom) * vec

    ideal, anti = v.max(axis=0), v.min(axis=0)
    d_pos = np.sqrt(((v - ideal) ** 2).sum(axis=1))
    d_neg = np.sqrt(((v - anti) ** 2).sum(axis=1))
    closeness = np.divide(d_neg, d_pos + d_neg, out=np.zeros_like(d_neg), where=(d_pos + d_neg) > 0)

    order = np.argsort(-closeness)
    return [
        {
            "rank": rank,
            "gateway_id": str(df.iloc[i]["gateway_id"]),
            "name": str(df.iloc[i]["name"]),
            "closeness": round(float(closeness[i]), 4),
        }
        for rank, i in enumerate(order, start=1)
    ]


def weight_sensitivity(n_draws: int = 4000, concentration: float = 12.0, seed: int = 7) -> dict:
    """How often does each gateway win, across many plausible weightings?

    Weight vectors are drawn from a Dirichlet distribution centred on the
    nominal weights.  `concentration` controls how far the draws wander: lower
    means a wider spread of opinion about what matters.  The output is the
    probability that each candidate ranks first, which is a far more honest
    summary than a single weighted score.
    """
    df, criteria, _, norm = _matrix()
    nominal = np.array([default_weights().get(c, 0.0) for c in criteria], dtype=float)
    nominal = nominal / nominal.sum()

    rng = np.random.default_rng(seed)
    draws = rng.dirichlet(nominal * concentration, size=n_draws)
    totals = draws @ norm.T                      # (draws, gateways)
    winners = np.argmax(totals, axis=1)

    names = [str(x) for x in df["name"]]
    ids = [str(x) for x in df["gateway_id"]]
    counts = np.bincount(winners, minlength=len(ids))

    ranks = np.argsort(np.argsort(-totals, axis=1), axis=1) + 1
    return {
        "draws": n_draws,
        "concentration": concentration,
        "nominal_weights": {c: round(float(x), 4) for c, x in zip(criteria, nominal)},
        "results": [
            {
                "gateway_id": ids[i],
                "name": names[i],
                "win_probability": round(float(counts[i] / n_draws), 4),
                "mean_rank": round(float(ranks[:, i].mean()), 3),
                "mean_score": round(float(totals[:, i].mean()), 4),
                "score_p05": round(float(np.percentile(totals[:, i], 5)), 4),
                "score_p95": round(float(np.percentile(totals[:, i], 95)), 4),
                "top2_probability": round(float((ranks[:, i] <= 2).mean()), 4),
            }
            for i in range(len(ids))
        ],
        "note": (
            "Weights are drawn from a Dirichlet centred on the nominal set, so "
            "the ranking is tested against a wide spread of reasonable opinion "
            "about what matters rather than one subjective vector."
        ),
    }


def gantries() -> List[dict]:
    """Candidate charging-point locations within the selected corridor."""
    return datasets.records(datasets.gantries())


def transit_alternatives() -> List[dict]:
    return datasets.records(datasets.transit_stations())


def report(n_draws: int = 4000) -> dict:
    """The complete Stage 0 screening result."""
    ranked = score()
    sens = weight_sensitivity(n_draws=n_draws)
    top = ranked["ranking"][0]
    tops = topsis()

    agree = tops[0]["gateway_id"] == top["gateway_id"]
    win_prob = next(
        (r["win_probability"] for r in sens["results"] if r["gateway_id"] == top["gateway_id"]),
        0.0,
    )
    return {
        "weighted_sum": ranked,
        "topsis": tops,
        "methods_agree": agree,
        "weight_sensitivity": sens,
        "selected": {
            "gateway_id": top["gateway_id"],
            "name": top["name"],
            "score": top["score"],
            "win_probability": win_prob,
            "topsis_agrees": agree,
        },
        "gantries": gantries(),
        "transit_alternatives": transit_alternatives(),
        "criteria": datasets.records(datasets.criteria()),
    }
