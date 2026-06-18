"""Daily lineup optimizer (best-response).

Given a team's per-day candidate pool over a matchup period, choose which players
to start each day -- subject to the daily active-slot capacity and position
eligibility -- so the aggregated period line maximizes a pluggable ``objective``
against a fixed opponent target. The default objective is Objective A (category
wins, opponent-aware); Objective B plugs in a z-score-weighted variant. This is
the engine behind ``mine_opt`` / ``their_opt`` in :mod:`max_pf.metric`.

Why this isn't a greedy per-day pick:
- FG%/FT% are ratios, so adding a high-volume inefficient game can *lower* a
  category you were winning; turnovers are lower-is-better. The optimum may bench
  a player who has a game, or punt a category entirely.
- The objective (count of categories won) is over the period aggregate, coupling
  days together.

Approach (v1): greedy value construction per day to get a strong feasible start,
then global local search (swap / add / drop a player-game) accepting moves that
improve ``(points_for, category-margin)``. Slot feasibility is enforced by a
bipartite matcher. This league has no games-played caps; a cap budget is a clean
future extension (the construction/search would carry a remaining-games state).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .categories import CATEGORIES
from .metric import CategoryResult, catwins
from .models import PlayerLine, aggregate

# An objective scores a started selection (per-day lists of Candidate) against
# the opponent target, returning any orderable value (higher = better). It takes
# the candidates rather than just the aggregate line so value-based objectives
# can score players at per-game scale. Objective A is the default
# (:func:`objective_catwins`); Objective B is :func:`make_total_z_objective`.
Objective = Callable[[list[list["Candidate"]], PlayerLine], object]


@dataclass(frozen=True)
class Slot:
    """One active lineup slot.

    ``eligible`` is the set of player position short-names this slot accepts; an
    empty set means a flex slot that accepts anyone.
    """

    name: str
    eligible: frozenset[str] = frozenset()

    def accepts(self, positions: tuple[str, ...]) -> bool:
        return not self.eligible or bool(self.eligible.intersection(positions))


@dataclass(frozen=True)
class Candidate:
    player_id: str
    line: PlayerLine
    positions: tuple[str, ...]


@dataclass
class OptimizerResult:
    line: PlayerLine                      # aggregated period line of started games
    started: list[list[str]] = field(default_factory=list)  # per-day started player ids
    result: CategoryResult | None = None  # catwins(line, target)


def can_assign(positions_list: list[tuple[str, ...]], slots: list[Slot]) -> bool:
    """True if every player (by eligible positions) can take a distinct slot."""
    if len(positions_list) > len(slots):
        return False
    slot_to_player: list[int] = [-1] * len(slots)

    def augment(p: int, seen: list[bool]) -> bool:
        for si, slot in enumerate(slots):
            if not seen[si] and slot.accepts(positions_list[p]):
                seen[si] = True
                if slot_to_player[si] == -1 or augment(slot_to_player[si], seen):
                    slot_to_player[si] = p
                    return True
        return False

    for p in range(len(positions_list)):
        if not augment(p, [False] * len(slots)):
            return False
    return True


def _value(line: PlayerLine) -> float:
    """Rough production proxy for the construction phase (search refines it)."""
    return (
        line.pts + line.reb + line.ast + 2 * line.stl + 2 * line.blk + line.tpm - line.to
    )


def _construct_day(candidates: list[Candidate], slots: list[Slot]) -> list[Candidate]:
    """Greedily pick the highest-value slot-feasible subset for one day."""
    chosen: list[Candidate] = []
    for cand in sorted(candidates, key=lambda c: _value(c.line), reverse=True):
        if can_assign([c.positions for c in chosen] + [cand.positions], slots):
            chosen.append(cand)
    return chosen


def objective_catwins(started: list[list["Candidate"]], target: PlayerLine) -> tuple[float, float]:
    """Objective A: maximize category points, then total normalized margin.

    The margin term gives the local search a gradient toward flipping near-miss
    categories even when the category-win count is unchanged. Opponent-aware: the
    started selection is aggregated and compared to ``target``.
    """
    line = _aggregate_started(started)
    res = catwins(line, target)
    mine, theirs = line.category_values(), target.category_values()
    margin = 0.0
    for cat in CATEGORIES:
        diff = mine[cat.key] - theirs[cat.key]
        if cat.lower_is_better:
            diff = -diff
        margin += diff / (abs(theirs[cat.key]) or 1.0)
    return res.points_for, margin


def _value_objective(value_fn: Callable[[PlayerLine], float]) -> Objective:
    """An opponent-independent objective: field a full lineup chosen by value.

    Returns ``(games_started, total_value)`` so the search **fills the lineup
    first** (you always field a full team in counting-cat H2H), then among full
    lineups maximizes ``Σ value_fn(player)``. Without the games-started term, a
    pure value-sum would bench every below-replacement (negative-value) player
    and field a partial lineup. ``value_fn`` scores one candidate's
    (per-game-scale) line; ``target`` is ignored.
    """

    def objective(started: list[list["Candidate"]], target: PlayerLine) -> tuple[int, float]:
        games = sum(len(day) for day in started)
        return games, sum(value_fn(c.line) for day in started for c in day)

    return objective


def make_total_z_objective(model) -> Objective:
    """Objective B: field a full lineup chosen by z-score value (scarcity-weighted).

    Opponent-independent; among full lineups it maximizes total z-value, so it
    prefers players who are scarce/valuable across categories. catwins becomes a
    *readout* on the result, not what was optimized.
    """
    return _value_objective(model.value)


def make_total_raw_objective(model) -> Objective:
    """Objective C: field a full lineup chosen by raw output (scarcity-blind).

    Same population/model as Objective B but values players by
    :meth:`ZScoreModel.raw_value` (no std weighting), so it prefers high-volume
    production rather than balanced rarity. Opponent-independent; catwins is a
    readout.
    """
    return _value_objective(model.raw_value)


def _aggregate_started(started: list[list[Candidate]]) -> PlayerLine:
    return aggregate([c.line for day in started for c in day])


def best_response(
    daily_candidates: list[list[Candidate]],
    slots: list[Slot],
    target: PlayerLine,
    max_passes: int = 50,
    objective: Objective = objective_catwins,
) -> OptimizerResult:
    """Return the lineup over the period that best beats ``target``.

    Args:
        daily_candidates: per-day lists of players who have a game that day.
        slots: active lineup slots (capacity = ``len(slots)`` per day).
        target: opponent line to maximize category wins against.
        max_passes: local-search iteration cap.
        objective: scoring function the search maximizes (default Objective A,
            opponent-aware category wins; Objective B passes a z-score variant).
    """
    started = [_construct_day(day, slots) for day in daily_candidates]
    best = objective(started, target)

    for _ in range(max_passes):
        best_move = None  # (day_index, new_day_selection, score)
        for d, day_all in enumerate(daily_candidates):
            current = started[d]
            current_ids = {c.player_id for c in current}
            benched = [c for c in day_all if c.player_id not in current_ids]

            neighbors: list[list[Candidate]] = []
            # Drop one started player (punt / efficiency).
            for s in current:
                neighbors.append([c for c in current if c.player_id != s.player_id])
            # Add one benched player (if a slot is free and feasible).
            for b in benched:
                if can_assign([c.positions for c in current] + [b.positions], slots):
                    neighbors.append(current + [b])
            # Swap a started player for a benched one.
            for s in current:
                kept = [c for c in current if c.player_id != s.player_id]
                for b in benched:
                    if can_assign([c.positions for c in kept] + [b.positions], slots):
                        neighbors.append(kept + [b])

            for cand_day in neighbors:
                trial = started[:d] + [cand_day] + started[d + 1:]
                score = objective(trial, target)
                if score > best and (best_move is None or score > best_move[2]):
                    best_move = (d, cand_day, score)

        if best_move is None:
            break
        d, cand_day, score = best_move
        started[d] = cand_day
        best = score

    line = _aggregate_started(started)
    return OptimizerResult(
        line=line,
        started=[[c.player_id for c in day] for day in started],
        result=catwins(line, target),
    )
