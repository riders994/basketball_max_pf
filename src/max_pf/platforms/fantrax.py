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
from ..optimize import Candidate, Slot
from ..sources import StatSource
from .base import LeaguePlatform

# How a slot's short name expands to the player position tags it accepts.
# Combo letters cover their base positions (G = guards, F = forwards); flex
# slots accept anyone (empty eligible set).
_POS_EXPAND: dict[str, set[str]] = {
    "PG": {"PG"}, "SG": {"SG"}, "SF": {"SF"}, "PF": {"PF"}, "C": {"C"},
    "G": {"PG", "SG", "G"}, "F": {"SF", "PF", "F"},
}


def slot_eligibility(short_name: str) -> frozenset[str]:
    """Player position tags a slot accepts, parsed from its short name.

    Handles single positions ("C"), combo letters ("G", "F"), slash combos
    ("G/C", "SG/SF"), and flex/util (any player -> empty set).
    """
    name = short_name.strip()
    if name.lower().startswith(("flx", "flex", "util")):
        return frozenset()
    eligible: set[str] = set()
    for token in name.split("/"):
        token = token.strip()
        eligible |= _POS_EXPAND.get(token, {token})
    return frozenset(eligible)


# Confirmed active-slot layout for league wserh14rmbbpqtcg (PG,SG,G,SF,PF,F,C +
# 2 Flex = 9). General code should prefer FantraxPlatform.active_slots(), which
# derives this from the league; this constant is a convenience/fallback.
DEFAULT_NBA_SLOTS: list[Slot] = [
    Slot(n, slot_eligibility(n)) for n in ("PG", "SG", "G", "SF", "PF", "F", "C", "Flx", "Flx")
]

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


def decode_roster_positions(stats_table: dict) -> dict[str, tuple[str, ...]]:
    """Map scorerId -> eligible position short-names from a roster table."""
    out: dict[str, tuple[str, ...]] = {}
    for row in stats_table.get("rows", []):
        scorer = row.get("scorer")
        if scorer:
            out[scorer["scorerId"]] = tuple((scorer.get("posShortNames") or "").split(","))
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


# Matchup scoring-grid labels (H2HRotisserie2 header shortNames) -> category keys.
GRID_LABEL: dict[str, str] = {
    "FG%": "fg_pct", "3PTM": "tpm", "FT%": "ft_pct", "PTS": "pts", "REB": "reb",
    "AST": "ast", "ST": "stl", "BLK": "blk", "TO": "to",
}


def team_line_from_grid(grid: dict[str, dict[str, float]], team_id: str) -> PlayerLine:
    """Build a team's realized line from a matchup ``scoring_grid``.

    The grid only carries the FG%/FT% *percentages*, not makes/attempts, so we
    store them with a unit denominator (fga/fta = 1) -- ``PlayerLine.fg_pct``
    then returns the grid value exactly. This is a terminal team line used only
    as a catwins operand/target; never aggregate it with other lines.
    """
    vals: dict[str, float] = {}
    for label, key in GRID_LABEL.items():
        if label in grid and team_id in grid[label]:
            vals[key] = float(grid[label][team_id])
    line = PlayerLine(
        tpm=vals.get("tpm", 0.0), pts=vals.get("pts", 0.0), reb=vals.get("reb", 0.0),
        ast=vals.get("ast", 0.0), stl=vals.get("stl", 0.0), blk=vals.get("blk", 0.0),
        to=vals.get("to", 0.0),
    )
    if "fg_pct" in vals:
        line.fgm, line.fga = vals["fg_pct"], 1.0
    if "ft_pct" in vals:
        line.ftm, line.fta = vals["ft_pct"], 1.0
    return line


