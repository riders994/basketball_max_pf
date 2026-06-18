# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Planned work is tracked in [TODO.md](TODO.md).

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
