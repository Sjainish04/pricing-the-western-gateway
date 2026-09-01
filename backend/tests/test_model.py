"""Tests for the corridor model.

These check the properties that would silently corrupt the policy conclusions
if they broke -- sign conventions, conservation, calibration fidelity and
monotonicity -- rather than pinning exact output values, which would just
freeze whatever the model happened to produce.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from uttan import (
    choice_model, congestion, datasets, equity, game, generalized_cost, metrics,
    network, political, scenarios, sensitivity, simulate, site_selection,
)
from uttan.config import ALTERNATIVES, BASE_SHARES, OCCUPANCY, Config
from uttan.demand import load_segments, value_of_time
from uttan.toll_policy import TollPolicy, credit_matrix, toll_matrix


@pytest.fixture(scope="module")
def cfg():
    return Config()


@pytest.fixture(scope="module")
def segs(cfg):
    return load_segments(cfg)


@pytest.fixture(scope="module")
def cal(cfg):
    return simulate.calibrated(cfg)


# --------------------------------------------------------------------------
# Data integrity
# --------------------------------------------------------------------------

def test_base_shares_sum_to_one():
    assert abs(sum(BASE_SHARES.values()) - 1.0) < 1e-9


def test_records_emit_no_nan_in_any_served_table():
    """Every table the API serves must survive a strict JSON round-trip.

    `json.dumps` writes a bare `NaN` for a float nan and `JSON.parse` rejects
    it, so a missing cell reaching a response body is a broken page rather than
    a wrong number.  Pinned as a property over the real tables because the ones
    with gaps are the interesting ones -- a scheme with no published Suits
    index, an episode with no model link -- and the guard that used to do this
    (`df.where(pd.notna(df), None)`) silently stopped working in pandas 3.0.
    """
    tables = {
        "sources": datasets.sources(),
        "network": datasets.network().reset_index(),
        "routes": datasets.routes(),
        "segments": datasets.segments(),
        "gateways": datasets.gateways(),
        "criteria": datasets.criteria(),
        "gantries": datasets.gantries(),
        "transit_stations": datasets.transit_stations(),
        "benchmarks": datasets.benchmarks(),
        "city_schemes": datasets.city_schemes(),
        "governance": datasets.governance(),
        "natural_experiments": datasets.natural_experiments(),
    }
    gappy = [n for n, df in tables.items() if df.isna().to_numpy().any()]
    assert gappy, "no table has a missing cell -- this test would prove nothing"

    for name, df in tables.items():
        rows = datasets.records(df)
        # allow_nan=False is the whole assertion: it raises on nan/inf.
        json.dumps(rows, allow_nan=False), name
        for row in rows:
            for key, value in row.items():
                assert not (isinstance(value, float) and math.isnan(value)), (
                    f"{name}.{key} came back as nan rather than None"
                )


def test_segment_shares_sum_to_one(segs):
    assert abs(segs.share.sum() - 1.0) < 1e-9
    assert segs.n == 70


def test_every_alternative_has_occupancy_and_share():
    assert set(OCCUPANCY) == set(ALTERNATIVES)
    assert set(BASE_SHARES) == set(ALTERNATIVES)


def test_base_link_volumes_match_observed_counts():
    """The derived link volumes must reproduce the counts the model calibrates to."""
    v = network.base_link_volumes()
    assert v["gardiner_west"] == pytest.approx(14256, rel=1e-3)
    assert v["lakeshore_west"] == pytest.approx(4180, rel=1e-3)
    assert v["queensway_west"] == pytest.approx(2560, rel=1e-3)
    # The shared downstream link carries through traffic plus the rejoiners.
    assert v["gardiner_east"] > v["gardiner_west"]


# --------------------------------------------------------------------------
# Link performance
# --------------------------------------------------------------------------

def test_travel_time_rises_with_volume():
    link = network.load_links()["gardiner_west"]
    times = [link.travel_time(v, 3.0) for v in (0, 5000, 10000, 14000, 18000)]
    assert times == sorted(times)
    assert times[0] == pytest.approx(link.uncongested_minutes)


def test_marginal_time_is_the_derivative():
    """Analytic dt/dv must match a numerical difference, or the Pigouvian toll is wrong."""
    link = network.load_links()["gardiner_west"]
    v, h, eps = 12000.0, 3.0, 1.0
    numeric = (link.travel_time(v + eps, h) - link.travel_time(v - eps, h)) / (2 * eps)
    assert link.marginal_time(v, h) == pytest.approx(numeric, rel=1e-4)


def test_calibrated_links_reproduce_observed_times():
    for row in network.validate():
        if row["role"] == "calibrated":
            assert abs(row["error_pct"]) < 1e-6, row


def test_held_out_links_validate_within_tolerance():
    """The transferred arterial alpha must predict the held-out links reasonably."""
    held = [r for r in network.validate() if r["role"] == "held out"]
    assert held, "expected out-of-sample links"
    for row in held:
        assert abs(row["error_pct"]) < 15.0, row


# --------------------------------------------------------------------------
# Choice model
# --------------------------------------------------------------------------

def test_probabilities_sum_to_one(cfg, segs):
    gc = np.random.default_rng(0).uniform(20, 80, size=(segs.n, len(ALTERNATIVES)))
    p = choice_model.probabilities(gc, np.zeros(len(ALTERNATIVES)), cfg)
    assert np.allclose(p.sum(axis=1), 1.0)


def test_cheaper_alternative_gains_share(cfg, segs):
    gc = np.full((segs.n, len(ALTERNATIVES)), 50.0)
    base = choice_model.probabilities(gc, np.zeros(len(ALTERNATIVES)), cfg)
    gc2 = gc.copy()
    gc2[:, 0] -= 10.0
    after = choice_model.probabilities(gc2, np.zeros(len(ALTERNATIVES)), cfg)
    assert after[:, 0].mean() > base[:, 0].mean()


def test_nesting_concentrates_substitution(cfg, segs):
    """Within-nest substitution must exceed cross-nest substitution.

    This is the property that plain multinomial logit lacks, and the reason the
    model uses nesting: without it, a driver priced off the Gardiner is as
    likely to board a train as to divert onto Lake Shore.
    """
    gc = np.full((segs.n, len(ALTERNATIVES)), 50.0)
    zeros = np.zeros(len(ALTERNATIVES))
    base = choice_model.probabilities(gc, zeros, cfg)
    bumped = gc.copy()
    bumped[:, ALTERNATIVES.index("drive_gardiner")] += 8.0
    after = choice_model.probabilities(bumped, zeros, cfg)

    gain_same_nest = after[:, ALTERNATIVES.index("drive_lakeshore")].mean() - base[
        :, ALTERNATIVES.index("drive_lakeshore")].mean()
    gain_other_nest = after[:, ALTERNATIVES.index("go_rail")].mean() - base[
        :, ALTERNATIVES.index("go_rail")].mean()
    assert gain_same_nest > gain_other_nest > 0


def test_value_of_time_rises_with_income_and_has_a_floor(cfg):
    income = np.array([10_000.0, 50_000.0, 200_000.0])
    vot = value_of_time(income, cfg)
    assert vot[0] < vot[1] < vot[2]
    assert vot[0] * 60 >= cfg.vot_floor_per_hour - 1e-9


# --------------------------------------------------------------------------
# Equilibrium and calibration
# --------------------------------------------------------------------------

def test_calibration_reproduces_observed_shares(cal):
    """Fitted shares must match the observed split.

    The tolerance is 5e-4 in share (0.05 percentage points) because the final
    equilibrium is solved to the SUE convergence tolerance, which bounds how
    exactly the published shares can sit on their targets.  The fitting loop
    itself converges several orders tighter.
    """
    info = cal["info"]
    assert info["converged"]
    assert info["fit_loop_error"] < 1e-6
    for alt, target in info["target_shares"].items():
        assert info["fitted_shares"][alt] == pytest.approx(target, abs=5e-4)


def test_equilibrium_converges(cfg, segs, cal):
    eq = congestion.solve(TollPolicy(peak_toll=5.0), segs, cfg, constants=cal["constants"])
    assert eq.converged
    assert eq.gap < cfg.convergence_epsilon


def test_person_trips_are_conserved(cfg, segs, cal):
    eq = congestion.solve(TollPolicy(peak_toll=6.0), segs, cfg, constants=cal["constants"])
    assert eq.market_shares.sum() == pytest.approx(1.0)
    assert np.allclose(eq.shares.sum(axis=1), 1.0)


def test_scenario_does_not_leak_into_the_next(cfg, segs, cal):
    """Complements mutate link capacity; a later run must not inherit that."""
    K = cal["constants"]
    plain_first = congestion.solve(TollPolicy(peak_toll=4.0), segs, cfg, constants=K)
    congestion.solve(
        TollPolicy(peak_toll=4.0, adaptive_signals=True, ramp_metering=True),
        segs, cfg, constants=K,
    )
    plain_after = congestion.solve(TollPolicy(peak_toll=4.0), segs, cfg, constants=K)
    assert plain_after.peak_volumes["gardiner_west"] == pytest.approx(
        plain_first.peak_volumes["gardiner_west"], rel=1e-9
    )


# --------------------------------------------------------------------------
# Policy response
# --------------------------------------------------------------------------

def test_higher_toll_reduces_charged_volume(cfg, segs, cal):
    K = cal["constants"]
    volumes = [
        congestion.solve(TollPolicy(peak_toll=t), segs, cfg, constants=K)
        .peak_volumes["gardiner_west"]
        for t in (0, 2, 4, 6, 8)
    ]
    assert volumes == sorted(volumes, reverse=True)


def test_freeway_only_charge_pushes_traffic_onto_the_bypass(cfg, segs, cal):
    """Charging the expressway alone must show diversion, not hide it."""
    K = cal["constants"]
    base = congestion.solve(TollPolicy(peak_toll=0.0), segs, cfg, constants=K)
    tolled = congestion.solve(
        TollPolicy(peak_toll=6.0, coverage="gardiner_only"), segs, cfg, constants=K
    )
    assert tolled.peak_volumes["lakeshore_west"] > base.peak_volumes["lakeshore_west"]
    assert tolled.peak_volumes["queensway_west"] > base.peak_volumes["queensway_west"]


def test_screenline_coverage_removes_the_diversion(cfg, segs, cal):
    """Pricing every crossing should stop the arterial being a free bypass."""
    K = cal["constants"]
    base = congestion.solve(TollPolicy(peak_toll=0.0), segs, cfg, constants=K)
    screen = congestion.solve(
        TollPolicy(peak_toll=6.0, coverage="screenline"), segs, cfg, constants=K
    )
    assert screen.peak_volumes["lakeshore_west"] < base.peak_volumes["lakeshore_west"]


def test_toll_is_levied_per_vehicle_not_per_person(cfg, segs):
    """Every charged movement must imply the same per-vehicle charge.

    Generalized cost is per person while the charge is per vehicle, so each
    alternative's per-person toll has to be the vehicle rate divided by its
    occupancy.  Dividing only for carpools over-collects 15% on the
    1.15-occupancy arterial routes, which inflates revenue and makes bypassing
    look dearer than it is -- understating diversion.
    """
    rate = 6.0
    t = toll_matrix(TollPolicy(peak_toll=rate, coverage="screenline"), segs, cfg)
    for alt in ("drive_gardiner", "drive_lakeshore", "drive_queensway", "carpool_gardiner"):
        per_person = t[0, ALTERNATIVES.index(alt)]
        assert per_person * OCCUPANCY[alt] == pytest.approx(rate), alt


def test_average_collected_charge_matches_the_posted_rate(cfg):
    """Revenue divided by charged vehicles must equal the posted charge."""
    rate = 5.0
    result = simulate.run(
        TollPolicy(peak_toll=rate, coverage="screenline", credit="none"), cfg, full=False
    )
    assert result["finance"]["average_charge_per_vehicle"] == pytest.approx(rate, rel=1e-3)


def test_carpool_friction_limits_occupancy_growth(cfg, segs, cal):
    """Without matching friction the model answers any toll by inventing carpools."""
    K = cal["constants"]
    eq = congestion.solve(TollPolicy(peak_toll=10.0), segs, cfg, constants=K)
    growth = eq.share_of("carpool_gardiner") / BASE_SHARES["carpool_gardiner"]
    assert 1.0 < growth < 2.5, f"carpool share grew {growth:.2f}x under a $10 charge"


def test_credit_never_exceeds_the_charge(cfg, segs):
    for mechanism in ("low_income", "low_income_transit_poor", "shift_worker",
                      "monthly_cap", "targeted_package"):
        policy = TollPolicy(peak_toll=6.0, coverage="screenline", credit=mechanism)
        t = toll_matrix(policy, segs, cfg)
        c = credit_matrix(policy, segs, cfg)
        charged = [ALTERNATIVES.index(a) for a in
                   ("drive_gardiner", "drive_lakeshore", "drive_queensway", "carpool_gardiner")]
        assert (c[:, charged] <= t[:, charged] + 1e-9).all(), mechanism


def test_transit_crowding_penalty_engages_beyond_capacity(cfg):
    assert generalized_cost.crowding_cost(1000, 10_000, cfg) == 0.0
    mild = generalized_cost.crowding_cost(9_000, 10_000, cfg)
    heavy = generalized_cost.crowding_cost(11_000, 10_000, cfg)
    assert 0 < mild < heavy


# --------------------------------------------------------------------------
# Equity
# --------------------------------------------------------------------------

def test_suits_index_sign_convention():
    """A charge on the poor must be negative, on the rich positive.

    The sign here decides whether the study reports the charge as regressive or
    progressive, so it is worth pinning down explicitly.
    """
    income = np.array([20_000.0, 50_000.0, 100_000.0, 200_000.0])
    w = np.ones(4)
    assert equity.suits_index(np.array([400.0, 0, 0, 0]), income, w) < -0.5
    assert equity.suits_index(np.array([0, 0, 0, 400.0]), income, w) > 0.3
    assert equity.suits_index(np.array([100.0] * 4), income, w) < 0      # flat is regressive
    assert equity.suits_index(income * 0.01, income, w) == pytest.approx(0.0, abs=1e-9)


def test_suits_index_is_tie_order_invariant():
    """Segments tied on income must not be able to change the answer.

    Income is a quintile here, so all 70 segments arrive in five 14-way ties
    while carrying very different burdens.  The index used to walk them one at
    a time under `np.argsort`, whose default quicksort is unstable -- so the
    headline moved with the order numpy happened to produce, and moved between
    numpy versions.  Over the real segments that ambiguity was worth 0.045 to
    0.089 of index, wider than the gaps between the published benchmarks this
    study ranks itself against, and it reordered the equity packages against
    each other.

    Pinned as invariance rather than a value: the property is what makes the
    number mean anything, and a pinned value would not have caught the bug.
    """
    rng = np.random.default_rng(0)
    income = np.repeat([24_000.0, 45_000.0, 70_000.0, 110_000.0, 215_000.0], 14)
    burden = rng.random(income.size) * 4_000.0     # varies WITHIN each tie group
    weights = rng.random(income.size)

    reference = equity.suits_index(burden, income, weights)
    for _ in range(50):
        p = rng.permutation(income.size)
        assert equity.suits_index(burden[p], income[p], weights[p]) == pytest.approx(
            reference, abs=1e-12
        )

    # The curve is built from the same points, so it must be invariant too.
    curve = equity.suits_curve(burden, income, weights)
    p = rng.permutation(income.size)
    assert equity.suits_curve(burden[p], income[p], weights[p]) == curve


def test_flat_charge_is_regressive_in_burden(cfg):
    result = simulate.run(
        TollPolicy(peak_toll=6.0, coverage="screenline", credit="none"), cfg, full=False
    )
    assert result["equity"]["burden_ratio_q1_q5"] > 1.0


def test_credits_improve_the_equity_score(cfg):
    plain = simulate.run(
        TollPolicy(peak_toll=5.0, coverage="screenline", credit="none"), cfg, full=False
    )
    targeted = simulate.run(
        TollPolicy(peak_toll=5.0, coverage="screenline", credit="targeted_package"),
        cfg, full=False,
    )
    assert targeted["equity"]["equity_score"] > plain["equity"]["equity_score"]


def test_untolled_baseline_has_no_burden(cfg):
    result = simulate.run(TollPolicy(peak_toll=0.0), cfg, full=False)
    assert result["equity"]["equity_score"] == 1.0
    assert result["finance"]["net_revenue_annual"] == 0.0
    assert result["finance"]["gross_revenue_annual"] == 0.0


def test_parking_surcharge_counts_as_a_charge(cfg):
    """A destination levy is paid by somebody and raises revenue.

    If it were left out of both accounts, the model would report congestion
    relief at no cost to anyone and recommend it for the wrong reason.
    """
    result = simulate.run(
        TollPolicy(peak_toll=0.0, parking_surcharge=10.0), cfg, full=False
    )
    assert result["finance"]["gross_revenue_annual"] > 0
    assert result["equity"]["equity_score"] < 1.0


# --------------------------------------------------------------------------
# Game theory
# --------------------------------------------------------------------------

def test_pigouvian_toll_is_positive_and_ordered(cfg, segs, cal):
    p = game.pigouvian_toll(cal["equilibrium"], segs, cfg)
    assert p["first_best_toll_charged_segment"] > 0
    # The busier shared link carries more external cost than the charged one.
    by_link = p["by_link"]
    assert by_link["gardiner_east"]["marginal_external_cost"] > \
           by_link["queensway_west"]["marginal_external_cost"]


def test_price_of_anarchy_exceeds_one(cfg, segs, cal):
    so = game.social_optimum(cfg, segs, cal["constants"], tolls=[0, 5, 10, 15, 20])
    assert so["price_of_anarchy"] >= 1.0
    assert so["optimal_uniform_toll"] > 0


def test_system_cost_excludes_the_toll_transfer(cfg, segs, cal):
    """A charge moves money, it does not consume resources.

    If the transfer were counted as a cost, every priced scenario would look
    worse automatically and the social optimum would always be a zero charge.
    """
    K = cal["constants"]
    free = congestion.solve(TollPolicy(peak_toll=0.0), segs, cfg, constants=K)
    priced = congestion.solve(
        TollPolicy(peak_toll=15.0, coverage="screenline"), segs, cfg, constants=K
    )
    assert game.system_cost(priced, segs, cfg) < game.system_cost(free, segs, cfg)


def test_pareto_frontier_members_are_not_dominated():
    rows = scenarios.compare(["baseline", "flat_4", "flat_8", "screenline_5",
                              "targeted_package", "no_toll_package"])
    frontier = rows["pareto_frontier"]
    objectives = ("delay_reduction_pct", "equity_score", "net_revenue_annual")
    for row in frontier:
        for other in rows["scenarios"]:
            strictly_better = all(other[o] >= row[o] for o in objectives) and any(
                other[o] > row[o] for o in objectives
            )
            assert not strictly_better, f"{row['label']} dominated by {other['label']}"


# --------------------------------------------------------------------------
# Site selection
# --------------------------------------------------------------------------

def test_gateway_screening_is_robust_to_weights():
    report = site_selection.report(n_draws=1500)
    assert report["selected"]["gateway_id"] == "gardiner_west"
    assert report["selected"]["win_probability"] > 0.5
    assert report["methods_agree"]


def test_weight_probabilities_sum_to_one():
    sens = site_selection.weight_sensitivity(n_draws=800)
    total = sum(r["win_probability"] for r in sens["results"])
    assert total == pytest.approx(1.0, abs=1e-6)


def test_lower_is_better_criteria_are_inverted():
    """Diversion risk and equity exposure must not reward the worst candidate."""
    ranked = site_selection.score()["ranking"]
    worst_diversion = max(ranked, key=lambda r: r["criteria"]["diversion_risk"]["raw"])
    assert worst_diversion["criteria"]["diversion_risk"]["normalised"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------

def test_full_run_is_internally_consistent(cfg):
    result = simulate.run(
        TollPolicy(peak_toll=5.0, coverage="screenline", credit="targeted_package"), cfg
    )
    m, f = result["metrics"], result["finance"]
    assert result["convergence"]["converged"]
    assert 0 <= result["equity"]["equity_score"] <= 1
    assert f["gross_revenue_annual"] > 0
    assert m["peak_entering_vehicles"] < m["peak_entering_vehicles_base"]
    # Mode shares must still be a distribution.
    assert sum(m["mode_shares"].values()) == pytest.approx(1.0, abs=1e-6)
    # The Sankey attribution cannot invent or lose trips.
    if result["sankey"]["flows"]:
        assert sum(x["value"] for x in result["sankey"]["flows"]) == pytest.approx(
            result["sankey"]["total"], rel=1e-3
        )


def test_no_toll_package_is_a_real_counterfactual(cfg):
    """The operational package must actually do something, or the comparison is empty."""
    result = simulate.run(scenarios.build("no_toll_package"), cfg, full=False)
    assert result["metrics"]["delay_reduction_pct"] > 5.0
    assert result["policy"]["peak_toll"] == 0.0


def test_equilibrium_is_independent_of_starting_point(cfg, segs, cal):
    """Warm-starting must reach the same fixed point as a flat start.

    The solver is warm-started from the calibrated baseline for speed.  That is
    only legitimate if the equilibrium is genuinely a fixed point rather than an
    artefact of where the iteration began.
    """
    import numpy as np

    K = cal["constants"]
    policy = TollPolicy(peak_toll=7.0, coverage="screenline", credit="targeted_package")
    flat = congestion.solve(policy, segs, cfg, constants=K)
    warm = congestion.solve(
        policy, segs, cfg, constants=K, start=cal["equilibrium"].shares
    )
    for link in flat.peak_volumes:
        assert warm.peak_volumes[link] == pytest.approx(flat.peak_volumes[link], rel=2e-3), link
    assert np.allclose(warm.market_shares, flat.market_shares, atol=1e-3)


@pytest.mark.slow
def test_sensitivity_holds_constants_fixed(cfg):
    """A perturbed parameter must actually move the base split.

    If the choice constants were re-fitted for each draw they would move to
    whatever value reproduces the observed shares under the new parameter, the
    baseline would be identical every time, and the sensitivity analysis would
    report almost no sensitivity at all.
    """
    perturbed = Config.from_dict({**cfg.to_dict(), "vot_base_per_hour": cfg.vot_base_per_hour * 1.5})

    _, base_fixed = simulate.context(perturbed, reference=cfg)
    _, base_refit = simulate.context(perturbed, reference=None)

    idx = ALTERNATIVES.index("drive_gardiner")
    assert abs(base_fixed.market_shares[idx] - BASE_SHARES["drive_gardiner"]) > 1e-3, (
        "holding constants fixed should let the parameter move the base split"
    )
    assert base_refit.market_shares[idx] == pytest.approx(
        BASE_SHARES["drive_gardiner"], abs=1e-3
    ), "re-fitting should snap the base split back onto the observed target"


@pytest.mark.slow
def test_tornado_finds_value_of_time_influential(cfg):
    """The value of time should be among the parameters that matter most."""
    result = sensitivity.tornado(cfg=cfg)
    top = [r["parameter"] for r in result["parameters"][:4]]
    assert "vot_base_per_hour" in top, top
    assert all(r["effects"]["delay_reduction_pct"]["swing"] >= 0 for r in result["parameters"])


# --------------------------------------------------------------------------
# Welfare incidence, deeper equity, and the political layer
# --------------------------------------------------------------------------

def test_consumer_surplus_matches_a_known_answer(cfg, segs):
    """A uniform cost increase must cost exactly that much surplus.

    If every option gets $5 dearer there is nothing to substitute toward, so
    the compensating variation is exactly -$5. This pins the welfare measure
    against a case with an analytic answer.
    """
    zeros = np.zeros(len(ALTERNATIVES))
    gc = np.full((segs.n, len(ALTERNATIVES)), 50.0)
    delta = choice_model.consumer_surplus_change(gc + 5.0, gc, zeros, cfg)
    assert np.allclose(delta, -5.0, atol=1e-9)

    # Making one option cheaper is worth something, but less than the discount,
    # because not everybody was using that option.
    better = gc.copy()
    better[:, 0] -= 5.0
    gain = choice_model.consumer_surplus_change(better, gc, zeros, cfg)
    assert np.all((gain > 0) & (gain < 5.0))


def test_welfare_incidence_reconciles_with_its_components(cfg):
    """surplus = resource - tolls, and net = surplus + recycling, by construction."""
    result = simulate.run(
        TollPolicy(peak_toll=8.0, coverage="screenline", credit="none"), cfg
    )
    for row in result["incidence"]["welfare_by_quintile"]:
        assert row["resource_per_trip"] == pytest.approx(
            row["surplus_per_trip"] + row["tolls_per_trip"], abs=1e-2
        ), row
        assert row["net_per_trip"] == pytest.approx(
            row["surplus_per_trip"] + row["recycled_per_trip"], abs=1e-2
        ), row


def test_flat_charge_is_regressive_in_welfare_not_just_in_tolls(cfg):
    """The lowest quintile must lose more of its income than the highest.

    Eliasson's finding: high-income travellers pay more in absolute terms, but
    low-income travellers lose a larger share of income. Both must hold, and a
    model that only reports the first would call a flat charge progressive.
    """
    result = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="none"), cfg
    )
    rows = {r["quintile"]: r for r in result["incidence"]["welfare_by_quintile"]}
    # Absolute payment rises with income...
    assert rows["Q5"]["tolls_per_trip"] > rows["Q1"]["tolls_per_trip"]
    # ...while the welfare loss as a share of income falls with income.
    assert rows["Q1"]["surplus_pct_income"] < rows["Q5"]["surplus_pct_income"]
    assert result["incidence"]["regressive_before_recycling"]


def test_means_testing_reverses_the_burden(cfg):
    """The San Francisco design should protect the bottom of the distribution."""
    flat = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="none"), cfg
    )
    tested = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="means_tested"), cfg
    )
    q1_flat = next(r for r in flat["incidence"]["welfare_by_quintile"] if r["quintile"] == "Q1")
    q1_test = next(r for r in tested["incidence"]["welfare_by_quintile"] if r["quintile"] == "Q1")
    assert q1_test["tolls_per_trip"] < q1_flat["tolls_per_trip"]
    assert q1_test["surplus_pct_income"] > q1_flat["surplus_pct_income"]
    assert not tested["incidence"]["regressive_before_recycling"]


def test_recycling_is_capped_below_face_value(cfg):
    """Corridor travellers must not be credited with the whole regional benefit.

    Crediting every dollar of net revenue back to the 40,000 people who cross
    this screenline would make any revenue-positive scheme a Pareto improvement
    on paper, which is an artefact of the accounting, not a finding.
    """
    result = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="none"), cfg
    )
    inc = result["incidence"]
    assert inc["capture_share"] < 1.0
    assert inc["captured_revenue_annual"] <= result["finance"]["net_revenue_annual"]
    # Before revenue comes back, a charge cannot make everybody better off.
    assert inc["winners_share_before_recycling"] < inc["winners_share"]


def test_burden_concentration_finds_the_hurt_subgroup(cfg):
    """Averages hide the people a scheme actually harms."""
    result = simulate.run(
        TollPolicy(peak_toll=12.0, coverage="screenline", credit="none"), cfg
    )
    conc = result["incidence"]["burden_concentration"]
    rows = {r["quintile"]: r for r in conc["by_quintile"]}
    # A charge this size must put a bigger share of Q1 over 1% of income than Q5.
    assert rows["Q1"]["share_above_0.01"] > rows["Q5"]["share_above_0.01"]


def test_steps_reports_unmodelled_dimensions_honestly(cfg):
    """Physiological and Social must be declared unmodelled, not scored as passes."""
    result = simulate.run(TollPolicy(peak_toll=6.0, coverage="screenline"), cfg)
    steps = {s["dimension"]: s for s in result["incidence"]["steps"]}
    assert steps["Physiological"]["modelled"] is False
    assert steps["Social"]["modelled"] is False
    assert steps["Spatial"]["modelled"] is True
    for name in ("Physiological", "Social"):
        assert steps[name]["verdict"] == "not modelled"


def test_acceptability_rises_with_experience(cfg):
    """Every scheme on record was unpopular before it ran and popular after."""
    result = simulate.run(
        TollPolicy(peak_toll=6.0, coverage="screenline", credit="none"), cfg, full=False
    )
    a = result["acceptability"]
    assert a["after_operation"]["support_share"] > a["before_operation"]["support_share"]
    assert a["experience_gain_pp"] > 0


def test_equity_design_buys_political_support(cfg):
    """Compensation should raise support, which is why it is a strategy not a cost."""
    plain = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="none"), cfg, full=False
    )
    fair = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="equity_first"), cfg, full=False
    )
    assert (fair["acceptability"]["before_operation"]["support_share"]
            > plain["acceptability"]["before_operation"]["support_share"])


def test_ride_hail_operator_absorbs_part_of_the_charge(cfg):
    """Pass-through is interior: the platform neither eats nor forwards all of it."""
    r = political.ride_hailing_response(10.0, 2.75, cfg)
    assert 0 < r["pass_through"] < 1
    assert r["rider_price_increase"] + r["operator_absorbs"] == pytest.approx(
        r["charge_per_trip"], abs=1e-6
    )
    assert r["trip_change_pct"] < 0
    # Deadheading means removing a ride-hail trip removes more than one vehicle trip.
    assert r["deadhead_vehicle_trips"] > 0


def test_suits_benchmark_places_the_model_against_real_schemes(cfg):
    result = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline", credit="none"), cfg
    )
    bench = result["incidence"]["benchmark"]
    operating = {b["scheme"]: b["suits_index"] for b in bench["operating_charges"]}
    # The comparison set must actually contain the schemes we cite.
    assert operating["stockholm"] == pytest.approx(-0.09)
    assert operating["lyon"] == pytest.approx(-0.16)
    assert bench["model_suits_index"] < 0     # a flat charge is regressive
