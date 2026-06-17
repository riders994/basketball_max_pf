from max_pf.estimators import estimate_attempts


def reconstruct_points(fgm, tpm, ftm):
    """PTS from makes: 2*(FGM-3PTM) + 3*3PTM + FTM = 2*FGM + 3PTM + FTM."""
    return 2 * fgm + tpm + ftm


def test_reconstructs_points_for_typical_line():
    # Probed real line: PTS 23, 3PTM 1, FG% .563, FT% .667, guard.
    fgm, fga, ftm, fta = estimate_attempts(23, 1, 0.563, 0.667, ("PG",))
    assert abs(reconstruct_points(fgm, 1, ftm) - 23.0) < 1e-9
    # makes are consistent with the reported percentages
    assert abs(fgm / fga - 0.563) < 1e-9
    assert abs(ftm / fta - 0.667) < 1e-9
    assert fga > 0 and fta > 0


def test_dnp_line_is_all_zero():
    assert estimate_attempts(0, 0, 0.0, 0.0, ("C",)) == (0.0, 0.0, 0.0, 0.0)


def test_no_free_throws_means_no_fta():
    fgm, fga, ftm, fta = estimate_attempts(10, 0, 0.5, 0.0, ("SF",))
    assert ftm == 0.0 and fta == 0.0
    assert abs(reconstruct_points(fgm, 0, ftm) - 10.0) < 1e-9


def test_zero_fg_pct_but_played_gets_fallback_attempts():
    # 0% from the field but had points (all from the line) -> FGA from prior, FGM 0.
    fgm, fga, ftm, fta = estimate_attempts(4, 0, 0.0, 0.8, ("PG",))
    assert fgm == 0.0
    assert fga > 0.0  # missed attempts still weigh on team FG%


def test_position_prior_is_averaged():
    # A PG/C dual-eligible player gets the mean of the two FT-rate priors, so
    # its FTA share lands between the pure-PG and pure-C estimates.
    pg = estimate_attempts(20, 2, 0.5, 0.8, ("PG",))[3]
    c = estimate_attempts(20, 2, 0.5, 0.8, ("C",))[3]
    both = estimate_attempts(20, 2, 0.5, 0.8, ("PG", "C"))[3]
    assert min(pg, c) < both < max(pg, c)
