# nba_scoring_per_game

Event-level NBA player scoring pipeline and local Dash explorer app built on official NBA play-by-play data via `nba_api`.

## Product goal

Build a reliable event-level scoring dataset for NBA games that supports:

- cumulative player scoring progression over game time
- score differential and competitiveness context from the scorer's perspective
- ranking and filtering historically great scoring games
- quarter, half, and burst analysis for all-time scoring explosions

The pipeline is source-first and validation-heavy. It only publishes curated outputs for games that pass validation.

## What it produces

- Raw scoring events: one row per made free throw, 2-point field goal, or 3-point field goal
- Chart-ready player timelines: cumulative scoring over forward-moving game time with normalized-time, shot-mix, and competitiveness fields
- Player-game summaries: ranking/filtering metrics for historic scoring games, burst metrics, offensive burden, and shot mix
- Player-quarter summaries: ranking/filtering metrics for best quarters ever
- Player-half summaries: ranking/filtering metrics for first-half and second-half explosions
- Player-burst summaries: best `60/120/180/300/600` second windows per player-game
- Batch season backfills with validation-gated Parquet outputs
- Local scoring explorer app for leaderboards, comparisons, and trajectory views

## Important source findings

- `PlayByPlayV3.pointsTotal` is the running game total after the event, not the event-level points scored
- `PlayByPlayV3.actionNumber` is not a safe chronological sort key by itself
- `PlayByPlayV3.actionId` is monotonic and is used as the ordering tiebreaker
- `scoreHome` and `scoreAway` behave like the post-event game score on scoring rows

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

If editable install fails because `setuptools` is missing in the virtualenv, install it once:

```bash
.venv/bin/python -m pip install setuptools
.venv/bin/python -m pip install -e . --no-build-isolation
```

## Quick start

Smoke-test the package and inspect the current implementation behavior:

```bash
PYTHONPATH=src .venv/bin/python scripts/demo_pipeline.py
```

Launch the interactive explorer against local parquet outputs:

```bash
.venv/bin/nba-scoring-per-game serve-app --out-dir data
```

## Live logo notes

The Dash explorer now includes a procedural `LiveLogo3D` brand mark rendered entirely in-browser with the asset pipeline already used by Dash.

- Architecture: the Python helper returns a normal Dash `html.Div` tree with `data-*` hooks, a canvas node, and a static HTML/CSS fallback. A single asset script initializes instances, survives Dash rerenders, and pauses offscreen or hidden-tab logos.
- Why Canvas2D: this repo has no JS bundler or React layer. Canvas2D keeps the implementation asset-free, lightweight, and production-safe inside Dash while still supporting layered fire, embers, controlled glow, and responsive sizing.
- Performance: the renderer caps device pixel ratio, keeps ember counts fixed, avoids free-running particle spawning, and disables animation when reduced motion is requested or the logo is offscreen.
- Reduced motion: `prefers-reduced-motion` renders a still frame by default. The Dash helper also supports an explicit override for always-static or always-animated rendering.
- Fallback: if JS, canvas, or observer APIs are unavailable, the static fallback remains visible so the app still shows a deliberate branded mark instead of a blank box.
- Future upgrade path: if the app later adopts a bundled JS frontend, the same Dash-side API can be preserved while swapping the asset script for a WebGL or React-driven renderer behind the same DOM contract.

## Typical workflow

1. Inspect one game to confirm the raw source shape.
2. Process one known game end to end.
3. Backfill a season.
4. Query the summary datasets without calling the API again.

## CLI

Inspect one game:

```bash
.venv/bin/nba-scoring-per-game inspect-game --game-id 0020500591
```

Describe the current dataset contract:

```bash
.venv/bin/nba-scoring-per-game describe-datasets --out-dir data
```

Process one game:

```bash
.venv/bin/nba-scoring-per-game process-game \
  --game-id 0020500591 \
  --season 2005-06 \
  --season-type "Regular Season" \
  --out-dir data
```

Backfill one season:

```bash
.venv/bin/nba-scoring-per-game backfill-season \
  --season 2023-24 \
  --season-type "Regular Season" \
  --out-dir data
```

