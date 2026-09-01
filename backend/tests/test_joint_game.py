"""Tests for the joint sequencing-and-authorisation game.

The joint model reuses the phased game's per-year welfare and rescales it by a
second gate. That rescale has to be exact rather than approximate, or the joint
answer drifts from the phased one for arithmetic reasons and gets read as a
finding. These pin the algebra first, the regime boundary second, and the
headline last.
"""
from __future__ import annotations

import json

import pytest

from uttan import bargaining, joint_game, phasing
from uttan.config import Config
from uttan.phasing import Path, Stage


@pytest.fixture(scope="module")
def cfg():
    return Config()


# --------------------------------------------------------------------------
# The regime boundary
# --------------------------------------------------------------------------

def test_regime_boundary_falls_where_the_transfer_does(cfg):
    """Fall 2027 is ~1.15 years out, so years 0 and 1 begin before it."""
    assert joint_game.regime_at(0, cfg) == "pre_transfer"
    assert joint_game.regime_at(1, cfg) == "pre_transfer"
    assert joint_game.regime_at(2, cfg) == "post_transfer"


def test_moving_the_transfer_date_moves_the_boundary(cfg):
    """The date is a parameter, not a constant. It has slipped before."""
    late = Config.from_dict({**cfg.to_dict(), "years_until_transfer": 3.5})
    assert joint_game.regime_at(2, late) == "pre_transfer"
    assert joint_game.regime_at(4, late) == "post_transfer"


# --------------------------------------------------------------------------
# The second gate
# --------------------------------------------------------------------------

def test_deal_probability_is_a_coin_toss_at_zero_surplus(cfg):
    """A party exactly indifferent between agreeing and walking away."""
    assert joint_game.deal_probability(0.0, cfg) == pytest.approx(0.5)


def test_deal_probability_is_monotone_and_bounded(cfg):
    probs = [joint_game.deal_probability(s, cfg)
             for s in (-2e7, -5e6, 0.0, 5e6, 2e7)]
    assert probs == sorted(probs)
    assert 0.0 < probs[0] < 0.5 < probs[-1] < 1.0


@pytest.mark.slow
def test_joint_probability_is_the_product_of_the_two_gates(cfg):
    """The substantive claim of the module, stated as arithmetic."""
    for row in joint_game.timing_frontier(cfg)["rows"]:
        assert row["p_joint"] == pytest.approx(
            row["p_voters"] * row["p_deal"], abs=1e-4
        )


@pytest.mark.slow
def test_a_second_gate_can_only_reduce_expected_welfare(cfg):
    """P(deal) <= 1, so the joint value never exceeds the voters-only value.

    If this inverts, the rescale has the probability the wrong way round.
    """
    for row in joint_game.timing_frontier(cfg)["rows"]:
        assert row["expected_discounted_welfare"] <= row["welfare_voters_only"] + 1e-9


# --------------------------------------------------------------------------
# The rescale must be exact, not approximate
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_rescaling_by_one_reproduces_the_phased_welfare_exactly(cfg):
    """The joint model must reduce to the phased model when the deal is certain.

    Welfare is linear in the enactment probability by construction, so
    recombining the same with/without pair at an unchanged probability has to
    return the identical number. Any drift here means the joint frontier is not
    comparable with the phased one, and the difference between them -- which is
    the whole finding -- would be partly arithmetic.
    """
    stages = [
        Stage(year=y, label=f"y{y}", transit_uplift=0.25,
              transit_delivered=phasing._ramp(0, y, 0.25, cfg.transit_delivery_lag_years),
              charge=10.0 if y >= 1 else 0.0, gate=(y == 1))
        for y in range(cfg.horizon_years)
    ]
    path = Path(key="t", name="t", precedent="", rationale="", stages=stages)
    voters = phasing.evaluate_path(path, cfg, reference=cfg)
    rescaled = joint_game._rescaled_welfare(voters, 1.0, cfg)
    assert rescaled == pytest.approx(voters["expected_discounted_welfare"], abs=1e-5)


@pytest.mark.slow
def test_rescaling_to_zero_removes_the_charge_entirely(cfg):
    """With no chance of enactment, only the non-price measures remain."""
    stages = [
        Stage(year=y, label=f"y{y}", charge=10.0 if y >= 1 else 0.0, gate=(y == 1))
        for y in range(4)
    ]
    path = Path(key="t", name="t", precedent="", rationale="", stages=stages)
    voters = phasing.evaluate_path(path, cfg, reference=cfg)
    zero = joint_game._rescaled_welfare(voters, 0.0, cfg)
    expected = sum(r["discount"] * r["welfare_without_charge"] for r in voters["years"])
    assert zero == pytest.approx(expected, abs=1e-9)


