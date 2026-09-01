"""What the operating schemes say about this one.

A table of other cities is not analysis.  The question worth asking is whether
this corridor's modelled result sits inside the range the record has actually
produced, and where the model's assumptions disagree with what happened
elsewhere.  Three things this module does that a comparison table does not:

**External validation.**  New York began charging on 5 January 2025 and is the
only North American scheme and the closest comparator this study has.  It
charges USD 9 and observed an 11% fall in vehicles entering the zone.  This
model, at a similar charge, predicts its own vehicle reduction from parameters
fitted only to Toronto data -- so New York is a genuine out-of-sample test of
the demand response, in the same spirit as the two held-out links in the
network calibration.

**Where the record contradicts the study.**  London's traffic reduction was
permanent but its *delay* reduction was not: congestion returned to
pre-charging levels within about five years, as road space was reallocated and
background demand grew.  This study's headline is a delay reduction.  Nothing
in a static equilibrium model can produce that reversion, so it has to be
stated rather than modelled.

**The failures, kept in the sample.**  Edinburgh and Manchester rejected
charges at referendum and New York lost its first attempt in the legislature.
Comparing only against schemes that survived is survivorship bias, and it is
exactly the bias that would make a model over-confident about deliverability --
which is what `phasing.py` and `bargaining.py` exist to resist.
"""
from __future__ import annotations

import functools
from typing import Dict, List, Optional

import numpy as np

from . import datasets, game, simulate
from .config import Config
from .demand import load_segments
from .toll_policy import TollPolicy

# New York's observed first-year outcome, used as the out-of-sample check.
# Kept here rather than read loosely from the table so the comparison cannot
# silently start pointing at a different row.
NYC = {"charge_usd": 9.0, "vehicle_change_pct": -11.0, "launched": "2025-01-05"}


def schemes() -> List[dict]:
    """Every scheme in the table, operating and failed alike."""
    return datasets.records(datasets.city_schemes())


@functools.lru_cache(maxsize=8)
def _cached_validation(payload: str) -> dict:
    import json

    kw = json.loads(payload)
    return _external_validation(Config.from_dict(kw["config"]))


def external_validation(cfg: Optional[Config] = None) -> dict:
    import json

    cfg = cfg or Config()
    return _cached_validation(json.dumps({"config": cfg.to_dict()}, sort_keys=True))


def _external_validation(cfg: Config) -> dict:
    """Run this model at New York's charge and compare the demand response.

    Not a like-for-like test and it must not be presented as one.  New York
    prices a downtown cordon with the densest transit network on the continent;
    this is a suburban freeway gateway where 40% of demand arrives from another
    municipality.  The model should therefore predict a *smaller* response than
    New York observed, and a prediction larger than New York's would be the
    warning sign -- a corridor with worse alternatives cannot shed more traffic
    than one with better ones at the same price.

    That directional expectation is the actual test.  Matching the number would
    be luck; matching the direction is evidence the elasticity is not absurd.
    """
    segs = load_segments(cfg)
    policy = TollPolicy(
        peak_toll=NYC["charge_usd"], coverage="screenline",
        credit="none", label=f"${NYC['charge_usd']:g} screenline (NYC-equivalent)",
    )
    result = simulate.run(policy, cfg, segs, full=False)
    modelled = float(result["metrics"]["peak_vehicle_change_pct"])
    observed = NYC["vehicle_change_pct"]

    return {
        "charge_usd": NYC["charge_usd"],
        "observed_new_york_pct": observed,
        "modelled_here_pct": round(modelled, 2),
        "difference_pp": round(modelled - observed, 2),
        # Both are reductions, so "smaller" means closer to zero.
        "direction_as_expected": bool(modelled > observed),
        "reading": (
            "This model predicts a %.1f%% fall in peak vehicles at New York's "
            "$9 charge, against the %.1f%% New York observed. %s"
            % (
                modelled, observed,
                "The modelled response is the smaller of the two, which is the "
                "expected direction: this corridor has worse alternatives than "
                "a Manhattan cordon, so it should shed less traffic at the same "
                "price."
                if modelled > observed else
                "The modelled response is LARGER than New York's, which is the "
                "wrong direction for a corridor with weaker alternatives. The "
                "leading explanation is that the two figures are not the same "
                "quantity: New York's is zone entries averaged over a whole "
                "year and a whole day, while this is AM-peak vehicles across a "
                "screenline. A peak-only response is normally the larger of the "
                "two, because peak travellers can retime and off-peak ones have "
                "no charge to avoid. That plausibly accounts for the gap, and it "
                "is not established that it does -- so this is recorded as an "
                "unresolved discrepancy rather than as either a passed test or a "
                "refuted model."
            )
        ),
        # Named separately so the caveat cannot be read as an excuse: if the
        # comparison is ever put on a like-for-like footing and the gap
        # survives, the elasticity is wrong and this study's demand response is
        # too strong.
        "what_would_settle_it": (
            "New York's entry counts restricted to a weekday AM peak, against "
            "this model's peak figure. The MTA publishes CRZ entries by hour, so "
            "this is obtainable and would turn an unresolved discrepancy into "
            "either a genuine out-of-sample pass or a reason to re-fit the "
            "logit scale."
        ),
        "verdict": ("consistent" if modelled > observed else "unresolved"),
        "not_like_for_like": [
            "New York prices a downtown cordon with the densest transit network "
            "in North America; this is a suburban freeway gateway.",
            "40% of demand here arrives from another municipality, with a "
            "commuter rail line as the only real alternative.",
            "New York's figure is entries to a zone over a full year; this is "
            "AM-peak vehicles across a screenline.",
        ],
    }


