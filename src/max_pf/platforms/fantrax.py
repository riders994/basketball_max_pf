"""Fantrax platform adapter (wraps the stable fork of fantraxapi).

Implements the pure transforms verified against live data. Note Fantrax uses
*different* stat ids for daily totals vs season per-game rates, so there are two
scipId maps below (only FG%/FT% share an id across them).

Install the optional dependency to use this adapter::

    pip install "max-pf[fantrax]"
"""
from __future__ import annotations

from datetime import date

from ..estimators import estimate_attempts
from ..models import PlayerDay, PlayerLine, RosterDay
from ..projections import project_period_line
from .base import LeaguePlatform

# Per-player *daily total* stat ids (getLiveScoringStats -> object2).
DAILY_STAT_SCIP: dict[int, str] = {
    1520: "fg_pct", 1435: "tpm", 1550: "ft_pct", 1390: "pts", 1400: "reb",
    1250: "ast", 1410: "stl", 1260: "blk", 1460: "to",
}

# Per-player *season per-game* stat ids (getTeamRosterInfo view=STATS columns).
PERGAME_STAT_SCIP: dict[int, str] = {
    1520: "fg_pct", 1620: "tpm", 1550: "ft_pct", 1590: "pts", 1600: "reb",
    1470: "ast", 1610: "stl", 1480: "blk", 1650: "to",
}
GAMES_PLAYED_SCIP = 1350


def parse_scip(field: str) -> int:
    """Parse the integer stat id out of a ``"3010#1390#-1"`` field."""
    return int(field.split("#")[1])


def parse_stat(content: str | None) -> float:
    """Parse a Fantrax stat cell: ``".376"`` -> 0.376, ``"8.0"`` -> 8.0, ``""`` -> 0.0."""
    if not content:
        return 0.0
    s = str(content).strip()
    return float(s) if s else 0.0


def _line_from_raw(raw: dict[str, float], positions: tuple[str, ...]) -> PlayerLine:
    """Build a PlayerLine from category-keyed values, filling makes/attempts."""
    fgm, fga, ftm, fta = estimate_attempts(
        pts=raw.get("pts", 0.0),
        tpm=raw.get("tpm", 0.0),
        fg_pct=raw.get("fg_pct", 0.0),
        ft_pct=raw.get("ft_pct", 0.0),
        positions=positions,
    )
    return PlayerLine(
        tpm=raw.get("tpm", 0.0), pts=raw.get("pts", 0.0), reb=raw.get("reb", 0.0),
        ast=raw.get("ast", 0.0), stl=raw.get("stl", 0.0), blk=raw.get("blk", 0.0),
        to=raw.get("to", 0.0), fgm=fgm, fga=fga, ftm=ftm, fta=fta,
    )


def decode_player_day_stats(object2: list[dict], positions: tuple[str, ...] = ()) -> PlayerLine:
    """Turn a live-scoring ``object2`` stat list into a normalized daily PlayerLine."""
    raw = {
        DAILY_STAT_SCIP[scip]: parse_stat(e.get("av"))
        for e in object2
        if (scip := parse_scip(e["scipId"])) in DAILY_STAT_SCIP
    }
    return _line_from_raw(raw, positions)


def decode_roster_stats(stats_table: dict) -> dict[str, PlayerLine]:
    """Parse a roster STATS table into per-player **per-game** lines (season-to-date).

    Keys columns by scipId from the header (language-independent). Returns a map
    of ``scorerId -> per-game PlayerLine`` (with makes/attempts estimated from
    the per-game rates, so scaling by games-in-period stays linear).
    """
    header = stats_table["header"]["cells"]
    col_key: dict[int, str] = {}  # column index -> category key
    for i, cell in enumerate(header):
        scip_field = cell.get("scipId") or cell.get("key")
        if scip_field and "#" in scip_field:
            cat = PERGAME_STAT_SCIP.get(parse_scip(scip_field))
            if cat is not None:
                col_key[i] = cat

    out: dict[str, PlayerLine] = {}
    for row in stats_table.get("rows", []):
        scorer = row.get("scorer")
        if not scorer:
            continue
        positions = tuple((scorer.get("posShortNames") or "").split(","))
        raw = {
            col_key[i]: parse_stat(cell.get("content"))
            for i, cell in enumerate(row["cells"])
            if i in col_key
        }
        out[scorer["scorerId"]] = _line_from_raw(raw, positions)
    return out


