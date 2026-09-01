"""HTTP API over the corridor model.

Read-only and stateless: every endpoint is a pure function of the model inputs,
so a result can always be reproduced from the request that produced it.  The
heavy calibration is cached in `simulate`, so a scenario returns in well under a
second after the first call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from uttan import (
    bargaining, comparators, datasets, game, geographic, incidence, joint_game,
    network, phasing, political, precomputed, rejoin_validation, reversion,
    scenarios, sensitivity, simulate, site_selection,
)
from uttan.config import ALTERNATIVES, BASE_SHARES, Config
from uttan.demand import load_segments
from uttan.toll_policy import (
    CHARGING_WINDOWS, COVERAGE_LINKS, CREDIT_MECHANISMS, TollPolicy,
)

app = FastAPI(
    title="UTTAN Etobicoke-Gardiner Congestion Pricing Model",
    description=(
        "Stackelberg congestion-pricing simulation for the Gardiner Expressway "
        "western gateway, Hwy 427 to the Humber River."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5178", "http://127.0.0.1:5178",
                   "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PolicyRequest(BaseModel):
    peak_toll: float = Field(0.0, ge=0, le=50)
    shoulder_toll: float = Field(0.0, ge=0, le=50)
    window: str = "0630_0930"
    coverage: str = "gardiner_only"
    credit: str = "none"
    hov_discount: float = Field(0.0, ge=0, le=1)
    monthly_cap_trips: int = Field(20, ge=1, le=44)
    low_income_rebate: float = Field(0.75, ge=0, le=1)
    transit_poor_rebate: float = Field(0.60, ge=0, le=1)
    shift_worker_rebate: float = Field(0.70, ge=0, le=1)
    mobility_credit_value: float = Field(2.40, ge=0, le=15)
    adaptive_signals: bool = False
    ramp_metering: bool = False
    transit_priority: bool = False
    parking_surcharge: float = Field(0.0, ge=0, le=40)
    go_frequency_uplift: float = Field(0.0, ge=0, le=1)
    label: str = "custom"
    # Config overrides are not all numeric: admin_cost_scenario is a string and
    # nest_lambda is a mapping, so this cannot be narrowed to Dict[str, float].
    config: Optional[Dict[str, Any]] = None

    def to_policy(self) -> TollPolicy:
        data = self.model_dump(exclude={"config"})
        return TollPolicy(**data)

    def to_config(self) -> Config:
        return Config.from_dict(self.config)


class GridRequest(BaseModel):
    tolls: Optional[List[float]] = None
    coverage: str = "gardiner_only"
    credit: str = "none"
    window: str = "0630_0930"
    config: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    tolls: Optional[List[float]] = None
    coverages: Optional[List[str]] = None
    credits: Optional[List[str]] = None
    windows: Optional[List[str]] = None
    enforce_constraints: bool = True
    config: Optional[Dict[str, Any]] = None


class WeightsRequest(BaseModel):
    weights: Optional[Dict[str, float]] = None


def _validate(policy: TollPolicy) -> None:
    if policy.coverage not in COVERAGE_LINKS:
        raise HTTPException(400, f"unknown coverage {policy.coverage!r}")
    if policy.window not in CHARGING_WINDOWS:
        raise HTTPException(400, f"unknown window {policy.window!r}")
    if policy.credit not in CREDIT_MECHANISMS:
        raise HTTPException(400, f"unknown credit mechanism {policy.credit!r}")


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/meta")
def meta() -> dict:
    """Everything the interface needs to render its controls."""
    cfg = Config()
    return {
        "alternatives": ALTERNATIVES,
        "base_shares": BASE_SHARES,
        "coverages": {
            k: {"charges": v, "label": {
                "gardiner_only": "Expressway only",
                "screenline": "Full western screenline",
                "city_roads_only": "City arterials only (branch B)",
            }.get(k, k)}
            for k, v in COVERAGE_LINKS.items()
        },
        "windows": {k: {"start": v[0], "end": v[1]} for k, v in CHARGING_WINDOWS.items()},
        "credits": CREDIT_MECHANISMS,
        "config_defaults": cfg.to_dict(),
        "constraints": {
            "max_diversion_increase_pct": round(100 * cfg.max_diversion_increase, 1),
            "min_equity_score": cfg.min_equity_score,
            "min_delay_reduction_pct": round(100 * cfg.min_delay_reduction, 1),
        },
        "objective_weights": {
            "delay": cfg.w_delay, "revenue": cfg.w_revenue,
            "reliability": cfg.w_reliability, "emissions": cfg.w_emissions,
            "equity": cfg.w_equity, "diversion": cfg.w_diversion,
            "implementation": cfg.w_implementation,
        },
        # Which of the slow, deterministic results are being served from disk
        # rather than computed. Exposed so a reader can tell, and so a stale
        # cache on a deployment is visible rather than silent.
        "precomputed": precomputed.status(cfg),
    }


@app.get("/api/data/sources")
def data_sources() -> dict:
    """Every model input with its provenance tier."""
    return {
        "summary": datasets.provenance_summary(),
        "sources": datasets.records(datasets.sources()),
        "note": (
            "PUBLISHED values come from a named public source. DERIVED values "
            "are computed from published values by a documented rule. ESTIMATED "
            "values are planning assumptions and are the ones the sensitivity "
            "analysis exists to test."
        ),
    }


@app.get("/api/data/network")
def data_network() -> dict:
    return {
        "links": datasets.records(datasets.network().reset_index()),
        "routes": datasets.records(datasets.routes()),
        "base_volumes": {k: round(v, 1) for k, v in network.base_link_volumes().items()},
        "validation": network.validate(),
    }


@app.get("/api/data/segments")
def data_segments() -> dict:
    cfg = Config()
    segs = load_segments(cfg)
    return {
        "count": segs.n,
        "segments": datasets.records(datasets.segments()),
        "value_of_time_by_quintile": {
            q: round(float(segs.vot_per_min[segs.quintile == q][0] * 60), 2)
            for q in ("Q1", "Q2", "Q3", "Q4", "Q5")
        },
    }


@app.get("/api/data/geography")
def data_geography() -> dict:
    """Map layers: study corridor, charging points, transit alternatives."""
    return {
        "corridor": {
            "study_segment": "Hwy 427 to the Humber River",
            "anchors": [
                {"name": "Hwy 427 / Gardiner interchange", "lat": 43.6082, "lon": -79.5460},
                {"name": "Kipling Avenue", "lat": 43.6180, "lon": -79.5335},
                {"name": "Islington Avenue", "lat": 43.6206, "lon": -79.5150},
                {"name": "Royal York / Mimico", "lat": 43.6240, "lon": -79.4980},
                {"name": "Park Lawn Road", "lat": 43.6270, "lon": -79.4830},
                {"name": "Humber River", "lat": 43.6320, "lon": -79.4720},
            ],
        },
        "gantries": site_selection.gantries(),
        "transit": site_selection.transit_alternatives(),
        "gateways": datasets.records(datasets.gateways()),
        "link_geometry": datasets.link_geometry(),
    }


# ---------------------------------------------------------------------------
# Site selection
# ---------------------------------------------------------------------------

@app.get("/api/site/screening")
def site_screening(draws: int = Query(4000, ge=200, le=20000)) -> dict:
    """Stage 0: which gateway should be the pilot, and how robust is that?"""
    return site_selection.report(n_draws=draws)


@app.post("/api/site/rescore")
def site_rescore(request: WeightsRequest) -> dict:
    """Re-rank the gateways under user-supplied criterion weights."""
    return {
        "weighted_sum": site_selection.score(request.weights),
        "topsis": site_selection.topsis(request.weights),
    }


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@app.get("/api/validation")
def validation() -> dict:
    """Step 4 evidence that the baseline is credible before any toll is set."""
    return simulate.validation_report()


@app.get("/api/validation/rejoin")
def rejoin_report() -> dict:
    """What the Gardiner rehabilitation record does and does not say about
    the rejoin fraction -- the model's most consequential unmeasured input.

    Deliberately returns the identification limits alongside the numbers. The
    switching analysis is the part a reviewer should read first: it says which
    conclusions in this study depend on a parameter nobody has measured.
    """
    return precomputed.serve("rejoin", rejoin_validation.report)


@app.get("/api/scenarios")
def scenario_catalogue() -> dict:
    return {"scenarios": scenarios.catalogue()}


@app.get("/api/scenarios/compare")
def scenario_compare(ids: Optional[str] = None) -> dict:
    names = [s.strip() for s in ids.split(",")] if ids else None
    try:
        return scenarios.compare(names)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/scenarios/{scenario_id}")
def scenario_run(scenario_id: str) -> dict:
    try:
        policy = scenarios.build(scenario_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    result = simulate.run(policy)
    result["objective"] = game.objective(result, Config())
    return result


@app.post("/api/simulate")
def simulate_policy(request: PolicyRequest) -> dict:
    """Run one arbitrary policy to equilibrium and score it."""
    policy = request.to_policy()
    _validate(policy)
    cfg = request.to_config()
    result = simulate.run(policy, cfg)
    result["objective"] = game.objective(result, cfg)
    return result


# ---------------------------------------------------------------------------
# Game theory
# ---------------------------------------------------------------------------

@app.get("/api/game/analysis")
def game_analysis() -> dict:
    """Pigouvian benchmark, price of anarchy and the player structure."""
    return game.analysis()


@app.post("/api/game/grid")
def game_grid(request: GridRequest) -> dict:
    cfg = Config.from_dict(request.config)
    rows = game.toll_grid(
        cfg=cfg, tolls=request.tolls, coverage=request.coverage,
        credit=request.credit, window=request.window,
    )
    return {"results": rows, "pareto_frontier": game.pareto_frontier(rows)}


@app.post("/api/game/stackelberg")
def game_stackelberg(request: SearchRequest) -> dict:
    """Search the leader's strategy space subject to the policy constraints."""
    cfg = Config.from_dict(request.config)
    result = game.stackelberg_search(
        cfg=cfg, tolls=request.tolls, coverages=request.coverages,
        credits=request.credits, windows=request.windows,
        enforce_constraints=request.enforce_constraints,
    )
    result["pareto_frontier"] = game.pareto_frontier(result["results"])
    return result


