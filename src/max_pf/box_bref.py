"""basketball-reference box-score source: exact per-player per-day 9-cat lines.

Fetches daily box scores (one index page per date -> one page per game), parses
real makes/attempts (no estimator needed), and caches raw HTML on disk so
re-runs are free. Rate-limited to stay under bref's ~20 requests/minute.

Requires the optional extra:  pip install "max-pf[boxscores]"
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import PlayerLine

BASE = "https://www.basketball-reference.com"
_GAME_PATH = re.compile(r"/boxscores/\d{9}[A-Z]{3}\.html")
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


@dataclass(frozen=True)
class PlayerBox:
    bref_id: str
    name: str
    team: str          # bref team abbreviation
    line: PlayerLine


def normalize_name(name: str) -> str:
    """Normalize a player name for matching: strip accents, punctuation, suffix.

    Handles both "First Last" and bref's "Last,First" forms.
    """
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first} {last}"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[.'`]", "", name.lower())
    tokens = [t for t in re.split(r"[\s\-]+", name) if t and t not in _SUFFIXES]
    return " ".join(tokens)


def parse_day_index(html: str) -> list[str]:
    """Game box-score paths listed on a daily index page."""
    return sorted(set(_GAME_PATH.findall(html)))


def parse_game_lines(html: str) -> list[PlayerBox]:
    """Per-player lines from a game box-score page (both teams)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: list[PlayerBox] = []
    for table in soup.find_all("table", id=re.compile(r"^box-[A-Z]{3}-game-basic$")):
        team = table["id"].split("-")[1]
        body = table.find("tbody")
        if body is None:
            continue
        for tr in body.find_all("tr"):
            th = tr.find("th", attrs={"data-append-csv": True})
            if th is None:
                continue  # subheader / team-total row
            cells = {td.get("data-stat"): td.get_text(strip=True) for td in tr.find_all("td")}
            if not cells.get("pts") and not cells.get("fga"):
                continue  # Did Not Play / Did Not Dress
            out.append(PlayerBox(
                bref_id=th["data-append-csv"],
                name=th.get_text(strip=True),
                team=team,
                line=_line_from_cells(cells),
            ))
    return out


def _num(cells: dict[str, str], key: str) -> float:
    val = cells.get(key, "")
    return float(val) if val else 0.0


def _line_from_cells(cells: dict[str, str]) -> PlayerLine:
    return PlayerLine(
        tpm=_num(cells, "fg3"), pts=_num(cells, "pts"), reb=_num(cells, "trb"),
        ast=_num(cells, "ast"), stl=_num(cells, "stl"), blk=_num(cells, "blk"),
        to=_num(cells, "tov"),
        fgm=_num(cells, "fg"), fga=_num(cells, "fga"),
        ftm=_num(cells, "ft"), fta=_num(cells, "fta"),
    )


@dataclass
class MappingResult:
    mapping: dict[str, str]       # fantrax scorerId -> bref_id
    unmatched: list[str]          # fantrax names with no bref match
    ambiguous: list[str]          # normalized names with >1 bref id

    @property
    def coverage(self) -> float:
        total = len(self.mapping) + len(self.unmatched)
        return len(self.mapping) / total if total else 0.0


# Nickname / short-form differences between Fantrax and bref (normalized
# Fantrax name -> normalized bref name). Seeded from the coverage report;
# extend as the full-season run surfaces more.
ALIASES: dict[str, str] = {
    "carlton carrington": "bub carrington",
    "nicolas claxton": "nic claxton",
}


def build_id_map(
    fantrax_names: dict[str, str],
    bref_players: list[PlayerBox],
    aliases: dict[str, str] | None = None,
) -> MappingResult:
    """Map Fantrax scorerIds to bref ids by normalized name.

    Args:
        fantrax_names: scorerId -> display name.
        bref_players: parsed box lines (union across the dates seen).
        aliases: normalized Fantrax name -> normalized bref name overrides for
            nickname/short-form differences (defaults to :data:`ALIASES`).
    """
    aliases = ALIASES if aliases is None else aliases
    index: dict[str, set[str]] = {}
    for pb in bref_players:
        index.setdefault(normalize_name(pb.name), set()).add(pb.bref_id)

    mapping: dict[str, str] = {}
    unmatched: list[str] = []
    ambiguous: list[str] = []
    for scorer_id, name in fantrax_names.items():
        norm = normalize_name(name)
        ids = index.get(aliases.get(norm, norm))
        if not ids:
            unmatched.append(name)
        elif len(ids) > 1:
            ambiguous.append(name)
        else:
            mapping[scorer_id] = next(iter(ids))
    return MappingResult(mapping, unmatched, ambiguous)


class BRefClient:
    """Cached, rate-limited basketball-reference fetcher."""

    def __init__(self, cache_dir: str = ".cache/bref", min_interval: float = 3.5, session=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last_fetch = 0.0
        if session is None:
            import requests
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0 (max_pf research)"})
        self._session = session

    def _get(self, path: str) -> str:
        cache_file = self.cache_dir / (re.sub(r"[^A-Za-z0-9]", "_", path).strip("_") + ".html")
        if cache_file.exists():
            return cache_file.read_text()
        wait = self.min_interval - (time.monotonic() - self._last_fetch)
        if wait > 0:
            time.sleep(wait)
        resp = self._session.get(BASE + path, timeout=30)
        self._last_fetch = time.monotonic()
        resp.raise_for_status()
        cache_file.write_text(resp.text)
        return resp.text

    def day_lines(self, on: date) -> dict[str, PlayerBox]:
        """All players' realized lines on a date, keyed by bref id."""
        index = self._get(f"/boxscores/?month={on.month}&day={on.day}&year={on.year}")
        lines: dict[str, PlayerBox] = {}
        for game_path in parse_day_index(index):
            for pb in parse_game_lines(self._get(game_path)):
                lines[pb.bref_id] = pb
        return lines

    def day_teams(self, on: date) -> set[str]:
        """bref team abbreviations that played on a date."""
        return {pb.team for pb in self.day_lines(on).values()}
