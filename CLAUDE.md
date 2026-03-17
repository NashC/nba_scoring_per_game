# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Event-level NBA player scoring pipeline and local Dash explorer app. Fetches official play-by-play data via `nba_api`, validates against box scores, and produces Parquet datasets for scoring timelines, summaries, quarter/half/burst analytics. The Dash app ("Heat Check") is a read-only explorer for leaderboards, comparisons, and trajectory charts.

## Commands

```bash
# Install (editable)
.venv/bin/python -m pip install -e .

# Run all tests
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests

# Run a single test file
PYTHONPATH=src .venv/bin/python -m unittest tests.test_transforms

# Run a single test method
PYTHONPATH=src .venv/bin/python -m unittest tests.test_transforms.TestTransforms.test_some_method

# Coverage
.venv/bin/python -m pip install --no-build-isolation -e '.[test]'
PYTHONPATH=src .venv/bin/python -m coverage run -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m coverage report -m

# Live integration tests (calls NBA API — opt-in)
NBA_API_LIVE_TESTS=1 PYTHONPATH=src .venv/bin/python -m unittest tests.test_live_integration

# Demo pipeline smoke test
PYTHONPATH=src .venv/bin/python scripts/demo_pipeline.py

# Launch dashboard
.venv/bin/nba-scoring-per-game serve-app --out-dir data
```

## Architecture

The pipeline follows a strict `source → transform → validate → write` flow:

- **`source.py`** — Thin wrappers around `nba_api` endpoints (PlayByPlayV3, BoxScoreTraditionalV3, LeagueGameLog). Returns raw DataFrames.
- **`transforms.py`** — Pure-function transforms: `extract_scoring_events` → `build_player_scoring_timeline` → `summarize_player_games/quarters/halves/bursts`. Also produces normalized time, shot mix, burst windows, projected pace, and competitiveness fields.
- **`validation.py`** — Validates processed games against box score totals. Games that fail validation are excluded from curated datasets but logged in the processing manifest.
- **`pipeline.py`** — Orchestrates the full flow: fetch → transform → validate → write Parquet partitioned by `season/season_type/game_id`. Manages `dataset_metadata.json` (schema version contract) and the processing manifest.
- **`cli.py`** — argparse CLI with subcommands: `inspect-game`, `process-game`, `backfill-season`, `query-summaries`, `describe-datasets`, `serve-app`.
- **`manual_games.py`** — Pre-play-by-play-era approximations (e.g., Wilt's 100-point game) seeded during backfill.

### Dashboard (`dashboard/`)

Single-page Dash app with Plotly charts. Key modules:

- **`app.py`** — Dash app factory and all callbacks. URL query-string persistence for filters and comparison state.
- **`loader.py`** — Reads Parquet summary datasets eagerly; loads timelines lazily per selected comparison set.
- **`state.py`** — Filter normalization, preset logic, leaderboard building, dashboard state encode/decode.
- **`layout.py`** — Dash component trees for leaderboard, comparison tray, detail cards, chart strips.
- **`charts.py`** — Plotly figure builders for trajectory, secondary analysis (burst/pace), and empty states.
- **`branding.py`** / **`team_logos.py`** — Logo rendering helpers. LiveLogo3D uses Canvas2D via Dash assets (no JS bundler).

## Key Domain Conventions

- **`point_value`** is the canonical scoring field (not `pointsTotal`, which is a running game total).
- **`actionId`** is the canonical event ordering tiebreaker (not `actionNumber`).
- **`scoreHome`/`scoreAway`** are post-event game scores on scoring rows.
- Curated outputs are only written for games that pass validation. Failed games stay in the processing manifest.
- Parquet outputs are Hive-partitioned under `data/` by `season=<season>/season_type=<season_type>/`.
- `dataset_metadata.json` is the schema version contract — the dashboard checks it before loading.
- Schema version is in `pipeline.py` as `DATASET_SCHEMA_VERSION`.

## Testing Notes

- Tests use `unittest` (not pytest). Shared fixtures live in `tests/fixtures.py`.
- Live tests (`test_live_integration.py`, `test_live_logo.py`) require `NBA_API_LIVE_TESTS=1` env var.
- `PYTHONPATH=src` is required for all test invocations since the package is under `src/`.
