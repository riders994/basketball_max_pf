"""Abstract league-platform interface.

A platform adapter turns one fantasy provider's API into the normalized models
the rest of ``max_pf`` consumes. Adding a new provider = implementing this
interface; the optimizer/metric layers never import a provider directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..models import PlayerDay, PlayerLine, RosterDay
from ..optimize import Slot


class LeaguePlatform(ABC):
    """Normalized read interface over a fantasy league provider."""

    @abstractmethod
    def team_ids(self) -> list[str]:
        """All team ids in the league."""

    @abstractmethod
    def active_slots(self) -> list[Slot]:
        """The league's active lineup slots (capacity + position eligibility)."""

    @abstractmethod
    def scoring_dates(self) -> dict[int, date]:
        """Map of daily period number -> calendar date."""

    @abstractmethod
    def matchup_opponent(self, team_id: str, period: int) -> str | None:
        """Opponent team id for ``team_id`` in the given matchup period."""

    @abstractmethod
    def actual_team_line(self, team_id: str, period: int) -> PlayerLine:
        """Realized 9-cat totals a team actually produced in a matchup period."""

    @abstractmethod
    def roster_day(self, team_id: str, period: int) -> RosterDay:
        """Candidate pool (rostered players) for a team on a daily period."""

    @abstractmethod
    def player_day_lines(self, on: date) -> dict[str, PlayerDay]:
        """All players' realized lines on a date, keyed by player id (A-hindsight)."""

    @abstractmethod
    def projected_roster_lines(self, team_id: str, period: int) -> dict[str, PlayerLine]:
        """Per-player projected period lines for a team's roster (A-expected).

        Season-to-date per-game rates as of the period start, scaled by each
        player's games scheduled in the matchup period. Keyed by player id.
        """
