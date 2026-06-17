"""A-expected projections.

Turn a player's season-to-date **per-game** line (parsed from the platform's
roster STATS view) into a projected line for a matchup period::

    projected_line = per_game_line * games_scheduled_in_period

Because per-game lines already carry makes/attempts (estimated from the per-game
rates), scaling is linear and FG%/FT% stay correct after aggregation.

Still to wire (next sub-step): the games-in-period count per player, which comes
from joining the NBA schedule to each player's team over the period's date range.
"""
from __future__ import annotations

from dataclasses import fields

from .models import PlayerLine


def project_period_line(per_game: PlayerLine, games_in_period: int) -> PlayerLine:
    """Scale a per-game line by the number of scheduled games in the period.

    Every field of ``PlayerLine`` (counting stats and makes/attempts) scales by
    the game count, so derived FG%/FT% are unchanged at the player level and
    aggregate correctly across a lineup.
    """
    if games_in_period < 0:
        raise ValueError("games_in_period must be non-negative")
    return PlayerLine(
        **{f.name: getattr(per_game, f.name) * games_in_period for f in fields(PlayerLine)}
    )