def positioning(cfg: Optional[Config] = None) -> dict:
    """Where the recommended design sits against the schemes that operate."""
    cfg = cfg or Config()
    segs = load_segments(cfg)
    policy = TollPolicy(peak_toll=10.0, coverage="screenline",
                        credit="low_income_transit_poor", label="recommended")
    result = game.evaluate(policy, cfg, segs)

    here = result["equity"]["components"]["suits_index"]
    suits = suits_benchmarks()
    charges = [b for b in suits if b["kind"] == "operating_charge"]

    # The comparison that means something is against charges that OPERATE. The
    # proposed schemes are designs nobody has tested, and the sales and fuel
    # taxes are there to give the number a scale a reader already has a feel
    # for -- not to be beaten. Mixing all three into one "more regressive than"
    # list would let a fuel tax at -0.25 flatter this design.
    more_regressive = [b["city"] for b in charges if here < b["suits_index"]]
    return {
        "charge_usd": policy.peak_toll,
        "suits_index_here": here,
        "suits_benchmarks": suits,
        "more_regressive_than": more_regressive,
        "more_regressive_than_all": bool(charges) and len(more_regressive) == len(charges),
        "vehicle_change_pct": result["metrics"]["peak_vehicle_change_pct"],
        "operating_range_pct": observed_range(),
        "operating_range_note": (
            "The range is computed from the six operating schemes rather than "
            "quoted from a review, so it moves if the table does. This design "
            "sits below it, because it charges one gateway of a corridor rather "
            "than enclosing a destination -- a driver can still reach downtown "
            "without crossing the screenline."
        ),
        "charge_response": charge_response(),
    }


# How each benchmark should be read. Operating charges are the comparison;
# proposals are designs nobody has tested; the taxes are a familiar yardstick.
KIND_LABELS = {
    "operating_charge": "Congestion charge, operating",
    "proposed_charge": "Congestion charge, proposed",
    "other_tax": "Other taxes, for scale",
}


# Names for the rows whose `city` does not identify them: two are both
# "United States", which would collide in a chart.
TAX_LABELS = {
    "us_sales_tax": "US sales tax",
    "us_vmt_tax": "US VMT tax",
    "texas_gas_tax": "Texas fuel tax",
    "swedish_fuel_tax": "Swedish fuel tax",
}


