"""Tests for the trust term in the acceptability model.

The term exists because two entries in the comparative record contradict this
study and both are the same missing mechanism: Edinburgh lost on trust rather
than economics, and Manchester lost with a GBP 3bn package attached.  A model in
which recycling reaches the vote at face value cannot produce either outcome at
any parameter value.

What these pin, in the order that matters:

  1. the term is inert at its default, so every result computed before it
     existed still holds -- the same discipline `test_phasing.py` applies to the
     sequencing state;
  2. it discounts the PROMISE and nothing else, which is the whole claim;
  3. it can actually produce the Manchester result, which is the point.

Properties rather than values throughout.  A pinned support figure would pass
just as happily with the discount applied to the wrong term.
"""
from __future__ import annotations

import numpy as np
import pytest

from uttan import political, simulate
from uttan.config import Config
from uttan.demand import load_segments
from uttan.toll_policy import TollPolicy

RECOMMENDED = TollPolicy(
    peak_toll=10.0, coverage="screenline", credit="low_income_transit_poor",
    window="0630_0930", label="recommended",
)


@pytest.fixture(scope="module")
def cfg():
    return Config()


@pytest.fixture(scope="module")
def context(cfg):
    """One equilibrium, reused: the per-segment incidence and its segments."""
    segs = load_segments(cfg)
    result = simulate.run(RECOMMENDED, cfg, segs, with_raw_incidence=True)
    return result["_raw_incidence"], segs


# --------------------------------------------------------------------------
# The term must not disturb anything that existed before it
# --------------------------------------------------------------------------

def test_trust_defaults_to_full_belief(cfg):
    """Anything else silently restates every acceptability figure in the study."""
    assert cfg.revenue_trust == 1.0
    assert political.revenue_trust(cfg) == 1.0


def test_the_gains_cannot_push_trust_above_certainty(cfg):
    """Trust is a share. You cannot more-than-believe a promise."""
    assert political.revenue_trust(cfg, operating=True) == 1.0
    delivered = Config.from_dict({**cfg.to_dict(), "delivered_alternative": 1.0})
    assert political.revenue_trust(delivered, operating=True) == 1.0


def test_trust_term_is_inert_at_the_default(cfg, context):
    """At full belief the vote must see exactly the undiscounted position.

    Tested by making the gains absurd rather than by comparing to a stored
    number: if the default is genuinely full belief then the clip absorbs any
    gain whatever it is, and this fails the moment somebody lowers the default.
    """
    inc, segs = context
    loud = Config.from_dict({
        **cfg.to_dict(),
        "revenue_trust_operating_gain": 25.0,
        "revenue_trust_delivery_gain": 25.0,
    })
    for operating in (False, True):
        base = political.support(inc, segs, cfg, operating=operating)
        same = political.support(inc, segs, loud, operating=operating)
        assert same["support_share"] == pytest.approx(base["support_share"], abs=1e-12)

    trips = inc["trips"]
    believed = political.support(inc, segs, cfg)["believed_net_per_trip"]
    actual = float(np.average(inc["net_per_trip"], weights=trips))
    assert believed == pytest.approx(round(actual, 3), abs=1e-9)


# --------------------------------------------------------------------------
# It must discount the promise, and only the promise
# --------------------------------------------------------------------------

def test_trust_does_not_touch_what_the_traveller_experiences(cfg, context):
    """A scheme that recycles nothing must be immune to disbelief.

    This is the test that the discount is attached to the right term. If it
    were applied to the whole net position instead, disbelief would make people
    doubt the toll they had already paid, and this would fail.
    """
    inc, segs = context
    no_recycling = {**inc, "recycled_per_trip": np.zeros_like(inc["recycled_per_trip"])}
    no_recycling["net_per_trip"] = inc["net_per_trip"] - inc["recycled_per_trip"]

    shares = {
        t: political.support(
            no_recycling, segs,
            Config.from_dict({**cfg.to_dict(), "revenue_trust": t}),
        )["support_share"]
        for t in (0.0, 0.25, 0.5, 1.0)
    }
    assert len(set(shares.values())) == 1, shares


def test_support_is_monotone_in_trust(cfg, context):
    """More belief in a positive promise cannot mean less support."""
    inc, segs = context
    shares = [
        political.support(
            inc, segs, Config.from_dict({**cfg.to_dict(), "revenue_trust": t})
        )["support_share"]
        for t in np.linspace(0.0, 1.0, 11)
    ]
    assert shares == sorted(shares)
    assert shares[-1] > shares[0], "the promise is worth nothing, so nothing is tested"


def test_disbelief_costs_exactly_the_promise(cfg, context):
    """Zero trust must land on the position before any revenue was recycled.

    The arithmetic identity behind the term, pinned so a later refactor cannot
    quietly turn the discount into something else that merely trends the right
    way.
    """
    inc, segs = context
    zero_trust = Config.from_dict({**cfg.to_dict(), "revenue_trust": 0.0})
    disbelieved = political.support(inc, segs, zero_trust)["believed_net_per_trip"]

    trips = inc["trips"]
    before_recycling = float(np.average(
        inc["net_per_trip"] - inc["recycled_per_trip"], weights=trips
    ))
    assert disbelieved == pytest.approx(round(before_recycling, 3), abs=1e-9)


# --------------------------------------------------------------------------
# The record it was built to reach
# --------------------------------------------------------------------------

