"""Pluggable player-performance sources.

A ``StatSource`` turns roster membership into per-day :class:`~max_pf.optimize.Candidate`
pools for the optimizer. League *structure* (rosters, slots, matchups, actual
results) always comes from the platform; a StatSource only supplies player
*performance* lines, so a league can be evaluated with data of varying fidelity:

- ``FantraxStatSource`` (platforms.fantrax): season-to-date per-game rates + the
  FG/FT attempts estimator. No extra dependency; supplies A-expected only
  (Fantrax exposes daily lines for *started* players only).
- ``BoxScoreStatSource`` (box_bref): exact realized per-day 9-cat lines with real
  makes/attempts from basketball-reference; supplies A-hindsight.

A source implements whichever methodologies it can; the platform routes each
methodology to a source that supports it. Both methods default to a clear error
so an unsupported request fails loudly rather than silently degrading.
"""
from __future__ import annotations

from .optimize import Candidate


class StatSource:
    """Supplies per-day candidate pools for a team over a matchup period."""

    def expected_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        """A-expected: per-day pools built from season-to-date projections."""
        raise NotImplementedError(
            f"{type(self).__name__} does not provide A-expected candidates"
        )

    def hindsight_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        """A-hindsight: per-day pools built from realized stats."""
        raise NotImplementedError(
            f"{type(self).__name__} does not provide A-hindsight candidates; "
            "attach a box-score source (platform.use_boxscores(...))"
        )
