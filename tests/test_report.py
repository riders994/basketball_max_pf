import csv
import io

from max_pf.models import PlayerLine
from max_pf.optimize import Candidate, Slot
from max_pf.report import (
    TeamSeason,
    render_csv,
    render_markdown,
    render_table,
    season_report,
)


def test_team_season_derived_metrics():
    ts = TeamSeason("t", "Team", periods=10, actual_pf=40.0, m1_pf=50.0, m2_pf=44.0, m3_pf=47.0)
    assert ts.delta == 6.0           # M1 - M2
    assert ts.potential == -10.0     # Actual - M1 (left on the table vs exploitation ceiling)
    assert ts.passivity == 3.0       # M1 - M3 (opponent-passivity dividend)
    assert ts.anticipation == 3.0    # M3 - M2 (decoupled estimate -> equilibrium)
    assert ts.luck == -7.0           # Actual - M3 (fell short of the both-optimal equilibrium)


def _rows():
    return [
        TeamSeason("t1", "Alpha", 4, 24.0, 28.0, 25.0),
        TeamSeason("t2", "Beta", 4, 12.0, 18.0, 16.0),
    ]


def test_render_csv_roundtrips():
    # _rows() carries no m3_pf, so the M3-relative columns (M3, Passivity, Anticipation,
    # Luck) are gated out; Potential (Actual - M1) is M1-only, so it stays.
    parsed = list(csv.reader(io.StringIO(render_csv(_rows()))))
    assert parsed[0] == ["Team", "GP", "Actual", "M1", "M2", "Delta", "Potential"]
    assert parsed[1][0] == "Alpha" and parsed[1][2] == "24.0"


def test_render_table_and_markdown_contain_teams():
    table = render_table(_rows())
    assert "Alpha" in table and "Beta" in table
    md = render_markdown(_rows())
    assert md.startswith("| Team |") and "| Alpha |" in md


# --- small end-to-end through the engine with a fake platform ---------------

SLOTS = [Slot("Flx"), Slot("Flx")]


class FakePlatform:
    def __init__(self):
        strong = PlayerLine(pts=120, reb=60, ast=40, stl=12, blk=8, tpm=15, to=18, fgm=50, fga=100, ftm=20, fta=25)
        weak = PlayerLine(pts=80, reb=40, ast=25, stl=7, blk=4, tpm=9, to=24, fgm=40, fga=100, ftm=15, fta=22)
        self._actual = {("A", 1): strong, ("B", 1): weak}
        self._cand = {
            ("A", 1): [[Candidate("a", strong, ("PG",))]],
            ("B", 1): [[Candidate("b", weak, ("SG",))]],
        }

    def team_ids(self):
        return ["A", "B"]

    def team_name(self, team_id):
        return {"A": "Alpha", "B": "Beta"}[team_id]

    def matchup_periods(self):
        return [1]

    def matchup_opponent(self, team_id, period):
        return {"A": "B", "B": "A"}[team_id]

    def actual_team_line(self, team_id, period):
        return self._actual[(team_id, period)]

    def period_candidates(self, team_id, period, methodology="expected"):
        return self._cand[(team_id, period)]


def test_season_report_sorted_by_actual():
    rows = season_report(FakePlatform(), SLOTS, periods=[1])
    assert [r.name for r in rows] == ["Alpha", "Beta"]  # Alpha scored more, sorted first
    assert all(r.periods == 1 for r in rows)
    assert rows[0].m1_pf >= rows[0].actual_pf  # ceiling >= actual


def test_season_report_omits_nash_columns_when_disabled():
    rows = season_report(FakePlatform(), SLOTS, periods=[1], include_nash=False)
    assert all(r.m3_pf is None for r in rows)
    header = list(csv.reader(io.StringIO(render_csv(rows))))[0]
    assert "M3" not in header and "Passivity" not in header and "Anticipation" not in header
    assert "Luck" not in header        # Actual - M3, gated out
    assert "Potential" in header       # Actual - M1, always shown


def test_season_report_includes_nash_columns_by_default():
    rows = season_report(FakePlatform(), SLOTS, periods=[1])
    assert all(r.m3_pf is not None for r in rows)
    # M3 is the mutual ceiling; M1 (exploit opponent's actual) should not be below it.
    assert all(r.m1_pf >= r.m3_pf for r in rows)

    header = list(csv.reader(io.StringIO(render_csv(rows))))[0]
    assert header == ["Team", "GP", "Actual", "M1", "M2", "M3", "Passivity",
                      "Anticipation", "Delta", "Potential", "Luck"]
    md = render_markdown(rows)
    assert "| M3 |" in md and "| Passivity |" in md and "| Anticipation |" in md
    assert "M3" in render_table(rows)
