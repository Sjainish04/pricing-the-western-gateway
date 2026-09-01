"""Confronting the rejoin fraction with the Gardiner rehabilitation record.

The handover names this as the single best available test of the structural
decision the whole diversion result rests on.  `drive_lakeshore` is not "use
Lake Shore for the whole trip" -- it is *leave the expressway before the
gantry, run the arterial, and re-enter past it*, and `cfg.rejoin_fraction`
says how many re-enter.  Nothing local was ever observed for it.

What the public record actually contains
----------------------------------------
Two capacity-reduction episodes on this expressway:

  section2_2024  Dufferin St - Strachan Ave, 3 lanes to 2 each way from
                 2024-04-15.  Downtown, ~8 km east of the study screenline.
                 Measured and published by Altitude by Geotab from commercial
                 vehicle telematics, with a clean 2.5-month pre-period.

  section3_2025  Islington Ave and Kipling Ave over the Gardiner, 3 lanes to 2
                 each direction, from April/May 2025 to December 2026.  This
                 is on the charged segment itself -- the episode the handover
                 actually asked for.  No measured travel times or counts have
                 been published for it.

So the experiment this study wants is running right now on exactly the right
piece of road, and nobody has published a number from it.  The one that has
been measured is in the wrong place.  That is the honest headline of this
module, and it is the reason `identification()` says the fraction is *not
identified* rather than reporting a fitted value with a false standard error.

Every published figure is a travel TIME.  No before/after volume count exists
for either episode.  A rejoin fraction is a statement about where vehicles go,
so times have to be inverted through the link performance curves to say
anything about volumes at all -- `implied_volume_ratio` does that, in closed
form, and it is the load-bearing assumption of everything below.

What the inversion can and cannot see
-------------------------------------
Inverting the observed times gives how much traffic left the expressway and
how much the parallel arterial absorbed.  That is the *bypass* response.  The
rejoin fraction is a different quantity: it splits bypassers at the Humber
between re-entering and staying on the arterial, and separating those two
requires a count *downstream* of the split.  None exists.  The inversion
therefore bounds the total diversion the model should reproduce, and says
nothing directly about the split -- see `identification()`.

What is left is a directional argument (`transfer_argument()`) and, more
usefully, `switching_analysis()`, which asks the question a reviewer actually
cares about: does any conclusion in this study change if the fraction is
wrong?  An unmeasurable parameter that moves nothing is not a problem.  One
that flips a recommendation is, whatever value it is set to.
"""
from __future__ import annotations

import functools
from typing import Dict, List, Optional

import numpy as np

from . import datasets, game, network
from .config import Config
from .demand import load_segments
from .toll_policy import TollPolicy

# Capacity ratios to invert the Section 2 travel times against.  The closure
# took 3 lanes to 2 (0.667) over a sub-segment of a longer measured corridor,
# so the effective ratio for the corridor as a whole is not pinned: a
# bottleneck governs throughput for everything behind it, which argues for
# 0.667, while a short enough restriction argues for something nearer 1.
# Reporting the band rather than a point keeps that argument visible.
CAPACITY_RATIO_BAND = (0.60, 0.667, 0.75, 1.00)

# Where the switching analysis looks.  Deliberately wider than any defensible
# belief about the fraction -- the point is to find the value at which a
# conclusion flips, and a narrow grid can only fail to find one.
REJOIN_GRID = (0.20, 0.35, 0.45, 0.55, 0.65, 0.75, 0.90)


def implied_volume_ratio(
    link: network.Link,
    time_ratio: float,
    hours: float,
    capacity_ratio: float = 1.0,
    baseline: str = "curve",
) -> Optional[float]:
    """v'/v implied by an observed travel-time ratio.  Closed form.

    The link performance curve is

        t(v) = t_u + t_f * alpha * (v / c) ** beta

    so for a treated state with capacity `capacity_ratio` * c,

        (t' - t_u) / (t - t_u) = (v' / (capacity_ratio * v)) ** beta

    and the volume ratio follows directly.

    `baseline` selects what plays the role of t.  "curve" uses the model's own
    value at the link's base volume, which makes the inversion exactly
    self-consistent with the curve being inverted.  "observed" uses the
    observed peak time, which is what the published ratio was actually measured
    against.  On the three calibrated links these are equal by construction; on
    the two held-out links they differ by the validation error, and the
    difference is NOT cosmetic -- see `conditioning` below.  Both are reported
    as a band rather than one being picked.

    Returns None where the inversion is undefined: a link with no congestion
    delay at base has no BPR term to invert, and a treated time below the
    uncongested floor is not something this functional form can produce.
    """
    if baseline == "curve":
        base_time = link.travel_time(link.base_volume_veh, hours)
    elif baseline == "observed":
        base_time = link.observed_peak_min
    else:
        raise ValueError(f"unknown baseline {baseline!r}")

    base_delay = base_time - link.uncongested_minutes
    treated_delay = time_ratio * base_time - link.uncongested_minutes
    if base_delay <= 1e-9 or treated_delay <= 0.0 or capacity_ratio <= 0.0:
        return None
    return float(capacity_ratio * (treated_delay / base_delay) ** (1.0 / link.beta))


