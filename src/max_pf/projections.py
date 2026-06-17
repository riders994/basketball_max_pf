"""A-expected projections -- build step after the scaffold.

Turn a platform's per-player season-to-date per-game rates (as of a period) plus
the period's game schedule into projected per-player period lines, which the
optimizer then assembles into ``mine_opt`` / ``their_opt`` under Objective A.

Projection (per player, per matchup period):
    projected_line = per_game_rate * games_scheduled_in_period

FG%/FT% per-game rates are converted to makes/attempts up front (via
:func:`max_pf.estimators.estimate_attempts` on the per-game line) so the volume
scales correctly with games played.
"""
from __future__ import annotations

from .models import PlayerLine


def project_period_line(per_game: PlayerLine, games_in_period: int) -> PlayerLine:
    """Scale a per-game line by the number of scheduled games.

    Not yet implemented -- see module docstring.
    """
    raise NotImplementedError("A-expected projection builder is the next build step")
