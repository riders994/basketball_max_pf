import json

import pytest

from max_pf.app import (
    PLATFORMS,
    build_platform,
    load_login,
    parse_weeks,
    register_platform,
    run,
)
from max_pf.models import PlayerLine
from max_pf.optimize import Candidate, Slot


def test_parse_weeks_forms():
    assert parse_weeks(None) is None
    assert parse_weeks(5) == [5]
    assert parse_weeks("5") == [5]
    assert parse_weeks("1-6") == [1, 2, 3, 4, 5, 6]
    assert parse_weeks("1,2,5") == [1, 2, 5]
    assert parse_weeks([3, 1, 3]) == [1, 3]
    assert parse_weeks(range(2, 5)) == [2, 3, 4]


def test_build_platform_dispatch_and_errors():
    register_platform("dummy", lambda login: ("built", login["x"]))
    try:
        assert build_platform({"platform": "dummy", "x": 9}) == ("built", 9)
        with pytest.raises(ValueError):
            build_platform({"platform": "nope"})
        with pytest.raises(ValueError):
            build_platform({})           # no 'platform' key
        with pytest.raises(ValueError):
            build_platform("not a dict")
    finally:
        PLATFORMS.pop("dummy", None)


def test_fantrax_login_requires_league_id():
    with pytest.raises(ValueError):
        build_platform({"platform": "fantrax"})  # missing league_id


def test_load_login_json(tmp_path):
    p = tmp_path / "league.json"
    p.write_text(json.dumps({"platform": "fantrax", "league_id": "abc"}))
    assert load_login(p) == {"platform": "fantrax", "league_id": "abc"}


def test_load_login_yaml(tmp_path):
    yaml = pytest.importorskip("yaml")
    p = tmp_path / "league.yaml"
    p.write_text(yaml.safe_dump({"platform": "fantrax", "league_id": "abc"}))
    assert load_login(p) == {"platform": "fantrax", "league_id": "abc"}


def test_load_login_rejects_unknown_type_and_nonmapping(tmp_path):
    bad_ext = tmp_path / "league.txt"
    bad_ext.write_text("{}")
    with pytest.raises(ValueError):
        load_login(bad_ext)
    not_map = tmp_path / "league.json"
    not_map.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        load_login(not_map)


class _FakePlatform:
    """Minimal platform the season report + run() need."""

    def team_ids(self):
        return ["a", "b"]

    def team_name(self, tid):
        return {"a": "Alpha", "b": "Beta"}[tid]

    def matchup_periods(self):
        return [1]

    def active_slots(self):
        return [Slot("Flx"), Slot("Flx")]

    def matchup_opponent(self, tid, period):
        return "b" if tid == "a" else "a"

    def actual_team_line(self, tid, period):
        return PlayerLine(pts=100) if tid == "a" else PlayerLine(pts=90)

    def period_candidates(self, tid, period, methodology):
        pts = 120 if tid == "a" else 80
        return [[Candidate(tid + "1", PlayerLine(pts=pts), ("PG",))]]


def test_run_end_to_end_with_fake_platform():
    register_platform("fake", lambda login: _FakePlatform())
    try:
        rows = run({"platform": "fake"}, boxscores=False)
        assert [r.name for r in rows] == ["Alpha", "Beta"]  # sorted by actual pf
        assert rows[0].periods == 1
        # Scoping to a week still works.
        assert run({"platform": "fake"}, weeks=1, boxscores=False)[0].name == "Alpha"
    finally:
        PLATFORMS.pop("fake", None)
