from max_pf.engine import nash_ceiling, period_delta, season_deltas
from max_pf.metric import catwins
from max_pf.models import PlayerLine
from max_pf.optimize import Candidate, Slot
from max_pf.platforms.fantrax import team_line_from_grid
from max_pf.zscores import build_model


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

    def zscore_model(self, period):
        # League-wide population: every candidate line across both teams.
        pop = [c.line for cands in self._cands.values() for day in cands for c in day]
        return build_model(pop)


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


def test_zscore_objective_picks_max_value_lineup_independent_of_opponent():
    # One slot forces a choice between a strong and a weak candidate.
    strong = _cand("m_hi", pts=40, reb=12, ast=9, stl=3, blk=2, tpm=4, to=1, fgm=15, fga=25, ftm=8, fta=9)
    weak = _cand("m_lo", pts=3, reb=1, ast=0, stl=0, blk=0, tpm=0, to=5, fgm=1, fga=9, ftm=1, fta=2)
    opp = _cand("o1", pts=20, reb=8, ast=5, stl=1, blk=1, tpm=2, to=3, fgm=8, fga=16, ftm=4, fta=6)
    plat = FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): PlayerLine(pts=10), ("opp", 1): PlayerLine(pts=10)},
        cands={("me", 1): [[strong, weak]], ("opp", 1): [[opp]]},
    )
    res = period_delta(plat, "me", 1, [Slot("Flx")], objective="zscore")
    assert res is not None
    # The z-objective started the high-value player regardless of the opponent;
    # mine_opt's line reflects the strong candidate, not the weak one.
    assert res.m1.points_for == catwins(strong.line, plat.actual_team_line("opp", 1)).points_for


def test_raw_objective_routes_and_picks_high_output_lineup():
    strong = _cand("m_hi", pts=40, reb=12, ast=9, stl=3, blk=2, tpm=4, to=1, fgm=15, fga=25, ftm=8, fta=9)
    weak = _cand("m_lo", pts=3, reb=1, ast=0, stl=0, blk=0, tpm=0, to=5, fgm=1, fga=9, ftm=1, fta=2)
    opp = _cand("o1", pts=20, reb=8, ast=5, stl=1, blk=1, tpm=2, to=3, fgm=8, fga=16, ftm=4, fta=6)
    plat = FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): PlayerLine(pts=10), ("opp", 1): PlayerLine(pts=10)},
        cands={("me", 1): [[strong, weak]], ("opp", 1): [[opp]]},
    )
    res = period_delta(plat, "me", 1, [Slot("Flx")], objective="raw")
    assert res is not None
    assert res.m1.points_for == catwins(strong.line, plat.actual_team_line("opp", 1)).points_for


def test_bye_period_returns_none():
    plat = FakePlatform(opp={("me", 5): None}, actuals={}, cands={})
    assert period_delta(plat, "me", 5, SLOTS) is None
    assert season_deltas(plat, "me", [5], SLOTS) == {}
    assert nash_ceiling(plat, "me", 5, SLOTS) is None


def test_nash_converges_to_fixed_point():
    # One dominant candidate per side -> best response is constant -> the pair is
    # immediately a mutual best response (pure Nash equilibrium).
    me = _cand("M", pts=30, reb=10, ast=8)
    opp = _cand("O", pts=20, reb=12, ast=4)
    plat = FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): PlayerLine(), ("opp", 1): PlayerLine()},  # seed != optimum
        cands={("me", 1): [[me]], ("opp", 1): [[opp]]},
    )
    res = nash_ceiling(plat, "me", 1, [Slot("Flx")])
    assert res.converged
    assert res.mine.pts == 30 and res.theirs.pts == 20
    assert res.m3 == catwins(me.line, opp.line)


def _cycle_platform():
    # Cyclic dominance over pts/reb/ast (a 4-cycle A>X>B>Y>A): best responses
    # chase each other forever, so there is no pure-strategy equilibrium.
    A = _cand("A", pts=2, reb=2, ast=0)
    B = _cand("B", pts=0, reb=2, ast=2)
    X = _cand("X", pts=1, reb=0, ast=3)
    Y = _cand("Y", pts=3, reb=1, ast=1)
    return FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): A.line, ("opp", 1): X.line},
        cands={("me", 1): [[A, B]], ("opp", 1): [[X, Y]]},
    )


def test_nash_detects_cycle_when_no_pure_equilibrium():
    res = nash_ceiling(_cycle_platform(), "me", 1, [Slot("Flx")], max_rounds=50)
    assert not res.converged
    assert res.equilibrium == "mixed"


def test_nash_cycle_resolves_to_mixed_strategy_value():
    # The 4-cycle's payoff matrix (rows me=[A,B], cols opp=[X,Y]) is
    # [[5, 4], [4, 5]] in category points: a matching-pennies game whose minimax
    # value is 4.5 at the 50/50 mixture on each side. Stage 2 recovers it.
    res = nash_ceiling(_cycle_platform(), "me", 1, [Slot("Flx")])
    assert res.value == 4.5
    assert res.m3_pf == 4.5
    assert {round(w, 6) for _, w in res.mine_mix} == {0.5}
    assert {round(w, 6) for _, w in res.theirs_mix} == {0.5}
    # Each side's mixture has two lineups summing to a proper distribution.
    assert abs(sum(w for _, w in res.mine_mix) - 1.0) < 1e-9
    assert abs(sum(w for _, w in res.theirs_mix) - 1.0) < 1e-9


def test_nash_pure_result_carries_value_equal_to_points_for():
    me = _cand("M", pts=30, reb=10, ast=8)
    opp = _cand("O", pts=20, reb=12, ast=4)
    plat = FakePlatform(
        opp={("me", 1): "opp"},
        actuals={("me", 1): PlayerLine(), ("opp", 1): PlayerLine()},
        cands={("me", 1): [[me]], ("opp", 1): [[opp]]},
    )
    res = nash_ceiling(plat, "me", 1, [Slot("Flx")])
    assert res.equilibrium == "pure"
    assert res.value == res.m3.points_for == res.m3_pf
