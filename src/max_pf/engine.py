"""Orchestration: turn a platform + slots into the per-period max-points-for Δ.

Ties together projections/optimizer/metric. For each matchup period:

    mine_opt  = best_response(my candidates,  slots, opp_actual)
    their_opt = best_response(opp candidates, slots, my_actual)
    Δ         = compute_delta(mine_opt, opp_actual, their_opt, my_actual)

This is the one-round best-response design (each side best-responds to the
other's *actual* line). See docs/PROMPT_LOG.md.
"""
from __future__ import annotations

from typing import Protocol

from .metric import DeltaResult, compute_delta
from .models import PlayerLine
from .optimize import Candidate, Slot, best_response


class SupportsMaxPF(Protocol):
    """Minimal platform surface the engine needs (see platforms.base)."""

    def matchup_opponent(self, team_id: str, period: int) -> str | None: ...
    def actual_team_line(self, team_id: str, period: int) -> PlayerLine: ...
    def period_candidates(self, team_id: str, period: int, methodology: str) -> list[list[Candidate]]: ...


def period_delta(
    platform: SupportsMaxPF,
    team_id: str,
    period: int,
    slots: list[Slot],
    methodology: str = "expected",
) -> DeltaResult | None:
    """Compute the M1/M2/Δ triplet for one team in one matchup period.

    ``methodology`` selects the candidate source ("expected" or "hindsight").
    Returns ``None`` when the team has no opponent that period (e.g. a bye).
    """
    opponent = platform.matchup_opponent(team_id, period)
    if opponent is None:
        return None

    my_actual = platform.actual_team_line(team_id, period)
    opp_actual = platform.actual_team_line(opponent, period)

    my_cands = platform.period_candidates(team_id, period, methodology)
    opp_cands = platform.period_candidates(opponent, period, methodology)
    mine_opt = best_response(my_cands, slots, opp_actual).line
    their_opt = best_response(opp_cands, slots, my_actual).line

    return compute_delta(mine_opt, opp_actual, their_opt, my_actual)


def season_deltas(
    platform: SupportsMaxPF,
    team_id: str,
    periods: list[int],
    slots: list[Slot],
    methodology: str = "expected",
) -> dict[int, DeltaResult]:
    """Compute ``period_delta`` for each period, skipping byes."""
    out: dict[int, DeltaResult] = {}
    for period in periods:
        result = period_delta(platform, team_id, period, slots, methodology)
        if result is not None:
            out[period] = result
    return out
