"""Top-level entry point: a login dict in, a season report out.

Programmatic use::

    import max_pf
    rows = max_pf.run({"platform": "fantrax", "league_id": "wserh14rmbbpqtcg"})
    print(max_pf.render_table(rows))

The ``login`` dict names the ``platform`` and carries whatever that platform
needs (for Fantrax, a ``league_id``). By default the report covers the whole
season to date; pass ``weeks`` to scope it to one week or a selection.

From the command line a JSON or YAML file holds the same dict::

    python -m max_pf league.json
    python -m max_pf league.yaml --weeks 1-6
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .report import TeamSeason, season_report

# platform name -> builder(login) -> platform instance. Add adapters here.
PLATFORMS: dict[str, Callable[[dict], object]] = {}


def register_platform(name: str, builder: Callable[[dict], object]) -> None:
    PLATFORMS[name] = builder


def _build_fantrax(login: dict):
    if "league_id" not in login:
        raise ValueError("fantrax login requires a 'league_id'")
    from .platforms.fantrax import FantraxPlatform

    return FantraxPlatform(login["league_id"], session=login.get("session"))


register_platform("fantrax", _build_fantrax)


def build_platform(login: dict):
    """Construct the platform adapter named by ``login['platform']``."""
    try:
        name = login["platform"]
    except (KeyError, TypeError):
        raise ValueError("login must be a dict with a 'platform' key") from None
    builder = PLATFORMS.get(name)
    if builder is None:
        raise ValueError(
            f"unknown platform {name!r}; available: {sorted(PLATFORMS)}"
        )
    return builder(login)


def parse_weeks(weeks: int | str | list[int] | None) -> list[int] | None:
    """Normalize a weeks selection to a sorted list of matchup periods (or None).

    Accepts ``None`` (whole season), an int (one week), a list/tuple/range of
    ints, or a spec string like ``"5"``, ``"1-6"``, or ``"1,2,5"``.
    """
    if weeks is None:
        return None
    if isinstance(weeks, int):
        return [weeks]
    if isinstance(weeks, str):
        out: list[int] = []
        for part in weeks.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-")
                out.extend(range(int(lo), int(hi) + 1))
            elif part:
                out.append(int(part))
        return sorted(set(out))
    return sorted(set(int(w) for w in weeks))


def load_login(path: str | Path) -> dict:
    """Load a login dict from a JSON or YAML file (dispatch by extension)."""
    path = Path(path)
    text = path.read_text()
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:  # pragma: no cover - only without the extra
            raise ImportError(
                'YAML login files need the optional dependency: pip install "max-pf[yaml]"'
            ) from e
        data = yaml.safe_load(text)
    else:
        raise ValueError(f"unsupported login file type {suffix!r}; use .json or .yaml")
    if not isinstance(data, dict):
        raise ValueError(f"login file {path} must contain a mapping, got {type(data).__name__}")
    return data


def run(
    login: dict,
    *,
    weeks: int | str | list[int] | None = None,
    methodology: str = "expected",
    objective: str = "catwins",
    boxscores: bool = True,
    cache_dir: str | None = None,
) -> list[TeamSeason]:
    """Build the platform from ``login`` and return the season report rows.

    Args:
        login: ``{"platform": ..., ...}`` selecting and configuring the adapter.
        weeks: a week, a selection, or a spec string; ``None`` = season to date.
        methodology: ``"expected"`` (projections) or ``"hindsight"`` (realized).
        objective: ``"catwins"`` (A), ``"zscore"`` (B), or ``"raw"`` (C).
        boxscores: attach the basketball-reference source (exact stats); set
            False to use the platform's built-in estimator (expected only).
        cache_dir: override the box-score on-disk cache location.

    Returns the per-team :class:`~max_pf.report.TeamSeason` rows, sorted by actual
    points for; render with ``max_pf.render_table`` / ``render_csv`` /
    ``render_markdown``.
    """
    platform = build_platform(login)
    if boxscores and hasattr(platform, "use_boxscores"):
        from .box_bref import BRefClient

        platform.use_boxscores(BRefClient(cache_dir) if cache_dir else BRefClient())
    slots = platform.active_slots()
    return season_report(
        platform, slots, periods=parse_weeks(weeks),
        methodology=methodology, objective=objective,
    )
