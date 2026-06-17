"""Fantrax platform adapter (wraps the stable fork of fantraxapi).

Implements the pure transforms that were verified against live data
(`getLiveScoringStats.object2` -> per-player per-day 9-cat lines via the scipId
map). Network-bound methods are wired to the fork but kept thin; several are
stubbed pending the optimizer/projection build step.

Install the optional dependency to use this adapter::

    pip install "max-pf[fantrax]"
"""
from __future__ import annotations

from datetime import date

from ..categories import BY_SCIP, scip_of
from ..estimators import estimate_attempts
from ..models import PlayerDay, PlayerLine, RosterDay
from .base import LeaguePlatform


def decode_player_day_stats(object2: list[dict], positions: tuple[str, ...] = ()) -> PlayerLine:
    """Turn a live-scoring ``object2`` stat list into a normalized PlayerLine.

    ``object2`` is a list of ``{"scipId": "3010#<scip>#-1", "av": <value>}``.
    The two ratio categories arrive as percentages only, so makes/attempts are
    filled in via :func:`estimate_attempts`.
    """
    raw: dict[str, float] = {}
    for entry in object2:
        scip = scip_of(entry["scipId"])
        cat = BY_SCIP.get(scip)
        if cat is not None:
            raw[cat.key] = float(entry.get("av") or 0.0)

    fgm, fga, ftm, fta = estimate_attempts(
        pts=raw.get("pts", 0.0),
        tpm=raw.get("tpm", 0.0),
        fg_pct=raw.get("fg_pct", 0.0),
        ft_pct=raw.get("ft_pct", 0.0),
        positions=positions,
    )
    return PlayerLine(
        tpm=raw.get("tpm", 0.0),
        pts=raw.get("pts", 0.0),
        reb=raw.get("reb", 0.0),
        ast=raw.get("ast", 0.0),
        stl=raw.get("stl", 0.0),
        blk=raw.get("blk", 0.0),
        to=raw.get("to", 0.0),
        fgm=fgm,
        fga=fga,
        ftm=ftm,
        fta=fta,
    )


def transaction_date_column(header_cells: list[dict]) -> int:
    """Locate the date column index from the transaction-table header.

    The fork assumes a fixed position (``cells[1]``) which is wrong for some
    leagues; resolve it from the header instead (mirrors how Standings does it).
    """
    for i, cell in enumerate(header_cells):
        label = (cell.get("name") or cell.get("shortName") or "").lower()
        key = (cell.get("key") or "").lower()
        if "date" in label or "date" in key or key in {"period", "txdate"}:
            return i
    return 1  # last-resort fallback to the fork's historical assumption


class FantraxPlatform(LeaguePlatform):
    """Normalized adapter over a fantraxapi ``League``."""

    def __init__(self, league_id: str, session=None) -> None:
        try:
            from fantraxapi import League
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "The Fantrax adapter requires the optional dependency. "
                'Install with: pip install "max-pf[fantrax]"'
            ) from e
        self._league = League(league_id, session=session) if session else League(league_id)

    def team_ids(self) -> list[str]:
        return [t.id for t in self._league.teams]

    def scoring_dates(self) -> dict[int, date]:
        return dict(self._league.scoring_dates)

    # --- Stubs for the next build step (optimizer + projections) -------------

    def matchup_opponent(self, team_id: str, period: int) -> str | None:
        raise NotImplementedError("wire up via scoring_period_results() matchup grid")

    def actual_team_line(self, team_id: str, period: int) -> PlayerLine:
        raise NotImplementedError("map the matchup scoring_grid categories to PlayerLine")

    def roster_day(self, team_id: str, period: int) -> RosterDay:
        raise NotImplementedError("build from league.team_roster(team_id, period)")

    def player_day_lines(self, on: date) -> dict[str, PlayerDay]:
        raise NotImplementedError("decode getLiveScoringStats(on) via decode_player_day_stats")

    def projected_player_lines(self, period: int) -> dict[str, PlayerLine]:
        raise NotImplementedError("parse season-to-date per-game rates from roster STATS view")