def conditioning(link: network.Link, hours: float) -> dict:
    """How trustworthy is inverting a travel time on this link at all?

    The inversion divides by the link's congestion delay at base.  On a link
    that is barely congested that denominator is small, so a modest error in
    the baseline travel time produces a large error in the implied volume --
    and every baseline here is an ESTIMATE.  `lakeshore_east` is the worst
    case: about a minute of queueing delay on a fifteen-minute trip, so the
    curve and observed baselines disagree by roughly a factor of two in the
    answer even though they disagree by 6% in the input.

    This is reported rather than smoothed over, because a single confident
    volume figure from this inversion would be exactly the kind of
    plausible-looking number this codebase keeps having to catch.
    """
    curve_time = link.travel_time(link.base_volume_veh, hours)
    curve_delay = curve_time - link.uncongested_minutes
    observed_delay = link.observed_peak_min - link.uncongested_minutes
    return {
        "link_id": link.link_id,
        "vc_ratio": round(link.vc_ratio(link.base_volume_veh, hours), 4),
        "curve_base_delay_min": round(curve_delay, 3),
        "observed_base_delay_min": round(observed_delay, 3),
        "baseline_disagreement_pct": (
            round(100.0 * (curve_delay / observed_delay - 1.0), 2)
            if observed_delay > 1e-9 else None
        ),
        # d ln(v) / d ln(base delay) = -1/beta: the inversion damps input error
        # by the BPR exponent, which is the one thing working in its favour.
        "error_damping": round(1.0 / link.beta, 4),
        "well_conditioned": bool(curve_delay > 2.0 and observed_delay > 2.0),
    }


def _episode_rows(episode: str) -> List[dict]:
    df = datasets.natural_experiments()
    return datasets.records(df[df["episode"] == episode])


def _time_ratio(row: dict) -> float:
    """Observed treated/baseline travel time, whether stored as a ratio or minutes."""
    if str(row["unit"]) == "ratio":
        return float(row["treated_value"])
    return float(row["treated_value"]) / float(row["baseline_value"])


