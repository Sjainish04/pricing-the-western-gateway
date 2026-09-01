"""Tests for the reversion model, and for the metric bug it uncovered.

The reversion module exists to close the highest-severity disagreement between
this study and the record: London's traffic reduction was permanent and its
delay reduction was not, which a static equilibrium cannot produce.

The first test here is not about reversion at all. Building the module needed a
scenario network and a baseline network to be scored separately, and that
exposed a bug in `metrics.compute` that had been understating every
capacity-improving scenario since the operational package was written. It is
pinned first because it is the more consequential of the two.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from uttan import congestion, metrics, network, reversion, scenarios, simulate
from uttan.config import Config
from uttan.demand import load_segments
from uttan.toll_policy import TollPolicy, apply_complements


@pytest.fixture(scope="module")
def cfg():
    return Config()


# --------------------------------------------------------------------------
# The baseline must be scored on the network the baseline actually ran on
# --------------------------------------------------------------------------

def test_a_capacity_improvement_is_not_charged_against_its_own_baseline(cfg):
    """Scoring both sides on the scenario's network hides the improvement.

    Every "against baseline" figure is a ratio. Evaluating baseline volumes on
    an improved network shrinks the denominator, so a scenario that adds
    capacity is charged for the improvement and credited with none of it.

    This understated the no-charge operational package by 11.2 points and
    reversed the study's finding that pricing beats good operations. It was
    invisible on most of the library because a pure-price scenario changes no
    capacity, so for those the two networks are the same object.
    """
    segs = load_segments(cfg)
    constants = simulate.calibrated(cfg)["constants"]
    hours = cfg.peak_end_h - cfg.peak_start_h

    links = network.load_links(hours, rejoin_fraction=cfg.rejoin_fraction)
    policy = scenarios.build("no_toll_package")
    base = congestion.solve(TollPolicy(peak_toll=0.0), segs, cfg,
                            links=links, constants=constants)
    eq = congestion.solve(policy, segs, cfg, links=links,
                          constants=constants, start=base.shares)
    scen_links = deepcopy(links)
    apply_complements(policy, scen_links, cfg)

    correct = metrics.compute(eq, base, scen_links, cfg, base_links=links)
    conflated = metrics.compute(eq, base, scen_links, cfg)

    # The package adds capacity, so conflating the two networks must understate
    # it. Pinned as a direction and a floor rather than a value.
    assert correct["delay_reduction_pct"] > conflated["delay_reduction_pct"] + 5.0

    # And a pure-price scenario must be untouched, because its two networks are
    # identical -- this is the half that let the bug survive.
    priced = scenarios.build("screenline_5")
    eq_p = congestion.solve(priced, segs, cfg, links=links,
                            constants=constants, start=base.shares)
    price_links = deepcopy(links)
    apply_complements(priced, price_links, cfg)
    assert (
        metrics.compute(eq_p, base, price_links, cfg, base_links=links)["delay_reduction_pct"]
        == metrics.compute(eq_p, base, price_links, cfg)["delay_reduction_pct"]
    )


def test_good_operations_now_outperforms_a_five_dollar_charge(cfg):
    """The corrected finding, pinned because it reverses a published one.

    The study previously reported the operational package removing ~34% of
    delay against ~36% for a $5 screenline charge -- pricing winning narrowly.
    Corrected, operations removes appreciably more. The study's conclusion is
    not that pricing is pointless but that it must be argued on revenue,
    durability and demand management rather than on delay alone.
    """
    ops = simulate.run(scenarios.build("no_toll_package"), cfg)["metrics"]
    charge = simulate.run(scenarios.build("screenline_5"), cfg)["metrics"]
    assert ops["delay_reduction_pct"] > charge["delay_reduction_pct"]
    # ...and the combination must still beat either alone, which is the actual
    # policy conclusion.
    both = simulate.run(scenarios.build("full_package"), cfg)["metrics"]
    assert both["delay_reduction_pct"] > ops["delay_reduction_pct"]


# --------------------------------------------------------------------------
# Reversion
# --------------------------------------------------------------------------

def test_the_trajectory_starts_at_the_static_answer(cfg):
    """Year 0 must be the number the rest of the study reports.

    If it is not, the trajectory is describing a different scenario and the
    reversion story would be attached to the wrong headline.
    """
    traj = reversion.trajectory(reallocation_share=0.0, years=2)
    static = simulate.run(reversion.recommended_policy(), cfg)["metrics"]
    assert traj["delay_reduction_year_0"] == pytest.approx(
        static["delay_reduction_pct"], abs=0.05
    )


def test_growth_alone_erodes_the_delay_benefit(cfg):
    """More trips on the same network must give back some of the reduction."""
    traj = reversion.trajectory(reallocation_share=0.0)
    delays = [r["delay_reduction_pct"] for r in traj["years"]]
    assert delays[-1] < delays[0]
    assert traj["years"][-1]["demand_index"] > 1.0


def test_reallocation_trades_delay_for_traffic(cfg):
    """The London asymmetry, which is the whole point of the module.

    Handing freed capacity to something else takes the delay benefit back while
    pushing MORE traffic off the road. Traffic down, delay reverting: that is
    what London recorded, and no static run can produce it.
    """
    none = reversion.trajectory(reallocation_share=0.0, years=5)
    lots = reversion.trajectory(reallocation_share=0.28, years=5)

    assert lots["delay_reduction_final"] < none["delay_reduction_final"]
    # More negative = more traffic removed.
    assert lots["traffic_change_final"] < none["traffic_change_final"]


def test_reallocation_defaults_to_zero_so_no_headline_moves(cfg):
    """The model must not assume Toronto gives the space away.

    Reallocation is a policy choice, not a physical law, so the default has to
    leave every existing result alone and the London figure has to be inverted
    rather than asserted.
    """
    assert cfg.space_reallocation_share == 0.0
    default = reversion.trajectory(years=1)
    explicit = reversion.trajectory(reallocation_share=0.0, years=1)
    assert default["delay_reduction_final"] == explicit["delay_reduction_final"]


@pytest.mark.slow
def test_the_london_match_is_reported_as_an_inversion(cfg):
    """It must report the share that reproduces London, not assume one."""
    match = reversion.reallocation_matching_london()
    assert match["london"]["years_to_revert"] == 5
    needed = match["reallocation_needed"]
    assert needed is None or 0.0 < needed <= 1.0
    # The sweep must be monotone: more reallocation cannot mean less reversion.
    delays = [c["delay_reduction_at_london_horizon"] for c in match["candidates"]]
    assert delays == sorted(delays, reverse=True)


@pytest.mark.slow
def test_report_separates_growth_from_reallocation(cfg):
    """The two mechanisms must stay distinguishable in the payload.

    Reporting a single reverted number would tell a Toronto reader that pricing
    wears off, when what London shows is that pricing converts congestion into
    road space that can then be given away.
    """
    rep = reversion.report(cfg)
    assert rep["growth_only"]["reallocation_share"] == 0.0
    assert "FIRST-YEAR" in rep["verdict"]
    assert rep["london_match"]["london"]["traffic_change_permanent"] is True
