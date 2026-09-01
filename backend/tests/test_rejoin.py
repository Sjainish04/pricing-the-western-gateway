"""Tests for the rejoin fraction and its validation against the Gardiner record.

The rejoin fraction was hard-coded in routes.csv until now, which meant the
parameter the handover called the driver of the diversion result was the one
parameter the robustness machinery could not reach.  These tests pin the
properties that make it reachable and keep it honest: that the default is
bit-identical to the old hard-coded value, that moving it actually moves
results, that the BPR inversion is a true inverse, and that the flow
accounting refuses to report an absorption share above one.

Following the house style, they pin properties rather than output values --
except where a value IS the property, as with the default-equals-CSV check.
"""
from __future__ import annotations

import pytest

from uttan import network, rejoin_validation as rv, sensitivity, simulate
from uttan.config import Config
from uttan.demand import load_segments
from uttan.toll_policy import TollPolicy


@pytest.fixture(scope="module")
def cfg():
    return Config()


@pytest.fixture(scope="module")
def links(cfg):
    return network.load_links(3.0, rejoin_fraction=cfg.rejoin_fraction)


# --------------------------------------------------------------------------
# The parameter itself
# --------------------------------------------------------------------------

def test_config_default_matches_the_csv_exactly(cfg):
    """Promoting the fraction out of routes.csv must not move the baseline.

    If these ever diverge, every calibrated result shifts silently -- the alpha
    fit, the validation errors, the base volumes -- with nothing raising.
    """
    from_csv = network.base_link_volumes(None)
    from_config = network.base_link_volumes(cfg.rejoin_fraction)
    assert from_csv.keys() == from_config.keys()
    for lid in from_csv:
        assert from_csv[lid] == pytest.approx(from_config[lid], rel=1e-12)


def test_bypass_route_shares_sum_to_one_at_any_fraction():
    """A bypasser either rejoins or does not; the two branches cannot leak trips."""
    for r in (0.0, 0.25, 0.55, 0.8, 1.0):
        routes = network.route_composition(r)
        for alt in ("drive_lakeshore", "drive_queensway"):
            downstream = routes[alt]["gardiner_east"] + routes[alt]["lakeshore_east"]
            assert downstream == pytest.approx(1.0, abs=1e-12), (alt, r)


def test_rejoin_fraction_moves_traffic_between_downstream_links():
    """More rejoiners means more expressway and less arterial, monotonically."""
    east = [network.base_link_volumes(r)["gardiner_east"] for r in (0.2, 0.4, 0.6, 0.8)]
    arterial = [network.base_link_volumes(r)["lakeshore_east"] for r in (0.2, 0.4, 0.6, 0.8)]
    assert east == sorted(east)
    assert arterial == sorted(arterial, reverse=True)


@pytest.mark.slow
def test_rejoin_fraction_is_live_in_a_scored_outcome(cfg):
    """The regression test for the bug this work fixed.

    Before the fraction moved into Config it was unreachable from any sweep, so
    a sensitivity analysis would have reported it as mattering not at all. If
    this ever goes back to asserting-equal, the plumbing has been broken again.
    """
    policy = TollPolicy(peak_toll=4.0, coverage="gardiner_only", credit="none",
                        label="test")
    outcomes = []
    for r in (0.30, 0.80):
        trial = Config.from_dict({**cfg.to_dict(), "rejoin_fraction": r})
        result = simulate.run(policy, trial, load_segments(trial), full=False,
                              reference=cfg)
        outcomes.append(result["metrics"]["worst_diversion_pct"])
    assert abs(outcomes[0] - outcomes[1]) > 1.0, outcomes


def test_robustness_sweep_can_reach_the_rejoin_fraction():
    """It is named as the driver of the diversion result, so it must be swept."""
    assert "rejoin_fraction" in sensitivity.UNCERTAIN
    assert "rejoin_fraction" in Config().to_dict()


# --------------------------------------------------------------------------
# The BPR inversion
# --------------------------------------------------------------------------

def test_inversion_recovers_a_known_volume(links):
    """The analytic check: invert a ratio the curve itself produced.

    Take a volume, ask the curve for its travel time, form the ratio against
    base, invert it, and the original volume must come back. Without this the
    implied-volume figures are unfalsifiable.
    """
    link = links["gardiner_east"]
    hours, base = 3.0, links["gardiner_east"].base_volume_veh
    for target in (0.7 * base, 0.9 * base, 1.15 * base):
        ratio = link.travel_time(target, hours) / link.travel_time(base, hours)
        recovered = rv.implied_volume_ratio(link, ratio, hours, 1.0, "curve")
        assert recovered == pytest.approx(target / base, rel=1e-9)