# ---------------------------------------------------------------------------
# Equity depth and political economy
# ---------------------------------------------------------------------------

@app.get("/api/game/phasing")
def phasing_report(
    charge: float = Query(10.0, ge=0.0, le=30.0,
                          description="Charge held constant across paths, so the "
                                      "comparison is about order, not price."),
) -> dict:
    """The sequential game: when to charge, not just how much.

    Compares sequencing strategies with real precedents (Stockholm, New York
    2008 and 2019-25, operations-only) on expected discounted welfare, where
    the charge only exists if it clears a political gate whose odds depend on
    what the earlier stages delivered.
    """
    if charge == 10.0:
        return precomputed.serve("phasing", phasing.report)
    return {**phasing.report(charge=charge), "_source": "computed"}


@app.get("/api/game/bargaining")
def bargaining_report(
    charge: float = Query(10.0, ge=0.0, le=30.0),
) -> dict:
    """The City and the Province as players, not as two scenarios.

    Nash and Kalai-Smorodinsky over the revenue split, with disagreement points
    taken from what each side can actually do alone. The 2027 transfer changes
    the Province's fallback from nothing to a unilateral freeway charge, which
    is the deadline the result turns on.
    """
    if charge == 10.0:
        return precomputed.serve("bargaining", bargaining.report)
    return {**bargaining.report(charge=charge), "_source": "computed"}


