"""Estimate FG/FT makes & attempts from the data Fantrax actually exposes.

Fantrax gives per-player per-day FG% and FT% but never the underlying
makes/attempts, and attempts are unrecoverable from the 9 categories alone
(PTS, 3PTM, FG%, FT% give one points equation in two unknowns). We close the
system with a position-based free-throw rate ``r = FTA / FGA``:

    PTS - 3PTM = 2*FGM + FTM = FGA*(2*FG% + r*FT%)
    => FGA = (PTS - 3PTM) / (2*FG% + r*FT%)
       FTA = r * FGA
       FGM = FG% * FGA;   FTM = FT% * FTA

This is the single seam to replace if/when exact external makes/attempts become
available -- swap the body of :func:`estimate_attempts`.
"""
from __future__ import annotations

# Position-based free-throw rate priors (FTA per FGA). Static, tunable; rises
# toward the rim. Refine later from external league averages.
POSITION_FT_RATE: dict[str, float] = {
    "PG": 0.20,
    "SG": 0.18,
    "SF": 0.22,
    "PF": 0.26,
    "C": 0.30,
}
DEFAULT_FT_RATE: float = 0.22

# Fallback field-goal-attempt prior (per game) used only when a player scored/
# played but FG% is 0, so missed attempts still weigh on team FG%.
FALLBACK_FGA_BY_POS: dict[str, float] = {
    "PG": 10.0,
    "SG": 11.0,
    "SF": 10.0,
    "PF": 9.0,
    "C": 8.0,
}
DEFAULT_FALLBACK_FGA: float = 9.0


def _avg_prior(table: dict[str, float], default: float, positions: tuple[str, ...]) -> float:
    vals = [table[p] for p in positions if p in table]
    return sum(vals) / len(vals) if vals else default


def estimate_attempts(
    pts: float,
    tpm: float,
    fg_pct: float,
    ft_pct: float,
    positions: tuple[str, ...] = (),
) -> tuple[float, float, float, float]:
    """Return ``(fgm, fga, ftm, fta)`` estimated from a single stat line.

    Args:
        pts: Points scored.
        tpm: Three-pointers made.
        fg_pct: Field-goal percentage as a fraction in [0, 1].
        ft_pct: Free-throw percentage as a fraction in [0, 1].
        positions: Eligible position short names (e.g. ``("PG", "SG")``); the
            free-throw-rate prior is averaged over them.
    """
    if pts <= 0:
        # DNP or scoreless: no scoring volume to attribute. (A scoreless line can
        # still have missed attempts, but we have no signal for them here.)
        return 0.0, 0.0, 0.0, 0.0

    r = _avg_prior(POSITION_FT_RATE, DEFAULT_FT_RATE, positions)

    denom = 2.0 * fg_pct + r * ft_pct
    if denom <= 0:
        # FG% and FT% both zero but points exist -- inconsistent input. Attribute
        # all points to free throws at a nominal rate so something is recorded.
        ftm = float(pts)
        fta = ftm / ft_pct if ft_pct > 0 else ftm
        return 0.0, 0.0, ftm, fta

    fga = (pts - tpm) / denom
    fta = r * fga
    fgm = fg_pct * fga
    ftm = ft_pct * fta

    if fg_pct <= 0:
        # Player produced but shot 0% from the field: keep makes at 0 but give
        # them a position-typical attempt volume so team FG% is dragged down.
        fgm = 0.0
        fga = _avg_prior(FALLBACK_FGA_BY_POS, DEFAULT_FALLBACK_FGA, positions)

    if ft_pct <= 0:
        # No made free throws -> assume no trips to the line (avoid phantom FTA).
        ftm = 0.0
        fta = 0.0

    return fgm, fga, ftm, fta