`backfill-season` also seeds the supported legacy manual approximations into the target out-dir, so manually reconstructed games such as Wilt Chamberlain's 100-point game stay available after fresh rebuilds.

Backfill only games where at least one player reached a point threshold:

```bash
.venv/bin/nba-scoring-per-game backfill-season \
  --season 2023-24 \
  --season-type "Regular Season" \
  --min-player-points 30 \
  --out-dir data
```

Query top high-scoring games:

```bash
.venv/bin/nba-scoring-per-game query-summaries \
  --out-dir data \
  --entity-mode game \
  --min-points 60 \
  --ranking-metric total_points
```

Rank high-scoring games by competitiveness instead of only points:

```bash
.venv/bin/nba-scoring-per-game query-summaries \
  --out-dir data \
  --entity-mode game \
  --min-points 60 \
  --ranking-metric avg_abs_margin_during_scoring_events \
  --descending false
```

Query best quarters ever:

```bash
.venv/bin/nba-scoring-per-game query-summaries \
  --out-dir data \
  --entity-mode quarter \
  --min-points 25 \
  --ranking-metric quarter_points
```

Query best 3-minute bursts in competitive, non-OT games:

```bash
.venv/bin/nba-scoring-per-game query-summaries \
  --out-dir data \
  --entity-mode burst \
  --burst-window 180 \
  --min-competitive-share 0.75 \
  --include-ot false \
  --ranking-metric points_in_window
```

Run the local explorer app:

```bash
.venv/bin/nba-scoring-per-game serve-app \
  --out-dir data \
  --host 127.0.0.1 \
  --port 8050
```

The app is read-only in v1. It loads local parquet outputs and `dataset_metadata.json`, validates the published schema version, eagerly loads summary tables, and lazily loads `player_scoring_timelines` only for the active comparison set.

Phase 4 app features now include:

- a synchronized secondary analysis panel for rolling burst intensity and projected pace
- query-driven presets such as `70+ games`, `best quarters`, and `competitive 60+ games`
- quick-view buttons for top games, best quarters/halves, bursts, and competitive high-scoring games
- URL query-string persistence for filters and comparison selections
- leaderboard CSV export and chart image export through the Plotly modebar
- richer leaderboard columns with efficiency, burden, and active-metric highlighting
- richer game detail cards with final score context, efficiency, burden, shot mix, and burst metrics
- period-aware hover context for quarter, half, and burst views
- stronger filtered-empty guidance and keyboard-friendly comparison tray controls
- detail badges for pace benchmarks and top burst windows
- saved comparison bundles backed by local browser storage

Benchmark the dashboard data path:

```bash
PYTHONPATH=src .venv/bin/python scripts/benchmark_dashboard.py --out-dir data
```

Threshold note:

- if dashboard summary loading exceeds `2.5s` on at least `100k` summary rows, add a summary index next phase
- if median summary filtering exceeds `250ms` over `20` runs, add `.dashboard_cache/summary_index.parquet` next phase

## Legacy pre-1996 games

The official event-level pipeline is still anchored to the post-1996 play-by-play era, but the repo now also tracks a seed catalog of important pre-1996 scoring games for manual reconstruction work:

- [Legacy games catalog guide](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/LEGACY_GAMES.md)
- [Legacy game catalog CSV](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/legacy_game_catalog.csv)
- [Legacy split evidence CSV](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/legacy_split_catalog.csv)

Wilt Chamberlain's 100-point game is already included locally as an explicitly labeled manual approximation built from published quarter splits.

## Phase 2 analytics

The timeline dataset now includes:

- normalized game progress for regulation and OT games
- quarter and half elapsed/normalized time
- cumulative points from `2PT`, `3PT`, and `FT`
- score-differential buckets for chart context coloring
- projected 48-point pace with an early-game noise guard
- matchup context fields so app consumers do not need a separate manifest join

The game summary dataset now includes:

- shot-mix totals and shares
- `points_per_minute`
- `offensive_share`
- `competitive_points`
- `competitive_scoring_share`
- `trailing_points`
- `trailing_scoring_rate`
- `peak_projected_48`
- `best_60_sec_points`
- `best_2_min_points`
- `best_3_min_points`
- `best_5_min_points`
- `best_10_min_points`
- `best_quarter_points`
- `best_half_points`
- `final_player_team_score`
- `final_opponent_score`
- `ts_pct`
- `efg_pct`

