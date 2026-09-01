"""Tests for the sequential game.

The phased model adds a state variable (a delivered transit alternative) to a
support calculation that every existing result already depends on, so the first
thing these pin is that a single-shot run is completely unaffected. After that
they pin the algebra of the expected payoff and the shape of the timing curve,
because both are easy to get subtly wrong in a way that still produces a
plausible ranking.
"""
from __future__ import annotations

import pytest

from uttan import phasing, political, simulate
from uttan.config import Config
from uttan.demand import load_segments
from uttan.phasing import Path, Stage
from uttan.toll_policy import TollPolicy


@pytest.fixture(scope="module")
def cfg():
    return Config()


# --------------------------------------------------------------------------
# The sequencing state must not leak into single-shot analysis
# --------------------------------------------------------------------------

def test_delivered_alternative_defaults_to_zero(cfg):
    """Everything outside the phased game must see the model it saw before."""
    assert cfg.delivered_alternative == 0.0


@pytest.mark.slow
def test_sequencing_term_is_inert_at_the_default(cfg):
    """The added term must contribute exactly zero to a single-shot run.

    Tested by making the coefficient absurd: if the state is genuinely zero the
    bonus cannot reach the answer whatever it is multiplied by. This fails the
    moment somebody gives `delivered_alternative` a non-zero default, which
    would silently restate every acceptability figure in the study.
    """
    segs = load_segments(cfg)
    policy = TollPolicy(peak_toll=10.0, coverage="screenline",
                        credit="low_income_transit_poor")
    loud = Config.from_dict({**cfg.to_dict(), "delivered_alternative_bonus": 25.0})

    base = simulate.run(policy, cfg, segs, full=False)["acceptability"]
    same = simulate.run(policy, loud, load_segments(loud), full=False,
                        reference=cfg)["acceptability"]
    assert same["before_operation"]["support_share"] == pytest.approx(
        base["before_operation"]["support_share"], abs=1e-9
    )
    assert same["after_operation"]["support_share"] == pytest.approx(
        base["after_operation"]["support_share"], abs=1e-9
    )


@pytest.mark.slow
def test_delivering_an_alternative_raises_support(cfg):
    """The sequencing claim, stated as a property.

    Same charge, same price, same everybody -- the only difference is whether
    the alternative has been built. If this does not raise support the whole
    phased game is measuring nothing.
    """
    policy = TollPolicy(peak_toll=10.0, coverage="screenline",
                        credit="low_income_transit_poor")
    before = phasing._evaluate_state(policy, cfg, load_segments(cfg), cfg, 0.0, False)
    after = phasing._evaluate_state(policy, cfg, load_segments(cfg), cfg, 1.0, False)
    assert after["support_share"] > before["support_share"]


# --------------------------------------------------------------------------
# Mechanics
# --------------------------------------------------------------------------

def test_enactment_probability_is_a_calibrated_logistic(cfg):
    assert phasing.enactment_probability(cfg.enactment_threshold, cfg) == pytest.approx(0.5)
    lo = phasing.enactment_probability(0.2, cfg)
    hi = phasing.enactment_probability(0.8, cfg)
    assert 0.0 < lo < 0.5 < hi < 1.0


def test_enactment_probability_is_monotone(cfg):
    probs = [phasing.enactment_probability(s, cfg) for s in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert probs == sorted(probs)


def test_transit_ramp_delivers_over_the_lag():
    assert phasing._ramp(None, 5, 0.25, 2) == 0.0        # never committed
    assert phasing._ramp(2, 1, 0.25, 2) == 0.0           # before the commitment
    assert phasing._ramp(0, 0, 0.25, 2) == pytest.approx(0.125)   # half delivered
    assert phasing._ramp(0, 1, 0.25, 2) == pytest.approx(0.25)    # fully delivered
    assert phasing._ramp(0, 9, 0.25, 2) == pytest.approx(0.25)    # cannot exceed
    assert phasing._ramp(0, 3, 0.25, 0) == pytest.approx(0.25)    # no lag


@pytest.mark.slow
def test_a_path_that_never_charges_has_no_gate(cfg):
    """No charge means no authorisation to obtain, which is its whole advantage."""
    paths = {p.key: p for p in phasing.build_paths(cfg)}
    result = phasing.evaluate_path(paths["operations_only"], cfg, reference=cfg)
    assert result["charge_year"] is None
    assert result["enactment_probability"] == 1.0
    assert result["support_at_gate"] is None


@pytest.mark.slow
def test_expected_welfare_is_the_probability_weighted_average(cfg):
    """Pin the payoff algebra on a one-year path with a known gate.

    E[W] = p*W(charge) + (1-p)*W(no charge) is the entire content of the model;
    an error here would reorder every path while still looking sensible.
    """
    stage = Stage(year=0, label="y0", charge=10.0, gate=True)
    path = Path(key="t", name="t", precedent="", rationale="", stages=[stage])
    r = phasing.evaluate_path(path, cfg, reference=cfg)
    row, p = r["years"][0], r["enactment_probability"]
    expected = p * row["welfare_with_charge"] + (1 - p) * row["welfare_without_charge"]
    # Tolerance is the reported precision: expected_welfare is stored rounded to
    # 5dp, as every other figure in this codebase is.
    assert row["expected_welfare"] == pytest.approx(expected, abs=1e-5)


@pytest.mark.slow
def test_discounting_reduces_later_years(cfg):
    stages = [Stage(year=y, label=f"y{y}") for y in range(4)]
    path = Path(key="t", name="t", precedent="", rationale="", stages=stages)
    discounts = [row["discount"] for row in
                 phasing.evaluate_path(path, cfg, reference=cfg)["years"]]
    assert discounts == sorted(discounts, reverse=True)
    assert discounts[0] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# The findings
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_sequencing_beats_charging_immediately(cfg):
    """The headline. Identical price -- the difference is purely enactment odds."""
    c = phasing.compare_paths(cfg)
    assert c["sequencing_value"] > 0
    assert c["best"] != "charge_now"
    ranked = [p["path"]["key"] for p in c["paths"]]
    assert ranked.index(c["best"]) == 0


@pytest.mark.slow
def test_charging_immediately_has_the_lowest_enactment_probability(cfg):
    """It is the most valuable charge per year and the least likely to exist."""
    c = phasing.compare_paths(cfg)
    priced = [p for p in c["paths"] if p["charge_year"] is not None]
    now = next(p for p in priced if p["path"]["key"] == "charge_now")
    assert now["enactment_probability"] == min(
        p["enactment_probability"] for p in priced
    )


@pytest.mark.slow
def test_timing_optimum_is_interior(cfg):
    """Both forces have to be real, or the model is not answering the question.

    Waiting buys enactment probability and costs discounted benefit-years. A
    corner solution would mean one of those is doing all the work.
    """
    f = phasing.timing_frontier(cfg)
    assert f["interior_optimum"], f["rows"]
    assert f["cost_of_charging_immediately"] > 0
    assert f["cost_of_waiting_too_long"] > 0


@pytest.mark.slow
def test_waiting_past_full_delivery_only_costs(cfg):
    """Once the alternative is fully delivered, further delay buys nothing.

    Support stops rising, so every additional year of waiting is pure
    discounted loss. This is what makes the answer 'as soon as the alternative
    lands', not 'as late as possible'.
    """
    f = phasing.timing_frontier(cfg)
    full = [r for r in f["rows"]
            if r["transit_delivered_at_start"] >= 0.25 - 1e-9]
    assert len(full) >= 3
    welfare = [r["expected_discounted_welfare"] for r in full]
    assert welfare == sorted(welfare, reverse=True), full