@app.get("/api/game/joint")
def joint_report(
    charge: float = Query(10.0, ge=0.0, le=30.0),
) -> dict:
    """Sequencing and authorisation solved as one problem.

    The phased game says wait for transit; the bargaining game says the City's
    hand changes at a fixed date. A charge needs both a public that tolerates it
    and two governments that can agree, so the enactment probability is the
    product of the two gates.
    """
    if charge == 10.0:
        return precomputed.serve("joint", joint_game.report)
    return {**joint_game.report(charge=charge), "_source": "computed"}


@app.get("/api/compare/cities")
def compare_cities() -> dict:
    """This corridor against the charges that operate -- and the ones that failed.

    Includes an out-of-sample check against New York, which began charging in
    January 2025 and is the closest comparator available, and a list of the
    places where the operating record contradicts this study rather than
    corroborating it.
    """
    return comparators.report()


@app.get("/api/equity/benchmarks")
def equity_benchmarks() -> dict:
    """Suits indices from congestion charges that actually operate."""
    return {
        "benchmarks": datasets.records(datasets.benchmarks()),
        "note": "Operating congestion charges cluster between -0.09 and -0.16 on the "
                "Suits index. A US sales tax is about -0.11 and the Texas fuel tax "
                "about -0.25.",
    }


@app.get("/api/equity/geographic")
def geographic_equity(
    toll: float = Query(10.0, ge=0.0, le=30.0),
    coverage: str = Query("screenline"),
    credit: str = Query("low_income_transit_poor"),
) -> dict:
    """FHWA's second equity type: who pays, by where they live.

    Reports burden, welfare and recycled benefit by sub-area and across the
    city boundary, and decomposes the geographic result against income so a
    reader can see whether it is a separate finding or §7 restated.
    """
    policy = TollPolicy(peak_toll=toll, coverage=coverage, credit=credit,
                        label=f"${toll:g} {coverage}")
    report = geographic.report(policy)
    # Indicative points so the burden can be shown geographically. Attached
    # here rather than inside geographic.py because the model never reads
    # coordinates -- see datasets.subarea_points.
    report["points"] = datasets.subarea_points()
    return report


