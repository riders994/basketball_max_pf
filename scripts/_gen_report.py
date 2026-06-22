"""One-off driver: generate the season report artifacts (the full Nash picture).

Run from the repo root: PYTHONPATH=src python3 scripts/_gen_report.py [--no-nash]
Writes season_report.{txt,csv,md}. Not part of the package.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, "src")
import max_pf

LEAGUE = "wserh14rmbbpqtcg"  # public finished league used for validation
nash = "--no-nash" not in sys.argv
prefix = "season_report"

t0 = time.perf_counter()
rows = max_pf.run({"platform": "fantrax", "league_id": LEAGUE}, nash=nash)  # expected + boxscores
elapsed = time.perf_counter() - t0

table = max_pf.render_table(rows)
Path(f"{prefix}.txt").write_text(table + "\n")
Path(f"{prefix}.csv").write_text(max_pf.render_csv(rows))
Path(f"{prefix}.md").write_text(
    "# Max Points For — Season Report\n\n" + max_pf.render_markdown(rows) + "\n"
)
print(table)
print(f"\n[done in {elapsed:.0f}s] wrote {prefix}.txt/.csv/.md for {len(rows)} teams")