def players_with_game(stats_table: dict) -> set[str]:
    """Scorer ids that have a game on the day this STATS table was fetched.

    Reads the per-day "Opponent" column (non-empty content = the player's NBA
    team played that day), which reflects scheduled games regardless of whether
    the player was started or benched.
    """
    header = stats_table["header"]["cells"]
    opp_idx = next(
        (i for i, c in enumerate(header) if c.get("key") == "opponent" or c.get("shortName") == "Opp"),
        None,
    )
    if opp_idx is None:
        return set()
    out: set[str] = set()
    for row in stats_table.get("rows", []):
        scorer = row.get("scorer")
        cells = row.get("cells", [])
        if scorer and opp_idx < len(cells) and (cells[opp_idx].get("content") or "").strip():
            out.add(scorer["scorerId"])
    return out


def transaction_date_column(header_cells: list[dict]) -> int:
    """Locate the date column index from the transaction-table header.

    The fork assumes ``cells[1]`` which is wrong for some leagues; resolve from
    the header instead (mirrors how Standings does it).
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
        except ImportError as e:  # pragma: no cover - only without the extra
            raise ImportError(
                'The Fantrax adapter requires the optional dependency: '
                'pip install "max-pf[fantrax]"'
            ) from e
        from fantraxapi import api  # noqa: F401 (kept for fetch methods below)

        self._api = api
        self._league = League(league_id, session=session) if session else League(league_id)

    def team_ids(self) -> list[str]:
        return [t.id for t in self._league.teams]

    def scoring_dates(self) -> dict[int, date]:
        return dict(self._league.scoring_dates)

    def _roster_stats_tables(self, team_id: str, daily_period: int) -> list[dict]:
        raw = self._api.get_team_roster_info(self._league, team_id, period_number=daily_period)
        return raw[0].get("tables", [])

    def season_to_date_rates(self, team_id: str, daily_period: int) -> dict[str, PlayerLine]:
        """Per-player per-game lines (season-to-date as of a daily period) for a team."""
        rates: dict[str, PlayerLine] = {}
        for table in self._roster_stats_tables(team_id, daily_period):
            rates.update(decode_roster_stats(table))
        return rates

    def matchup_period_days(self, period: int) -> list[int]:
        """Daily period numbers that fall within a matchup period's date range."""
        sp = self._league.scoring_periods[period]
        return [num for num, d in sorted(self._league.scoring_dates.items()) if sp.start <= d <= sp.end]

    def projected_roster_lines(self, team_id: str, period: int) -> dict[str, PlayerLine]:
        """A-expected projection: season-to-date per-game rates (as of period
        start) scaled by each player's games scheduled in the matchup period.

        Sweeps the matchup week's daily roster views once each: the first day
        supplies the rates; every day contributes to per-player game counts via
        the Opponent column. Players added mid-period are not projected (v1).
        """
        days = self.matchup_period_days(period)
        if not days:
            return {}
        rates: dict[str, PlayerLine] = {}
        games: dict[str, int] = {}
        for i, daily_period in enumerate(days):
            tables = self._roster_stats_tables(team_id, daily_period)
            if i == 0:
                for table in tables:
                    rates.update(decode_roster_stats(table))
            for table in tables:
                for pid in players_with_game(table):
                    games[pid] = games.get(pid, 0) + 1
        return {
            pid: project_period_line(rate, games.get(pid, 0))
            for pid, rate in rates.items()
        }

    # --- Remaining fetch methods: next sub-steps of the build -----------------

    def matchup_opponent(self, team_id: str, period: int) -> str | None:
        raise NotImplementedError("wire up via scoring_period_results() matchup grid")

    def actual_team_line(self, team_id: str, period: int) -> PlayerLine:
        raise NotImplementedError("map the matchup scoring_grid categories to PlayerLine")

    def roster_day(self, team_id: str, period: int) -> RosterDay:
        raise NotImplementedError("build from league.team_roster(team_id, period)")

    def player_day_lines(self, on: date) -> dict[str, PlayerDay]:
        raise NotImplementedError("decode getLiveScoringStats(on) via decode_player_day_stats")
