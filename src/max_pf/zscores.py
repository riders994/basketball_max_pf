"""Z-score player valuation (the foundation for Objective B).

Standardizes each category against a player population so values are comparable
across categories with different units, then sums them into one scalar per
player. This is the classic 9-cat fantasy valuation, and it is what makes
*punting* quantifiable: a category you concede simply contributes a (large)
negative z-score that a strong lineup can outweigh elsewhere.

Two category kinds are handled differently:

- **Counting** (PTS, REB, AST, STL, BLK, 3PTM, TO): standardize the per-game
  stat directly. Turnovers are inverted (lower is better) so a high z-score is
  always good.
- **Ratio** (FG%, FT%): standardize *volume-weighted impact*, not the raw
  percentage. A player's impact is ``(pct - league_pct) * attempts`` per game,
  so a high percentage on few attempts moves the needle less than the same
  percentage on many — the correct way to value ratios in a lineup that
  aggregates as Σmakes/Σattempts.

The model is built from a population of *per-game* :class:`~max_pf.models.PlayerLine`
(e.g. all rostered players' season-to-date rates). Population (not sample) std
is used: the population is the valuation universe, not a draw from a larger one.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from .categories import BY_KEY, CATEGORY_KEYS, PERCENTAGE_KEYS
from .models import PlayerLine

# attempts attribute backing each ratio category's volume weighting.
_RATIO_ATTEMPTS = {"fg_pct": "fga", "ft_pct": "fta"}


def _league_pcts(lines: list[PlayerLine]) -> dict[str, float]:
    """Population FG%/FT% as Σmakes / Σattempts (the impact baseline)."""
    fgm = sum(l.fgm for l in lines)
    fga = sum(l.fga for l in lines)
    ftm = sum(l.ftm for l in lines)
    fta = sum(l.fta for l in lines)
    return {
        "fg_pct": fgm / fga if fga else 0.0,
        "ft_pct": ftm / fta if fta else 0.0,
    }


def _raw_value(line: PlayerLine, key: str, league_pcts: dict[str, float]) -> float:
    """The quantity standardized for one category: impact for ratios, the
    (TO-inverted) per-game stat for counting categories."""
    if key in PERCENTAGE_KEYS:
        pct = line.fg_pct if key == "fg_pct" else line.ft_pct
        attempts = getattr(line, _RATIO_ATTEMPTS[key])
        return (pct - league_pcts[key]) * attempts
    value = line.category_values()[key]
    return -value if BY_KEY[key].lower_is_better else value


@dataclass(frozen=True)
class ZScoreModel:
    """Per-category mean/std (and ratio baselines) for standardizing players."""

    league_pcts: dict[str, float]
    mean: dict[str, float]
    std: dict[str, float]

    def zscores(self, line: PlayerLine) -> dict[str, float]:
        """Per-category z-scores for a per-game line (TO already inverted)."""
        out: dict[str, float] = {}
        for key in CATEGORY_KEYS:
            raw = _raw_value(line, key, self.league_pcts)
            sd = self.std[key] or 1.0  # degenerate population -> no spread
            out[key] = (raw - self.mean[key]) / sd
        return out

    def value(self, line: PlayerLine) -> float:
        """Total z-score value: the sum across all 9 categories."""
        return sum(self.zscores(line).values())


def build_model(population: list[PlayerLine]) -> ZScoreModel:
    """Fit a :class:`ZScoreModel` to a population of per-game player lines."""
    if not population:
        raise ValueError("cannot build a z-score model from an empty population")
    league_pcts = _league_pcts(population)
    values = {
        key: [_raw_value(line, key, league_pcts) for line in population]
        for key in CATEGORY_KEYS
    }
    mean = {key: statistics.fmean(vals) for key, vals in values.items()}
    std = {key: statistics.pstdev(vals) for key, vals in values.items()}
    return ZScoreModel(league_pcts, mean, std)
