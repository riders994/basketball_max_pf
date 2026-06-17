"""max_pf -- "max points for" methodology for 9-cat fantasy basketball.

Public surface kept small while the optimizer/projection layers are built out.
"""
from __future__ import annotations

from .categories import CATEGORIES, CATEGORY_KEYS, Category
from .estimators import estimate_attempts
from .metric import CategoryResult, DeltaResult, catwins, compute_delta
from .models import PlayerDay, PlayerLine, RosterDay, aggregate

__version__ = "0.0.1"

__all__ = [
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