def suits_benchmarks() -> List[dict]:
    """Every published Suits index, labelled by what kind of thing it measures.

    Drawn from benchmarks.csv rather than from the city table, because that is
    where the fuller set lives -- eight values against the city table's two.
    Reporting only the two made this study look better than the evidence
    warrants: the handover's claim is that this design is more regressive than
    every OPERATING charge, and two rows cannot support "every".

    The kind matters and is carried through to the chart. A fuel tax at -0.25
    is not a congestion charge and must not be read as one; it is there so a
    reader who has no feel for a Suits index has something familiar to scale it
    against.
    """
    rows = datasets.records(datasets.benchmarks())
    out = [
        {
            # `city` is the wrong label for the taxes: two of them are both
            # "United States", which would put two differently-valued bars
            # under one name. The scheme key disambiguates, so it is used
            # wherever the place name does not identify the thing.
            "city": TAX_LABELS.get(r["scheme"], r["city"]),
            "suits_index": float(r["suits_index"]),
            "kind": r.get("kind", "other_tax"),
            "kind_label": KIND_LABELS.get(r.get("kind", "other_tax"), "Other"),
            "note": r.get("note"),
        }
        for r in rows
        if r["suits_index"] is not None and not _isnan(r["suits_index"])
    ]
    # Most regressive first, so the chart reads in one direction.
    out.sort(key=lambda b: b["suits_index"])
    return out


def observed_range() -> List[float]:
    """The reduction actually achieved by the operating schemes, from the table.

    Derived rather than quoted, so it cannot drift out of step with the rows a
    reader can see. Returns [most negative, least negative].
    """
    vals = [
        float(r["traffic_change_pct"]) for r in datasets.records(datasets.city_schemes())
        if r["status"] == "operating"
        and r["traffic_change_pct"] is not None
        and not _isnan(r["traffic_change_pct"])
    ]
    return [round(min(vals), 1), round(max(vals), 1)] if vals else []


def charge_response() -> dict:
    """Charge against traffic reduction -- separated by what the charge IS.

    The single most misleading thing available here would be a scatter of price
    against response across all six schemes, because they are not pricing the
    same event.  London, Milan and New York levy a charge ONCE PER DAY however
    many times you cross; Singapore, Stockholm and Gothenburg charge EVERY
    PASSAGE.  A daily 19 dollars and a per-passage 2 dollars can be the same
    annual cost to a commuter making two crossings a day, or wildly different
    for anyone making more.

    So the two bases are returned as separate groups and must be plotted as
    separate series.  Six points across two bases is far too few to fit
    anything to, and no fit is attempted: the purpose is to show where this
    corridor sits, not to estimate an elasticity from other people's cities.
    """
    rows = [
        r for r in datasets.records(datasets.city_schemes())
        if r["status"] == "operating"
        and r["charge_usd_peak"] is not None and not _isnan(r["charge_usd_peak"])
        and r["traffic_change_pct"] is not None and not _isnan(r["traffic_change_pct"])
    ]
    groups: Dict[str, List[dict]] = {}
    for r in rows:
        groups.setdefault(str(r["charge_basis"]), []).append({
            "city": r["city"],
            "charge_usd": float(r["charge_usd_peak"]),
            "traffic_change_pct": float(r["traffic_change_pct"]),
            "metric": r["traffic_metric"],
        })
    return {
        "groups": groups,
        "basis_labels": {
            "daily": "Charged once per day",
            "per_passage": "Charged every passage",
        },
        "warning": (
            "The two bases price different events and must not be read as one "
            "series. A daily charge and a per-passage charge of the same "
            "headline value are different instruments, and this corridor's "
            "design is a per-passage charge in a peak window."
        ),
        "pattern": _price_does_not_predict(groups),
        "no_fit_attempted": (
            "Six points across two bases, six cities, six network geometries "
            "and fifty years. Fitting a curve through that would produce a "
            "number with no defensible standard error, and the comparison is "
            "here to locate this study, not to estimate its elasticity."
        ),
    }


