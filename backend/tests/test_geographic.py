"""Tests for geographic equity.

Shares and ratios are the easiest thing in this codebase to get quietly wrong:
a denominator that does not sum to one, or a boundary test matched on the wrong
string, produces a complete table in which every row looks reasonable. These
pin conservation first and the findings second.
"""
from __future__ import annotations

import pytest

from uttan import geographic
from uttan.config import Config
from uttan.demand import load_segments


@pytest.fixture(scope="module")
def report():
    return geographic.report()


# --------------------------------------------------------------------------
# Conservation
# --------------------------------------------------------------------------

def test_shares_sum_to_one(report):
    """Trip, charge and benefit shares each partition the corridor exactly."""
    rows = report["incidence"]["subareas"]
    for key in ("trip_share", "charge_share", "benefit_share"):
        assert sum(r[key] for r in rows) == pytest.approx(1.0, abs=1e-3), key


def test_boundary_split_partitions_the_subareas(report):
    b = report["incidence"]["boundary"]
    assert b["outside_toronto"]["trip_share"] + b["toronto"]["trip_share"] == \
        pytest.approx(1.0, abs=1e-6)
    assert b["outside_toronto"]["charge_share"] + b["toronto"]["charge_share"] == \
        pytest.approx(1.0, abs=1e-3)


def test_every_subarea_is_classified_and_only_one_is_outside(report):
    """A boundary test matched on the wrong label would silently move an entire
    sub-area to the other side of the city line and change every headline."""
    rows = report["incidence"]["subareas"]
    outside = [r["subarea"] for r in rows if r["outside_toronto"]]
    assert outside == ["Mississauga / west GTA"]
    assert len(rows) == len(set(load_segments(Config()).subarea))


def test_pays_vs_uses_is_the_ratio_it_claims_to_be(report):
    for r in report["incidence"]["subareas"]:
        assert r["pays_vs_uses"] == pytest.approx(
            r["charge_share"] / r["trip_share"], rel=1e-3
        )


def test_net_contributor_gap_is_paid_minus_received(report):
    for r in report["incidence"]["subareas"]:
        assert r["net_contributor_gap"] == pytest.approx(
            r["charge_share"] - r["benefit_share"], abs=1e-3
        )


# --------------------------------------------------------------------------
# The findings
# --------------------------------------------------------------------------

def test_geography_is_not_just_income_restated(report):
    """The justification for the page existing at all.

    If income explained nearly all of the geographic burden variation, this
    would be §7 with a map on it and should be reported there instead.
    """
    d = report["decomposition"]
    assert d["share_explained_by_income"] + d["share_not_explained_by_income"] == \
        pytest.approx(1.0, abs=1e-6)
    assert d["share_not_explained_by_income"] > 0.25


def test_the_corridor_is_not_the_new_jersey_case(report):
    """A finding worth pinning because it contradicts the obvious analogy.

    FHWA found New Jersey residents paying 45% of New York's tolls while making
    24% of the trips, a ratio of 1.88. The handover assumed this corridor had
    the same structure. Under the recommended design it does not: the 905 pays
    slightly LESS than its share of trips, because Lakeshore West GO gives it a
    way out that inner Etobicoke does not have. If this ever flips, the
    recommendation's geographic story has changed and the page must say so.
    """
    b = report["incidence"]["boundary"]
    assert b["outside_toronto"]["pays_vs_uses"] < 1.0
    assert (b["outside_toronto"]["pays_vs_uses"]
            < report["incidence"]["benchmark"]["ratio"])


def test_the_heaviest_burden_is_borne_inside_toronto(report):
    """The corollary: the charge concentrates on inner Etobicoke, not the 905."""
    rows = report["incidence"]["subareas"]
    worst = max(rows, key=lambda r: r["burden_pct_income"])
    assert not worst["outside_toronto"]


def test_residual_burden_runs_against_transit_access(report):
    """Direction only. With seven sub-areas the magnitude is not evidence."""
    assert report["decomposition"]["residual_vs_transit_access_corr"] < 0.0


def test_all_three_fhwa_equity_types_are_accounted_for(report):
    """FHWA's warning is that most analyses stop at income. State where each
    one lives, so a reader can check rather than take it on trust."""
    types = {t["type"] for t in report["fhwa_types"]}
    assert types == {"Income", "Geographic", "Modal"}
    for t in report["fhwa_types"]:
        assert t["where"] and t["status"]


def test_the_synthetic_od_caveat_is_carried(report):
    """These shares are Census-derived, not a TTS extract. Saying so is part of
    the result, not an optional footnote."""
    assert "TTS" in report["incidence"]["caveat"]