@app.get("/api/equity/steps")
def equity_steps() -> dict:
    """The STEPS equity framework and what this model can and cannot see."""
    return {
        "dimensions": incidence.STEPS_DIMENSIONS,
        "source": "Shaheen et al., Social Equity Impacts of Congestion Management "
                  "Strategies (UC Berkeley TSRC, 2019).",
        "note": "Spatial, Temporal and Economic are scored from model output. "
                "Physiological and Social are reported as not modelled, because a "
                "generalized-cost corridor model cannot see them.",
    }


@app.get("/api/political/ride-hailing")
def political_ride_hailing() -> dict:
    """Why ride-hail needs its own instrument, and how the operator responds."""
    cfg = Config()
    return {
        "case": political.ride_hailing_case(cfg),
        "response_curve": [
            political.ride_hailing_response(t, 0.0, cfg) for t in (0, 2, 5, 10, 15)
        ],
    }


@app.post("/api/political/acceptability")
def political_acceptability(request: PolicyRequest) -> dict:
    """Would this policy survive a vote, before and after it operates?"""
    policy = request.to_policy()
    _validate(policy)
    result = simulate.run(policy, request.to_config(), full=False)
    return result["acceptability"]


@app.get("/api/game/joint-optimum")
def game_joint_optimum() -> dict:
    """Price and start year chosen together, with and without the constraint set.

    The fixed-charge sweep at /api/game/joint answers *when*. This answers when
    and how much, and reports whether solving the two in sequence would have
    reached the same place.
    """
    return precomputed.serve("joint_optimum", lambda: joint_game.joint_optimum(Config()))


@app.get("/api/game/gate-dependence")
def game_gate_dependence() -> dict:
    """What the independence assumption between the two enactment gates costs."""
    return precomputed.serve(
        "gate_dependence", lambda: joint_game.gate_dependence_sweep(Config())
    )


