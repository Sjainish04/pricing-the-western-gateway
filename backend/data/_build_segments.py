"""Deterministically build the traveller-segment table.

A segment is (sub-area, income quintile, schedule flexibility).  Transit
accessibility is a *property of the sub-area*, not an independent draw --
where you live determines whether Lakeshore West GO is a realistic option.
Run:  python _build_segments.py   (regenerates segments.csv)
"""
import csv

# --- Sub-areas of the western gateway catchment -----------------------------
# transit_access: 0-1 composite of walk/drive access to Lakeshore West GO or a
#   frequent TTC route with a competitive downtown connection.
# demand_share: share of AM-peak inbound person-trips crossing the screenline.
# quintile_mix: local household income distribution (Census 2021 neighbourhood
#   profiles), renormalised over the commuting population.
SUBAREAS = [
    # name, transit_access, demand_share, quintile_mix (Q1..Q5)
    ("Long Branch",              0.85, 0.070, (0.16, 0.24, 0.24, 0.22, 0.14)),
    ("New Toronto / Mimico S",   0.80, 0.075, (0.18, 0.25, 0.23, 0.21, 0.13)),
    ("Mimico / Park Lawn",       0.88, 0.130, (0.09, 0.16, 0.23, 0.28, 0.24)),
    ("Alderwood",                0.55, 0.065, (0.11, 0.19, 0.26, 0.27, 0.17)),
    ("Islington-City Centre W",  0.70, 0.145, (0.12, 0.18, 0.23, 0.26, 0.21)),
    ("Markland / Etobicoke W",   0.30, 0.115, (0.06, 0.11, 0.19, 0.30, 0.34)),
    ("Mississauga / west GTA",   0.45, 0.400, (0.08, 0.14, 0.22, 0.29, 0.27)),
]

# --- Income quintiles, City of Toronto CMA, Census 2021 ---------------------
# Midpoint household income used to scale value of time.
QUINTILES = [
    ("Q1", 24_000), ("Q2", 49_000), ("Q3", 79_000),
    ("Q4", 120_000), ("Q5", 215_000),
]

# Share of each quintile that cannot retime or work remotely (shift work,
# trades, healthcare, retail, logistics).  Falls steeply with income.
FIXED_SCHEDULE_SHARE = {"Q1": 0.62, "Q2": 0.52, "Q3": 0.36, "Q4": 0.22, "Q5": 0.14}

# Share able to substitute a remote day for the trip entirely.  Zero for
# fixed-schedule workers by construction.
WFH_CAPABLE = {"Q1": 0.06, "Q2": 0.13, "Q3": 0.28, "Q4": 0.44, "Q5": 0.52}

rows = []
for area, access, area_share, mix in SUBAREAS:
    assert abs(sum(mix) - 1.0) < 1e-9, area
    for (q, income), qshare in zip(QUINTILES, mix):
        fixed = FIXED_SCHEDULE_SHARE[q]
        for sched, sshare in (("fixed", fixed), ("flexible", 1.0 - fixed)):
            share = area_share * qshare * sshare
            if share < 1e-6:
                continue
            rows.append({
                "segment_id": f"{area.split(' /')[0].split(' (')[0].replace(' ', '_')}|{q}|{sched}",
                "subarea": area,
                "quintile": q,
                "household_income": income,
                "schedule": sched,
                "transit_access": access,
                "wfh_capable": 0.0 if sched == "fixed" else round(WFH_CAPABLE[q], 3),
                "share": share,
            })

total = sum(r["share"] for r in rows)
assert abs(total - 1.0) < 1e-9, total
for r in rows:
    r["share"] = round(r["share"], 8)

# Rounding drift -> push the residual onto the largest segment.
drift = 1.0 - sum(r["share"] for r in rows)
big = max(rows, key=lambda r: r["share"])
big["share"] = round(big["share"] + drift, 8)

with open("segments.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"wrote segments.csv: {len(rows)} segments, shares sum to {sum(r['share'] for r in rows):.10f}")
