"""Daily lineup optimizer (Objective A) -- build step after the scaffold.

Given a team's candidate pool per day, position slots, and games-played caps,
choose the active lineup over a matchup period that maximizes category wins
against a fixed target line (best-response). This is the engine behind
``mine_opt`` / ``their_opt`` in :mod:`max_pf.metric`.

Design notes (not yet implemented):
- Objective is pluggable; A maximizes catwins vs a fixed opponent target.
- Constraints: per-position daily slot limits and per-period games-played caps
  (from the platform's position-count data). A player only contributes on days
  they actually have a game (the game-log join handles injuries/DNPs).
- FG%/FT% are non-additive, so the objective is evaluated on aggregated
  makes/attempts (see :mod:`max_pf.models`), not summed percentages -- meaning
  greedy per-day selection is not exact; expect an ILP / search formulation.
"""
from __future__ import annotations

from .models import PlayerLine, RosterDay


def best_response(
    roster_days: list[RosterDay],
    target: PlayerLine,
    slot_limits: dict[str, int],
    games_played_caps: dict[str, int],
) -> PlayerLine:
    """Return the optimized period line that best beats ``target``.

    Not yet implemented -- see module docstring for the intended formulation.
    """
    raise NotImplementedError("daily lineup optimizer is the next build step")
