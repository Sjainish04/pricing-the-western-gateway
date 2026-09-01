"""Revenue, cost and financial efficiency.

Operating costs at proposal stage are genuinely uncertain, so every figure is
produced under three cost cases rather than a single point estimate.  The
headline uses the medium case; the low and high cases are always carried
alongside it so the reader can see how much of the result is an assumption.
"""
from __future__ import annotations

from typing import Dict

from .config import ALTERNATIVES, OCCUPANCY, Config
from .congestion import Equilibrium
from .demand import Segments
from .toll_policy import COVERAGE_LINKS, TollPolicy

IDX = {a: i for i, a in enumerate(ALTERNATIVES)}


def charged_vehicles(eq: Equilibrium, policy: TollPolicy, cfg: Config) -> float:
    """Vehicles that generate a chargeable transaction in the peak period.

    A tolled crossing and a surcharged parking event are both transactions with
    a collection cost, so both are counted.
    """
    total = 0.0
    if policy.peak_toll > 0:
        coverage = policy.window_coverage(cfg)
        for alt in COVERAGE_LINKS.get(policy.coverage, []):
            occ = OCCUPANCY.get(alt, 0.0)
            if occ <= 0:
                continue
            trips = float(eq.market_shares[IDX[alt]]) * cfg.total_person_trips
            total += (trips / occ) * coverage
    if policy.parking_surcharge > 0:
        for alt in ("drive_gardiner", "drive_lakeshore", "drive_queensway",
                    "carpool_gardiner", "shift_offpeak"):
            occ = OCCUPANCY.get(alt, 0.0)
            if occ <= 0:
                continue
            total += float(eq.market_shares[IDX[alt]]) * cfg.total_person_trips / occ
    return total


def compute(
    eq: Equilibrium,
    base: Equilibrium,
    policy: TollPolicy,
    segs: Segments,
    cfg: Config,
    delay_saved_vehicle_hours: float = 0.0,
    vehicles_removed: float = 0.0,
) -> dict:
    """Gross and net revenue under three administrative cost cases."""
    from . import equity as equity_mod

    days = cfg.working_days_per_year
    charges = equity_mod.per_segment_charges(eq, segs, cfg)

    gross_peak = charges["gross_total"]
    credits_peak = charges["credit_total"]
    gross_annual = gross_peak * days
    credits_annual = credits_peak * days

    transactions = charged_vehicles(eq, policy, cfg)
    transactions_annual = transactions * days

    # No charge means no scheme, so no scheme to run and nothing to collect.
    # Without this an untolled baseline would be reported as losing the fixed
    # operating cost of a system that was never built.
    if gross_annual <= 1e-6:
        empty = {"admin_cost": 0.0, "fixed_cost": 0.0, "enforcement_cost": 0.0,
                 "credits": 0.0, "net_revenue": 0.0, "cost_ratio": 0.0}
        return {
            "gross_revenue_peak": 0.0, "gross_revenue_daily": 0.0,
            "gross_revenue_annual": 0.0, "credits_annual": 0.0,
            "net_revenue_annual": 0.0, "charged_vehicles_peak": 0.0,
            "charged_vehicles_annual": 0.0, "average_charge_per_vehicle": 0.0,
            "cost_cases": {c: dict(empty) for c in ("low", "medium", "high")},
            "cost_case_used": cfg.admin_cost_scenario,
            "break_even_admin_ratio": 0.0,
            "revenue_per_vehicle_removed": 0.0,
            "revenue_per_delay_hour_saved": 0.0,
            "net_positive": False, "no_charge": True,
        }

    cases: Dict[str, dict] = {}
    for case in ("low", "medium", "high"):
        admin = transactions_annual * cfg.admin_cost_per_transaction[case]
        fixed = cfg.fixed_annual_cost[case]
        enforcement = gross_annual * cfg.enforcement_rate
        net = gross_annual - admin - fixed - enforcement - credits_annual
        cases[case] = {
            "admin_cost": round(admin, 0),
            "fixed_cost": round(fixed, 0),
            "enforcement_cost": round(enforcement, 0),
            "credits": round(credits_annual, 0),
            "net_revenue": round(net, 0),
            "cost_ratio": round(
                (admin + fixed + enforcement) / gross_annual, 4
            ) if gross_annual > 0 else 0.0,
        }

    headline = cases[cfg.admin_cost_scenario]
    net = headline["net_revenue"]

    # Break-even: the administrative cost ratio at which net revenue hits zero,
    # after credits are paid.  Below this the scheme funds nothing.
    break_even = (
        (gross_annual - credits_annual) / gross_annual if gross_annual > 0 else 0.0
    )

    return {
        "gross_revenue_peak": round(gross_peak, 2),
        "gross_revenue_daily": round(gross_peak, 2),
        "gross_revenue_annual": round(gross_annual, 0),
        "credits_annual": round(credits_annual, 0),
        "net_revenue_annual": round(net, 0),
        "charged_vehicles_peak": round(transactions, 1),
        "charged_vehicles_annual": round(transactions_annual, 0),
        "average_charge_per_vehicle": round(
            gross_peak / transactions, 3
        ) if transactions > 0 else 0.0,
        "cost_cases": cases,
        "cost_case_used": cfg.admin_cost_scenario,
        "break_even_admin_ratio": round(break_even, 4),
        "revenue_per_vehicle_removed": round(
            net / (vehicles_removed * days), 2
        ) if vehicles_removed > 0 else 0.0,
        "revenue_per_delay_hour_saved": round(
            net / (delay_saved_vehicle_hours * days), 2
        ) if delay_saved_vehicle_hours > 0 else 0.0,
        "net_positive": bool(net > 0),
    }


def recycling_plan(net_revenue_annual: float) -> list:
    """Illustrative allocation of net revenue to corridor improvements.

    The split follows the proposal's commitment to spend the money where the
    charge is felt: station access and first/last mile first, then bus priority
    and traffic management, then direct mobility credits.
    """
    allocation = [
        ("Lakeshore West station access and platforms", 0.24,
         "Mimico, Long Branch and the planned Park Lawn station."),
        ("First and last mile connections", 0.18,
         "Walking, cycling and local shuttle access to the three stations."),
        ("TTC feeder service and bus priority", 0.20,
         "Frequency and priority on the routes feeding the GO stations."),
        ("Adaptive signals and traffic management", 0.14,
         "Lake Shore Blvd W and the diversion corridors."),
        ("Targeted mobility credits", 0.16,
         "Funds the low-income and transit-poor credits in the preferred package."),
        ("Local diversion mitigation", 0.08,
         "Neighbourhood traffic calming where diversion is measured."),
    ]
    return [
        {
            "programme": name,
            "share": share,
            "annual_amount": round(max(net_revenue_annual, 0.0) * share, 0),
            "note": note,
        }
        for name, share, note in allocation
    ]