@app.get("/api/validation/reversion")
def validation_reversion() -> dict:
    """Does the delay reduction last? The trajectory, against London.

    The headline delay figure is a first-year effect. This separates the part
    that background growth takes back from the part a road-space reallocation
    would take back, because only the second is a choice.
    """
    return reversion.report(Config())


@app.get("/api/political/trust")
def political_trust() -> dict:
    """How much of the revenue promise has to be believed for this to pass.

    The corridor's own trust level is not observable, so this reports the
    threshold and sets it against the one figure the record measured --
    Edinburgh's, where about one in four believed the revenue would reach
    transport and the charge lost 74.4-25.6.
    """
    return political.trust_report(Config())


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

@app.post("/api/sensitivity/tornado")
def sensitivity_tornado(request: PolicyRequest) -> dict:
    policy = request.to_policy()
    _validate(policy)
    return sensitivity.tornado(policy, request.to_config())


@app.get("/api/sensitivity/monte-carlo")
def sensitivity_monte_carlo(draws: int = Query(120, ge=20, le=400)) -> dict:
    return sensitivity.monte_carlo(draws=draws)


@app.get("/api/sensitivity/convergence")
def sensitivity_convergence() -> dict:
    return sensitivity.convergence_study()


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

@app.get("/api/recommendation")
def recommendation() -> dict:
    """The final answer in the format the proposal asks for."""
    cfg = Config()
    search = game.stackelberg_search(cfg=cfg)
    best = search["best_feasible"]
    if best is None:
        return {
            "status": "no feasible policy",
            "search": search,
            "note": "No policy in the searched space satisfied every constraint. "
                    "Either the constraints or the instrument set must change.",
        }

    policy = TollPolicy(
        peak_toll=best["peak_toll"], coverage=best["coverage"],
        credit=best["credit"], window=best["window"], label="recommended",
    )
    detail = simulate.run(policy, cfg)
    comparison = scenarios.compare(
        ["baseline", "no_toll_package", "branch_b_city_roads", "branch_b_parking"]
    )
    ga = game.analysis()
    win = CHARGING_WINDOWS[best["window"]]

    return {
        "recommended_corridor": "Etobicoke-Gardiner western gateway, Hwy 427 to the Humber River",
        "recommended_charging_period": f"{win[0]:04.1f} to {win[1]:04.1f}".replace(".5", ":30").replace(".0", ":00"),
        "recommended_price": best["peak_toll"],
        "coverage": best["coverage"],
        "equity_mechanism": best["credit"],
        "diversion_mitigation": (
            "Charge the full western screenline so Lake Shore Blvd W and The Queensway "
            "stop acting as a free bypass, with adaptive signals on the arterials as a backstop."
        ),
        "expected_traffic_reduction_pct": best["peak_vehicle_change_pct"],
        "expected_delay_reduction_pct": best["delay_reduction_pct"],
        "expected_net_revenue_annual": best["net_revenue_annual"],
        "equity_score": best["equity_score"],
        "governance_pathway": (
            "A charge on the expressway needs provincial authorisation, because a toll "
            "cannot be levied on a highway where the Crown is the road authority unless "
            "an Act permits it, and the Gardiner transfers to the Province in fall 2027. "
            "Branch B substitutes a City-controlled instrument."
        ),
        "detail": detail,
        "search": {k: v for k, v in search.items() if k != "results"},
        "benchmarks": {
            "first_best_pigouvian_toll": ga["pigouvian"]["first_best_toll_charged_segment"],
            "welfare_maximising_uniform_toll": ga["social_optimum"]["optimal_uniform_toll"],
            "price_of_anarchy": ga["social_optimum"]["price_of_anarchy"],
        },
        "alternatives_considered": comparison["scenarios"],
    }


# ---------------------------------------------------------------------------
# Static frontend, when it has been built
# ---------------------------------------------------------------------------

DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        candidate = DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
