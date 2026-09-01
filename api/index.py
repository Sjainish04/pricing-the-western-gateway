"""Vercel serverless entrypoint.

Vercel's Python runtime turns every file under `/api` into a function and looks
for a module-level ASGI callable named `app`.  The whole application already is
one, so this file only has to put `backend/` on the import path and re-export
it -- there is no second copy of the API here, and nothing to keep in sync.

Two things about running this model on serverless that are worth stating,
because they shaped the setup rather than being incidental:

**Cold starts recalibrate.**  `simulate` caches the fitted choice constants in
process memory, and a serverless process does not survive between requests, so
the first request to a cold instance pays the calibration again -- about 1.6 s
on top of ~1.6 s of imports.  That is tolerable for a study interface and it is
why `maxDuration` is 60 s rather than the default.

**Three endpoints cannot be computed here at all.**  The bargaining sweep is
about 100 seconds and the joint game about 70, against a hard ceiling of 60 on
Vercel Pro and 10 on the free tier.  They are served from
`backend/data/precomputed/`, which is committed; see `uttan/precomputed.py` for
why that is a cache rather than a fork of the results, and what stops it going
stale.  Nothing here silently degrades: if a precomputed entry is missing or
its fingerprint no longer matches, the endpoint falls back to computing and
will time out visibly rather than serve a wrong number quietly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/ holds both the `api` package and the `uttan` package. Inserting it
# rather than appending means the application's own modules win over anything
# with a colliding name in the runtime image.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from api.main import app  # noqa: E402,F401  (re-exported for the runtime)

__all__ = ["app"]