def section2_inversion(cfg: Optional[Config] = None) -> dict:
    """Turn the Section 2 travel times into implied volume changes.

    Two links carry the episode: the expressway that was restricted, and the
    parallel arterial that was not.  The arterial is the informative one,
    because its capacity did not change -- its time ratio inverts to a volume
    change with no capacity assumption at all.
    """
    cfg = cfg or Config()
    hours = cfg.peak_end_h - cfg.peak_start_h
    links = network.load_links(hours, rejoin_fraction=cfg.rejoin_fraction)
    rows = _episode_rows("section2_2024")

    treated = [
        r for r in rows
        if r["metric"] == "peak_travel_time" and r["model_link"] == "gardiner_east"
    ]
    bypass = [
        r for r in rows
        if r["metric"] == "peak_travel_time" and r["model_link"] == "lakeshore_east"
    ]

    # The bypass arterial: no capacity change, so this is the one figure that
    # needs no capacity assumption.  It still needs a baseline, and on this
    # link the two defensible baselines disagree enough to matter, so both are
    # carried.
    bypass_out = []
    for r in bypass:
        ratio = _time_ratio(r)
        band = {}
        for baseline in ("curve", "observed"):
            vr = implied_volume_ratio(
                links["lakeshore_east"], ratio, hours, 1.0, baseline
            )
            band[baseline] = None if vr is None else round(vr, 4)
        valid = [v for v in band.values() if v is not None]
        bypass_out.append(
            {
                "facility": r["facility"],
                "time_ratio": round(ratio, 4),
                "volume_ratio_by_baseline": band,
                "volume_ratio_range": [min(valid), max(valid)] if valid else None,
                "volume_change_pct_range": (
                    [round(100.0 * (min(valid) - 1.0), 2),
                     round(100.0 * (max(valid) - 1.0), 2)] if valid else None
                ),
                "source": r["source"],
            }
        )

    # The restricted expressway: the answer depends on a capacity ratio the
    # published record does not pin down, so it is reported across the band.
    #
    # The three rows are three DIFFERENT spatial definitions -- a 5 km stretch
    # through the work zone, the Humber-to-Strachan run, and the whole
    # 427-to-Cherry corridor -- all inverted against the one modelled
    # downstream link.  They are not three measurements of the same quantity
    # and their spread is not a confidence interval; it is mostly the spread of
    # what "the corridor" was taken to mean.
    treated_out = []
    for r in treated:
        ratio = _time_ratio(r)
        by_kappa = {}
        for kappa in CAPACITY_RATIO_BAND:
            vr = implied_volume_ratio(links["gardiner_east"], ratio, hours, kappa)
            by_kappa[f"{kappa:.3f}"] = None if vr is None else round(vr, 4)
        treated_out.append(
            {
                "facility": r["facility"],
                "time_ratio": round(ratio, 4),
                "volume_ratio_by_capacity_ratio": by_kappa,
                "source": r["source"],
            }
        )

    # Coherence check.  With no capacity reduction at all, a travel time that
    # rose this much could only be produced by MORE traffic -- which is absurd
    # for a corridor everyone was avoiding.  The largest capacity ratio that
    # still implies the expressway lost traffic is therefore something the
    # travel-time record establishes on its own, independently of the City's
    # announcement.  That it lands near the announced 3-lanes-to-2 is the
    # closest thing to an external check this module has.
    coherent = []
    for r in treated:
        ratio = _time_ratio(r)
        unit_vr = implied_volume_ratio(links["gardiner_east"], ratio, hours, 1.0)
        if unit_vr:
            coherent.append(1.0 / unit_vr)
    max_coherent_kappa = round(float(min(coherent)), 4) if coherent else None

    return {
        "episode": "section2_2024",
        "bypass_arterial": bypass_out,
        "restricted_expressway": treated_out,
        "max_capacity_ratio_consistent_with_traffic_loss": max_coherent_kappa,
        "announced_capacity_ratio": 0.667,
        "conditioning": [
            conditioning(links["lakeshore_east"], hours),
            conditioning(links["gardiner_east"], hours),
        ],
        "note": (
            "The arterial inversion needs no capacity assumption; the expressway "
            "inversion needs one, and is shown across a band. A 30% travel-time "
            "rise on a congested arterial implies a far smaller volume rise, "
            "because the performance curve is convex -- reading the 30% as a "
            "volume increase would overstate absorption several times over."
        ),
    }


