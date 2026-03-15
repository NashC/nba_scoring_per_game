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
- quick-view buttons that map directly to the preset system
- URL-persisted filters and comparison selections
- local saved comparison bundles backed by browser storage
- richer mode-aware leaderboard columns with efficiency, burden, and active-metric highlighting
- richer detail cards with final score, efficiency, burden, and burst summaries
- period-aware hover formatting for quarter, half, and burst views
- keyboard-friendly comparison tray controls with remove-last and clear-all actions
- stronger filtered-empty guidance for incompatible control combinations
- detail badges for pace benchmarks and best-burst windows
- leaderboard CSV export and chart-image export through Plotly
- in-memory caching for filtered leaderboard slices
- a benchmark script for dashboard startup and summary filtering

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

### Phase 7: deeper exploration and data density

- add secondary leaderboard tabs or segmented leaderboard panes without leaving the current page
- add optional compare-by metric chips that swap the active ranking without opening the filter bar
- expose more compact burst metadata directly in the leaderboard, such as start period/clock
- add lightweight “saved bundle preview” metadata so users can see what a bundle contains before loading it

### Backend and performance follow-up

- keep monitoring the benchmark thresholds for a persisted summary index
- consider caching already-sliced entity timelines in memory if comparison loads become heavier on large local datasets
- extend the benchmark script with selectable scenario profiles once larger datasets are available

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
