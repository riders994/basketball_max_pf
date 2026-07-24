# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Planned work is tracked in [TODO.md](TODO.md).

## [2.1.0] - 2026-07-24

### Added

- **A per-team progress bar on the command line.** The season report ticks a bar
  on stderr as each team's row is computed — handy because the Nash mutual-ceiling
  search makes a full run take a while. It's on by default but only draws when
  stderr is a terminal, so redirected or piped output is untouched; `--no-progress`
  suppresses it. The library stays terminal-agnostic: `season_report`/`run` take a
  `progress(completed, total)` callback (`max_pf.progress.bar_callback` supplies the
  bar), so programmatic callers can plug in their own reporter or none at all.

### Fixed

- **The season's opening matchup period is now skipped under the `expected`
  methodology.** "Expected" lineups are built from season-to-date rates as of the
  period start, so week 1 has no prior games to project from — every team's
  projected lineup collapsed to near-empty, producing degenerate, uniform
  M1/M2/M3 (an empty lineup draws all categories versus another empty lineup, and
  only "wins" TO versus a real one). That period is now excluded from `expected`
  reports, so its meaningless numbers no longer pollute the season totals. The
  `hindsight` methodology is unaffected (week 1's own realized box scores exist).
  Requesting *only* an unprojectable opening week under `expected` now raises a
  clear `ValueError` instead of returning an all-zero report. The check consults
  the league calendar, so it short-circuits before any box-score fetching.

## [2.0.0] - 2026-06-22

Major bump: the report's `Luck` column changes meaning and the `M1-M3` column /
`TeamSeason.m1_minus_m3` property are renamed — see **Changed** below.

### Changed

- **`Luck` is now `Actual − M3`** (was `Actual − M1`). Luck is measured against
  the both-optimal mutual ceiling — the equilibrium where both managers play
  intelligently — rather than against your own one-sided exploitation ceiling.
  Positive Luck means the team scored above that equilibrium (opponent passivity
  or a hot week); negative means it fell short of it. Because Luck now depends on
  M3, the column is **only shown alongside the Nash columns** (`include_nash`).
- **Renamed the `M1-M3` column to `Passivity`** (the opponent-passivity dividend);
  the `TeamSeason.m1_minus_m3` property is now `TeamSeason.passivity`.

### Added

- **`Potential` column (`Actual − M1`)** — the previous `Luck` definition, kept
  under a clearer name: realized result vs your exploitation ceiling (points left
  on the table against the opponent's actual play; ≤ 0 under hindsight). M1-only,
  so it appears in every report, including `--no-nash`.
- **`Anticipation` column (`M3 − M2`)** — the swing from the decoupled
  both-optimize estimate (M2, each side aimed at the other's *actual* lineup) to
  the true equilibrium (M3, where both anticipate the other optimizing). The
  value of mutual strategic anticipation; usually positive, not guaranteed.
  M3-relative, so shown with the Nash columns.

## [1.1.0] - 2026-06-22

### Added

- **Nash mutual ceiling, stage 2 (mixed-strategy value).** Matchup periods whose
  iterated best responses cycle (no pure-strategy equilibrium) are now resolved to
  their mixed-strategy minimax *value* via a double-oracle: `engine._double_oracle`
  grows restricted lineup sets with expected-catwins best responses (new
  `optimize.make_expected_catwins_objective`) and solves the restricted zero-sum
  game with `nash_lp.solve_zero_sum_game` (an exact LP solver over
  `scipy.optimize.linprog`). `NashResult` gains `value` (the mutual ceiling in
  category points for both pure and mixed periods), `equilibrium` (`"pure"` /
  `"mixed"`), and the `mine_mix` / `theirs_mix` equilibrium mixtures; `m3_pf` now
  returns `value`.
- **Nash M3 in the season report.** The report now carries two more columns by
  default — the full picture every time: **M3** (the mutual-ceiling score, summed)
  and **M1-M3** (the opponent-passivity dividend — how much of the exploitation
  ceiling relied on the opponent not also optimizing). Pass `nash=False` /
  `max-pf --no-nash` (or `season_report(..., include_nash=False)`) to skip the
  per-team mutual-ceiling search for a quicker M1/M2-only report. The three
  renderers are now column-driven, so the columns are defined in one place.

### Changed

- Added **numpy** and **scipy** as runtime dependencies (the stage-2 LP).
- `zscores.build_model` now computes the population mean/std with numpy
  (`statistics.fmean`/`pstdev` dropped), a single vectorized pass over the whole
  roster — the genuine population-scale numeric op.

### Performance

- Optimizer inner loop: `objective_catwins` and `make_expected_catwins_objective`
  no longer rebuild `category_values()` dicts redundantly. Each line's values are
  built once per evaluation (via new `metric.catwins_from_values`), and the fixed
  opponent mixture's values are hoisted out of the per-neighbor loop. ~1.3× faster
  on the double-oracle objective path, identical results. (numpy was deliberately
  *not* used for the 9-category comparisons — array overhead regresses on inputs
  that small; the win is eliminating redundant work.)

## [1.0.0] - 2026-06-18

First public release. Computes the "max points for" metric for 9-category
head-to-head fantasy basketball.

### Added

- **Metric & engine.** Opponent-relative category wins (ties = draws worth 0.5,
  turnovers inverted); one-round best response yielding **M1 / M2 / Δ** (the
  opponent-mismanagement dividend). FG%/FT% aggregated as Σmakes/Σattempts.
- **Two methodologies** behind a pluggable `StatSource`: **A-expected**
  (season-to-date projections) and **A-hindsight** (realized box scores).
- **Data sources.** Fantrax for league structure (the FantraxAPI fork, vendored
  under `max_pf._vendor` so installs need no VCS/URL dependency) and
  basketball-reference for exact per-player makes/attempts (disk-cached). Exact
  A-expected on box scores replaces the FG/FT attempt estimator (kept as a
  no-extra-dependency fallback).
- **Three lineup objectives.** A (`catwins`, opponent-aware category wins),
  B (`zscore`, scarcity-weighted z-value — benches below-replacement players to
  protect ratios/TO), C (`raw`, raw output / volume). All pluggable.
- **Nash mutual ceiling, stage 1.** `engine.nash_ceiling` runs iterated best
  response to a pure-strategy equilibrium (**M3**), with cycle detection for
  matchups with no pure equilibrium.
- **Entry point & CLI.** `max_pf.run(login, weeks=..., methodology=...,
  objective=...)` takes a platform login dict and returns the season report;
  `max-pf <login.json|yaml>` (also `python -m max_pf ...`) renders a table and
  writes CSV/Markdown. `weeks` scopes to one week or a selection.
- Installable package (`src/` layout, hatchling) with `boxscores` and `yaml`
  extras; 52 unit tests; live-validated against a finished public league.

[2.1.0]: https://github.com/riders994/basketball_max_pf/releases/tag/v2.1.0
[2.0.0]: https://github.com/riders994/basketball_max_pf/releases/tag/v2.0.0
[1.1.0]: https://github.com/riders994/basketball_max_pf/releases/tag/v1.1.0
[1.0.0]: https://github.com/riders994/basketball_max_pf/releases/tag/v1.0.0
