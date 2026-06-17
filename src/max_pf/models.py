"""Normalized stat containers shared across platforms.

A ``PlayerLine`` is one player's production over some window (a single day, or a
season-to-date projection). It always carries makes/attempts for the two ratio
categories so that aggregation is exact: a team line is the element-wise sum of
its players, and FG%/FT% are recomputed from summed makes and attempts rather
than averaged.

When a platform only exposes the percentages (Fantrax does), populate
``fgm/fga/ftm/fta`` via :func:`max_pf.estimators.estimate_attempts` before
aggregating.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass
class PlayerLine:
    # Counting categories
    tpm: float = 0.0
    pts: float = 0.0
    reb: float = 0.0
    ast: float = 0.0
    stl: float = 0.0
    blk: float = 0.0
    to: float = 0.0
    # Ratio-category volumes (makes/attempts). Percentages are derived from these.
    fgm: float = 0.0
    fga: float = 0.0
    ftm: float = 0.0
    fta: float = 0.0

    @property
    def fg_pct(self) -> float:
        return self.fgm / self.fga if self.fga else 0.0

    @property
    def ft_pct(self) -> float:
        return self.ftm / self.fta if self.fta else 0.0

    def category_values(self) -> dict[str, float]:
        """Return the 9 category values keyed by category key."""
        return {
            "fg_pct": self.fg_pct,
            "tpm": self.tpm,
            "ft_pct": self.ft_pct,
            "pts": self.pts,
            "reb": self.reb,
            "ast": self.ast,
            "stl": self.stl,
            "blk": self.blk,
            "to": self.to,
        }

    def __add__(self, other: "PlayerLine") -> "PlayerLine":
        return PlayerLine(
            **{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(PlayerLine)}
        )


def aggregate(lines: list[PlayerLine]) -> PlayerLine:
    """Sum a set of player lines into one (team) line.

    Counting stats add; FG%/FT% follow automatically from summed makes/attempts.
    """
    total = PlayerLine()
    for line in lines:
        total = total + line
    return total


@dataclass
class PlayerDay:
    """A player's line on a specific date, with identity + eligibility."""

    player_id: str
    name: str
    positions: tuple[str, ...]
    line: PlayerLine
    played: bool = True


@dataclass
class RosterDay:
    """A team's rostered players (the candidate pool) on a given fantasy day."""

    team_id: str
    period: int
    players: list[PlayerDay] = field(default_factory=list)
