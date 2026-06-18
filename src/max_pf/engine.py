"""Orchestration: turn a platform + slots into the per-period max-points-for Δ.

Ties together projections/optimizer/metric. For each matchup period:

    mine_opt  = best_response(my candidates,  slots, opp_actual)
    their_opt = best_response(opp candidates, slots, my_actual)
    Δ         = compute_delta(mine_opt, opp_actual, their_opt, my_actual)

The ``objective`` selects what "optimal" means:

- ``"catwins"`` (Objective A): each side best-responds to the other's *actual*
  line (one-round best response). The metric and the objective coincide.
- ``"zscore"`` (Objective B): each side maximizes its lineup's total z-score
  value, *independent* of the opponent, against one league-wide z-score model
  for the period. Below-replacement players are benched (protecting ratio cats /
  TO). catwins is then a readout, not what was optimized.
- ``"raw"`` (Objective C): like B but values raw output (no scarcity weighting),
  so it benches far less; also opponent-independent, catwins as a readout.

See docs/PROMPT_LOG.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .categories import CATEGORY_KEYS
from .metric import CategoryResult, DeltaResult, catwins, compute_delta
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


# --- Nash mutual ceiling (stage 1: iterated best response) --------------------


@dataclass
class NashResult:
    """Outcome of the iterated best-response search for one matchup period.

    ``converged`` is True when the dynamics reached a fixed point — a pure-strategy
    Nash equilibrium where each lineup is a best response to the other (the mutual
    ceiling). False means the best responses cycled (no pure equilibrium; the
    mixed-strategy value needs stage 2) or the round cap was hit.
    """

    converged: bool
    rounds: int
    mine: PlayerLine        # my equilibrium / terminal lineup line
    theirs: PlayerLine      # opponent's
    m3: CategoryResult      # catwins(mine, theirs) at the (terminal) state

    @property
    def m3_pf(self) -> float:
        return self.m3.points_for


def _line_key(line: PlayerLine) -> tuple[float, ...]:
    """Hashable identity of a line for fixed-point / cycle detection."""
    vals = line.category_values()
    return tuple(round(vals[k], 6) for k in CATEGORY_KEYS)


def nash_ceiling(
    platform: SupportsMaxPF,
    team_id: str,
    period: int,
    slots: list[Slot],
    methodology: str = "expected",
    max_rounds: int = 50,
) -> NashResult | None:
    """Iterated best response toward the mutual (Nash) ceiling for one period.

    Both sides simultaneously best-respond (catwins) to the other's *current*
    lineup, seeded from the actual lineups. A fixed point — where each lineup is a
    best response to the other — is a pure-strategy Nash equilibrium: the score
    when both manage perfectly against each other. If the dynamics revisit a state
    the best responses cycle (no pure equilibrium), reported as not converged.
    Returns ``None`` for a bye. Always uses the catwins objective (the game's
    payoff); Objectives B/C are opponent-independent and have no equilibrium.
    """
    opponent = platform.matchup_opponent(team_id, period)
    if opponent is None:
        return None

    my_cands = platform.period_candidates(team_id, period, methodology)
    opp_cands = platform.period_candidates(opponent, period, methodology)
    mine = platform.actual_team_line(team_id, period)
    theirs = platform.actual_team_line(opponent, period)

    seen: set[tuple] = set()
    for r in range(1, max_rounds + 1):
        new_mine = best_response(my_cands, slots, theirs).line
        new_their = best_response(opp_cands, slots, mine).line
        # Fixed point: each current lineup already best-responds to the other.
        if _line_key(new_mine) == _line_key(mine) and _line_key(new_their) == _line_key(theirs):
            return NashResult(True, r, mine, theirs, catwins(mine, theirs))
        state = (_line_key(mine), _line_key(theirs))
        if state in seen:  # revisited a state -> deterministic cycle
            return NashResult(False, r, mine, theirs, catwins(mine, theirs))
        seen.add(state)
        mine, theirs = new_mine, new_their

    return NashResult(False, max_rounds, mine, theirs, catwins(mine, theirs))


def season_nash(
    platform: SupportsMaxPF,
    team_id: str,
    periods: list[int],
    slots: list[Slot],
    methodology: str = "expected",
) -> dict[int, NashResult]:
    """Compute ``nash_ceiling`` for each period, skipping byes."""
    out: dict[int, NashResult] = {}
    for period in periods:
        result = nash_ceiling(platform, team_id, period, slots, methodology)
        if result is not None:
            out[period] = result
    return out
