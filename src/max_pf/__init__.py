"""max_pf -- "max points for" methodology for 9-cat fantasy basketball.

Top-level entry point: ``max_pf.run(login, ...)`` takes a platform login dict and
returns the season report. See :mod:`max_pf.app`.
"""
from __future__ import annotations

from .app import build_platform, load_login, parse_weeks, run
from .categories import CATEGORIES, CATEGORY_KEYS, Category
from .estimators import estimate_attempts
from .metric import CategoryResult, DeltaResult, catwins, compute_delta
from .models import PlayerDay, PlayerLine, RosterDay, aggregate
from .report import TeamSeason, render_csv, render_markdown, render_table

__version__ = "1.1.0"

__all__ = [
    # entry point
    "run",
    "build_platform",
    "load_login",
    "parse_weeks",
    "TeamSeason",
    "render_table",
    "render_csv",
    "render_markdown",
    # primitives
    "CATEGORIES",
    "CATEGORY_KEYS",
    "Category",
    "estimate_attempts",
    "CategoryResult",
    "DeltaResult",
    "catwins",
    "compute_delta",
    "PlayerLine",
    "PlayerDay",
    "RosterDay",
    "aggregate",
    "__version__",
]