def diversion_decomposition(cfg: Optional[Config] = None) -> dict:
    """Where did the traffic the expressway lost actually go?

    Flow accounting across the Section 2 episode:

        expressway loss = parallel arterial gain + everything else

    "Everything else" is retiming, mode shift, suppressed trips, and arterials
    outside the two modelled here.  The split matters for this study because
    the model's central structural claim is that most of the response to a
    cost shock on this corridor is *rerouting*, not mode shift.  If the record
    showed the arterials absorbing almost everything, a rejoin fraction would
    be the dominant parameter in the model.  If it showed them absorbing very
    little, the diversion cap is a less binding constraint than assumed.
    """
    cfg = cfg or Config()
    hours = cfg.peak_end_h - cfg.peak_start_h
    links = network.load_links(hours, rejoin_fraction=cfg.rejoin_fraction)
    inv = section2_inversion(cfg)

    arterial = links["lakeshore_east"]
    expressway = links["gardiner_east"]

    ranges = [
        b["volume_ratio_range"] for b in inv["bypass_arterial"]
        if b["volume_ratio_range"] is not None
    ]
    if not ranges:
        return {"available": False, "reason": "no invertible bypass observation"}
    # Carry the arterial gain as a low/high pair rather than a mean, because
    # the two baselines disagree by about a factor of two on this link and
    # averaging them would manufacture a precision the inversion does not have.
    gain_low = arterial.base_volume_veh * (min(r[0] for r in ranges) - 1.0)
    gain_high = arterial.base_volume_veh * (max(r[1] for r in ranges) - 1.0)

    rows, incoherent = [], []
    for entry in inv["restricted_expressway"]:
        for kappa_s, vr in entry["volume_ratio_by_capacity_ratio"].items():
            base = {"facility": entry["facility"], "capacity_ratio": float(kappa_s)}
            if vr is None or vr >= 1.0:
                # Under this capacity assumption the expressway GAINED traffic
                # while its travel time rose sharply. Nothing to decompose.
                incoherent.append({**base, "reason": "implies the expressway gained traffic"})
                continue
            loss_veh = expressway.base_volume_veh * (1.0 - vr)
            share_low, share_high = gain_low / loss_veh, gain_high / loss_veh
            if share_low > 1.0:
                # The arterial absorbed more than the expressway lost. The
                # accounting cannot close, so this combination is rejected
                # rather than reported as an absorption share above 1 -- which
                # is what a naive sweep produces, and reads as a finding.
                incoherent.append(
                    {**base, "reason": "arterial gain exceeds expressway loss",
                     "implied_share": round(share_low, 3)}
                )
                continue
            rows.append(
                {
                    **base,
                    "expressway_loss_veh": round(loss_veh, 1),
                    "arterial_gain_veh_range": [round(gain_low, 1), round(gain_high, 1)],
                    "arterial_absorption_share_range": [
                        round(share_low, 4), round(min(share_high, 1.0), 4)
                    ],
                    "left_peak_road_system_share_range": [
                        round(1.0 - min(share_high, 1.0), 4), round(1.0 - share_low, 4)
                    ],
                }
            )

    shares = [s for r in rows for s in r["arterial_absorption_share_range"]]
    return {
        "available": True,
        "rows": rows,
        "rejected_combinations": incoherent,
        "absorption_share_range": (
            [round(min(shares), 4), round(max(shares), 4)] if shares else None
        ),
        "interpretation": (
            "Across every coherent assumption the parallel arterial absorbed "
            "part but never all of what the expressway lost -- roughly a sixth "
            "to two thirds, with the wide spread coming from which stretch of "
            "expressway the published figure refers to rather than from "
            "measurement noise. The remainder retimed, changed mode, was "
            "suppressed, or used arterials outside the two modelled here. "
            "Two things follow for this study. A diversion cap is worth "
            "carrying as a binding constraint, because arterial absorption is "
            "clearly material. But the arterials are not a near-perfect "
            "substitute for the expressway, so a model that routed almost all "
            "priced-off traffic onto them would be overstating the leak."
        ),
        "caveats": [
            "Geotab measures COMMERCIAL vehicles. Freight is more route-constrained "
            "and more time-sensitive than the commuters this study models, so its "
            "diversion behaviour is not the corridor average.",
            "Section 2 is downtown, ~8 km east of the screenline, with a denser "
            "arterial grid and more transit than the western gateway.",
            "The arterial base volume is the model's own derived figure, not a count.",
        ],
    }


def identification() -> dict:
    """What the record identifies, and what it does not.  Stated plainly.

    Kept as a first-class result rather than a footnote because the honest
    answer to "validate the rejoin fraction" is that the available data cannot,
    and a reader is entitled to see that before any number below it.
    """
    return {
        "identified": [
            "The bypass response: how much traffic left the expressway when it "
            "became costly, and how much the parallel arterial absorbed.",
            "That the arterial absorbed a minority of the loss, so most of the "
            "response was not rerouting onto the modelled bypasses.",
            "That the published travel times independently imply a capacity "
            "reduction close to the one the City announced.",
        ],
        "not_identified": [
            "The rejoin fraction itself. It splits bypassers at the Humber "
            "between re-entering the expressway and staying on the arterial, "
            "which requires a count DOWNSTREAM of that split. No such count has "
            "been published for either episode.",
            "Whether a money cost produces the same route response as a time "
            "cost. Every observation available is a capacity reduction.",
            "Anything at all from the Section 3 episode on the charged segment, "
            "which is running now and has produced no published measurement.",
        ],
        "conclusion": (
            "The rejoin fraction remains ESTIMATED. This module does not move it "
            "from ESTIMATED to DERIVED, and no result in this study should be "
            "presented as though it had. What it does establish is a bound on "
            "how much the uncertainty matters -- see switching_analysis."
        ),
    }


