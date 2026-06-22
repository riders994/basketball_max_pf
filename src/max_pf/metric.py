"""Category-win scoring and the max-points-for (Delta) metric.

"Points for" in this 9-cat H2H league is category wins, where a tie is a draw
(0.5). The headline metric is::

    M1 = catwins(mine_opt, opp_actual)     # exploitation ceiling
    M2 = catwins(mine_opt, their_opt)       # same lineup vs their best counter
    delta = M1 - M2                          # opponent-mismanagement dividend

where ``mine_opt`` / ``their_opt`` come from one round of best-response (each
side best-responds to the other's actual line). See docs/PROMPT_LOG.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from .categories import CATEGORIES
from .models import PlayerLine


@dataclass(frozen=True)
class CategoryResult:
    wins: int
    losses: int
    draws: int

    @property
    def points_for(self) -> float:
        """Category points: a win is 1, a draw is 0.5."""
        return self.wins + 0.5 * self.draws


def category_outcome(a: float, b: float, lower_is_better: bool) -> int:
    """Return +1 if A wins the category, -1 if B wins, 0 for a draw."""
    if a == b:
        return 0
    a_better = (a < b) if lower_is_better else (a > b)
    return 1 if a_better else -1


def catwins_from_values(a_vals: dict[str, float], b_vals: dict[str, float]) -> CategoryResult:
    """``catwins`` on already-extracted category-value dicts.

    Lets hot callers (the optimizer's inner loop) build each line's
    ``category_values()`` once and reuse it, instead of rebuilding it per call.
    """
    wins = losses = draws = 0
    for cat in CATEGORIES:
        outcome = category_outcome(a_vals[cat.key], b_vals[cat.key], cat.lower_is_better)
        if outcome > 0:
            wins += 1
        elif outcome < 0:
            losses += 1
        else:
            draws += 1
    return CategoryResult(wins, losses, draws)


def catwins(a: PlayerLine, b: PlayerLine) -> CategoryResult:
    """Score team A's category line against team B's across all 9 categories."""
    return catwins_from_values(a.category_values(), b.category_values())


@dataclass(frozen=True)
class DeltaResult:
    m1: CategoryResult  # mine_opt vs opp_actual
    m2: CategoryResult  # mine_opt vs their_opt
    actual: CategoryResult | None = None  # my_actual vs opp_actual, if known

    @property
    def delta(self) -> float:
        """Opponent-mismanagement dividend, in category points."""
        return self.m1.points_for - self.m2.points_for


def compute_delta(
    mine_opt: PlayerLine,
    opp_actual: PlayerLine,
    their_opt: PlayerLine,
    my_actual: PlayerLine | None = None,
) -> DeltaResult:
    """Compute the M1/M2/Delta triplet for a single matchup period."""
    return DeltaResult(
        m1=catwins(mine_opt, opp_actual),
        m2=catwins(mine_opt, their_opt),
        actual=catwins(my_actual, opp_actual) if my_actual is not None else None,
    )