class FantraxPlatform(LeaguePlatform):
    """Normalized adapter over a fantraxapi ``League``."""

    def __init__(self, league_id: str, session=None, stat_source: StatSource | None = None) -> None:
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
        self._period_results_cache: dict | None = None
        # Player performance comes from pluggable StatSources, routed by
        # methodology: A-expected from expected_source (Fantrax projections +
        # estimator by default), A-hindsight from an optional box-score source.
        # use_boxscores() attaches one box-score source and points BOTH routes at
        # it (exact rates for expected, realized lines for hindsight). The
        # optimizer/engine/report are unchanged.
        self.stat_source: StatSource = stat_source or FantraxStatSource(self)
        self.expected_source: StatSource = self.stat_source
        self.hindsight_source: StatSource | None = None
        # Finished-season data is immutable, so memoize the expensive fetches.
        # Each (team, period) candidate set is otherwise computed twice (once as
        # a team, once as its opponent's opponent). Keyed by methodology too.
        self._candidates_cache: dict[tuple[str, int, str], list[list[Candidate]]] = {}

    def team_ids(self) -> list[str]:
        return [t.id for t in self._league.teams]

    def team_name(self, team_id: str) -> str:
        return self._league.team(team_id).name

    def all_players(self) -> dict[str, str]:
        """Map scorerId -> display name across all current rosters (for id mapping)."""
        out: dict[str, str] = {}
        for team_id in self.team_ids():
            raw = self._api.get_team_roster_info(self._league, team_id)
            for table in raw[0].get("tables", []):
                for row in table.get("rows", []):
                    scorer = row.get("scorer")
                    if scorer:
                        out[scorer["scorerId"]] = scorer["name"]
        return out

    def matchup_periods(self) -> list[int]:
        return sorted(self._league.scoring_periods)

    def scoring_dates(self) -> dict[int, date]:
        return dict(self._league.scoring_dates)

    def active_slots(self) -> list[Slot]:
        """Derive the league's active lineup slots from a roster (status=Active).

        Slot multiplicities and eligibility come straight from the league, so
        this works for any roster configuration, not just the default NBA one.
        """
        raw = self._api.get_team_roster_info(self._league, self.team_ids()[0])
        slots: list[Slot] = []
        for table in raw[0].get("tables", []):
            for row in table.get("rows", []):
                if row.get("statusId") == "1" and "posId" in row:  # 1 = Active
                    short = self._league.positions[row["posId"]].short_name
                    slots.append(Slot(short, slot_eligibility(short)))
        return slots

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

    def roster_membership(self, team_id: str, daily_period: int) -> dict[str, tuple[str, tuple[str, ...]]]:
        """scorerId -> (name, eligible positions) for a team's roster on a day.

        Names come from the historical roster itself (not current rosters), so
        players dropped before now are still resolvable for box-score matching.
        """
        out: dict[str, tuple[str, tuple[str, ...]]] = {}
        for table in self._roster_stats_tables(team_id, daily_period):
            for row in table.get("rows", []):
                scorer = row.get("scorer")
                if scorer:
                    positions = tuple((scorer.get("posShortNames") or "").split(","))
                    out[scorer["scorerId"]] = (scorer["name"], positions)
        return out

    def period_candidates(
        self, team_id: str, period: int, methodology: str = "expected"
    ) -> list[list[Candidate]]:
        """Per-day candidate pool for the optimizer, via the configured StatSource.

        ``methodology`` is ``"expected"`` (season-to-date projections) or
        ``"hindsight"`` (realized lines). Memoized per (team, period, methodology).
        """
        key = (team_id, period, methodology)
        cached = self._candidates_cache.get(key)
        if cached is not None:
            return cached
        if methodology == "hindsight":
            if self.hindsight_source is None:
                raise NotImplementedError(
                    "no hindsight source attached; call platform.use_boxscores(client)"
                )
            result = self.hindsight_source.hindsight_candidates(team_id, period)
        else:
            result = self.expected_source.expected_candidates(team_id, period)
        self._candidates_cache[key] = result
        return result

    def use_boxscores(self, client) -> None:
        """Attach a basketball-reference box-score source for both methodologies.

        Routes A-hindsight (realized per-day lines) AND A-expected (exact
        season-to-date rates, replacing the FG/FT estimator) through it.
        """
        from ..box_bref import BoxScoreStatSource

        box = BoxScoreStatSource(self, client)
        self.hindsight_source = box
        self.expected_source = box

    def expected_period_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        """Fantrax-derived A-expected per-day pools (used by FantraxStatSource).

        Each day lists players with a game that day, carrying their season-to-date
        per-game line (as of period start) and eligible positions. Summing a
        player's candidate days reproduces their projected period total. Players
        added mid-period are not projected (v1).
        """
        days = self.matchup_period_days(period)
        if not days:
            return []
        day_tables = {dp: self._roster_stats_tables(team_id, dp) for dp in days}

        rates: dict[str, PlayerLine] = {}
        positions: dict[str, tuple[str, ...]] = {}
        for table in day_tables[days[0]]:  # rates/eligibility as of period start
            rates.update(decode_roster_stats(table))
            positions.update(decode_roster_positions(table))

        per_day: list[list[Candidate]] = []
        for dp in days:
            playing: set[str] = set()
            for table in day_tables[dp]:
                playing |= players_with_game(table)
            per_day.append([
                Candidate(pid, rates[pid], positions.get(pid, ()))
                for pid in playing if pid in rates
            ])
        return per_day

    def projected_roster_lines(self, team_id: str, period: int) -> dict[str, PlayerLine]:
        """A-expected per-player projected period totals (sum of candidate days)."""
        totals: dict[str, PlayerLine] = {}
        for day in self.period_candidates(team_id, period):
            for cand in day:
                totals[cand.player_id] = totals.get(cand.player_id, PlayerLine()) + cand.line
        return totals

    def _period_results(self) -> dict:
        if self._period_results_cache is None:
            self._period_results_cache = self._league.scoring_period_results(playoffs=False)
        return self._period_results_cache

    @staticmethod
    def _side_id(side) -> str | None:
        return side.id if hasattr(side, "id") else None

    def _matchup_for(self, team_id: str, period: int):
        spr = self._period_results().get(period)
        if spr is None:
            return None
        for matchup in spr.matchups.values():
            if team_id in (self._side_id(matchup.home), self._side_id(matchup.away)):
                return matchup
        return None

    def matchup_opponent(self, team_id: str, period: int) -> str | None:
        matchup = self._matchup_for(team_id, period)
        if matchup is None:
            return None
        home, away = self._side_id(matchup.home), self._side_id(matchup.away)
        return away if home == team_id else home

    def actual_team_line(self, team_id: str, period: int) -> PlayerLine:
        matchup = self._matchup_for(team_id, period)
        if matchup is None or not getattr(matchup, "scoring_grid", None):
            raise ValueError(f"no scoring grid for team {team_id} in period {period}")
        return team_line_from_grid(matchup.scoring_grid, team_id)

    def roster_day(self, team_id: str, period: int) -> RosterDay:
        raise NotImplementedError("build from league.team_roster(team_id, period)")

    def player_day_lines(self, on: date) -> dict[str, PlayerDay]:
        raise NotImplementedError("decode getLiveScoringStats(on) via decode_player_day_stats")


class FantraxStatSource(StatSource):
    """A-expected source backed by Fantrax roster STATS + the FG/FT estimator.

    Cannot supply A-hindsight: Fantrax exposes daily lines only for started
    players, so ``hindsight_candidates`` keeps the base NotImplementedError.
    """

    def __init__(self, platform: FantraxPlatform) -> None:
        self._platform = platform

    def expected_candidates(self, team_id: str, period: int) -> list[list[Candidate]]:
        return self._platform.expected_period_candidates(team_id, period)
