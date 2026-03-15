from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from nba_scoring_per_game.dashboard import create_dashboard_app, load_dashboard_datasets, render_dashboard_view
from nba_scoring_per_game.dashboard.charts import (
    MARGIN_COLORS,
    build_rolling_analysis_series,
    build_secondary_analysis_figure,
    build_trajectory_figure,
)
from nba_scoring_per_game.dashboard.state import (
    DashboardFilters,
    apply_dashboard_preset,
    build_leaderboard_table,
    decode_dashboard_state,
    encode_dashboard_state,
    filter_summary_frame,
)
from nba_scoring_per_game.pipeline import DATASET_METADATA_FILENAME, DATASET_SCHEMA_VERSION, process_game


def make_manifest_row() -> dict[str, object]:
    return {
        "season": "2023-24",
        "season_type": "Regular Season",
        "game_id": "game-123",
        "game_date": "2024-01-01",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_tricode": "HOM",
        "away_team_tricode": "AWY",
    }


def make_raw_playbyplay() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gameId": "game-123",
                "actionNumber": 0,
                "actionId": 1,
                "teamId": 0,
                "teamTricode": "",
                "personId": 0,
                "playerName": "",
                "period": 1,
                "clock": "PT12M00.00S",
                "isFieldGoal": 0,
                "scoreHome": 0,
                "scoreAway": 0,
                "pointsTotal": 0,
                "location": "",
                "description": "Start of 1st Period",
                "actionType": "period",
                "subType": "start",
            },
            {
                "gameId": "game-123",
                "actionNumber": 1,
                "actionId": 10,
                "teamId": 1,
                "teamTricode": "HOM",
                "personId": 100,
                "playerName": "Home Scorer",
                "period": 1,
                "clock": "PT11M30.00S",
                "isFieldGoal": 1,
                "scoreHome": 2,
                "scoreAway": 0,
                "pointsTotal": 2,
                "location": "h",
                "description": "Home Scorer Jump Shot (2 PTS)",
                "actionType": "Made Shot",
                "subType": "Jump Shot",
            },
            {
                "gameId": "game-123",
                "actionNumber": 2,
                "actionId": 11,
                "teamId": 2,
                "teamTricode": "AWY",
                "personId": 200,
                "playerName": "Away Scorer",
                "period": 1,
                "clock": "PT11M00.00S",
                "isFieldGoal": 1,
                "scoreHome": 2,
                "scoreAway": 3,
                "pointsTotal": 5,
                "location": "v",
                "description": "Away Scorer 3PT Jump Shot (3 PTS)",
                "actionType": "Made Shot",
                "subType": "Jump Shot",
            },
            {
                "gameId": "game-123",
                "actionNumber": 3,
                "actionId": 12,
                "teamId": 1,
                "teamTricode": "HOM",
                "personId": 100,
                "playerName": "Home Scorer",
                "period": 2,
                "clock": "PT10M00.00S",
                "isFieldGoal": 0,
                "scoreHome": 3,
                "scoreAway": 3,
                "pointsTotal": 6,
                "location": "h",
                "description": "Home Scorer Free Throw 1 of 1",
                "actionType": "Free Throw",
                "subType": "Free Throw 1 of 1",
            },
            {
                "gameId": "game-123",
                "actionNumber": 4,
                "actionId": 13,
                "teamId": 2,
                "teamTricode": "AWY",
                "personId": 200,
                "playerName": "Away Scorer",
                "period": 4,
                "clock": "PT00M10.00S",
                "isFieldGoal": 1,
                "scoreHome": 3,
                "scoreAway": 5,
                "pointsTotal": 8,
                "location": "v",
                "description": "Away Scorer Layup",
                "actionType": "Made Shot",
                "subType": "Layup Shot",
            },
        ]
    )


def make_boxscore_totals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "game-123",
                "team_id": 1,
                "team_tricode": "HOM",
                "player_id": 100,
                "player_name_boxscore": "Home Scorer",
                "official_points": 3,
                "minutes_played_raw": "PT30M00.00S",
                "minutes_played": 30.0,
                "field_goals_made": 1,
                "field_goals_attempted": 1,
                "three_pointers_made": 0,
                "three_pointers_attempted": 0,
                "free_throws_made": 1,
                "free_throws_attempted": 1,
            },
            {
                "game_id": "game-123",
                "team_id": 2,
                "team_tricode": "AWY",
                "player_id": 200,
                "player_name_boxscore": "Away Scorer",
                "official_points": 5,
                "minutes_played_raw": "PT32M00.00S",
                "minutes_played": 32.0,
                "field_goals_made": 2,
                "field_goals_attempted": 2,
                "three_pointers_made": 1,
                "three_pointers_attempted": 1,
                "free_throws_made": 0,
                "free_throws_attempted": 0,
            },
        ]
    )