The repo also exposes thin selection helpers for app consumers:

- `build_quarter_timeline(...)`
- `build_half_timeline(...)`
- `build_burst_timeline(...)`

The repo now also includes a Dash app package under [`dashboard/`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/app.py) with:

- summary-table loading and schema checks
- a leaderboard-driven comparison workflow with quick views and active-metric highlighting
- full-game, quarter, half, and burst chart modes
- optional shot markers and margin-context coloring
- a secondary analysis panel for rolling burst windows and projected pace
- URL-persisted dashboard state and preset filters
- local saved bundles that restore a dashboard view from browser storage
- an in-app "How to Use This Explorer" guide for quick views, ranking, saved bundles, and chart modes
- rich detail cards for the current selection set

## Validation behavior

Each processed game gets a validation report. Curated outputs are written only when the game passes validation.

The main validation checks include:

- final play-by-play score matches the official box score
- summed player scoring events match official player point totals
- `pointsTotal` matches the running game total
- free throws resolve to `point_value == 1`
- scorer identity fields are present
- scorer-perspective margin math is correct for both home and away players

If a game fails validation or official play-by-play is unavailable, the game is retained in the processing manifest but excluded from curated datasets.

## Package layout

- [`source.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/source.py)
- [`transforms.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/transforms.py)
- [`validation.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/validation.py)
- [`pipeline.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/pipeline.py)
- [`cli.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/cli.py)
- [`dashboard/app.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/app.py)
- [`dashboard/charts.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/charts.py)
- [`dashboard/layout.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/layout.py)
- [`dashboard/loader.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/loader.py)
- [`dashboard/state.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/dashboard/state.py)

## Output layout

Curated outputs are written under `data/`:

- `dataset_metadata.json`
- `raw_playbyplay_cache/season=<season>/season_type=<season_type>/game_id=<game_id>.parquet`
- `raw_scoring_events/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_scoring_timelines/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_game_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_quarter_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_half_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_burst_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `validation_reports/run_date=<YYYY-MM-DD>/part-<game_id>.parquet`
- `processing_manifest/run_date=<YYYY-MM-DD>.parquet`

`processing_manifest` is the authoritative log of what happened for each game in a run: success, skip, validation failure, transform failure, network failure, or write failure.

## Dataset reference

Detailed dataset schemas and processing-manifest fields live in [`docs/DATASETS.md`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/DATASETS.md).

The current app roadmap and remaining improvements live in [`docs/EXPANSION_PLAN.md`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/EXPANSION_PLAN.md).

## Coverage and limitations

- Historical analyses only cover games where official event-level play-by-play exists and validates cleanly.
- Older games such as Wilt Chamberlain's 100-point game are only included if the official source exposes compatible play-by-play.
- The batch pipeline is single-threaded in v1.
- Queries operate on local Parquet outputs; no database is required.
- `ts_pct` and `efg_pct` are sourced from official box score makes/attempts when available; they are left null if the upstream box score response does not expose the required fields.
- The explorer app in this repo is a single-page Dash app and is read-only in v1.
- `dataset_metadata.json` is the intended app-facing schema/version contract and should be checked before adapters load parquet outputs.

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Coverage reporting uses the optional test extra:

```bash
.venv/bin/python -m pip install --no-build-isolation -e '.[test]'
PYTHONPATH=src .venv/bin/python -m coverage run -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m coverage report -m
```

Live integration tests are opt-in:

```bash
NBA_API_LIVE_TESTS=1 PYTHONPATH=src .venv/bin/python -m unittest tests.test_live_integration
```

## Development notes

- `point_value` is the canonical scoring field.
- `actionId` is the canonical event ordering field.
- `actionNumber` is preserved for debugging but never used for chronology.
- The summary table's `final_player_team_margin` comes from the final game score, not the player's last scoring event.
- Burst metrics are precomputed in the backend so the app does not need to scan windows client-side.
