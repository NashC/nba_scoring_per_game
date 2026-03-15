# Dataset Reference

This project materializes six curated datasets plus two operational outputs.

## Curated datasets

### `raw_scoring_events`

One row per made player scoring event.

Core columns:

- `season`
- `season_type`
- `game_date`
- `game_id`
- `action_number`
- `action_id`
- `player_id`
- `player_name`
- `team_id`
- `team_tricode`
- `period`
- `clock`
- `point_value`
- `is_field_goal`
- `score_home`
- `score_away`
- `action_type`
- `sub_type`
- `description`
- `location`

Rules:

- Includes made free throws, made 2-point field goals, and made 3-point field goals only.
- Sorted by `game_id`, then `action_id`.
- `point_value` is derived from score deltas, not from `pointsTotal`.

### `player_scoring_timelines`

One row per scoring event, enriched for plotting and competitiveness analysis.

Adds:

- `seconds_remaining_in_period`
- `period_duration_seconds`
- `quarter_time_elapsed`
- `quarter_time_normalized`
- `elapsed_seconds_in_game`
- `elapsed_minutes_in_game`
- `game_minute`
- `total_game_seconds`
- `total_game_minutes`
- `game_time_normalized`
- `half_index`
- `half_label`
- `half_time_elapsed`
- `half_time_normalized`
- `is_overtime`
- `player_game_cumulative_points`
- `player_game_final_points`
- `player_quarter_cumulative_points`
- `player_quarter_final_points`
- `player_half_cumulative_points`
- `player_half_final_points`
- `cumulative_2pt_points`
- `cumulative_3pt_points`
- `cumulative_ft_points`
- `player_team_score_after`
- `opponent_score_after`
- `player_team_margin_after`
- `abs_margin_after`
- `score_diff`
- `abs_score_diff`
- `is_competitive_moment`
- `margin_bucket`
- `scoring_type`
- `competitiveness_bucket`
- `projected_48`

Rules:

- Still event-level, not possession-level.
- `elapsed_seconds_in_game` is monotonic within a game by `action_id`.
- Margin fields are always from the scorer's team perspective.
- `projected_48` is null until at least one minute of game time has elapsed.

### `player_game_summaries`

One row per player-game.

Core columns:

- all identifying columns from the base summary grain
- `final_points`
- `num_scoring_events`
- `max_cumulative_points`
- `final_player_team_margin`
- `avg_margin_during_scoring_events`
- `median_margin_during_scoring_events`
- `avg_abs_margin_during_scoring_events`
- `median_abs_margin_during_scoring_events`
- `pct_scoring_events_within_3`
- `pct_scoring_events_within_5`
- `pct_scoring_events_within_10`
- `max_lead_during_scoring_events`
- `max_deficit_during_scoring_events`
- `points_from_2s`
- `points_from_3s`
- `points_from_fts`
- `share_points_from_2s`
- `share_points_from_3s`
- `share_points_from_fts`
- `minutes_played`
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
- `ts_pct`
- `efg_pct`
- `went_to_overtime`
- `total_game_minutes`

Rules:

- `final_player_team_margin` comes from the final game score.
- `max_deficit_during_scoring_events` is stored as a positive magnitude.
- `points_per_minute` and `trailing_scoring_rate` use official box-score minutes when available.

### `player_quarter_summaries`

One row per player-quarter.

Columns:

- identifying columns through `team_tricode`
- `quarter_number`
- `quarter_label`
- `is_overtime_quarter`
- `quarter_points`
- `num_scoring_events`
- `quarter_duration_minutes`
- `points_per_minute`
- `interval_start_seconds_in_game`
- `interval_end_seconds_in_game`
- `avg_margin_during_scoring_events`
- `median_margin_during_scoring_events`
- `avg_abs_margin_during_scoring_events`
- `median_abs_margin_during_scoring_events`
- `competitive_points`
- `competitive_scoring_share`
- `points_from_2s`
- `points_from_3s`
- `points_from_fts`
- `share_points_from_2s`
- `share_points_from_3s`
- `share_points_from_fts`

### `player_half_summaries`

One row per player-half for regulation halves only.

Columns:

- identifying columns through `team_tricode`
- `half_index`
- `half_label`
- `half_points`
- `num_scoring_events`
- `half_duration_minutes`
- `points_per_minute`
- `interval_start_seconds_in_game`
- `interval_end_seconds_in_game`
- `avg_margin_during_scoring_events`
- `median_margin_during_scoring_events`
- `avg_abs_margin_during_scoring_events`
- `median_abs_margin_during_scoring_events`
- `competitive_points`
- `competitive_scoring_share`
- `points_from_2s`
- `points_from_3s`
- `points_from_fts`
- `share_points_from_2s`
- `share_points_from_3s`
- `share_points_from_fts`

### `player_burst_summaries`

One row per player-game per precomputed burst window.

Columns:

- identifying columns through `team_tricode`
- `burst_window_seconds`
- `burst_window_label`
- `points_in_window`
- `num_scoring_events`
- `window_start_seconds_in_game`
- `window_end_seconds_in_game`
- `start_period`
- `start_clock`
- `end_period`
- `end_clock`
- `includes_overtime`
- `window_points_per_minute`
- `avg_score_diff_in_window`
- `median_score_diff_in_window`
- `avg_abs_score_diff_in_window`
- `competitive_points_in_window`
- `competitive_scoring_share`
- `trailing_points_in_window`
- `points_from_2s`
- `points_from_3s`
- `points_from_fts`
- `share_points_from_2s`
- `share_points_from_3s`
- `share_points_from_fts`

Rules:

- The current fixed windows are `60`, `120`, `180`, `300`, and `600` seconds.
- Each row represents the best scoring window of that size for that player-game.

## Operational outputs

### `validation_reports`

One row per processed game, written for every processing attempt.

Important fields:

- `game_id`
- `season`
- `season_type`
- `game_date`
- `num_scoring_events`
- `points_total_matches_running_score`
- `source_is_field_goal_consistent`
- `free_throw_point_values_all_one`
- `missing_scoring_identity_count`
- `action_number_is_monotonic`
- `action_id_is_monotonic`
- `action_number_duplicate_count`
- `scoring_action_id_duplicate_count`
- `multiple_scoring_events_same_clock`
- `home_margin_check_passed`
- `away_margin_check_passed`
- `num_player_total_mismatches`
- `final_score_matches_boxscore`
- `validation_passed`

`validation_passed` is the gating field for curated dataset publication.

### `processing_manifest`

One row per attempted game per run.

Important fields:

- `run_date`
- `processed_at`
- `season`
- `season_type`
- `game_date`
- `game_id`
- `status`
- `skipped_existing`
- `error_type`
- `error_message`
- `num_scoring_events`
- `validation_passed`

Typical status values:

- `success`
- `network_error`
- `transform_error`
- `validation_error`
- `write_error`

## Output layout

Outputs are written under `data/`:

- `raw_playbyplay_cache/season=<season>/season_type=<season_type>/game_id=<game_id>.parquet`
- `raw_scoring_events/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_scoring_timelines/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_game_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_quarter_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_half_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `player_burst_summaries/season=<season>/season_type=<season_type>/part-<game_id>.parquet`
- `validation_reports/run_date=<YYYY-MM-DD>/part-<game_id>.parquet`
- `processing_manifest/run_date=<YYYY-MM-DD>.parquet`

## Coverage rule

The curated datasets are coverage-limited:

- A game is included only if official play-by-play exists.
- A game is included only if the extracted scoring data passes validation.
- Historical ranking queries therefore operate on covered games only.