# --------------------------------------------------------------------------
# The degenerate case
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_no_possible_deal_reports_no_timing_recommendation(cfg):
    """When no deal is reachable, every year returns the same no-charge welfare
    and argmax picks year 0 arbitrarily. Reporting that as "charge immediately"
    is a confident reversal that does not exist, so it must be suppressed."""
    d = joint_game.deadline_sensitivity(cfg, rates=(0.9, 10.0))
    dead = [r for r in d["rows"] if not r["charge_ever_enacted"]]
    assert dead, "expected the highest political cost to make a deal impossible"
    for r in dead:
        assert r["optimal_start_year"] is None
        assert r["optimum_before_transfer"] is None


# --------------------------------------------------------------------------
# The finding
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_the_deal_gate_does_not_bind_at_the_assumed_political_cost(cfg):
    """At the assumed rate the joint answer equals the phased one.

    Worth pinning because it is the honest baseline: the joint game adds
    nothing until the political cost is high enough to matter, and the case for
    it rests on the 2017 refusal implying that it is.
    """
    f = joint_game.timing_frontier(cfg)
    assert not f["deadline_moves_the_answer"]
    assert f["optimal_start_year_joint"] == f["optimal_start_year_voters_only"]


@pytest.mark.slow
def test_the_timing_recommendation_reverses_below_the_2017_implied_cost(cfg):
    """The headline, and it runs against the leverage intuition.

    A zone of agreement survives to a HIGHER political cost after the transfer
    than before, because the Province's post-transfer fallback is a unilateral
    charge that carries political cost of its own. So at a rate consistent with
    the Province actually having refused in 2017, the model says wait until
    after the transfer rather than rush a deal before it.
    """
    d = joint_game.deadline_sensitivity(cfg)
    switch = d["recommendation_switches_at"]
    assert switch is not None, d["rows"]

    implied = bargaining.breakeven_political_cost(cfg)["threshold_per_charged_trip"]
    # The 2017 refusal puts the true rate above `implied`; the recommendation
    # has already reversed by then.
    assert switch <= implied, (switch, implied)

    high = [r for r in d["rows"]
            if r["charge_ever_enacted"]
            and r["political_cost_per_charged_trip"] >= implied]
    assert high, "no live rows above the implied bound"
    assert all(r["optimum_before_transfer"] is False for r in high)


@pytest.mark.slow
def test_post_transfer_deals_survive_higher_political_cost(cfg):
    """The mechanism behind the reversal, checked directly rather than inferred."""
    pre = bargaining.breakeven_political_cost(cfg, regime="pre_transfer")
    post = bargaining.breakeven_political_cost(cfg, regime="post_transfer")
    assert post["threshold_per_charged_trip"] > pre["threshold_per_charged_trip"]


# --------------------------------------------------------------------------
# Price and timing chosen together
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_joint_optimum_reports_both_a_constrained_and_an_unconstrained_answer(cfg):
    """The political gates alone do not discipline the price on this corridor.

    Support falls only about six points across the whole price range, because a
    larger charge also recycles more. So an unconstrained joint solve runs the
    price to the top of whatever grid it is given, and reporting only that would
    be presenting a grid boundary as a result.
    """
    r = joint_game.joint_optimum(cfg)
    assert r["unconstrained_optimum"]["charge"] >= r["constrained_optimum"]["charge"]
    assert r["constrained_optimum"]["feasible"] is True
    assert r["price_of_the_constraints"] >= 0
    # Whatever stops the price must be named, or the constrained answer is a
    # number with no argument behind it.
    assert r["constraints_that_bind"]


def test_every_admissible_cell_really_passes_the_constraint_set(cfg):
    """Feasibility must come from the same machinery the recommendation uses.

    If this drifted from `game.evaluate`, the joint answer would be optimising
    over designs the study would refuse elsewhere.
    """
    from uttan import game
    from uttan.demand import load_segments
    from uttan.toll_policy import TollPolicy

    r = joint_game.joint_optimum(cfg, charges=[10.0, 14.0])
    for cell in r["cells"]:
        if cell["charge_start_year"] != 1:
            continue
        delivered_capacity = phasing._ramp(
            0, 1, joint_game.TRANSIT_UPLIFT, cfg.transit_delivery_lag_years
        )
        trial = Config.from_dict({
            **cfg.to_dict(),
            "delivered_alternative": min(delivered_capacity / 0.25, 1.0),
        })
        policy = TollPolicy(
            peak_toll=cell["charge"], coverage="screenline",
            credit="low_income_transit_poor", go_frequency_uplift=delivered_capacity,
        )
        expected = game.evaluate(policy, trial, load_segments(trial), reference=cfg)
        assert cell["feasible"] is bool(expected["feasible"]["passes"])


