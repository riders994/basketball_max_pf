"""Exact zero-sum (constant-sum) matrix-game solver via linear programming.

Computes the value and optimal mixed strategies of a two-player zero-sum game
from its row-player payoff matrix. Used by the Nash mutual-ceiling double-oracle
(engine stage 2) to *value* matchup periods whose iterated best responses cycle
-- i.e. have no pure-strategy equilibrium, so the ceiling is a mixed-strategy
minimax value rather than a single pair of lineups.

The 9-category payoff is constant-sum (a period's category points always total 9,
ties split), so maximizing the row player's points-for is exactly the minimax
game and the value is well defined.

Method: two linear programs (one per player), each the textbook matrix-game LP

    row (maximizer):  max v  s.t.  Aᵀx >= v·1,  1ᵀx = 1,  x >= 0
    col (minimizer):  min w  s.t.  A y <= w·1,  1ᵀy = 1,  y >= 0

solved with ``scipy.optimize.linprog`` (HiGHS). Both LPs share the same optimal
value; we return the row LP's value and cross-check the column LP's against it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

# Row/column values agree in exact arithmetic; allow for LP solver tolerance.
_VALUE_TOL = 1e-6


@dataclass(frozen=True)
class GameSolution:
    """Solution of a zero-sum matrix game from the row player's perspective."""

    value: float                 # row player's guaranteed expected payoff
    row_strategy: list[float]    # optimal mixed strategy over rows (sums to 1)
    col_strategy: list[float]    # optimal mixed strategy over columns (sums to 1)


def _solve_player(payoff: np.ndarray) -> tuple[float, list[float]]:
    """Maximin LP for the row player of ``payoff``: returns (value, row strategy).

    Variables are ``[x_0..x_{m-1}, v]`` with ``v`` free; we minimize ``-v`` subject
    to ``v - (Aᵀx)_j <= 0`` for each column ``j`` and ``1ᵀx = 1``.
    """
    m, n = payoff.shape
    c = [0.0] * m + [-1.0]                         # minimize -v  (maximize v)
    # For each column j: v - sum_i A[i][j] x_i <= 0.
    a_ub = [[-payoff[i, j] for i in range(m)] + [1.0] for j in range(n)]
    b_ub = [0.0] * n
    a_eq = [[1.0] * m + [0.0]]                     # probabilities sum to 1
    b_eq = [1.0]
    bounds = [(0.0, None)] * m + [(None, None)]    # x >= 0, v free
    res = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        raise ValueError(f"matrix-game LP failed: {res.message}")
    value = float(res.x[-1])
    strategy = [max(0.0, float(p)) for p in res.x[:m]]
    total = sum(strategy) or 1.0
    return value, [p / total for p in strategy]


def solve_zero_sum_game(payoff: list[list[float]]) -> GameSolution:
    """Solve the zero-sum matrix game with row-player ``payoff`` matrix.

    ``payoff[i][j]`` is the row player's (maximizer's) payoff when it plays pure
    strategy ``i`` and the column player (minimizer) plays ``j``. Returns the game
    value and both optimal mixed strategies. The column strategy is obtained by
    solving the maximin LP of the transposed, negated game (the column player as a
    maximizer), so the same routine serves both sides.
    """
    a = np.asarray(payoff, dtype=float)
    if a.ndim != 2 or a.size == 0:
        raise ValueError("payoff must be a non-empty 2-D matrix")
    value, row_strategy = _solve_player(a)
    # Column player maximizes its own payoff -Aᵀ; its value is -(row value).
    neg_value, col_strategy = _solve_player(-a.T)
    if abs(value + neg_value) > _VALUE_TOL:
        raise ValueError(f"row/column game values disagree: {value} vs {-neg_value}")
    return GameSolution(value=value, row_strategy=row_strategy, col_strategy=col_strategy)