def transfer_argument() -> dict:
    """Why a construction episode understates the rejoin fraction under a toll.

    This is a mechanism argument, not a measurement, and it is the only reason
    the Section 2 record says anything at all about the value of a parameter it
    cannot identify.  It gives a direction, not a number.
    """
    return {
        "claim": (
            "A construction episode is a LOWER bound on the toll-era rejoin "
            "fraction, not an estimate of it."
        ),
        "mechanism": [
            "Under construction the degraded facility IS the downstream "
            "expressway, so a driver who leaves it has little reason to come "
            "back. Rejoining buys a share of the same queue they left.",
            "Under a gateway charge the opposite holds. Past the gantry the "
            "expressway is untolled and, because the charge removed traffic "
            "from it, faster than before. A bypasser who does not rejoin is "
            "paying an arterial's travel time to avoid a charge they have "
            "already escaped.",
            "So whatever rejoin behaviour a construction period reveals, a "
            "gateway charge should produce at least as much.",
        ],
        "consequence_for_this_study": (
            "It cuts against the direction that would be convenient. A higher "
            "rejoin fraction puts more diverted traffic back onto the shared "
            "untolled section, which is exactly the externality a gateway charge "
            "cannot price -- the study's own central objection to the design it "
            "recommends. Erring toward a low fraction would flatter the scheme."
        ),
    }


@functools.lru_cache(maxsize=4)
def _cached_switching(payload: str) -> dict:
    import json

    kwargs = json.loads(payload)
    return _switching_analysis(
        cfg=Config.from_dict(kwargs["config"]), grid=tuple(kwargs["grid"])
    )


def switching_analysis(
    cfg: Optional[Config] = None, grid: Optional[tuple] = None
) -> dict:
    """Cached entry point for the sweep over the rejoin fraction."""
    import json

    cfg = cfg or Config()
    grid = tuple(grid or REJOIN_GRID)
    payload = json.dumps({"config": cfg.to_dict(), "grid": list(grid)}, sort_keys=True)
    return _cached_switching(payload)


def _switching_analysis(cfg: Config, grid: tuple) -> dict:
    """Does any conclusion in this study change if the rejoin fraction is wrong?

    Three policies, chosen because each carries a published headline finding:

      $4 freeway only   the finding that a gateway charge leaks onto local
                        streets and breaches the diversion cap
      $5 screenline     the finding that full coverage turns diversion negative
      $10 screenline    the recommended design

    The choice constants are held at their central fitted values throughout,
    for the reason set out in METHODS section 5: re-fitting them per draw would
    let them absorb the parameter and report a sensitivity of nearly zero.
    """
    policies = [
        TollPolicy(peak_toll=4.0, coverage="gardiner_only", credit="none",
                   label="$4 freeway only"),
        TollPolicy(peak_toll=5.0, coverage="screenline", credit="targeted_package",
                   label="$5 screenline + targeted credits"),
        TollPolicy(peak_toll=10.0, coverage="screenline",
                   credit="low_income_transit_poor", label="$10 screenline (recommended)"),
    ]

    results: Dict[str, List[dict]] = {p.label: [] for p in policies}
    for r in grid:
        trial = Config.from_dict({**cfg.to_dict(), "rejoin_fraction": float(r)})
        segs = load_segments(trial)
        for p in policies:
            row = game.summarise(game.evaluate(p, trial, segs, reference=cfg))
            results[p.label].append(
                {
                    "rejoin_fraction": float(r),
                    "worst_diversion_pct": row["worst_diversion_pct"],
                    "delay_reduction_pct": row["delay_reduction_pct"],
                    "net_revenue_annual": row["net_revenue_annual"],
                    "equity_score": row["equity_score"],
                    "feasible": row["feasible"],
                }
            )

    # A conclusion "switches" if a qualitative claim changes sign anywhere on
    # the grid.  Pinning the qualitative claim rather than the number is the
    # point: a diversion figure that moves from 11.6% to 13% changes nothing a
    # reader was told, but one that crosses the cap changes the recommendation.
    cap = 100.0 * cfg.max_diversion_increase
    switches = []
    for label, rows in results.items():
        breaches = [r["worst_diversion_pct"] > cap for r in rows]
        feas = [r["feasible"] for r in rows]
        revenue_positive = [r["net_revenue_annual"] > 0 for r in rows]
        for name, flags in (
            ("breaches the diversion cap", breaches),
            ("is feasible under all constraints", feas),
            ("is revenue positive", revenue_positive),
        ):
            if len(set(flags)) > 1:
                first = next(
                    i for i in range(1, len(flags)) if flags[i] != flags[i - 1]
                )
                switches.append(
                    {
                        "policy": label,
                        "claim": name,
                        "switches_between": [
                            rows[first - 1]["rejoin_fraction"],
                            rows[first]["rejoin_fraction"],
                        ],
                        "holds_at_default": flags[
                            min(
                                range(len(rows)),
                                key=lambda i: abs(
                                    rows[i]["rejoin_fraction"] - cfg.rejoin_fraction
                                ),
                            )
                        ],
                    }
                )

    return {
        "grid": list(grid),
        "default_rejoin_fraction": cfg.rejoin_fraction,
        "diversion_cap_pct": cap,
        "results": results,
        "switches": switches,
        "robust": not switches,
        "note": (
            "A parameter nobody can measure is only a problem if it moves a "
            "conclusion. Any entry in `switches` is a claim in this study whose "
            "truth depends on an unobserved number, and should be reported with "
            "that dependence attached."
        ),
    }


