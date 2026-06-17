"""The 9 scoring categories and their metadata.

Single source of truth for category identity, ordering, whether a category is a
ratio (FG%/FT%) versus a counting stat, whether lower is better (turnovers), and
how each maps onto the raw Fantrax ``getLiveScoringStats`` stat ids.

Stat-id mapping was decoded from live data (league wserh14rmbbpqtcg); the live
payload keys each per-player per-day value by ``"3010#<scip>#-1"``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """One scoring category.

    Attributes:
        key: Short stable identifier used throughout the package.
        name: Human-readable name.
        scip: Fantrax stat id (the middle number of ``3010#<scip>#-1``).
        is_percentage: True for ratio categories (FG%, FT%) that must be
            aggregated as Σmakes / Σattempts, never averaged.
        lower_is_better: True for turnovers; a lower total wins the category.
    """

    key: str
    name: str
    scip: int
    is_percentage: bool = False
    lower_is_better: bool = False


# Canonical order, matching the order Fantrax returns in object2.
CATEGORIES: tuple[Category, ...] = (
    Category("fg_pct", "Field Goal %", 1520, is_percentage=True),
    Category("tpm", "Three Pointers Made", 1435),
    Category("ft_pct", "Free Throw %", 1550, is_percentage=True),
    Category("pts", "Points", 1390),
    Category("reb", "Rebounds", 1400),
    Category("ast", "Assists", 1250),
    Category("stl", "Steals", 1410),
    Category("blk", "Blocks", 1260),
    Category("to", "Turnovers", 1460, lower_is_better=True),
)

CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES)
BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}
BY_SCIP: dict[int, Category] = {c.scip: c for c in CATEGORIES}

# Counting categories (everything that is summed directly, not derived from a ratio).
COUNTING_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES if not c.is_percentage)
PERCENTAGE_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES if c.is_percentage)


def scip_of(scip_field: str) -> int:
    """Parse the integer stat id out of a Fantrax ``"3010#1390#-1"`` field."""
    return int(scip_field.split("#")[1])
