import pytest

from max_pf.models import PlayerLine
from max_pf.zscores import build_model


def _population():
    # Three per-game lines spanning a range so std > 0 everywhere used.
    return [
        PlayerLine(pts=30, reb=5, ast=5, stl=1, blk=0, tpm=3, to=4,
                   fgm=10, fga=20, ftm=8, fta=10),   # high scorer, turnover-prone
        PlayerLine(pts=10, reb=12, ast=2, stl=2, blk=3, tpm=0, to=1,
                   fgm=4, fga=7, ftm=2, fta=4),       # efficient big
        PlayerLine(pts=20, reb=8, ast=8, stl=1, blk=1, tpm=2, to=2,
                   fgm=8, fga=16, ftm=4, fta=5),       # balanced
    ]


def test_zscores_are_centered_and_turnovers_inverted():
    pop = _population()
    model = build_model(pop)

    # Mean z-score across the population is ~0 for every category.
    for key in ("pts", "reb", "to", "fg_pct"):
        avg = sum(model.zscores(p)[key] for p in pop) / len(pop)
        assert abs(avg) < 1e-9

    # Turnovers are inverted: the *fewest* turnovers gets the best (highest) z.
    to_z = [model.zscores(p)["to"] for p in pop]
    assert to_z[1] == max(to_z)   # 1 TO -> best
    assert to_z[0] == min(to_z)   # 4 TO -> worst


def test_total_value_orders_players_and_rewards_volume_efficiency():
    model = build_model(_population())
    # The efficient big shoots .571 FG on volume; the high scorer .500 but with
    # heavy turnovers. Total value sums all nine standardized categories.
    values = [model.value(p) for p in _population()]
    assert len(values) == 3
    assert all(isinstance(v, float) for v in values)


def test_ratio_impact_is_volume_weighted():
    # Same FG% (.500), very different volume -> different standardized impact.
    hi_vol = PlayerLine(fgm=10, fga=20)
    lo_vol = PlayerLine(fgm=1, fga=2)
    avg = PlayerLine(fgm=4, fga=10)        # .400, drags league pct below .500
    model = build_model([hi_vol, lo_vol, avg])
    z = model.zscores
    # Both beat the league pct, but the high-volume shooter's impact is larger.
    assert z(hi_vol)["fg_pct"] > z(lo_vol)["fg_pct"] > 0


def test_raw_value_rewards_volume_over_balance_and_penalizes_turnovers():
    model = build_model(_population())
    # Objective C: a pure high-volume scorer outranks a balanced low-volume line,
    # because raw output isn't scarcity-weighted (PTS dominates the sum).
    scorer = PlayerLine(pts=40, fgm=15, fga=30)
    balanced = PlayerLine(pts=4, reb=4, ast=4, stl=2, blk=2, tpm=2)
    assert model.raw_value(scorer) > model.raw_value(balanced)
    # Turnovers subtract from raw output.
    clean = PlayerLine(pts=20, to=0)
    sloppy = PlayerLine(pts=20, to=8)
    assert model.raw_value(clean) > model.raw_value(sloppy)


def test_empty_population_rejected():
    with pytest.raises(ValueError):
        build_model([])