def breakeven_rejoin_fraction(
    cfg: Optional[Config] = None,
    policy: Optional[TollPolicy] = None,
    lo: float = 0.05,
    hi: float = 0.95,
    tol: float = 0.005,
) -> dict:
    """The rejoin fraction at which a policy's diversion crosses the cap.

    The switching grid says a conclusion flips somewhere between two grid
    points; this says where.  It matters here because the study's second
    headline finding -- that a freeway-only charge leaks past the local-street
    cap -- turns out to switch close to the assumed value, so the distance
    between the assumption and the crossing is the finding's whole margin.

    Bisection rather than a solver: diversion is monotone in the rejoin
    fraction over the relevant range (more rejoiners means more of the bypass
    traffic is counted onto the arterial west of the gantry before it returns),
    each evaluation costs a full equilibrium, and ten evaluations is enough to
    place the crossing inside half a percentage point.
    """
    cfg = cfg or Config()
    policy = policy or TollPolicy(
        peak_toll=4.0, coverage="gardiner_only", credit="none", label="$4 freeway only"
    )
    cap = 100.0 * cfg.max_diversion_increase

    def diversion_at(r: float) -> float:
        trial = Config.from_dict({**cfg.to_dict(), "rejoin_fraction": float(r)})
        segs = load_segments(trial)
        return game.summarise(game.evaluate(policy, trial, segs, reference=cfg))[
            "worst_diversion_pct"
        ]

    f_lo, f_hi = diversion_at(lo) - cap, diversion_at(hi) - cap
    if f_lo * f_hi > 0:
        return {
            "policy": policy.to_dict(),
            "cap_pct": cap,
            "crossing": None,
            "reason": (
                "The cap is not crossed anywhere on [%.2f, %.2f]; the conclusion "
                "does not depend on the rejoin fraction." % (lo, hi)
            ),
        }

    iterations = 0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if (diversion_at(mid) - cap) * f_lo > 0:
            lo = mid
        else:
            hi = mid
        iterations += 1

    crossing = round(0.5 * (lo + hi), 4)
    return {
        "policy": policy.to_dict(),
        "cap_pct": cap,
        "crossing": crossing,
        "assumed": cfg.rejoin_fraction,
        "margin": round(cfg.rejoin_fraction - crossing, 4),
        "iterations": iterations,
        "reading": (
            "Below a rejoin fraction of about %.2f this policy stays inside the "
            "local-street diversion cap; above it, it breaches. The study assumes "
            "%.2f, so the finding survives on a margin of %.2f in a parameter "
            "nothing local has ever measured."
            % (crossing, cfg.rejoin_fraction, cfg.rejoin_fraction - crossing)
        ),
    }


def report(cfg: Optional[Config] = None) -> dict:
    """Everything the study can honestly say about the rejoin fraction."""
    cfg = cfg or Config()
    return {
        "parameter": {
            "name": "rejoin_fraction",
            "value": cfg.rejoin_fraction,
            "tier": "ESTIMATED",
            "meaning": (
                "Share of drivers bypassing the gantry on an arterial who "
                "re-enter the expressway past it rather than continuing on the "
                "arterial into downtown."
            ),
        },
        "episodes": datasets.records(datasets.natural_experiments()),
        "identification": identification(),
        "inversion": section2_inversion(cfg),
        "decomposition": diversion_decomposition(cfg),
        "transfer": transfer_argument(),
        "switching": switching_analysis(cfg),
        "breakeven": breakeven_rejoin_fraction(cfg),
    }
