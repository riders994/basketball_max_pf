"""Command-line season report: ``python -m max_pf <login-file>``.

The login file is a JSON or YAML mapping naming the platform and its details::

    {"platform": "fantrax", "league_id": "wserh14rmbbpqtcg"}

Computes the max-points-for season summary for every team, prints it, and writes
``<out>.csv`` and ``<out>.md``.

    python -m max_pf league.json
    python -m max_pf league.yaml --weeks 1-6 --out reports/half1
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .app import load_login, run
from .report import render_csv, render_markdown, render_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="max_pf", description="9-cat max-points-for season report")
    parser.add_argument("login", help="path to a JSON or YAML login file (platform + details)")
    parser.add_argument("--weeks", default=None,
                        help='one week or a selection, e.g. "5", "1-6", "1,2,5"; default: season to date')
    parser.add_argument("--out", default="season_report", help="output path prefix (writes .csv and .md)")
    parser.add_argument("--methodology", choices=["expected", "hindsight"], default="expected",
                        help="expected = season-to-date box-score projections; "
                             "hindsight = realized box scores (both use basketball-reference)")
    parser.add_argument("--objective", choices=["catwins", "zscore", "raw"], default="catwins",
                        help="catwins = Objective A (opponent-aware category wins); "
                             "zscore = Objective B (max total z-value lineup); "
                             "raw = Objective C (max raw output lineup)")
    parser.add_argument("--no-boxscores", action="store_true",
                        help="use the platform's built-in estimator instead of box scores (expected only)")
    args = parser.parse_args(argv)

    login = load_login(args.login)
    rows = run(
        login, weeks=args.weeks, methodology=args.methodology,
        objective=args.objective, boxscores=not args.no_boxscores,
    )

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