@pytest.mark.slow
def test_separability_is_reported_per_direction_not_as_one_flag(cfg):
    """The two dimensions fail separability asymmetrically here.

    The best price is the same at every start year; the best year is not the
    same at every price. A single boolean would have to call that "not
    separable" and then the study would claim solving in sequence misses the
    answer -- which, run explicitly, it does not.
    """
    r = joint_game.joint_optimum(cfg)
    assert r["charge_is_year_invariant"] is True
    assert r["year_is_charge_invariant"] is False
    # Keys must survive a JSON round-trip unchanged: a dict keyed by float
    # reorders on reload and breaks the precomputed comparison.
    for mapping in (r["optimal_charge_by_start_year"], r["optimal_start_year_by_charge"]):
        assert all(isinstance(k, str) for k in mapping)
        assert json.loads(json.dumps(mapping, sort_keys=True)) == mapping
    seq = r["sequential"]
    assert seq is not None
    assert seq["matches_joint"] is True
    assert seq["expected_discounted_welfare"] == pytest.approx(
        r["constrained_optimum"]["expected_discounted_welfare"], abs=1e-9
    )


# --------------------------------------------------------------------------
# The two gates, allowed to move together
# --------------------------------------------------------------------------

def test_gate_dependence_defaults_to_independence(cfg):
    """Every joint result computed so far assumed it, so it must stay the default."""
    assert cfg.gate_dependence == 0.0
    assert bargaining.political_cost_given_support(cfg, 0.2) == (
        cfg.political_cost_per_charged_trip
    )
    assert bargaining.political_cost_given_support(cfg, None) == (
        cfg.political_cost_per_charged_trip
    )


def test_the_rate_is_anchored_at_the_referendum_threshold(cfg):
    """At 50% support the rate must be the stated base, whatever the dependence.

    The dependence rotates the line about that point rather than shifting it,
    which is what keeps the existing calibration meaningful: a parameter that
    moved the rate at the anchor would silently restate the bargaining results.
    """
    for dep in (0.0, 0.5, 1.0, 5.0):
        trial = Config.from_dict({**cfg.to_dict(), "gate_dependence": dep})
        assert bargaining.political_cost_given_support(trial, 0.5) == pytest.approx(
            cfg.political_cost_per_charged_trip, abs=1e-12
        )


def test_support_lowers_the_cost_of_authorising(cfg):
    """The direction is the whole claim: a popular scheme is cheaper to authorise."""
    trial = Config.from_dict({**cfg.to_dict(), "gate_dependence": 1.0})
    unpopular = bargaining.political_cost_given_support(trial, 0.2)
    popular = bargaining.political_cost_given_support(trial, 0.8)
    assert unpopular > cfg.political_cost_per_charged_trip > popular
    # ...and it can reach zero but never invert: there is no evidence for a
    # government being PAID to authorise, and a negative cost would flip the
    # sign of the term the whole bargain turns on.
    extreme = Config.from_dict({**cfg.to_dict(), "gate_dependence": 50.0})
    assert bargaining.political_cost_given_support(extreme, 0.99) == 0.0


@pytest.mark.slow
def test_independence_understates_the_value_of_waiting_where_the_gate_binds(cfg):
    """The reason the assumption was worth removing.

    It is nearly harmless at the assumed political cost, because P(deal) is
    about 0.997 either way. It matters in the regime the 2017 refusal points to,
    and that is exactly where the study's sequencing argument lives.
    """
    sweep = joint_game.gate_dependence_sweep(cfg)
    by_cost = {a["political_cost_per_charged_trip"]: a for a in sweep["amplification"]}

    cheap = by_cost[0.9]
    assert cheap["deal_gate_binds"] is False
    assert cheap["ratio"] == pytest.approx(1.0, abs=0.05)

    binding = by_cost[3.5]
    assert binding["deal_gate_binds"] is True
    assert binding["ratio"] > 2.0
    assert binding["value_of_waiting_dependent"] > binding["value_of_waiting_independent"]


@pytest.mark.slow
def test_dependence_changes_the_magnitude_not_the_ranking(cfg):
    """Waiting stays the right answer, which is what makes this a robustness result.

    If the recommendation flipped with an unobservable parameter the study would
    have to say so loudly; it does not, and that is worth pinning.
    """
    sweep = joint_game.gate_dependence_sweep(cfg)
    assert sweep["changes_the_recommended_year_anywhere"] is False


def test_no_zone_of_agreement_still_reports_the_rate(cfg):
    """The branch the analysis most wants to read must not raise.

    When no deal exists the early return used to omit the rate entirely, so
    reading it failed exactly in the regime worth studying.
    """
    hostile = Config.from_dict({
        **cfg.to_dict(), "political_cost_per_charged_trip": 20.0, "gate_dependence": 1.0,
    })
    deal = joint_game._bargain_at(0, hostile, 10.0, "screenline", support=0.3)
    assert deal["deal_probability"] == 0.0
    assert "political_cost_rate" in deal
