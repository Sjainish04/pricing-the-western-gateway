"""Tests for the comparative study and the Suits concentration curve.

The risk with a comparison table is that it becomes decoration: numbers from
other cities sitting next to this study's numbers without either being used to
check the other. These tests pin the parts that make it evidence -- that the
failed schemes stay in the sample, that the external check reports its own
verdict honestly rather than always passing, and that the curve is the one the
index is actually computed from.
"""
from __future__ import annotations

import numpy as np
import pytest

from uttan import comparators, datasets, equity
from uttan.config import Config


@pytest.fixture(scope="module")
def cfg():
    return Config()


# --------------------------------------------------------------------------
# The sample
# --------------------------------------------------------------------------

def test_failed_schemes_are_kept_in_the_sample():
    """Comparing only against charges that survived is survivorship bias, and it
    is the bias that would make this study over-confident about deliverability."""
    rows = comparators.schemes()
    statuses = {r["status"] for r in rows}
    assert "operating" in statuses
    assert {"rejected", "withdrawn"} & statuses, statuses
    failed = [r for r in rows if r["status"] != "operating"]
    assert len(failed) >= 3, failed


def test_every_scheme_carries_a_source_and_a_lesson():
    """A row with no source is an assertion; a row with no lesson is decoration."""
    for r in comparators.schemes():
        assert r["source"], r["city"]
        assert r["tier"] in {"PUBLISHED", "DERIVED", "ESTIMATED"}, r["city"]
        assert r["lesson"] and len(r["lesson"]) > 40, r["city"]


def test_new_york_is_present_as_both_a_success_and_a_failure():
    """The same city tried and failed in 2008 and succeeded in 2025. Carrying
    only the success would lose the most useful governance lesson in the set."""
    ny = [r for r in comparators.schemes() if r["city"] == "New York"]
    assert len(ny) == 2
    assert {r["status"] for r in ny} == {"operating", "withdrawn"}


# --------------------------------------------------------------------------
# The external check
# --------------------------------------------------------------------------

def test_external_validation_reports_its_own_verdict(cfg):
    """It must be able to FAIL. A check that always passes is not a check.

    The directional expectation is that this corridor -- a suburban gateway with
    weaker alternatives than a Manhattan cordon -- shows a smaller response at
    the same charge. Whichever way it comes out, the verdict has to say so.
    """
    v = comparators.external_validation(cfg)
    assert v["verdict"] in {"consistent", "unresolved"}
    assert (v["verdict"] == "consistent") == v["direction_as_expected"]
    # Both are reductions, so "as expected" means closer to zero.
    assert v["direction_as_expected"] == (v["modelled_here_pct"] > v["observed_new_york_pct"])


def test_external_validation_says_what_would_settle_it(cfg):
    """An unresolved discrepancy has to name the observation that resolves it,
    or the caveat is an excuse rather than a research step."""
    v = comparators.external_validation(cfg)
    assert v["what_would_settle_it"]
    assert v["not_like_for_like"]


def test_contradictions_are_not_all_corroboration():
    """The point of the comparison is the places the record disagrees.

    This used to require at least one HIGH severity row, which was a proxy for
    "the study has not explained away its own inconvenient findings". The proxy
    broke the moment a contradiction was genuinely closed, and downgrading the
    severity is exactly the move the assertion existed to catch -- so the
    invariant is now stated directly instead: a contradiction may only be
    marked addressed if it names the code that addresses it AND that code
    actually exists.
    """
    import importlib

    rows = comparators.contradictions()
    assert len(rows) >= 3
    for r in rows:
        assert r["claim_here"] and r["record"]
        assert r.get("why_the_model_cannot_see_it") or r.get("why_it_matters_here")

    addressed = [r for r in rows if r.get("status") == "addressed"]
    assert addressed, "a comparison that closes nothing is not being acted on"
    for r in addressed:
        assert r.get("how"), f"{r['claim_here'][:40]!r} claims a fix without naming it"
        # "addressed" must be checkable, not a claim: resolve every symbol it
        # cites. A renamed function would otherwise leave the study asserting a
        # fix it no longer has.
        for ref in r["how"].split(";"):
            ref = ref.strip()
            if ref.startswith("/api/"):
                continue
            module_name, _, attr = ref.partition(".")
            module = importlib.import_module(f"uttan.{module_name}")
            assert hasattr(module, attr), f"{ref} does not exist"


