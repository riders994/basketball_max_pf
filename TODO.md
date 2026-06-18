# TODO — open roadmap items

Tracked work beyond the 1.0.0 release. See `docs/PROMPT_LOG.md` for the full
design history and `CHANGELOG.md` for what shipped.

## Next release round

- [ ] **Regenerate the season report artifacts** on the box-score default and
      re-commit them. The 1.0.0 release removed the previous `season_report.*`
      files because they were generated on the old Fantrax-estimator path
      (pre-dating exact A-expected on box scores) and were stale.
- [ ] **Nash mutual ceiling, stage 2.** Mixed-strategy / minimax *value* via a
      double-oracle LP for the ~20% of matchup periods where iterated best
      response cycles (no pure equilibrium). Adds an LP dependency + a
      payoff-matrix builder.
- [ ] **Wire Nash M3 into the report.** Surface the mutual-ceiling split (and the
      `M1 − M3` decomposition) as columns in the CSV/Markdown season report.

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
