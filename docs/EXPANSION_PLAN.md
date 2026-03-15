# Phase 2 Plan: Analytics and Comparison Expansion for the NBA Scoring Trajectory System

## Summary

- Extend the current pipeline in this repo and define the app-layer work needed in the existing scoring trajectory app; do not redesign the core chart or create a separate system.
- Keep the current player-game event and timeline flow as the base, then add quarter-, half-, and burst-level derived datasets plus UI modes that consume them.
- The current workspace contains the backend only; app-specific work from this plan is an integration contract for the separate app codebase.

## Key Changes

### Data and pipeline

- Keep `raw_scoring_events` and `player_scoring_timelines` as canonical event-level outputs and extend timelines with normalized game/quarter/half time, scorer-perspective score-differential context, cumulative shot-component fields, and `projected_48`.
- Extend `player_game_summaries` with shot-mix totals and shares, `points_per_minute`, `offensive_share`, `competitive_points`, `competitive_scoring_share`, `trailing_points`, `trailing_scoring_rate`, `peak_projected_48`, `best_60_sec_points`, `best_2_min_points`, `best_3_min_points`, `best_5_min_points`, `best_10_min_points`, `best_quarter_points`, `best_half_points`, `ts_pct`, and `efg_pct`.
- Add `player_quarter_summaries`, `player_half_summaries`, and `player_burst_summaries` as new curated outputs for quarter, half, and burst rankings.
- Precompute fixed burst windows of `60`, `120`, `180`, `300`, and `600` seconds so the app does not need to scan windows client-side.

### App behavior and UX

- Keep the existing cumulative scoring line chart as the default full-game view and add optional scoring-event markers colored by `scoring_type`.
- Add a line or context color mode driven by score-differential buckets so the chart distinguishes trailing, close, and blowout scoring.
- Expand tooltips to show player, opponent, date/season, period, game minute, cumulative points, event points, shot type, score after play, score differential, and projected pace.
- Add comparison modes for `full game`, `quarter`, `half`, and `burst`, plus `raw` vs `normalized` time toggles.
- Add leaderboard views that rank by total points, scoring rate, burst metrics, quarter and half peaks, offensive share, efficiency, and projected pace.
- Add a detail panel that summarizes the selected game, quarter, half, or burst interval.

### Data loading and integration

- Keep expensive feature engineering in the backend: the app should load summary tables for leaderboards and filters first, then request event-level timelines only for selected comparisons.
- Reuse a single comparison model keyed by entity grain plus interval metadata so games, quarters, halves, and bursts can share chart, tooltip, and detail-panel patterns.
- Add schema and version checks between parquet outputs and app-side data adapters so contract changes fail loudly.

## Public Interfaces

- `process_game(...)` now returns quarter, half, and burst summaries in addition to the existing outputs.
- `query_player_games(...)` now accepts `entity_mode`, `ranking_metric`, `competitive_only`, `include_ot`, and `burst_window` so one query path can serve multiple leaderboard grains.
- The CLI `query-summaries` command now supports `game`, `quarter`, `half`, and `burst` entity modes.

## Test Plan

- Backend unit tests cover normalized time math, cumulative shot-component fields, scorer-perspective context, `projected_48`, quarter and half summaries, burst windows, offensive share, and rate metrics.
- Integration tests validate that game-, quarter-, half-, and burst-level summaries reconcile to the underlying event timelines and official box-score totals.
- App-side tests, to be implemented in the app repo, should cover shot markers, context-color toggles, tooltip content, mode switching, normalized-time rendering, leaderboard sorting, and drill-down behavior.

## Assumptions and Defaults

- `PlayByPlayV3` remains the canonical event source.
- Default competitiveness logic is `abs(score_diff) <= 10`.
- Default burst windows are `60`, `120`, `180`, `300`, and `600` seconds.
- `ts_pct` and `efg_pct` are sourced from official box-score makes and attempts when available; they are left null rather than approximated from scoring events.