def test_means_test_claim_matches_the_library(cfg):
    """The claim about means-testing must be recomputed, not asserted.

    It read "means-testing is the only DESIGN that reverses the burden
    ordering", and the model disagreed: two designs manage it, means_tested and
    equity_first. Both contain a means test, so the claim is true of the
    INSTRUMENT and false of the design -- a distinction the sentence had lost.

    Pinned by recomputing which designs reverse the ordering and requiring every
    one of them to carry a means test, because a written claim sitting beside a
    computed library is exactly how the two drift apart. This study has already
    recorded that failure once, in its comparative charts.
    """
    from uttan import scenarios, simulate

    reversing = []
    for name in scenarios.LIBRARY:
        policy = scenarios.build(name)
        if policy.peak_toll <= 0:
            continue
        eq = simulate.run(policy, cfg, full=False)["equity"]
        by_q = {q["quintile"]: q["burden_pct_income"] for q in eq["by_quintile"]}
        if by_q["Q1"] < by_q["Q5"]:
            reversing.append(name)

    assert reversing, "no design reverses the ordering -- the claim is empty"
    for name in reversing:
        policy = scenarios.build(name)
        assert policy.means_test_exempt_quintiles or policy.means_test_half_quintiles, (
            f"{name} reverses the burden ordering without a means test, "
            "which falsifies the claim in comparators.contradictions()"
        )

    claim = next(
        c for c in comparators.contradictions()
        if "means test" in c["claim_here"].lower()
    )
    assert "INSTRUMENT" in claim["claim_here"], (
        "the claim must be about the instrument, not the design: "
        f"{len(reversing)} designs reverse the ordering"
    )


# --------------------------------------------------------------------------
# The Suits concentration curve
# --------------------------------------------------------------------------

def _fixture(burden, income, weights=None):
    b = np.array(burden, dtype=float)
    i = np.array(income, dtype=float)
    w = np.ones_like(b) if weights is None else np.array(weights, dtype=float)
    return b, i, w


def test_curve_starts_at_zero_and_ends_at_one():
    """It is a cumulative share of each quantity, so both ends are pinned."""
    b, i, w = _fixture([1, 2, 3, 4], [10, 20, 30, 40])
    curve = equity.suits_curve(b, i, w)
    assert curve[0]["cumulative_income_share"] == pytest.approx(0.0, abs=1e-9)
    assert curve[0]["cumulative_charge_share"] == pytest.approx(0.0, abs=1e-9)
    assert curve[-1]["cumulative_income_share"] == pytest.approx(1.0, abs=1e-6)
    assert curve[-1]["cumulative_charge_share"] == pytest.approx(1.0, abs=1e-6)


def test_a_proportional_charge_traces_the_diagonal():
    """Charge exactly proportional to income: every gap is zero, index is zero."""
    b, i, w = _fixture([1, 2, 3, 4], [10, 20, 30, 40])
    curve = equity.suits_curve(b, i, w)
    assert max(abs(p["gap"]) for p in curve) < 1e-6
    assert equity.suits_index(b, i, w) == pytest.approx(0.0, abs=1e-6)


def test_a_regressive_charge_sits_above_the_diagonal():
    """A flat charge on unequal incomes: the poor pay a larger share of the
    charge than of the income, so the curve rises above the diagonal and the
    index is negative. If these two ever disagree in sign, one of them is
    inverted -- which is the bug that once reported this charge as progressive.
    """
    b, i, w = _fixture([1, 1, 1, 1], [10, 20, 40, 80])
    curve = equity.suits_curve(b, i, w)
    assert max(p["gap"] for p in curve) > 0.1
    assert equity.suits_index(b, i, w) < 0


def test_a_progressive_charge_sits_below_the_diagonal():
    b, i, w = _fixture([1, 4, 16, 64], [10, 20, 40, 80])
    curve = equity.suits_curve(b, i, w)
    assert min(p["gap"] for p in curve) < -0.05
    assert equity.suits_index(b, i, w) > 0


def test_curve_is_undefined_rather_than_wrong_with_no_charge():
    """No charge collected means no distribution to describe."""
    b, i, w = _fixture([0, 0, 0], [10, 20, 30])
    assert equity.suits_curve(b, i, w) == []


@pytest.mark.slow
def test_the_reported_curve_matches_the_reported_index(cfg):
    """The curve must be the one the index is computed from, not a lookalike.

    Suits is 1 - 2L with L the area under the concentration curve, so
    integrating the reported curve has to return the reported index. Publishing
    a chart drawn from different arithmetic than the headline number is exactly
    how a figure and its caption drift apart.
    """
    from uttan import simulate
    from uttan.demand import load_segments
    from uttan.toll_policy import TollPolicy

    segs = load_segments(cfg)
    result = simulate.run(
        TollPolicy(peak_toll=10.0, coverage="screenline",
                   credit="low_income_transit_poor"),
        cfg, segs, full=False,
    )
    curve = result["equity"]["suits_curve"]
    reported = result["equity"]["components"]["suits_index"]

    x = np.array([p["cumulative_income_share"] for p in curve])
    y = np.array([p["cumulative_charge_share"] for p in curve])
    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    # The curve is the knots the index is integrated from, not a resampling of
    # them, so this is equality up to the rounding in the payload -- the 0.01
    # tolerance this used to carry was hiding interpolation error, not model
    # disagreement.
    assert 1.0 - 2.0 * float(trapz(y, x)) == pytest.approx(reported, abs=1e-4)