def test_a_bigger_package_cannot_carry_a_vote_at_low_trust(cfg, context):
    """The Manchester result, which is unreachable without this term.

    Manchester attached GBP 3bn and still lost. Where recycling enters at face
    value, support is increasing and unbounded in the size of the package, so
    some package always wins; here each extra dollar reaches the vote multiplied
    by trust, so the curve flattens below the threshold and no multiplier
    catches it.
    """
    inc, segs = context
    result = political.package_credibility(inc, segs, cfg)
    by_trust = {s["revenue_trust"]: s for s in result["series"]}

    assert by_trust[0.25]["any_package_passes"] is False
    assert by_trust[1.00]["any_package_passes"] is True
    # ...and the ceiling must rise with trust, which is the mechanism rather
    # than an accident of where the threshold happens to sit.
    ceilings = [by_trust[t]["ceiling"] for t in sorted(by_trust)]
    assert ceilings == sorted(ceilings)
    assert result["trust_levels_no_package_can_carry"]


def test_the_edinburgh_threshold_is_reported_not_assumed(cfg, context):
    """The level is unobservable here, so the output is a threshold.

    Mirrors `bargaining.py`, which inverts the political-cost rate rather than
    tuning it. What this must never do is claim a trust level for Toronto.
    """
    inc, segs = context
    sens = political.trust_sensitivity(inc, segs, cfg)

    assert sens["edinburgh_trust"] == 0.25
    assert len(sens["levels"]) == 21
    for row in sens["levels"]:
        assert 0.0 <= row["revenue_trust"] <= 1.0
    # Whatever the breakeven is, the verdict must state it rather than assert a
    # level for this corridor.
    assert "Edinburgh" in sens["verdict_before"] or "No level of trust" in sens["verdict_before"]
    assert cfg.revenue_trust == 1.0, "the analysis must not mutate the config it was given"


# --------------------------------------------------------------------------
# Belief that the charge works, which is the larger doubt
# --------------------------------------------------------------------------

def test_efficacy_belief_defaults_to_full_and_is_inert(cfg, context):
    """Every result computed before this term existed must be unchanged."""
    inc, segs = context
    assert cfg.charge_efficacy_belief == 1.0
    believed = political.support(inc, segs, cfg)["believed_net_per_trip"]
    actual = float(np.average(inc["net_per_trip"], weights=inc["trips"]))
    assert believed == pytest.approx(round(actual, 3), abs=1e-9)


def test_efficacy_discounts_the_forecast_not_the_toll(cfg, context):
    """Disbelief must cost the time saving and leave the toll alone.

    The toll is a certainty -- you know what you will be charged. The time
    saving is a forecast that depends on other people changing their behaviour.
    Discounting the whole position instead would make people doubt a charge they
    had already paid, and this pins that it does not.
    """
    inc, segs = context
    none = Config.from_dict({**cfg.to_dict(), "charge_efficacy_belief": 0.0})
    disbelieved = political.support(inc, segs, none)["believed_net_per_trip"]

    trips = inc["trips"]
    # net - resource == -tolls, so total disbelief must land exactly on the toll.
    just_the_toll = float(np.average(
        inc["net_per_trip"] - inc["resource_per_trip"], weights=trips
    ))
    assert disbelieved == pytest.approx(round(just_the_toll, 3), abs=1e-9)


def test_efficacy_does_not_apply_after_operation(cfg, context):
    """Once it runs the effect is visible -- and `experience` already carries that.

    Applying the discount after operation too would count one phenomenon twice
    and break the Stockholm anchors the support coefficients were set against.
    """
    inc, segs = context
    shares = {
        e: political.support(
            inc, segs,
            Config.from_dict({**cfg.to_dict(), "charge_efficacy_belief": e}),
            operating=True,
        )["support_share"]
        for e in (0.0, 0.5, 1.0)
    }
    assert len(set(shares.values())) == 1, shares


def test_believing_the_charge_matters_more_than_believing_the_money(cfg, context):
    """The quantitative form of Manchester's lesson.

    If these were the same size the study would have no basis for saying the
    package was not the problem.
    """
    inc, segs = context
    e = political.efficacy_sensitivity(inc, segs, cfg)
    assert e["forecast_per_trip"] > 3 * e["promised_per_trip"]


def test_a_credible_package_cannot_rescue_an_incredible_charge(cfg, context):
    """Manchester with the money believed, which is the real case.

    The earlier package result got here by disbelieving the GBP 3bn. That was
    the right story for the wrong reason: the package was credible and the
    charge was not.
    """
    inc, segs = context
    result = political.manchester_test(inc, segs, cfg)
    assert result["revenue_trust_held_at"] == 1.0
    by_e = {s["charge_efficacy_belief"]: s for s in result["series"]}
    assert by_e[0.25]["any_package_passes"] is False
    assert by_e[1.00]["any_package_passes"] is True
    ceilings = [by_e[e]["ceiling"] for e in sorted(by_e)]
    assert ceilings == sorted(ceilings)


def test_trust_report_runs_the_recommended_design(cfg):
    """The end-to-end payload, since the API serves it directly."""
    report = political.trust_report(cfg)
    assert report["policy"]["peak_toll"] == 10.0
    assert 0.0 <= report["support_at_full_trust"] <= 1.0
    assert report["sensitivity"]["levels"]
    assert report["package"]["series"]
    assert "Edinburgh" in report["why_this_exists"]