def test_inversion_handles_a_capacity_reduction(links):
    """With capacity scaled by kappa, the inverse must undo exactly that too."""
    link, hours = links["gardiner_east"], 3.0
    base = link.base_volume_veh
    kappa, target = 0.667, 0.9 * base
    # Travel time the link would post carrying `target` on `kappa` of its lanes.
    treated = link.uncongested_minutes + link.free_flow_minutes * link.alpha * (
        target / (kappa * link.capacity(hours))
    ) ** link.beta
    ratio = treated / link.travel_time(base, hours)
    recovered = rv.implied_volume_ratio(link, ratio, hours, kappa, "curve")
    assert recovered == pytest.approx(target / base, rel=1e-9)


def test_inversion_is_undefined_rather_than_wrong(links):
    """A time below the uncongested floor has no BPR solution; say so, don't guess."""
    link = links["gardiner_east"]
    assert rv.implied_volume_ratio(link, 0.01, 3.0, 1.0) is None
    with pytest.raises(ValueError):
        rv.implied_volume_ratio(link, 1.5, 3.0, 1.0, baseline="nonsense")


def test_conditioning_flags_the_barely_congested_link(links):
    """lakeshore_east carries ~1 minute of queueing delay, so its inversion is fragile.

    This is asserted so the fragility stays visible in the output rather than
    being quietly averaged into a confident-looking volume figure.
    """
    weak = rv.conditioning(links["lakeshore_east"], 3.0)
    strong = rv.conditioning(links["gardiner_east"], 3.0)
    assert not weak["well_conditioned"]
    assert strong["well_conditioned"]
    assert abs(weak["baseline_disagreement_pct"]) > abs(
        strong["baseline_disagreement_pct"] or 0.0
    )


# --------------------------------------------------------------------------
# Flow accounting
# --------------------------------------------------------------------------

def test_absorption_share_never_exceeds_one():
    """The arterial cannot gain more vehicles than the expressway lost.

    A naive sweep over capacity assumptions produces shares above 1 on the
    combinations where the accounting cannot close, and an absorption share of
    3.8 reads like a finding rather than an arithmetic impossibility. Those
    combinations must be rejected, not reported.
    """
    d = rv.diversion_decomposition()
    assert d["available"]
    for row in d["rows"]:
        lo, hi = row["arterial_absorption_share_range"]
        assert 0.0 < lo <= hi <= 1.0, row
    assert d["absorption_share_range"][1] <= 1.0


def test_incoherent_capacity_assumptions_are_rejected_with_a_reason():
    d = rv.diversion_decomposition()
    assert d["rejected_combinations"], "no capacity assumption was screened out"
    for row in d["rejected_combinations"]:
        assert row["reason"]


def test_unchanged_capacity_cannot_explain_the_observed_slowdown():
    """An independent check on the City's announced lane reduction.

    If capacity had not fallen, a travel time that rose this much could only
    come from MORE traffic on a corridor everyone was avoiding. The largest
    capacity ratio consistent with the expressway losing traffic should
    therefore land near the announced 3-lanes-to-2.
    """
    inv = rv.section2_inversion()
    kappa_max = inv["max_capacity_ratio_consistent_with_traffic_loss"]
    assert kappa_max is not None
    assert kappa_max < 1.0
    assert kappa_max == pytest.approx(inv["announced_capacity_ratio"], abs=0.15)


# --------------------------------------------------------------------------
# Honesty of the reported conclusion
# --------------------------------------------------------------------------

def test_identification_does_not_claim_to_have_measured_the_fraction():
    """The record cannot identify this parameter, and the module must say so."""
    ident = rv.identification()
    assert ident["not_identified"]
    assert "ESTIMATED" in ident["conclusion"]


def test_every_natural_experiment_row_carries_provenance():
    from uttan import datasets

    rows = datasets.records(datasets.natural_experiments())
    assert rows
    for row in rows:
        assert row["tier"] in {"PUBLISHED", "DERIVED", "ESTIMATED"}
        assert row["source"]


@pytest.mark.slow
def test_switching_analysis_finds_the_freeway_only_cap_crossing(cfg):
    """The study's second headline finding depends on this unmeasured parameter.

    A $4 freeway-only charge is reported as breaching the local-street diversion
    cap. That claim is not robust across the plausible range of the rejoin
    fraction, and the test exists to make sure nobody quietly stops reporting
    that dependence.
    """
    s = rv.switching_analysis(cfg)
    flips = [x for x in s["switches"] if x["claim"] == "breaches the diversion cap"]
    assert flips, "expected the freeway-only diversion claim to be fraction-dependent"
    assert not s["robust"]
    # The recommended screenline design must NOT be one of the fragile ones.
    fragile = {x["policy"] for x in s["switches"]}
    assert not any("screenline" in label for label in fragile), fragile


@pytest.mark.slow
def test_breakeven_lies_below_the_assumed_fraction(cfg):
    """The margin is the finding's whole safety factor, so pin its sign."""
    b = rv.breakeven_rejoin_fraction(cfg)
    assert b["crossing"] is not None
    assert 0.0 < b["crossing"] < cfg.rejoin_fraction
    assert b["margin"] > 0
