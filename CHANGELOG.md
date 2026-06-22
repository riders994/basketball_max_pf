# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Planned work is tracked in [TODO.md](TODO.md).

## [Unreleased]

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

[1.0.0]: https://github.com/riders994/basketball_max_pf/releases/tag/v1.0.0