def build_test_outputs(tmpdir: str) -> None:
    with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
        "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
        return_value=make_boxscore_totals(),
    ):
        process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)


def find_component_by_id(component, component_id: str):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            found = find_component_by_id(child, component_id)
            if found is not None:
                return found
        return None
    return find_component_by_id(children, component_id)


class DashboardTests(unittest.TestCase):
    def test_load_dashboard_datasets_missing_metadata_returns_unavailable(self) -> None:
        with TemporaryDirectory() as tmpdir:
            datasets = load_dashboard_datasets(tmpdir)
            self.assertFalse(datasets.available)
            self.assertIn("No curated parquet outputs", datasets.message or "")

    def test_load_dashboard_datasets_rejects_schema_mismatch(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / DATASET_METADATA_FILENAME
            path.write_text('{"dataset_schema_version": "0.0.0"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported dataset schema version"):
                load_dashboard_datasets(tmpdir)

    def test_render_dashboard_view_supports_game_and_burst_modes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)

            game_view = render_dashboard_view(datasets, tmpdir, DashboardFilters(entity_mode="game"), None)
            self.assertTrue(game_view["records"])
            self.assertEqual(game_view["selected_ids"], [game_view["records"][0]["selection_id"]])
            self.assertTrue(game_view["figure"].data)
            self.assertTrue(game_view["primary_figure"].data)
            self.assertEqual(game_view["secondary_title"], "Secondary Analysis")

            burst_filters = DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180)
            burst_view = render_dashboard_view(datasets, tmpdir, burst_filters, None)
            self.assertTrue(burst_view["records"])
            self.assertEqual(float(burst_view["figure"].data[0]["x"][0]), 0.0)
            self.assertEqual(
                int(burst_view["figure"].data[0]["y"][-1]),
                int(burst_view["records"][0]["points_in_window"]),
            )
            self.assertIn("already isolates", burst_view["secondary_note"])

    def test_build_trajectory_figure_supports_quarter_half_and_burst_modes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )

            quarter_filters = DashboardFilters(entity_mode="quarter", ranking_metric="quarter_points")
            quarter_frame = filter_summary_frame(datasets, quarter_filters)
            quarter_records, _ = build_leaderboard_table(quarter_frame, quarter_filters, limit=1)
            quarter_figure = build_trajectory_figure(quarter_records, timelines, quarter_filters)
            self.assertTrue(quarter_figure.data)
            self.assertEqual(quarter_figure.layout.xaxis.title.text, "Quarter Minute")

            half_filters = DashboardFilters(entity_mode="half", ranking_metric="half_points")
            half_frame = filter_summary_frame(datasets, half_filters)
            half_records, _ = build_leaderboard_table(half_frame, half_filters, limit=1)
            half_figure = build_trajectory_figure(half_records, timelines, half_filters)
            self.assertTrue(half_figure.data)
            self.assertEqual(half_figure.layout.xaxis.title.text, "Half Minute")

            burst_filters = DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180)
            burst_frame = filter_summary_frame(datasets, burst_filters)
            burst_records, _ = build_leaderboard_table(burst_frame, burst_filters, limit=1)
            burst_figure = build_trajectory_figure(burst_records, timelines, burst_filters)
            self.assertTrue(burst_figure.data)
            self.assertEqual(burst_figure.layout.xaxis.title.text, "Burst Seconds")

    def test_marker_toggle_and_margin_mode_change_figure_traces(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game")
            frame = filter_summary_frame(datasets, filters)
            records, _ = build_leaderboard_table(frame, filters, limit=1)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )

            player_figure = build_trajectory_figure(records, timelines, filters)
            margin_figure = build_trajectory_figure(
                records,
                timelines,
                DashboardFilters(
                    entity_mode="game",
                    line_color_mode="margin",
                    show_shot_markers=False,
                ),
            )

            self.assertNotEqual(margin_figure.data[0].line.color, player_figure.data[0].line.color)
            self.assertIn(margin_figure.data[0].line.color, MARGIN_COLORS.values())
            marker_trace = margin_figure.data[-1]
            self.assertEqual(marker_trace.mode, "markers")
            self.assertEqual(marker_trace.marker.size, 14)

    def test_create_dashboard_app_layout_contains_core_components(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            app = create_dashboard_app(tmpdir)
            self.assertIsNotNone(find_component_by_id(app.layout, "leaderboard-table"))
            self.assertIsNotNone(find_component_by_id(app.layout, "comparison-chart"))
            self.assertIsNotNone(find_component_by_id(app.layout, "secondary-analysis-chart"))
            self.assertIsNotNone(find_component_by_id(app.layout, "comparison-tray"))
            self.assertIsNotNone(find_component_by_id(app.layout, "detail-panel-content"))

    def test_create_dashboard_app_empty_state_without_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            app = create_dashboard_app(tmpdir)
            self.assertEqual(app.layout.className, "app-shell")

    def test_encode_decode_dashboard_state_round_trip(self) -> None:
        filters = DashboardFilters(
            entity_mode="quarter",
            ranking_metric="quarter_points",
            time_mode="normalized",
            analysis_mode="rolling_points",
            analysis_window=300,
            include_ot=False,
            competitive_only=True,
            min_points=30,
            min_competitive_share=0.8,
            season="2023-24",
            era="2020s",
            preset="best_quarters",
        )
        search = encode_dashboard_state(filters, ["quarter:g:1:q1", "quarter:g:2:q2"])
        decoded = decode_dashboard_state(search)
        self.assertEqual(decoded["filters"].entity_mode, "quarter")
        self.assertEqual(decoded["filters"].analysis_mode, "rolling_points")
        self.assertEqual(decoded["filters"].analysis_window, 300)
        self.assertEqual(decoded["filters"].season, "2023-24")
        self.assertEqual(decoded["filters"].era, "2020s")
        self.assertEqual(decoded["selected_row_ids"], ["quarter:g:1:q1", "quarter:g:2:q2"])

    def test_apply_dashboard_preset_returns_expected_defaults(self) -> None:
        burst = apply_dashboard_preset("best_3_min_bursts")
        self.assertEqual(burst.entity_mode, "burst")
        self.assertEqual(burst.ranking_metric, "points_in_window")
        self.assertEqual(burst.burst_window, 180)
        self.assertEqual(burst.min_points, 10)

        competitive = apply_dashboard_preset("competitive_60_plus_games")
        self.assertEqual(competitive.entity_mode, "game")
        self.assertEqual(competitive.min_points, 60)
        self.assertEqual(competitive.min_competitive_share, 0.75)
        self.assertFalse(competitive.include_ot)

    def test_build_rolling_analysis_series_handles_partial_and_same_clock_windows(self) -> None:
        entity_timeline = pd.DataFrame(
            [
                {"elapsed_seconds_in_game": 100.0, "action_id": 1, "point_value": 2},
                {"elapsed_seconds_in_game": 100.0, "action_id": 2, "point_value": 3},
                {"elapsed_seconds_in_game": 140.0, "action_id": 3, "point_value": 2},
            ]
        )
        rolling_points = build_rolling_analysis_series(entity_timeline, window_seconds=60, mode="rolling_points")
        rolling_rate = build_rolling_analysis_series(entity_timeline, window_seconds=60, mode="rolling_rate")
        self.assertEqual(rolling_points["analysis_window_points"].tolist(), [5.0, 5.0, 7.0])
        self.assertTrue(pd.isna(rolling_rate["analysis_value"].iloc[0]))
        self.assertTrue(pd.isna(rolling_rate["analysis_value"].iloc[1]))
        self.assertAlmostEqual(float(rolling_rate["analysis_value"].iloc[2]), 10.5, places=6)

    def test_secondary_analysis_figure_adds_projected_pace_benchmarks(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game", analysis_mode="projected_pace")
            frame = filter_summary_frame(datasets, filters)
            records, _ = build_leaderboard_table(frame, filters, limit=1)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )
            figure = build_secondary_analysis_figure(records, timelines, filters)
            self.assertTrue(figure.data)
            self.assertGreaterEqual(len(figure.layout.shapes), 5)

    def test_game_filters_support_competitive_and_efficiency_thresholds(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            frame = filter_summary_frame(
                datasets,
                DashboardFilters(
                    entity_mode="game",
                    competitive_only=True,
                    min_points=5,
                    min_ts_pct=1.1,
                    min_offensive_share=0.9,
                ),
            )
            self.assertEqual(frame["player_name"].tolist(), ["Away Scorer"])


if __name__ == "__main__":
    unittest.main()
