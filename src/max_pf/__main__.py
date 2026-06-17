"""Command-line season report: ``python -m max_pf <league_id>``.

Computes the max-points-for season summary for every team in a Fantrax 9-cat
league, prints it, and writes ``<out>.csv`` and ``<out>.md``.

    python -m max_pf wserh14rmbbpqtcg
    python -m max_pf wserh14rmbbpqtcg --periods 1-6 --out reports/half1
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .report import render_csv, render_markdown, render_table, season_report


def parse_periods(spec: str | None) -> list[int] | None:
    """Parse ``"3-6"``, ``"1,2,5"``, or ``None`` (-> all periods)."""
    if not spec:
        return None
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="max_pf", description="9-cat max-points-for season report")
    parser.add_argument("league_id", help="Fantrax league id")
    parser.add_argument("--periods", help='e.g. "1-6" or "1,2,5"; default: all', default=None)
    parser.add_argument("--out", default="season_report", help="output path prefix (writes .csv and .md)")
    parser.add_argument("--methodology", choices=["expected", "hindsight"], default="expected",
                        help="expected = season-to-date projections; hindsight = realized box scores")
    args = parser.parse_args(argv)

    from .platforms.fantrax import FantraxPlatform  # imported here so --help works without the extra

    platform = FantraxPlatform(args.league_id)
    if args.methodology == "hindsight":
        from .box_bref import BRefClient

        platform.use_boxscores(BRefClient())
    slots = platform.active_slots()
    rows = season_report(platform, slots, periods=parse_periods(args.periods), methodology=args.methodology)

    print(render_table(rows))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = out.with_suffix(".csv"), out.with_suffix(".md")
    csv_path.write_text(render_csv(rows))
    md_path.write_text("# Max Points For — Season Report\n\n" + render_markdown(rows) + "\n")
    print(f"\nwrote {csv_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