# --------------------------------------------------------------------------
# Comparability: the two charge bases price different events
# --------------------------------------------------------------------------

def test_every_operating_scheme_has_a_charge_and_a_response():
    """The point of filling the table is that the positioning chart is complete."""
    op = [r for r in comparators.schemes() if r["status"] == "operating"]
    assert len(op) == 6
    for r in op:
        assert r["charge_usd_peak"] and not np.isnan(float(r["charge_usd_peak"])), r["city"]
        assert r["traffic_change_pct"] and not np.isnan(float(r["traffic_change_pct"])), r["city"]
        # A percentage with no statement of what was measured is not a datum.
        assert r["traffic_metric"] and len(r["traffic_metric"]) > 20, r["city"]


def test_charge_bases_are_kept_apart():
    """A daily charge and a per-passage charge are different instruments.

    London levies once a day however many times you cross; Stockholm charges
    every passage. Plotting them as one series invites a reader to draw a
    demand curve through six points that do not price the same event.
    """
    cr = comparators.charge_response()
    assert set(cr["groups"]) == {"daily", "per_passage"}
    assert all(len(v) == 3 for v in cr["groups"].values())
    assert cr["warning"] and cr["no_fit_attempted"]


def test_no_scheme_appears_in_both_bases():
    cr = comparators.charge_response()
    cities = [r["city"] for rows in cr["groups"].values() for r in rows]
    assert len(cities) == len(set(cities))


def test_the_observed_range_is_derived_not_quoted():
    """It must move if the table moves, or it will drift out of step with the
    rows a reader can see beneath it."""
    lo, hi = comparators.observed_range()
    vals = [float(r["traffic_change_pct"]) for r in comparators.schemes()
            if r["status"] == "operating"]
    assert lo == pytest.approx(min(vals), abs=0.05)
    assert hi == pytest.approx(max(vals), abs=0.05)
    assert lo < hi < 0


def test_the_price_pattern_matches_the_table_it_describes():
    """The prose is generated from the computed result, not written beside it.

    An earlier version asserted the ordering failed in BOTH bases when it fails
    in one, which is how a caption stops matching its figure.
    """
    pat = comparators.charge_response()["pattern"]
    for basis, v in pat["by_basis"].items():
        expected = v["dearest"]["traffic_change_pct"] < v["cheapest"]["traffic_change_pct"]
        assert v["dearest_achieved_more"] == expected, basis
        assert (basis in pat["bases_where_it_fails"]) == (not expected), basis
    if pat["bases_where_it_fails"]:
        assert pat["price_orders_the_response"] is False
        for b in pat["bases_where_it_fails"]:
            assert pat["by_basis"][b]["cheapest"]["city"] in pat["reading"]


# --------------------------------------------------------------------------
# Benchmarks: what kind of thing each one is
# --------------------------------------------------------------------------

def test_every_benchmark_is_classified():
    """A new row must not default silently into "other tax".

    The kind decides both how a benchmark is coloured and whether it counts
    toward "more regressive than every operating charge". An unclassified row
    would quietly join the yardsticks and stop being compared.
    """
    known = set(comparators.KIND_LABELS)
    for r in datasets.records(datasets.benchmarks()):
        assert r.get("kind") in known, r["scheme"]


def test_benchmark_labels_are_unique():
    """Two rows both called "United States" would put differently-valued bars
    under one name -- unreadable, and the reason TAX_LABELS exists."""
    labels = [b["city"] for b in comparators.suits_benchmarks()]
    assert len(labels) == len(set(labels)), labels


def test_benchmarks_are_sorted_most_regressive_first():
    vals = [b["suits_index"] for b in comparators.suits_benchmarks()]
    assert vals == sorted(vals)


def test_only_operating_charges_count_as_comparators(cfg):
    """A fuel tax at -0.25 must not be allowed to flatter this design.

    "More regressive than" is a claim about congestion charges that actually
    operate. Proposals are untested designs and the taxes are a yardstick; if
    either could enter the comparison, the study would look better than the
    evidence warrants.
    """
    pos = comparators.positioning(cfg)
    operating = {b["city"] for b in comparators.suits_benchmarks()
                 if b["kind"] == "operating_charge"}
    assert set(pos["more_regressive_than"]) <= operating
    # The taxes are still reported -- they are just not comparators.
    kinds = {b["kind"] for b in pos["suits_benchmarks"]}
    assert "other_tax" in kinds
