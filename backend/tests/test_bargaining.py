"""Tests for the City/Province bargaining problem.

The load-bearing parts are the closed-form solution concepts and the
disagreement points. Both are easy to get wrong in ways that still return a
complete, plausible-looking deal -- this codebase's characteristic failure --
so these pin the algebra against cases with known answers and pin the
institutional asymmetry that drives the result.
"""
from __future__ import annotations

import pytest

from uttan import bargaining, datasets
from uttan.config import Config

# A stripped outcome for testing the payoff algebra in isolation: no benefit,
# no revenue, so only the political-cost and liability terms are live.
POLITICAL_ONLY = {
    "congestion_benefit_annual": 0.0,
    "net_revenue_annual": 0.0,
    "charged_trips_annual": 1_000_000.0,
}


@pytest.fixture(scope="module")
def cfg():
    return Config()


# --------------------------------------------------------------------------
# Geography: the asymmetry is derived, not assumed
# --------------------------------------------------------------------------

def test_constituency_shares_come_from_the_segment_table():
    c = bargaining.constituencies()
    assert c["toronto_share"] + c["non_toronto_share"] == pytest.approx(1.0)
    # 40% of corridor demand originates outside the city doing the charging.
    assert c["non_toronto_share"] == pytest.approx(0.40, abs=1e-6)


def test_province_bears_more_political_cost_than_the_city(cfg):
    """The mechanism the whole result rests on.

    Same charge, same trips: the Province answers to the 905 travellers as well
    as the Toronto ones, and weights them higher because those are the seats
    that decide provincial majorities.
    """
    cons = bargaining.constituencies()
    terms = bargaining.payoffs(POLITICAL_ONLY, 0.5, "pre_transfer", cfg, cons)["terms"]
    assert terms["province_political_cost"] > terms["city_political_cost"]


def test_removing_the_marginal_seat_weight_removes_the_extra_weighting(cfg):
    """With the weight at 1 the Province still bears more, but only because its
    electorate is larger -- not because a 905 vote counts for more."""
    flat = Config.from_dict({**cfg.to_dict(), "province_marginal_weight": 1.0})
    cons = bargaining.constituencies()
    t = bargaining.payoffs(POLITICAL_ONLY, 0.5, "pre_transfer", flat, cons)["terms"]
    assert t["province_political_cost"] == pytest.approx(
        t["city_political_cost"] / cons["toronto_share"], rel=1e-9
    )


# --------------------------------------------------------------------------
# Solution concepts, against cases with known answers
# --------------------------------------------------------------------------

def test_symmetric_nash_splits_a_symmetric_problem_evenly():
    """Identical fallbacks and identical stakes must give exactly half."""
    s = bargaining.nash_split(a_city=0.0, a_prov=0.0, revenue=100.0,
                              d_city=-50.0, d_prov=-50.0, alpha=0.5)
    assert s == pytest.approx(0.5)


def test_nash_favours_the_stronger_player():
    kw = dict(a_city=0.0, a_prov=0.0, revenue=100.0, d_city=-50.0, d_prov=-50.0)
    weak = bargaining.nash_split(**kw, alpha=0.2)
    even = bargaining.nash_split(**kw, alpha=0.5)
    strong = bargaining.nash_split(**kw, alpha=0.8)
    assert weak < even < strong


def test_nash_favours_the_player_with_the_better_fallback():
    """A better outside option must buy a larger share, all else equal."""
    base = bargaining.nash_split(0.0, 0.0, 100.0, -50.0, -50.0, 0.5)
    better_city = bargaining.nash_split(0.0, 0.0, 100.0, -20.0, -50.0, 0.5)
    assert better_city > base


def test_no_solution_when_nobody_can_be_made_better_off():
    """Fallbacks too good for the surplus to cover: there is no deal, and the
    honest return is None rather than a clipped corner that looks like one."""
    assert bargaining.nash_split(0.0, 0.0, 1.0, 500.0, 500.0, 0.5) is None
    assert bargaining.kalai_smorodinsky_split(0.0, 0.0, 1.0, 500.0, 500.0) is None


