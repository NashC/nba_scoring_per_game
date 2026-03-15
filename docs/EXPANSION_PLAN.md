# Scoring Explorer Roadmap

## Current status

The repo now includes:

- the validated parquet-producing backend pipeline
- a single-page Dash + Plotly scoring explorer

Implemented in the app today:

- full-game, quarter, half, and burst comparison modes
- raw and normalized time views
- scoring-event markers by `scoring_type`
- margin-context line coloring with a visible `margin_bucket` legend
- a synchronized secondary analysis panel for:
  - rolling points in trailing windows
  - rolling points-per-minute in trailing windows
  - projected 48-minute pace
- query-driven presets
- URL-persisted filters and comparison selections
- richer detail cards with final score, efficiency, burden, and burst summaries
- leaderboard CSV export and chart-image export through Plotly

## Stable data/app contract

The app continues to treat these outputs as canonical:

- `raw_scoring_events`
- `player_scoring_timelines`
- `player_game_summaries`
- `player_quarter_summaries`
- `player_half_summaries`
- `player_burst_summaries`

Important semantics that remain fixed:

- `projected_48` stays null until one minute of game time has elapsed
- burst windows stay fixed at `60`, `120`, `180`, `300`, and `600` seconds
- `competitive_only` remains a strict alias for `competitive_scoring_share == 1.0`
- app-side era filtering is derived from season start decade at load time

## Highest-value next improvements

### Phase 5: refinement and usability

- add more polished period-aware hover formatting for quarter, half, and burst views
- improve comparison management with keyboard-friendly add/remove behavior
- add stronger filtered-empty messages and guidance for incompatible control combinations
- add optional annotations or badges for benchmark lines and best-burst windows in the detail area

### Phase 6: richer exploration surfaces

- add secondary leaderboard tabs or preset views for:
  - best quarters ever
  - best halves ever
  - best bursts ever
  - competitive high-scoring games
- expose `ts_pct`, `efg_pct`, and `offensive_share` more prominently in the leaderboard itself
- add saved comparison bundles built from filters and rankings rather than hardcoded player buttons

### Backend polish

- add a shared test-fixture module so pipeline and dashboard tests stop duplicating sample-game builders
- consider a lightweight summary index if parquet scans become expensive on larger local datasets
- consider caching already-sliced entity timelines in memory if comparison loads become heavier

## Acceptance targets from here

The app should continue to cleanly support:

- top 50 scoring games in history
- best quarters ever
- best halves ever
- best 3-minute, 5-minute, and 10-minute bursts
- `60+` point games filtered by `min_competitive_share`
- ranking by `offensive_share`, `ts_pct`, and `peak_projected_48`
- comparing shot-mix and competitiveness profiles across elite scoring performances

## Constraints

- keep the app read-only in v1
- keep parquet as the storage contract
- keep burst computation out of the UI
- preserve the single shared chart model instead of branching into separate mode-specific apps
