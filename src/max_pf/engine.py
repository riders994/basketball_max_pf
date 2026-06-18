"""Orchestration: turn a platform + slots into the per-period max-points-for Δ.

Ties together projections/optimizer/metric. For each matchup period:

    mine_opt  = best_response(my candidates,  slots, opp_actual)
    their_opt = best_response(opp candidates, slots, my_actual)
    Δ         = compute_delta(mine_opt, opp_actual, their_opt, my_actual)

The ``objective`` selects what "optimal" means:

- ``"catwins"`` (Objective A): each side best-responds to the other's *actual*
  line (one-round best response). The metric and the objective coincide.
- ``"zscore"`` (Objective B): each side fields a full lineup chosen by z-score
  value, *independent* of the opponent, against one league-wide z-score model
  for the period. catwins is then a readout, not what was optimized.
- ``"raw"`` (Objective C): like B but chosen by raw output (no scarcity
  weighting); also opponent-independent, catwins as a readout.

See docs/PROMPT_LOG.md.
"""
from __future__ import annotations

from typing import Protocol

from .metric import DeltaResult, compute_delta
from .models import PlayerLine
from .optimize import (
    Candidate,
    Objective,
    Slot,
    best_response,
    make_total_raw_objective,
    make_total_z_objective,
)


class SupportsMaxPF(Protocol):
    """Minimal platform surface the engine needs (see platforms.base)."""

    def matchup_opponent(self, team_id: str, period: int) -> str | None: ...
    def actual_team_line(self, team_id: str, period: int) -> PlayerLine: ...
    def period_candidates(self, team_id: str, period: int, methodology: str) -> list[list[Candidate]]: ...
    def zscore_model(self, period: int): ...  # only needed for objective="zscore"


def _objective_for(platform: SupportsMaxPF, period: int, objective: str) -> Objective | None:
    """Resolve the objective name to a callable for ``best_response``.

    ``"catwins"`` -> None (best_response's default Objective A); ``"zscore"`` /
    ``"raw"`` -> a value objective built from the period's league-wide model.
    """
    if objective == "catwins":
        return None
    if objective == "zscore":
        return make_total_z_objective(platform.zscore_model(period))
    if objective == "raw":
        return make_total_raw_objective(platform.zscore_model(period))
    raise ValueError(f"unknown objective: {objective!r}")


def period_delta(
    platform: SupportsMaxPF,
    team_id: str,
    period: int,
    slots: list[Slot],
    methodology: str = "expected",
    objective: str = "catwins",
) -> DeltaResult | None:
    """Compute the M1/M2/Δ triplet for one team in one matchup period.

    ``methodology`` selects the candidate source ("expected" or "hindsight");
    ``objective`` selects what "optimal" means ("catwins" or "zscore").
    Returns ``None`` when the team has no opponent that period (e.g. a bye).
    """
    opponent = platform.matchup_opponent(team_id, period)
    if opponent is None:
        return None

    my_actual = platform.actual_team_line(team_id, period)
    opp_actual = platform.actual_team_line(opponent, period)

    obj = _objective_for(platform, period, objective)
    kwargs = {"objective": obj} if obj is not None else {}
    my_cands = platform.period_candidates(team_id, period, methodology)
    opp_cands = platform.period_candidates(opponent, period, methodology)
    mine_opt = best_response(my_cands, slots, opp_actual, **kwargs).line
    their_opt = best_response(opp_cands, slots, my_actual, **kwargs).line

    return compute_delta(mine_opt, opp_actual, their_opt, my_actual)


def season_deltas(
    platform: SupportsMaxPF,
    team_id: str,
    periods: list[int],
    slots: list[Slot],
    methodology: str = "expected",
    objective: str = "catwins",
) -> dict[int, DeltaResult]:
    """Compute ``period_delta`` for each period, skipping byes."""
    out: dict[int, DeltaResult] = {}
    for period in periods:
        result = period_delta(platform, team_id, period, slots, methodology, objective)
        if result is not None:
            out[period] = result
    return out
