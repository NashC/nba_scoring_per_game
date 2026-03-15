# nba_scoring_per_game

Event-level NBA player scoring pipeline built on official NBA play-by-play data via `nba_api`.

## What it produces

- Raw scoring events: one row per made free throw, 2-point field goal, or 3-point field goal
- Chart-ready player timelines: cumulative scoring over forward-moving game time
- Player-game summaries: ranking/filtering metrics for historic scoring games and competitiveness context
- Batch season backfills with validation-gated Parquet outputs

## Important source findings

- `PlayByPlayV3.pointsTotal` is the running game total after the event, not the event-level points scored
- `PlayByPlayV3.actionNumber` is not a safe chronological sort key by itself
- `PlayByPlayV3.actionId` is monotonic and is used as the ordering tiebreaker
- `scoreHome` and `scoreAway` behave like the post-event game score on scoring rows

## Quick start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python scripts/demo_pipeline.py
```

## CLI

Inspect one game:

```bash
.venv/bin/nba-scoring-per-game inspect-game --game-id 0020500591
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

Query summaries:

```bash
.venv/bin/nba-scoring-per-game query-summaries \
  --out-dir data \
  --min-points 60 \
  --min-pct-within-10 0.7
```

## Package layout

- [`source.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/source.py)
- [`transforms.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/transforms.py)
- [`validation.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/validation.py)
- [`pipeline.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/pipeline.py)
- [`cli.py`](/Users/nash/Documents/coding_projects/nba_scoring_per_game/src/nba_scoring_per_game/cli.py)

## Output layout

Curated outputs are written under `data/`:

- `raw_playbyplay_cache/season=<season>/season_type=<season_type>/game_id=<game_id>.parquet`
- `raw_scoring_events/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_scoring_timelines/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_game_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `validation_reports/run_date=<YYYY-MM-DD>/part-<game_id>.parquet`
- `processing_manifest/run_date=<YYYY-MM-DD>.parquet`

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Live integration tests are opt-in:

```bash
NBA_API_LIVE_TESTS=1 PYTHONPATH=src .venv/bin/python -m unittest tests.test_live_integration
```
