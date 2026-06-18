"""The 9 scoring categories and their metadata.

Provider-agnostic single source of truth for category identity, ordering,
whether a category is a ratio (FG%/FT%) versus a counting stat, and whether
lower is better (turnovers). Provider-specific stat-id encodings (e.g. Fantrax
scipIds) live in the platform adapters, not here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """One scoring category.

    Attributes:
        key: Short stable identifier used throughout the package.
        name: Human-readable name.
        is_percentage: True for ratio categories (FG%, FT%) that must be
            aggregated as Σmakes / Σattempts, never averaged.
        lower_is_better: True for turnovers; a lower total wins the category.
    """

    key: str
    name: str
    is_percentage: bool = False
    lower_is_better: bool = False


# Canonical order (matches the order Fantrax returns per-player daily stats).
CATEGORIES: tuple[Category, ...] = (
    Category("fg_pct", "Field Goal %", is_percentage=True),
    Category("tpm", "Three Pointers Made"),
    Category("ft_pct", "Free Throw %", is_percentage=True),
    Category("pts", "Points"),
    Category("reb", "Rebounds"),
    Category("ast", "Assists"),
    Category("stl", "Steals"),
    Category("blk", "Blocks"),
    Category("to", "Turnovers", lower_is_better=True),
)

CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES)
BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}

# Counting categories (summed directly) vs ratio categories (Σmakes/Σattempts).
COUNTING_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES if not c.is_percentage)
PERCENTAGE_KEYS: tuple[str, ...] = tuple(c.key for c in CATEGORIES if c.is_percentage)
