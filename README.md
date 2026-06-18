# basketball_max_pf

A Python package for computing a **"max points for"** metric for a 9-category
head-to-head fantasy basketball league. Give it your league platform and a
league id and it reconstructs, for every team and every matchup period, the
best lineup you *could* have set — and turns the gap between that and reality
into a single interpretable number.

The first supported platform is **Fantrax**; the design keeps the platform,
the player-stat source, and the lineup objective behind seams so other sports
or platforms can be added later.

> Status: Objective A (opponent-aware category-win maximization) is implemented
> end-to-end and validated against a finished public league. See
> [Roadmap](#roadmap) for what's next, and
> [`docs/PROMPT_LOG.md`](docs/PROMPT_LOG.md) for the full design journal.

## The metric

"Points for" in this league *are* category wins — they only exist relative to
an opponent (a tie is a **draw**, worth 0.5; Fantrax awards ties, it does not
wash or split them). So the metric and the benchmark are one decision, not two.

For each matchup period we compute a one-round **best response** (each side
optimizes against the *other side's actual* lineup — a well-posed fixed target,
avoiding the Nash infinite regress):

| Quantity | Definition | Reads as |
| --- | --- | --- |
| **M1** | catwins(`mine_opt`, `opp_actual`) | your exploitation ceiling vs how they actually played |
| **M2** | catwins(`mine_opt`, `their_opt`) | the same lineup vs their best counter |
| **Δ** | M1 − M2 | the **opponent-mismanagement dividend** — points banked purely because the opponent didn't optimize |
| **Luck** | Actual − M1 | points left on the table (negative ⇒ you fell short of your own ceiling) |

FG% and FT% are aggregated correctly across a lineup via Σmakes / Σattempts
(never by averaging percentages); TO is treated as lower-is-better.

The best-response above is **Objective A** (the default, `--objective catwins`):
each side optimizes category wins against the other's *actual* lineup. The
optimizer's objective is pluggable, with two opponent-independent alternatives
that report catwins as a readout: **Objective B** (`--objective zscore`) maximizes
total **z-score value** (scarcity-weighted), and **Objective C** (`--objective raw`)
maximizes total **raw output** (scarcity-blind, volume-chasing). Both *bench
below-replacement (negative-value) players* — since value prices in FG%/FT%
volume-impact and turnovers, dropping them protects the ratio cats and TO that
swing a week (C, whose raw value is almost always positive, benches far less).
See [Roadmap](#roadmap).

## Two methodologies

The optimizer needs a target statline for each player. Where that comes from is
the **ex-ante vs ex-post** fork, and the package implements both:

- **A-expected** (`--methodology expected`) — season-to-date *per-game rates*
  placed on the days each player's team plays in the period. No clairvoyance;
  the ceiling is a projection. Rates come from exact basketball-reference
  box scores (real makes/attempts, no estimator); the Fantrax season-to-date
  view + position-based FG/FT attempt estimator is the no-extra-dependency
  fallback when box scores aren't attached. Its `Luck` mixes forecast variance
  with real mismanagement.
- **A-hindsight** (`--methodology hindsight`) — *realized* per-day box scores
  from basketball-reference, joined to the full historical roster. This is the
  true "best lineup you could have set" ceiling: **M1 ≥ Actual always**, so
  `Luck` is genuine lineup mismanagement with projection noise removed.

## Data sources

- **Fantrax** (via the [stable fork of FantraxAPI](https://github.com/riders994/FantraxAPI/releases/tag/stable))
  is the source of truth for league structure: rosters (incl. historical daily
  membership), active-slot config, matchup schedule, and **actual results**.
  Public leagues read with only the league id (no credentials).
- **basketball-reference** supplies exact per-player per-day 9-cat lines with
  real makes/attempts (FG%/FT% denominators Fantrax never exposes). Disk-cached
  under `.cache/bref/` at a polite request rate; `nba_api` is a drop-in for
  local runs where stats.nba.com is reachable.

These sit behind a pluggable `StatSource` seam, so the optimizer, engine, and
report are identical across methodologies.

## Install

```bash
pip install -e ".[fantrax,boxscores]"   # add 'dev' for the test suite
```

`fantrax` pulls the FantraxAPI fork at `@stable`; `boxscores` pulls
beautifulsoup4 for the basketball-reference source; `yaml` adds YAML login-file
support on the CLI (JSON works without it). (Per packaging convention, all
version specifiers are `>=` for compatibility.)

## Usage

**Programmatic** — pass a *login dict* naming the platform and its details; you
get back the season-to-date report rows (render with the `render_*` helpers):

```python
import max_pf

rows = max_pf.run({"platform": "fantrax", "league_id": "wserh14rmbbpqtcg"})
print(max_pf.render_table(rows))

# Scope to one week or a selection, and pick methodology / objective:
rows = max_pf.run(login, weeks="1-6", methodology="hindsight", objective="zscore")
rows = max_pf.run(login, weeks=6)            # a single week
```

`weeks` accepts a single int, a list, or a spec string (`"5"`, `"1-6"`,
`"1,2,5"`); `None` (the default) is the whole season to date. Box scores back
both methodologies by default; pass `boxscores=False` for the no-extra-dependency
Fantrax estimator (A-expected only).

**Command line** — point it at a JSON or YAML file holding the same login dict:

```bash
# league.json: {"platform": "fantrax", "league_id": "wserh14rmbbpqtcg"}
python -m max_pf league.json
python -m max_pf league.yaml --weeks 1-6 --methodology hindsight --out reports/half1
```

It prints the table and writes `<out>.csv` and `<out>.md`.

## Findings

Full-season run on the finished public league `wserh14rmbbpqtcg` ("Mao's Macho
Mandarins", 2025-26 NBA, 16 teams × 24 periods). Artifacts:
[`season_report.md`](season_report.md) (A-expected) and
[`season_report_hindsight.md`](season_report_hindsight.md) (A-hindsight).

- **The ceiling invariant holds under hindsight.** M1 ≥ Actual for every team
  in both reports; A-hindsight makes this a *guarantee* (realized data),
  whereas A-expected can't because a team that ran hot beats its projection.
- **Projections are optimistic.** A-expected M1 > A-hindsight M1 for 15 of 16
  teams (smooth per-game rates, no DNPs/variance). The lone exception is
  *Trusting the Process*, whose players out-ran their season rates in the games
  actually played.
- **Hindsight isolates real mismanagement.** With projection variance stripped,
  `Luck` magnitudes shrink (band −6.5…−60 vs expected −9.5…−66) — the Actual−M1
  gap becomes genuine points left on the table, not forecast noise.
- **The dividend Δ tightens to a credible band.** The expected spread (7–73)
  compresses to 11–35 under hindsight. The dbyun89 expected outlier (Δ=73,
  driven by an implausible expected M2=38) corrects to Δ=35 (M2=71), confirming
  it was a projection artifact rather than a real opponent giveaway.

**Takeaway:** A-hindsight is the trustworthy read for both the efficiency
ceiling (`Luck`) and the dividend (`Δ`); A-expected is the no-clairvoyance
projection useful before results are in.

## Roadmap

- Live re-validation against the updated `@stable` fork — **done** (results
  bit-identical to the pre-update fork; see the prompt log).
- Exact A-expected on box scores (estimator replaced as the metric's data
  source) — **done**; reproduces the estimator's category-win metric while using
  real makes/attempts and the real schedule. (The committed `season_report.*`
  artifact was generated on the earlier estimator path; regenerating it on box
  scores is the next full run.)
- Objective B (z-score / punt-aware weighting) — **done**. `--objective zscore`
  plays each side's opponent-independent max-total-z-value lineup (league-wide
  per-game population; volume-weighted ratio impact, TO inverted); catwins is a
  readout. Objective A's category-win M1 is >= Objective B's by construction.
- Objective C (raw statistical output) — **done**. `--objective raw` plays each
  side's max-raw-output lineup (same league-wide population as B, but values
  players without scarcity weighting, so it chases volume); opponent-independent,
  catwins as a readout.
- Nash "mutual ceiling" (two-player equilibrium): stage 1 done —
  `engine.nash_ceiling` runs iterated best response to the fixed point where each
  lineup best-responds to the other (pure-strategy Nash), yielding **M3** = the
  both-sides-optimal category split; it flags cycles (no pure equilibrium). On
  the test league it converges in ~80% of periods. Stage 2 (mixed-strategy /
  minimax value via double-oracle LP) would resolve the cycling periods.
- Nash "mutual ceiling" (two-player equilibrium) as an advanced methodology.

See [`docs/PROMPT_LOG.md`](docs/PROMPT_LOG.md) for the complete design history.
