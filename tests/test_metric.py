from max_pf.metric import catwins, category_outcome, compute_delta
from max_pf.models import PlayerLine, aggregate


def line(**kw) -> PlayerLine:
    return PlayerLine(**kw)


def test_turnovers_lower_is_better():
    # Fewer turnovers should win the TO category.
    assert category_outcome(2, 5, lower_is_better=True) == 1
    assert category_outcome(5, 2, lower_is_better=True) == -1
    assert category_outcome(3, 3, lower_is_better=True) == 0


def test_catwins_counts_wld_and_draws_are_half():
    a = line(pts=100, reb=50, ast=30, stl=10, blk=5, tpm=12, to=10, fgm=40, fga=80, ftm=20, fta=25)
    b = line(pts=90, reb=50, ast=20, stl=8, blk=8, tpm=10, to=12, fgm=35, fga=80, ftm=18, fta=25)
    res = catwins(a, b)
    # a wins: pts, ast, stl, tpm, to(fewer), fg% (40/80 vs 35/80), ft% (.8 vs .72) = 7
    # tie: reb (50 vs 50)
    # b wins: blk = 1
    assert (res.wins, res.losses, res.draws) == (7, 1, 1)
    assert res.points_for == 7 + 0.5


def test_percentages_aggregate_by_volume_not_average():
    # Two players: one efficient low-volume, one inefficient high-volume.
    p1 = line(fgm=1, fga=2)      # 50% on 2 attempts
    p2 = line(fgm=3, fga=18)     # 16.7% on 18 attempts
    team = aggregate([p1, p2])
    assert abs(team.fg_pct - 4 / 20) < 1e-9  # 20%, not the 33% you'd get averaging


def test_compute_delta_is_m1_minus_m2():
    mine_opt = line(pts=100, reb=60, ast=30, stl=10, blk=6, tpm=14, to=8, fgm=45, fga=90, ftm=22, fta=26)
    opp_actual = line(pts=80, reb=40, ast=20, stl=6, blk=4, tpm=9, to=12, fgm=30, fga=80, ftm=15, fta=22)
    their_opt = line(pts=110, reb=70, ast=35, stl=12, blk=9, tpm=16, to=6, fgm=50, fga=95, ftm=25, fta=28)
    res = compute_delta(mine_opt, opp_actual, their_opt)
    assert res.delta == res.m1.points_for - res.m2.points_for
    # mine_opt crushes opp_actual but loses to their_opt -> positive dividend.
    assert res.m1.points_for > res.m2.points_for
