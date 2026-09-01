"""Loads the public-data CSVs and keeps their provenance attached.

Every number the model consumes is tagged PUBLISHED (taken from a named public
source), DERIVED (computed from published numbers by a documented rule) or
ESTIMATED (a planning assumption).  The API exposes this table so a reader can
see exactly which results rest on assumptions.
"""
from __future__ import annotations

import functools
import json
import math
from pathlib import Path
from typing import Dict, List

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"missing data file: {path}")
    return pd.read_csv(path)


@functools.lru_cache(maxsize=1)
def segments() -> pd.DataFrame:
    """Traveller segments: (sub-area, income quintile, schedule flexibility)."""
    df = _read("segments.csv")
    total = df["share"].sum()
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"segment shares sum to {total}, expected 1.0")
    return df


@functools.lru_cache(maxsize=1)
def network() -> pd.DataFrame:
    return _read("network.csv").set_index("link_id")


@functools.lru_cache(maxsize=1)
def routes() -> pd.DataFrame:
    """Which links each route alternative uses, and in what proportion."""
    return _read("routes.csv")


@functools.lru_cache(maxsize=1)
def gateways() -> pd.DataFrame:
    return _read("gateways.csv")


@functools.lru_cache(maxsize=1)
def criteria() -> pd.DataFrame:
    return _read("criteria.csv")


@functools.lru_cache(maxsize=1)
def gantries() -> pd.DataFrame:
    return _read("gantries.csv")


@functools.lru_cache(maxsize=1)
def transit_stations() -> pd.DataFrame:
    return _read("transit_stations.csv")


@functools.lru_cache(maxsize=1)
def link_geometry() -> dict:
    """GeoJSON centrelines for the five modelled links.

    Presentation only -- the model works on link lengths and capacities from
    network.csv, never on these coordinates.  They exist so the map can show
    where the corridor, its bypasses and the charging screenline actually are.
    """
    path = DATA_DIR / "link_geometry.json"
    if not path.exists():
        raise FileNotFoundError(f"missing data file: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=1)
def subarea_points() -> dict:
    """Indicative points for the seven demand sub-areas.

    Points rather than polygons, and presentation only, for the same reason
    link_geometry.json is: the OD pattern behind the sub-areas is synthetic, so
    drawing boundaries would imply a spatial precision it does not have.
    Nothing in the model reads these coordinates.
    """
    path = DATA_DIR / "subarea_points.json"
    if not path.exists():
        raise FileNotFoundError(f"missing data file: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=1)
def benchmarks() -> pd.DataFrame:
    """Outcomes and Suits indices from congestion charges that actually operate."""
    return _read("benchmarks.csv")


@functools.lru_cache(maxsize=1)
def natural_experiments() -> pd.DataFrame:
    """Observed before/after figures from the Gardiner rehabilitation episodes.

    These are the only real corridor-behaviour observations available to this
    study.  Every one of them is a travel TIME; no volume count has been
    published for either episode, which is the whole reason
    rejoin_validation.py has to invert times through the link performance
    curves instead of simply differencing counts.
    """
    return _read("natural_experiments.csv")


@functools.lru_cache(maxsize=1)
def city_schemes() -> pd.DataFrame:
    """Congestion charges elsewhere -- the ones that operate and the ones that failed.

    The rejected schemes are in the same table on purpose. A comparison drawn
    only from charges that survived is survivorship bias, and it is exactly the
    bias that would make this study over-confident about deliverability.
    """
    return _read("city_schemes.csv")


@functools.lru_cache(maxsize=1)
def governance() -> pd.DataFrame:
    """Published terms of the Gardiner/DVP upload, and the 2016-17 toll episode.

    The 2017 rows matter as much as the money: Council voted for tolls, the
    Province refused, and a side payment was accepted instead. That is the
    bargaining problem in `bargaining.py` actually played once, which is more
    than most of this model's game theory has behind it.
    """
    return _read("governance.csv")


@functools.lru_cache(maxsize=1)
def sources() -> pd.DataFrame:
    return _read("sources.csv")


def source_value(key: str) -> float:
    """Look up a single published/derived input by key."""
    df = sources()
    hit = df.loc[df["key"] == key, "value"]
    if hit.empty:
        raise KeyError(f"no source row for {key!r}")
    return float(hit.iloc[0])


def governance_value(key: str) -> float:
    """Look up one published governance figure by key."""
    df = governance()
    hit = df.loc[df["key"] == key, "value"]
    if hit.empty:
        raise KeyError(f"no governance row for {key!r}")
    return float(hit.iloc[0])


def provenance_summary() -> Dict[str, int]:
    """Count of inputs by provenance tier -- reported in the API and the UI."""
    return sources()["tier"].value_counts().to_dict()


def _missing(value) -> bool:
    """True for every flavour of "no value" pandas can put in a cell.

    Deliberately not `pd.isna`, which returns an *array* for a list-valued cell
    and then `bool()` of it raises.  Identity checks for the singletons and an
    explicit float test cover what a CSV can produce, and `numpy.float64`
    subclasses `float`, so it is caught by the same branch.
    """
    if value is None or value is pd.NaT or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def records(df: pd.DataFrame) -> List[dict]:
    """DataFrame -> JSON-safe list of dicts.

    JSON-safe is the whole point: `json.dumps` writes a bare `NaN` for a float
    nan, which is not JSON and which `JSON.parse` rejects.  Missing cells are
    common here -- a scheme with no published Suits index, an episode with no
    model link -- so this runs on almost every table the API serves.

    This was `df.where(pd.notna(df), None)`, which stopped substituting None in
    pandas 3.0: the value came back as nan and the promise in this docstring
    quietly became false.  Nothing broke loudly, because FastAPI normalises nan
    to null on the way out and every in-process consumer happened to test for
    both -- the only thing that noticed was `test_precomputed.py`, comparing a
    cache written under pandas 2 against a live recomputation under pandas 3.
    Converting per value depends on no pandas behaviour at all.
    """
    return [
        {k: (None if _missing(v) else v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
