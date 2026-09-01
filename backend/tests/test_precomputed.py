"""Tests for the precomputed API results.

A committed JSON file that no longer matches the model it was generated from is
this codebase's characteristic failure in its purest form: a plausible number,
served confidently, with nothing raising. These tests are the thing standing
between that and a deployment.

The expensive check -- recomputing each entry and comparing it to the file --
is marked slow, because it costs about three minutes. It is the one that
actually catches staleness, so it must run before any deploy.
"""
from __future__ import annotations

import json

import pytest

from uttan import bargaining, joint_game, phasing, precomputed, rejoin_validation
from uttan.config import Config

BUILDERS = {
    "rejoin": rejoin_validation.report,
    "phasing": phasing.report,
    "bargaining": bargaining.report,
    "joint": joint_game.report,
    "joint_optimum": joint_game.joint_optimum,
    "gate_dependence": joint_game.gate_dependence_sweep,
}


@pytest.fixture(scope="module")
def cfg():
    return Config()


def _strip(obj):
    """Drop the provenance marker `serve` adds, so payloads compare equal."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "_source"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


# --------------------------------------------------------------------------
# The cache exists and is wired up
# --------------------------------------------------------------------------

def test_every_slow_endpoint_has_an_entry():
    """The three endpoints that cannot run inside a serverless timeout, plus
    rejoin. If one is added to ENTRIES without being generated, deploys start
    timing out instead of serving."""
    assert set(precomputed.ENTRIES) == set(BUILDERS)


def test_all_entries_are_present_and_valid(cfg):
    """Missing or stale entries do not break the API -- they make it fall back
    to computing, which on Vercel is a timeout. So this is a deploy gate."""
    st = precomputed.status(cfg)
    bad = [r for r in st["entries"] if r["state"] != "valid"]
    assert not bad, (
        f"regenerate with `python scripts/precompute.py`: {bad}"
    )


def test_fingerprint_tracks_the_whole_config(cfg):
    """A config change must invalidate the cache, whatever parameter moved.

    Fingerprinting a hand-picked subset would mean deciding in advance which
    parameters can affect a result, and being wrong about that is exactly how a
    stale file survives.
    """
    base = precomputed.fingerprint(cfg)
    for field, value in (
        ("rejoin_fraction", 0.6),
        ("political_cost_per_charged_trip", 2.0),
        ("discount_rate", 0.05),
        ("vot_base_per_hour", 25.0),
    ):
        moved = Config.from_dict({**cfg.to_dict(), field: value})
        assert precomputed.fingerprint(moved) != base, field


def test_a_stale_entry_is_never_served(cfg):
    """The guard that makes this a cache rather than a second set of results."""
    moved = Config.from_dict({**cfg.to_dict(), "rejoin_fraction": 0.31})
    for name in precomputed.ENTRIES:
        assert precomputed.load(name, moved) is None, name


def test_serve_reports_where_the_answer_came_from(cfg):
    """Provenance discipline applies to the cache too: a reader is entitled to
    know whether a number was computed or read off disk."""
    hit = precomputed.serve("rejoin", lambda: {"never": "called"}, cfg)
    assert hit["_source"] == "precomputed"

    moved = Config.from_dict({**cfg.to_dict(), "rejoin_fraction": 0.31})
    miss = precomputed.serve("rejoin", lambda: {"computed": True}, moved)
    assert miss["_source"] == "computed"
    assert miss["computed"] is True


def test_a_corrupt_file_falls_back_rather_than_raising(tmp_path, monkeypatch, cfg):
    """A broken cache should make the API slower, never down."""
    monkeypatch.setattr(precomputed, "DIR", tmp_path)
    (tmp_path / "rejoin.json").write_text("{not json", encoding="utf-8")
    assert precomputed.load("rejoin", cfg) is None
    assert precomputed.serve("rejoin", lambda: {"ok": 1}, cfg)["_source"] == "computed"


def test_entries_are_json_serialisable_and_not_empty():
    for name in precomputed.ENTRIES:
        path = precomputed.path_for(name)
        assert path.exists(), name
        blob = json.loads(path.read_text(encoding="utf-8"))
        assert blob["_entry"] == name
        assert blob["_fingerprint"]
        assert isinstance(blob["result"], dict) and blob["result"]


# --------------------------------------------------------------------------
# The check that actually catches staleness
# --------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_precomputed_matches_a_live_recomputation(name, cfg):
    """Recompute each entry and require it to equal what is committed.

    This is the deploy gate. The fingerprint catches a changed *parameter*; only
    this catches changed *code* -- a rewritten solver that still reads the same
    config would pass every other check here while the committed answer quietly
    stopped being the model's answer.
    """
    live = _strip(BUILDERS[name]())
    stored = _strip(precomputed.load(name, cfg))
    assert stored is not None, f"{name} is missing or stale"
    assert json.dumps(stored, sort_keys=True) == json.dumps(live, sort_keys=True), (
        f"{name} is out of date -- regenerate with `python scripts/precompute.py`"
    )
