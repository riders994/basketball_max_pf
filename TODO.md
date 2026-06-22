# TODO — open roadmap items

Tracked work beyond the 1.0.0 release. See `docs/PROMPT_LOG.md` for the full
design history and `CHANGELOG.md` for what shipped.

## Next release round

- [ ] **Regenerate the season report artifacts** for the `Luck = Actual − M3`
      redefinition. The committed `season_report.{txt,csv,md}` still carry the old
      `Actual − M1` Luck column; regenerate on the box-score default path and
      re-commit. (Needs a live Fantrax + basketball-reference run.)
- [x] **Regenerate the season report artifacts** on the box-score default and
      re-commit them. Done in 1.1.0: `season_report.{txt,csv,md}` regenerated with
      the full Nash picture (M3 / M1-M3), replacing the stale Fantrax-estimator
      files the 1.0.0 release had removed.
- [x] **Nash mutual ceiling, stage 2.** Mixed-strategy / minimax *value* via a
      double-oracle LP for matchup periods where iterated best response cycles (no
      pure equilibrium). Done: `engine._double_oracle` + `nash_lp.solve_zero_sum_game`
      (scipy `linprog`); `NashResult` now carries `value` / `equilibrium` /
      `mine_mix` / `theirs_mix`. Added numpy + scipy as dependencies.
- [x] **Wire Nash M3 into the report.** Done: `M3` and `M1-M3` columns on by
      default (the full picture every time) via `season_report(...)` / `run(...)` /
      `max-pf`; opt out with `include_nash=False` / `nash=False` / `--no-nash`.
      Renderers are now column-driven (`report._Column`).

## Packaging / infra

- [ ] **Replace the vendored fantraxapi with a real dependency** once a published
      `fantraxapi` (PyPI, with maintainer access) is available. Swap
      `src/max_pf/_vendor/fantraxapi` for a versioned `>=` dep; refresh steps are
      in `src/max_pf/_vendor/NOTICE.md`.
- [ ] **CI** (GitHub Actions): run `pytest` and a vendored-import
      self-containment check (import with no top-level `fantraxapi` installed) on
      pushes/PRs.
- [ ] *(Optional)* Prune the vendored fantraxapi to just the modules the adapter
      uses (trades / trade blocks / standings are unused), trading a slightly
      smaller footprint for more effort at each fork refresh.

## Methodology / scope

- [ ] **Additional platforms** behind the `LeaguePlatform` interface (beyond
      Fantrax) via the `register_platform` hook.
