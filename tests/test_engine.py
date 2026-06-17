from max_pf.engine import period_delta, season_deltas
from max_pf.metric import catwins
from max_pf.models import PlayerLine
from max_pf.optimize import Candidate, Slot
from max_pf.platforms.fantrax import team_line_from_grid


def test_team_line_from_grid_sets_percentages_and_counts():
    grid = {
        "FG%": {"t1": 0.483, "t2": 0.461},
        "FT%": {"t1": 0.79, "t2": 0.77},
        "3PTM": {"t1": 77, "t2": 57},
        "PTS": {"t1": 649, "t2": 574},
        "REB": {"t1": 174, "t2": 201},
        "AST": {"t1": 127, "t2": 130},
        "ST": {"t1": 40, "t2": 35},
        "BLK": {"t1": 25, "t2": 22},
        "TO": {"t1": 90, "t2": 100},
    }
    line = team_line_from_grid(grid, "t1")
    assert line.pts == 649 and line.reb == 174 and line.tpm == 77 and line.to == 90
    assert abs(line.fg_pct - 0.483) < 1e-9  # exact grid percentage, unit denominator
    assert abs(line.ft_pct - 0.79) < 1e-9


def _cand(pid, **kw):
    return Candidate(pid, PlayerLine(**kw), ("PG",))


SLOTS = [Slot("Flx"), Slot("Flx"), Slot("Flx")]


class FakePlatform:
    def __init__(self, opp, actuals, cands):
        self._opp, self._actuals, self._cands = opp, actuals, cands

    def matchup_opponent(self, team_id, period):
        return self._opp.get((team_id, period))

    def actual_team_line(self, team_id, period):
        return self._actuals[(team_id, period)]

    def period_candidates(self, team_id, period, methodology="expected"):
        return self._cands[(team_id, period)]


def test_period_delta_wires_one_round_best_response():
    my_actual = PlayerLine(pts=400, reb=150, ast=100, stl=30, blk=20, tpm=40, to=80, fgm=45, fga=100, ftm=70, fta=90)
    opp_actual = PlayerLine(pts=380, reb=140, ast=90, stl=25, blk=18, tpm=35, to=95, fgm=44, fga=100, ftm=68, fta=92)
    plat = FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): my_actual, ("opp", 1): opp_actual},
        cands={
            ("me", 1): [[_cand("m1", pts=420, reb=160, ast=110, stl=33, blk=22, tpm=44, to=70, fgm=50, fga=100, ftm=72, fta=88)]],
            ("opp", 1): [[_cand("o1", pts=500, reb=220, ast=140, stl=45, blk=30, tpm=60, to=60, fgm=55, fga=100, ftm=80, fta=90)]],
        },
    )
    res = period_delta(plat, "me", 1, SLOTS)
    assert res is not None
    # Δ identity holds, and the realized result is recomputed from actuals.
    assert res.delta == res.m1.points_for - res.m2.points_for
    assert res.actual == catwins(my_actual, opp_actual)
    # M1 (vs opp's actual) should be at least as good as M2 (vs opp's optimum).
    assert res.m1.points_for >= res.m2.points_for


def test_bye_period_returns_none():
    plat = FakePlatform(opp={("me", 5): None}, actuals={}, cands={})
    assert period_delta(plat, "me", 5, SLOTS) is None
    assert season_deltas(plat, "me", [5], SLOTS) == {}
