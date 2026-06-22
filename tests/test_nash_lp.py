import math

from max_pf.nash_lp import solve_zero_sum_game


def _approx(xs, ys, tol=1e-6):
    return all(math.isclose(a, b, abs_tol=tol) for a, b in zip(xs, ys))


def test_rock_paper_scissors_value_zero_uniform():
    sol = solve_zero_sum_game([[0, -1, 1], [1, 0, -1], [-1, 1, 0]])
    assert math.isclose(sol.value, 0.0, abs_tol=1e-7)
    assert _approx(sol.row_strategy, [1 / 3, 1 / 3, 1 / 3])
    assert _approx(sol.col_strategy, [1 / 3, 1 / 3, 1 / 3])


def test_matching_pennies_value_zero_uniform():
    sol = solve_zero_sum_game([[1, -1], [-1, 1]])
    assert math.isclose(sol.value, 0.0, abs_tol=1e-7)
    assert _approx(sol.row_strategy, [0.5, 0.5])
    assert _approx(sol.col_strategy, [0.5, 0.5])


def test_saddle_point_pure_strategies():
    # Row 0 dominates row 1; the column player then prefers column 0 (payoff 2).
    sol = solve_zero_sum_game([[2, 3], [0, 1]])
    assert math.isclose(sol.value, 2.0, abs_tol=1e-7)
    assert _approx(sol.row_strategy, [1.0, 0.0])
    assert _approx(sol.col_strategy, [1.0, 0.0])


def test_strategies_are_probability_distributions():
    sol = solve_zero_sum_game([[3, 0, 4], [1, 5, 2], [4, 2, 1]])
    assert math.isclose(sum(sol.row_strategy), 1.0, abs_tol=1e-7)
    assert math.isclose(sum(sol.col_strategy), 1.0, abs_tol=1e-7)
    assert all(p >= -1e-9 for p in sol.row_strategy + sol.col_strategy)
    # Value is bounded by the matrix entries either way.
    assert 0.0 <= sol.value <= 5.0


def test_constant_sum_shifts_value_but_not_strategies():
    # Adding a constant to every payoff shifts the value by that constant and
    # leaves the optimal strategies unchanged (the shift used internally).
    base = [[0, -1, 1], [1, 0, -1], [-1, 1, 0]]
    shifted = [[v + 4.5 for v in row] for row in base]
    sol = solve_zero_sum_game(shifted)
    assert math.isclose(sol.value, 4.5, abs_tol=1e-7)
    assert _approx(sol.row_strategy, [1 / 3, 1 / 3, 1 / 3])


def test_single_strategy_each_side():
    sol = solve_zero_sum_game([[4.5]])
    assert math.isclose(sol.value, 4.5, abs_tol=1e-7)
    assert sol.row_strategy == [1.0]
    assert sol.col_strategy == [1.0]
