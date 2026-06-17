"""Season-level max-points-for report.

Aggregates per-period Δ results into a per-team season summary and renders it as
a text table, CSV, or Markdown.

These columns are the **A-expected** reading: ``mine_opt`` is the best lineup of
season-to-date *projections*, not realized stats. So M1 is an *expected* ceiling,
and ``Luck`` (Actual - M1) can be positive when a team outran its projections.
A true lineup-management efficiency (realized-optimal vs realized-actual, always
>= actual) requires the A-hindsight variant; see docs/PROMPT_LOG.md.

Columns:
- Actual: category points the team actually scored (sum of weekly results).
- M1: projection-optimal lineup vs each opponent's actual line (sum).
- M2: projection-optimal lineup vs each opponent's projection-optimum (sum).
- Delta = M1 - M2: the opponent-mismanagement dividend.
- Luck = Actual - M1: realized result minus expected ceiling (week/projection
  variance; positive = overperformed expectation).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .engine import season_deltas
from .optimize import Slot


@dataclass
class TeamSeason:
    team_id: str
    name: str
    periods: int
    actual_pf: float
    m1_pf: float
    m2_pf: float

    @property
    def delta(self) -> float:
        return self.m1_pf - self.m2_pf

    @property
    def luck(self) -> float:
        return self.actual_pf - self.m1_pf


_COLUMNS = ["Team", "GP", "Actual", "M1", "M2", "Delta", "Luck"]


def build_team_season(platform, team_id: str, periods: list[int], slots: list[Slot]) -> TeamSeason:
    results = season_deltas(platform, team_id, periods, slots)
    return TeamSeason(
        team_id=team_id,
        name=platform.team_name(team_id),
        periods=len(results),
        actual_pf=sum(r.actual.points_for for r in results.values()),
        m1_pf=sum(r.m1.points_for for r in results.values()),
        m2_pf=sum(r.m2.points_for for r in results.values()),
    )


def season_report(platform, slots: list[Slot], periods: list[int] | None = None) -> list[TeamSeason]:
    """Compute the season summary for every team, sorted by actual points for."""
    periods = periods or platform.matchup_periods()
    rows = [build_team_season(platform, tid, periods, slots) for tid in platform.team_ids()]
    rows.sort(key=lambda r: r.actual_pf, reverse=True)
    return rows


def _row_values(r: TeamSeason) -> list[str]:
    return [
        r.name, str(r.periods), f"{r.actual_pf:.1f}", f"{r.m1_pf:.1f}",
        f"{r.m2_pf:.1f}", f"{r.delta:.1f}", f"{r.luck:+.1f}",
    ]


def render_table(rows: list[TeamSeason]) -> str:
    table = [_COLUMNS] + [_row_values(r) for r in rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(_COLUMNS))]

    def fmt(row: list[str]) -> str:
        cells = [row[0].ljust(widths[0])] + [row[i].rjust(widths[i]) for i in range(1, len(row))]
        return "  ".join(cells)

    sep = "  ".join("-" * w for w in widths)
    return "\n".join([fmt(table[0]), sep, *(fmt(r) for r in table[1:])])


def render_markdown(rows: list[TeamSeason]) -> str:
    lines = ["| " + " | ".join(_COLUMNS) + " |",
             "| " + " | ".join("---" for _ in _COLUMNS) + " |"]
    lines += ["| " + " | ".join(_row_values(r)) + " |" for r in rows]
    return "\n".join(lines)


def render_csv(rows: list[TeamSeason]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)
    writer.writerows(_row_values(r) for r in rows)
    return buf.getvalue()
