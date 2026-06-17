"""Pluggable player-performance source.

A ``StatSource`` turns roster membership into per-day :class:`~max_pf.optimize.Candidate`
pools for the optimizer. The league *structure* (rosters, slots, matchups,
actual results) always comes from the platform; the StatSource only supplies
player *performance* lines, so the same league can be evaluated with different
data of varying fidelity:

- ``FantraxStatSource`` (platforms.fantrax): season-to-date per-game rates plus
  the FG/FT attempts estimator. No extra dependency, but Fantrax exposes daily
  lines only for *started* players, so it cannot produce full A-hindsight.
- ``BoxScoreStatSource`` (Stage 2): exact per-game and per-day 9-cat lines with
  real makes/attempts and schedule, from an external box-score provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .optimize import Candidate


class StatSource(ABC):
    """Supplies per-day candidate pools for a team over a matchup period."""

    @abstractmethod
    def expected_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        """A-expected: per-day pools built from season-to-date projections."""

    def hindsight_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        """A-hindsight: per-day pools built from realized stats.

        Not every source can supply realized full-roster daily lines; the
        default raises so callers fail loudly rather than silently degrade.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not provide realized full-roster daily "
            "lines; use a box-score-backed StatSource for A-hindsight"
        )