def contradictions() -> List[dict]:
    """Where the operating record disagrees with this study, stated plainly.

    Kept as a first-class output rather than a caveat paragraph, because a
    comparison that only finds corroboration is not being used as evidence.
    """
    return [
        {
            "kind": "contradiction",
            "claim_here": "The recommended design removes 39.4% of peak delay.",
            "record": (
                "London's traffic reduction was permanent but its delay "
                "reduction was not: congestion returned to roughly "
                "pre-charging levels within about five years, as road space "
                "was reallocated to buses and pedestrians and background "
                "demand grew."
            ),
            "why_the_model_cannot_see_it": (
                "It now can, and the answer separates two things the record does "
                "not. Background demand growth alone takes the delay reduction "
                "from 39.4% to 34.7% over ten years -- an erosion, not a "
                "reversion. Reproducing London's five-year reversion needs about "
                "28% of the charged links' capacity to be handed to buses, "
                "footway or public realm, and at that point traffic is down MORE "
                "than at the start while the delay benefit has gone. That is "
                "London's asymmetry exactly, and it means the delay benefit "
                "reverts because the space gets spent, not because the charge "
                "stops working. The headline is still a first-year figure and is "
                "labelled as one."
            ),
            "status": "addressed",
            "how": "reversion.trajectory; /api/validation/reversion",
            "severity": "medium",
        },
        {
            "kind": "contradiction",
            "claim_here": (
                "Acceptability is modelled from the traveller's own net "
                "position plus a citizen view that rises with income."
            ),
            "record": (
                "Edinburgh rejected its charge 74.4% to 25.6%, and the "
                "research found the driver was TRUST rather than economics: "
                "only one in four believed the revenue would reach transport. "
                "Car ownership predicted the vote better than income did."
            ),
            "why_the_model_cannot_see_it": (
                "It now can, and this entry is kept to record what changed. The "
                "acceptability model discounts the PROMISED part of a traveller's "
                "position -- the recycled revenue -- by `cfg.revenue_trust` before "
                "it enters the vote, while the toll they pay and the time they save "
                "are experienced rather than promised and are not discounted. What "
                "remains outside the model is trust in the CHARGE (whether it will "
                "relieve congestion at all) as distinct from trust in the money, and "
                "Edinburgh's finding that car ownership predicted the vote better "
                "than income did, which no term here reproduces."
            ),
            "status": "addressed",
            "how": "political.trust_sensitivity; /api/political/trust",
            "severity": "medium",
        },
        {
            # "design" was wrong and the model said so: TWO designs reverse the
            # ordering, means_tested and equity_first. Both contain a means
            # test, which is the actual evidence and a stronger claim than the
            # one it replaces. `test_means_test_claim_matches_the_library`
            # recomputes it so the sentence cannot drift from the scenarios
            # again.
            "kind": "contradiction",
            "claim_here": (
                "A means test is the only INSTRUMENT in the library that "
                "reverses the burden ordering -- the two designs that manage it "
                "both contain one -- so equity requires an income instrument."
            ),
            "record": (
                "Stockholm has no income-based discount of any kind and is "
                "still not regressive, because wealthy inner-city residents pay "
                "the most and the revenue funds transit that low-income riders "
                "use disproportionately."
            ),
            "why_it_matters_here": (
                "It contradicts the NECESSITY, not the effectiveness: Stockholm "
                "shows an income instrument is not required to avoid "
                "regressivity, because geography can do the same distributional "
                "work where a city's wealthy live centrally and pay most. This "
                "model has no term that could have found that -- it reaches "
                "distribution only through the credit design, so a city whose "
                "geography already does the work would look to it like a city "
                "that needs a means test."
            ),
            "also_corroborates": (
                "The same mechanism is this study's geographic finding: the 905 "
                "pays LESS than its share of trips because Lakeshore West GO "
                "gives it a way out. Geography doing distributional work is a "
                "fact about a particular city, though, not a design principle -- "
                "which is why it is reported as a contradiction of the general "
                "claim and a corroboration of the local one."
            ),
            "severity": "medium",
        },
        {
            "kind": "contradiction",
            "claim_here": (
                "A revenue package improves acceptability, so recycling is "
                "part of the political case."
            ),
            "record": (
                "Manchester attached a GBP 3bn transport package to its charge "
                "and still lost its referendum."
            ),
            "why_the_model_cannot_see_it": (
                "It now can. Recycling used to enter through each traveller's net "
                "position at face value, so support was increasing and unbounded in "
                "the size of the package and some package always won. Each dollar "
                "now reaches the vote multiplied by trust, so the support curve "
                "flattens below the threshold and no multiplier catches it. But "
                "disbelieving the MONEY was the wrong mechanism for this case: "
                "Manchester's GBP 3bn was credible and the charge was what nobody "
                "believed in. Belief that the charge relieves congestion is now "
                "modelled separately, and it is the larger lever by about six times "
                "-- worth $1.68 a trip here against $0.28 for the revenue promise, "
                "because the time saving is a forecast while the toll is a "
                "certainty. With the money fully believed, no package up to eight "
                "times the modelled one carries the vote at 50% belief or below. "
                "That is the actual Manchester failure."
            ),
            "status": "addressed",
            "how": "political.manchester_test; /api/political/trust",
            "severity": "medium",
        },
    ]


