"""Generate the precomputed API results.

Run from the backend directory:

    python scripts/precompute.py           # regenerate everything
    python scripts/precompute.py bargaining joint

Takes a few minutes, dominated by the bargaining and joint-game sweeps, which
are hundreds of equilibria each.  Deliberately NOT part of the build: a build
that recomputes this would take twelve minutes every deploy and would silently
produce a different answer if anything drifted.  Committing the output makes
the deployed numbers identical to the reviewed ones, and
`test_precomputed.py` fails if they stop matching.

Regenerate after any change to `config.py` or to the modules below. The
fingerprint guard means forgetting is slow rather than wrong -- the API falls
back to live computation, which on Vercel means a timeout on those three
endpoints, so forgetting is still worth avoiding.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uttan import bargaining, joint_game, phasing, precomputed, rejoin_validation  # noqa: E402
from uttan.config import Config  # noqa: E402

BUILDERS = {
    "rejoin": rejoin_validation.report,
    "phasing": phasing.report,
    "bargaining": bargaining.report,
    "joint": joint_game.report,
    "joint_optimum": joint_game.joint_optimum,
    "gate_dependence": joint_game.gate_dependence_sweep,
}


def main(argv: list[str]) -> int:
    wanted = argv[1:] or list(BUILDERS)
    unknown = [w for w in wanted if w not in BUILDERS]
    if unknown:
        print(f"unknown entries: {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(BUILDERS)}", file=sys.stderr)
        return 2

    cfg = Config()
    print(f"fingerprint {precomputed.fingerprint(cfg)}")
    total = 0.0
    for name in wanted:
        t = time.time()
        result = BUILDERS[name]()
        path = precomputed.write(name, result, cfg)
        dt = time.time() - t
        total += dt
        print(f"  {name:12s} {dt:6.1f}s  {path.stat().st_size / 1024:8.1f} KB")
    print(f"  {'total':12s} {total:6.1f}s")

    st = precomputed.status(cfg)
    if not st["all_valid"]:
        bad = [r["entry"] for r in st["entries"] if r["state"] != "valid"]
        print(f"WARNING: not valid after writing: {', '.join(bad)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