def test_kalai_smorodinsky_is_symmetric_too():
    s = bargaining.kalai_smorodinsky_split(0.0, 0.0, 100.0, -50.0, -50.0)
    assert s == pytest.approx(0.5)


@pytest.mark.slow
def test_both_solution_concepts_lie_inside_the_bargaining_set(cfg):
    r = bargaining.solve(cfg, "pre_transfer")
    lo = r["bargaining_set"]["city_share_min"]
    hi = r["bargaining_set"]["city_share_max"]
    for concept in ("nash", "kalai_smorodinsky"):
        if r[concept] is not None:
            assert lo - 1e-9 <= r[concept]["city_share"] <= hi + 1e-9


# --------------------------------------------------------------------------
# The institutional result
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_the_transfer_gives_the_province_a_unilateral_option(cfg):
    """Before 2027 neither side can charge the Gardiner alone; after, one can.

    This is the entire content of the regime distinction. If the two fallbacks
    ever come out identical, the model has stopped representing the transfer.
    """
    pre = bargaining.solve(cfg, "pre_transfer")["disagreement"]
    post = bargaining.solve(cfg, "post_transfer")["disagreement"]
    assert pre["province_fallback"] != post["province_fallback"]
    # The City's fallback is unchanged: it gains no new instrument at all.
    assert pre["city_fallback"] == post["city_fallback"]


@pytest.mark.slow
def test_province_unilateral_option_diverts_onto_city_streets(cfg):
    """The exposure the City loses standing over.

    The Province's post-transfer fallback is a freeway-only charge, which this
    study finds breaches the local-street diversion cap -- and those streets
    are the City's.
    """
    post = bargaining.solve(cfg, "post_transfer")["disagreement"]
    assert post["province_fallback_diversion_pct"] > 100 * cfg.max_diversion_increase


@pytest.mark.slow
def test_the_city_does_not_gain_leverage_from_the_transfer(cfg):
    """Its surplus must not rise: it acquires no instrument and loses an asset."""
    c = bargaining.compare_regimes(cfg)
    assert c["city_surplus_change"] <= 0


def test_repair_liability_is_carried_but_cancels_out_of_the_split(cfg):
    """A lump sum shifts deal and no-deal payoffs equally, so it cannot move the
    bargain. Pinned because an earlier version put the transfer's whole effect
    in this term, where it silently did nothing."""
    cons = bargaining.constituencies()
    pre = bargaining.payoffs(POLITICAL_ONLY, 0.5, "pre_transfer", cfg, cons)["terms"]
    post = bargaining.payoffs(POLITICAL_ONLY, 0.5, "post_transfer", cfg, cons)["terms"]
    assert pre["city_liability"] > 0
    assert post["city_liability"] == 0        # relieved by the upload
    assert post["province_liability"] > pre["province_liability"]


@pytest.mark.slow
def test_bargaining_power_does_not_create_or_destroy_a_deal(cfg):
    """Power divides a surplus; it does not decide whether one exists.

    Whether a zone of agreement exists is set by the fallbacks alone, so it must
    be invariant to alpha.
    """
    rows = bargaining.power_sensitivity(cfg)["rows"]
    assert len({r["has_zone_of_agreement"] for r in rows}) == 1
    shares = [r["city_share"] for r in rows if r["city_share"] is not None]
    assert shares == sorted(shares)


@pytest.mark.slow
def test_breakeven_political_cost_is_above_the_assumed_rate(cfg):
    """At the assumed rate a deal exists, so the threshold must sit above it.

    The Province refused in 2017, which on this model puts its true valuation
    above the threshold -- a revealed-preference bound rather than a fit.
    """
    b = bargaining.breakeven_political_cost(cfg)
    assert b["threshold_per_charged_trip"] > cfg.political_cost_per_charged_trip


def test_the_2017_precedent_is_carried_with_provenance():
    p = bargaining.precedent()
    assert "32-9" in p["council_vote"]
    assert p["side_payment_annual"] == datasets.governance_value("side_payment_accepted")
    assert p["caveat"]