def exemption_regimes() -> List[dict]:
    """Who each scheme lets off, and what that does to its distribution.

    A charge's equity profile is set as much by its exemptions as by its rate,
    and Gothenburg is the cautionary case: a company-car exemption granted for
    administrative convenience roughly doubles the scheme's measured
    regressivity, from a Suits index of -0.06 to -0.13.
    """
    rows = datasets.records(datasets.city_schemes())
    return [
        {
            "city": r["city"],
            "status": r["status"],
            "regime": r["equity_regime"],
            "suits_index": r["suits_index"],
        }
        for r in rows
    ]


def _price_does_not_predict(groups: Dict[str, List[dict]]) -> dict:
    """Is the response ordered by price within a basis?  It is not.

    Read straight off the table rather than inferred: within the daily-charge
    group the CHEAPEST scheme produced the largest reduction and the dearest
    produced less than half of it.  No statistic is claimed from three points --
    this is arithmetic on six numbers, and its only purpose is to stop a reader
    drawing a demand curve through a scatter that does not contain one.

    It matters for this study because it is the same conclusion the model
    reached internally: coverage moved the diversion result far more than the
    rate did.  What a charge encloses beats what it costs.
    """
    out = {}
    for basis, rows in groups.items():
        if len(rows) < 2:
            continue
        by_price = sorted(rows, key=lambda r: r["charge_usd"])
        cheapest, dearest = by_price[0], by_price[-1]
        # More negative is a bigger reduction.
        out[basis] = {
            "cheapest": {"city": cheapest["city"], "charge_usd": cheapest["charge_usd"],
                         "traffic_change_pct": cheapest["traffic_change_pct"]},
            "dearest": {"city": dearest["city"], "charge_usd": dearest["charge_usd"],
                        "traffic_change_pct": dearest["traffic_change_pct"]},
            "dearest_achieved_more": dearest["traffic_change_pct"] < cheapest["traffic_change_pct"],
        }
    ordered = [v["dearest_achieved_more"] for v in out.values()]
    broken = [b for b, v in out.items() if not v["dearest_achieved_more"]]

    # Built from the result rather than asserted. An earlier version of this
    # string claimed the ordering failed in BOTH bases; it fails in one. Writing
    # the conclusion by hand next to a computed table is how a caption stops
    # matching its figure.
    if broken:
        detail = "; ".join(
            "in the %s group %s charges $%.2f and achieved %.1f%%, while %s "
            "charges $%.2f and achieved %.1f%%"
            % (b.replace("_", "-"),
               out[b]["cheapest"]["city"], out[b]["cheapest"]["charge_usd"],
               out[b]["cheapest"]["traffic_change_pct"],
               out[b]["dearest"]["city"], out[b]["dearest"]["charge_usd"],
               out[b]["dearest"]["traffic_change_pct"])
            for b in broken
        )
        reading = (
            "Price does not order the response across every basis: %s. Network "
            "geometry and the quality of the alternatives evidently matter more "
            "than the rate -- which is the same thing this model found "
            "internally, where coverage moved the diversion result far more "
            "than the rate did. Three points per basis, so this is arithmetic "
            "on the table rather than an estimated relationship." % detail
        )
    else:
        reading = (
            "Within every basis the dearer charge did achieve the larger "
            "reduction. With three points per basis that is consistent with a "
            "price response and is nowhere near evidence of one."
        )

    return {
        "by_basis": out,
        "price_orders_the_response": all(ordered) if ordered else None,
        "bases_where_it_fails": broken,
        "reading": reading,
    }


def _isnan(x) -> bool:
    try:
        return bool(np.isnan(float(x)))
    except (TypeError, ValueError):
        return False


def report(cfg: Optional[Config] = None) -> dict:
    cfg = cfg or Config()
    return {
        "schemes": schemes(),
        "positioning": positioning(cfg),
        "external_validation": external_validation(cfg),
        "contradictions": contradictions(),
        "exemptions": exemption_regimes(),
        "note": (
            "The failed schemes are kept in the sample deliberately. Comparing "
            "only against charges that survived is survivorship bias, and it is "
            "the bias that would make this study over-confident about "
            "deliverability."
        ),
    }
