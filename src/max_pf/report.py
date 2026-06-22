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

With ``include_nash`` two more columns appear (per-period Nash mutual ceiling,
``engine.season_nash``; see docs/PROMPT_LOG.md):
- M3: the mutual-ceiling score (sum) — both managers play their equilibrium
  lineup, so neither can exploit the other. Pure or mixed-strategy value alike.
- M1-M3: the opponent-passivity dividend — how much of my exploitation ceiling
  M1 relied on the opponent *not* also optimizing (M1 >= M3, so this is >= 0).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Callable

from .engine import season_deltas, season_nash
from .optimize import Slot


@dataclass
class TeamSeason:
    team_id: str
    name: str
    periods: int
    actual_pf: float
    m1_pf: float
    m2_pf: float
    m3_pf: float | None = None   # Nash mutual ceiling (sum); None unless computed

    @property
    def delta(self) -> float:
        return self.m1_pf - self.m2_pf

    @property
    def luck(self) -> float:
        return self.actual_pf - self.m1_pf

    @property
    def m1_minus_m3(self) -> float:
        """Opponent-passivity dividend (only meaningful when ``m3_pf`` is set)."""
        return self.m1_pf - (self.m3_pf or 0.0)


@dataclass(frozen=True)
class _Column:
    header: str
    render: Callable[[TeamSeason], str]


def _columns(rows: list[TeamSeason]) -> list[_Column]:
    """The active columns: the base set, plus the Nash pair when M3 was computed.

    Column-driven so the three renderers share one column list (and adding a
    column — here the Nash mutual ceiling — touches one place, not three).
    """
    cols = [
        _Column("Team", lambda r: r.name),
        _Column("GP", lambda r: str(r.periods)),
        _Column("Actual", lambda r: f"{r.actual_pf:.1f}"),
        _Column("M1", lambda r: f"{r.m1_pf:.1f}"),
        _Column("M2", lambda r: f"{r.m2_pf:.1f}"),
        _Column("Delta", lambda r: f"{r.delta:.1f}"),
        _Column("Luck", lambda r: f"{r.luck:+.1f}"),
    ]
    if rows and rows[0].m3_pf is not None:
        # Keep the ceiling family together: M3 after M2, its dividend beside it.
        cols[5:5] = [
            _Column("M3", lambda r: f"{r.m3_pf:.1f}"),
            _Column("M1-M3", lambda r: f"{r.m1_minus_m3:+.1f}"),
        ]
    return cols


def build_team_season(
    platform, team_id: str, periods: list[int], slots: list[Slot],
    methodology: str = "expected", objective: str = "catwins", include_nash: bool = True,
) -> TeamSeason:
    results = season_deltas(platform, team_id, periods, slots, methodology, objective)
    m3_pf = None
    if include_nash:
        nash = season_nash(platform, team_id, periods, slots, methodology)
        m3_pf = sum(r.value for r in nash.values())
    return TeamSeason(
        team_id=team_id,
        name=platform.team_name(team_id),
        periods=len(results),
        actual_pf=sum(r.actual.points_for for r in results.values()),
        m1_pf=sum(r.m1.points_for for r in results.values()),
        m2_pf=sum(r.m2.points_for for r in results.values()),
        m3_pf=m3_pf,
    )


def season_report(
    platform, slots: list[Slot], periods: list[int] | None = None,
    methodology: str = "expected", objective: str = "catwins", include_nash: bool = True,
) -> list[TeamSeason]:
    """Compute the season summary for every team, sorted by actual points for.

    ``include_nash`` runs the Nash mutual-ceiling search per team and surfaces the
    M3 / M1-M3 columns — the full picture, and on by default. It is markedly more
    expensive (iterated best response, plus a double-oracle LP for cycling weeks),
    so pass ``include_nash=False`` to skip it for a quicker, M1/M2-only report.
    """
    periods = periods or platform.matchup_periods()
    rows = [build_team_season(platform, tid, periods, slots, methodology, objective, include_nash)
            for tid in platform.team_ids()]
    rows.sort(key=lambda r: r.actual_pf, reverse=True)
    return rows


def render_table(rows: list[TeamSeason]) -> str:
    cols = _columns(rows)
    table = [[c.header for c in cols]] + [[c.render(r) for c in cols] for r in rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(cols))]

    def fmt(row: list[str]) -> str:
        cells = [row[0].ljust(widths[0])] + [row[i].rjust(widths[i]) for i in range(1, len(row))]
        return "  ".join(cells)

    sep = "  ".join("-" * w for w in widths)
    return "\n".join([fmt(table[0]), sep, *(fmt(r) for r in table[1:])])


def render_markdown(rows: list[TeamSeason]) -> str:
    cols = _columns(rows)
    lines = ["| " + " | ".join(c.header for c in cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(c.render(r) for c in cols) + " |" for r in rows]
    return "\n".join(lines)


def render_csv(rows: list[TeamSeason]) -> str:
    cols = _columns(rows)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c.header for c in cols])
    writer.writerows([c.render(r) for c in cols] for r in rows)
    return buf.getvalue()
