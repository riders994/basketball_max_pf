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

from dataclasses import dataclass, field
from typing import Protocol

from .categories import CATEGORY_KEYS
from .metric import CategoryResult, DeltaResult, catwins, compute_delta
from .models import PlayerLine
from .nash_lp import solve_zero_sum_game
from .optimize import (
    Candidate,
    Objective,
    Slot,
    best_response,
    make_expected_catwins_objective,
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


# Per-period category points always total this (ties split), so the game is
# constant-sum and the mutual ceiling is a well-defined minimax value.
_TOTAL_POINTS = float(len(CATEGORY_KEYS))
# An oracle strategy is added only if it beats the restricted-game value by more
# than this, so float wobble doesn't drive a spurious extra double-oracle round.
_ORACLE_TOL = 1e-9


@dataclass
class NashResult:
    """Outcome of the mutual-ceiling search for one matchup period.

    ``converged`` is True when iterated best response reached a fixed point — a
    pure-strategy Nash equilibrium where each lineup best-responds to the other
    (``equilibrium == "pure"``). False means the best responses cycle (no pure
    equilibrium); stage 2 then resolves the ceiling as a **mixed-strategy** minimax
    value via a double-oracle LP (``equilibrium == "mixed"``), and ``mine_mix`` /
    ``theirs_mix`` carry the equilibrium mixtures.

    ``value`` is the mutual-ceiling score in category points either way: the pure
    equilibrium's ``m3.points_for``, or the mixed game's value. For a mixed result
    ``mine`` / ``theirs`` / ``m3`` describe the modal (most-probable) lineup pair as
    a representative readout; the value, not that pair, is the ceiling.
    """

    converged: bool
    rounds: int
    mine: PlayerLine        # my equilibrium / modal lineup line
    theirs: PlayerLine      # opponent's
    m3: CategoryResult      # catwins(mine, theirs) at the (terminal/modal) state
    value: float            # mutual-ceiling category points (pure: m3.points_for)
    equilibrium: str = "pure"   # "pure" | "mixed"
    mine_mix: list[tuple[PlayerLine, float]] = field(default_factory=list)
    theirs_mix: list[tuple[PlayerLine, float]] = field(default_factory=list)

    @property
    def m3_pf(self) -> float:
        return self.value


def _line_key(line: PlayerLine) -> tuple[float, ...]:
    """Hashable identity of a line for fixed-point / cycle detection."""
    vals = line.category_values()
    return tuple(round(vals[k], 6) for k in CATEGORY_KEYS)


def _contains(lines: list[PlayerLine], line: PlayerLine) -> bool:
    key = _line_key(line)
    return any(_line_key(existing) == key for existing in lines)


def _pure_result(rounds: int, mine: PlayerLine, theirs: PlayerLine) -> NashResult:
    res = catwins(mine, theirs)
    return NashResult(True, rounds, mine, theirs, res, res.points_for, "pure")


def _double_oracle(
    my_cands: list[list[Candidate]],
    opp_cands: list[list[Candidate]],
    slots: list[Slot],
    seed_mine: PlayerLine,
    seed_their: PlayerLine,
    max_iters: int = 100,
) -> NashResult:
    """Mixed-strategy mutual ceiling for a cycling matchup via double oracle.

    Maintains restricted pure-strategy sets (lineups) for both sides, seeded from
    the terminal best-response lines. Each round solves the restricted zero-sum
    game for its value and mixtures, then grows the sets with a best response to
    the opponent's mixture (the row/column *oracles*, reusing the daily optimizer
    with an expected-catwins objective). When neither oracle can beat the current
    value, the restricted game's equilibrium is an equilibrium of the full game and
    its value is the mutual ceiling (M3).
    """
    my_lines = [seed_mine]
    opp_lines = [seed_their]

    for _ in range(max_iters):
        payoff = [[catwins(a, b).points_for for b in opp_lines] for a in my_lines]
        sol = solve_zero_sum_game(payoff)
        x, y = sol.row_strategy, sol.col_strategy

        # Row oracle: my best response to the opponent's mixture y.
        br_mine = best_response(
            my_cands, slots, opp_lines[0], objective=make_expected_catwins_objective(opp_lines, y)
        ).line
        row_ev = sum(w * catwins(br_mine, t).points_for for t, w in zip(opp_lines, y))

        # Column oracle: opponent's best response to my mixture x. It maximizes its
        # own points (= _TOTAL_POINTS − mine), i.e. minimizes my expected points.
        br_their = best_response(
            opp_cands, slots, my_lines[0], objective=make_expected_catwins_objective(my_lines, x)
        ).line
        my_ev_vs_their = sum(w * catwins(a, br_their).points_for for a, w in zip(my_lines, x))

        grew = False
        if row_ev > sol.value + _ORACLE_TOL and not _contains(my_lines, br_mine):
            my_lines.append(br_mine)
            grew = True
        if my_ev_vs_their < sol.value - _ORACLE_TOL and not _contains(opp_lines, br_their):
            opp_lines.append(br_their)
            grew = True
        if not grew:
            break

    # Re-solve over the final sets so the reported mixtures/value are consistent
    # with them (the last loop iteration may have appended a strategy).
    payoff = [[catwins(a, b).points_for for b in opp_lines] for a in my_lines]
    sol = solve_zero_sum_game(payoff)
    mine_mix = list(zip(my_lines, sol.row_strategy))
    theirs_mix = list(zip(opp_lines, sol.col_strategy))
    mine = max(mine_mix, key=lambda p: p[1])[0]
    theirs = max(theirs_mix, key=lambda p: p[1])[0]
    return NashResult(
        converged=False,
        rounds=len(my_lines) + len(opp_lines) - 2,
        mine=mine,
        theirs=theirs,
        m3=catwins(mine, theirs),
        value=sol.value,
        equilibrium="mixed",
        mine_mix=mine_mix,
        theirs_mix=theirs_mix,
    )


def nash_ceiling(
    platform: SupportsMaxPF,
    team_id: str,
    period: int,
    slots: list[Slot],
    methodology: str = "expected",
    max_rounds: int = 50,
    max_oracle_iters: int = 100,
) -> NashResult | None:
    """Iterated best response toward the mutual (Nash) ceiling for one period.

    Both sides simultaneously best-respond (catwins) to the other's *current*
    lineup, seeded from the actual lineups. A fixed point — where each lineup is a
    best response to the other — is a pure-strategy Nash equilibrium: the score
    when both manage perfectly against each other. If the dynamics revisit a state
    the best responses cycle (no pure equilibrium); the ceiling is then the
    mixed-strategy minimax value, resolved by a double-oracle LP (stage 2) and
    reported with ``converged=False``, ``equilibrium="mixed"``. Returns ``None``
    for a bye. Always uses the catwins objective (the game's payoff); Objectives
    B/C are opponent-independent and have no equilibrium.
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
            return _pure_result(r, mine, theirs)
        state = (_line_key(mine), _line_key(theirs))
        if state in seen:  # revisited a state -> no pure equilibrium
            return _double_oracle(my_cands, opp_cands, slots, mine, theirs, max_oracle_iters)
        seen.add(state)
        mine, theirs = new_mine, new_their

    # Round cap hit without a fixed point: also resolve the mixed-strategy value.
    return _double_oracle(my_cands, opp_cands, slots, mine, theirs, max_oracle_iters)


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