# --------------------------------------------------------------------------
# Side payments: the instrument the 2017 negotiation actually used
# --------------------------------------------------------------------------

def test_total_surplus_is_invariant_to_the_revenue_split(cfg):
    """The defining property of a transferable-utility problem.

    Moving a dollar between the two leaves the sum unchanged, so whether a deal
    exists depends on the total and the split decides only who banks it. If
    this fails, the side-payment analysis is measuring an artefact of where the
    split happened to be evaluated.
    """
    cons = bargaining.constituencies()
    outcome = {"congestion_benefit_annual": 1.0e7, "net_revenue_annual": 5.0e6,
               "charged_trips_annual": 1.0e6}
    totals = []
    for split in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = bargaining.payoffs(outcome, split, "pre_transfer", cfg, cons)
        totals.append(p["city"] + p["province"])
    assert max(totals) - min(totals) < 1.0    # dollars, on sums of ~1e7


@pytest.mark.slow
def test_no_side_payment_is_needed_when_the_charge_is_jointly_worth_having(cfg):
    sp = bargaining.side_payment(cfg)
    assert sp["deal_exists_with_transfers"]
    assert sp["total_surplus_annual"] > 0
    assert sp["city_must_pay_province"] == 0


@pytest.mark.slow
def test_the_observed_side_payment_dwarfs_the_corridor_revenue(cfg):
    """Why arguing over the revenue split is arguing over the wrong number.

    The 2017 settlement moved about $170M/yr, against a corridor net revenue
    near $5.5M. If a future change ever brings these within an order of
    magnitude, the framing in METHODS 11a needs revisiting.
    """
    sp = bargaining.side_payment(cfg)
    assert sp["observed_vs_corridor_revenue"] > 10


@pytest.mark.slow
def test_a_high_enough_political_cost_makes_the_scheme_not_worth_doing(cfg):
    """Distinguish 'hard to agree on' from 'not worth doing'.

    A deal needing a transfer is still a deal. A negative total surplus is not:
    no split and no payment can make both sides prefer the charge.
    """
    curve = bargaining.side_payment_curve(cfg)
    pre = [r for r in curve["rows"] if r["regime"] == "pre_transfer"]
    assert any(r["deal_exists_with_transfers"] for r in pre)
    assert any(not r["deal_exists_with_transfers"] for r in pre)
    # Once the total surplus goes negative it must stay negative as the
    # political cost rises further; surplus falls monotonically in the rate.
    surpluses = [r["total_surplus_annual"] for r in pre]
    assert surpluses == sorted(surpluses, reverse=True)


@pytest.mark.slow
def test_the_transfer_becomes_more_favourable_as_political_cost_rises(cfg):
    """The counterintuitive half of the governance result, and it is a gradient.

    The relation is NOT a universal ordering, and asserting one is wrong. At a
    low political cost the Province's post-transfer fallback -- levying a
    freeway charge alone -- is genuinely valuable, so its outside option is
    better and the joint surplus from agreeing is smaller than before the
    transfer. At a high political cost that same fallback is a liability: the
    Province is exposed whether it agrees or not, so the cost of agreeing
    shrinks in difference terms and the post-transfer surplus overtakes.

    The property that holds throughout is the gradient: post-transfer improves
    relative to pre-transfer, monotonically, as the political cost rises. That
    crossover is why the joint game's timing recommendation reverses.
    """
    curve = bargaining.side_payment_curve(cfg)
    by_rate = {}
    for r in curve["rows"]:
        by_rate.setdefault(r["political_cost_per_charged_trip"], {})[r["regime"]] = r

    rates = sorted(by_rate)
    gaps = [
        by_rate[r]["post_transfer"]["total_surplus_annual"]
        - by_rate[r]["pre_transfer"]["total_surplus_annual"]
        for r in rates
    ]
    assert gaps == sorted(gaps), dict(zip(rates, gaps))
    # And it does cross over inside the swept range, or there is no reversal
    # for the joint game to find.
    assert gaps[0] < 0 < gaps[-1], dict(zip(rates, gaps))
