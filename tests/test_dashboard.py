from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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
    build_quick_view_options,
    apply_dashboard_preset,
    build_leaderboard_table,
    decode_dashboard_state,
    encode_dashboard_state,
    filter_summary_frame,
    normalize_saved_bundles,
    serialize_saved_bundle,
)
from nba_scoring_per_game.pipeline import DATASET_METADATA_FILENAME
from tests.fixtures import build_test_outputs, find_component_by_id


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
            quarter_records, _, _ = build_leaderboard_table(quarter_frame, quarter_filters, limit=1)
            quarter_figure = build_trajectory_figure(quarter_records, timelines, quarter_filters)
            self.assertTrue(quarter_figure.data)
            self.assertEqual(quarter_figure.layout.xaxis.title.text, "Quarter Minute")

            half_filters = DashboardFilters(entity_mode="half", ranking_metric="half_points")
            half_frame = filter_summary_frame(datasets, half_filters)
            half_records, _, _ = build_leaderboard_table(half_frame, half_filters, limit=1)
            half_figure = build_trajectory_figure(half_records, timelines, half_filters)
            self.assertTrue(half_figure.data)
            self.assertEqual(half_figure.layout.xaxis.title.text, "Half Minute")

            burst_filters = DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180)
            burst_frame = filter_summary_frame(datasets, burst_filters)
            burst_records, _, _ = build_leaderboard_table(burst_frame, burst_filters, limit=1)
            burst_figure = build_trajectory_figure(burst_records, timelines, burst_filters)
            self.assertTrue(burst_figure.data)
            self.assertEqual(burst_figure.layout.xaxis.title.text, "Burst Seconds")

    def test_marker_toggle_and_margin_mode_change_figure_traces(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game")
            frame = filter_summary_frame(datasets, filters)
            records, _, _ = build_leaderboard_table(frame, filters, limit=1)
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
            self.assertIsNotNone(find_component_by_id(app.layout, "app-guide"))
            self.assertIsNotNone(find_component_by_id(app.layout, "leaderboard-table"))
            self.assertIsNotNone(find_component_by_id(app.layout, "quick-view-bar"))
            self.assertIsNotNone(find_component_by_id(app.layout, "comparison-chart"))
            self.assertIsNotNone(find_component_by_id(app.layout, "secondary-analysis-chart"))
            self.assertIsNotNone(find_component_by_id(app.layout, "comparison-tray"))
            self.assertIsNotNone(find_component_by_id(app.layout, "chart-summary-strip"))
            self.assertIsNotNone(find_component_by_id(app.layout, "chart-visual-key"))
            self.assertIsNotNone(find_component_by_id(app.layout, "saved-bundle-select"))
            self.assertIsNotNone(find_component_by_id(app.layout, "remove-last-comparison"))
            self.assertIsNotNone(find_component_by_id(app.layout, "detail-panel-content"))
            table = find_component_by_id(app.layout, "leaderboard-table")
            self.assertEqual(table.markdown_options, {"html": True})

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

    def test_decode_dashboard_state_invalid_mode_falls_back_to_game(self) -> None:
        decoded = decode_dashboard_state("?mode=garbage&rank=quarter_points")
        self.assertEqual(decoded["filters"].entity_mode, "game")
        self.assertEqual(decoded["filters"].ranking_metric, "total_points")

    def test_quick_view_options_match_preset_definitions(self) -> None:
        options = build_quick_view_options()
        self.assertEqual(options[0]["value"], "top_scoring_games")
        self.assertEqual(options[-1]["value"], "competitive_60_plus_games")

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
        self.assertEqual(rolling_points["analysis_window_points"].tolist(), [2.0, 5.0, 7.0])
        self.assertTrue(pd.isna(rolling_rate["analysis_value"].iloc[0]))
        self.assertTrue(pd.isna(rolling_rate["analysis_value"].iloc[1]))
        self.assertAlmostEqual(float(rolling_rate["analysis_value"].iloc[2]), 10.5, places=6)

    def test_saved_bundle_serialization_and_normalization(self) -> None:
        bundle = serialize_saved_bundle(
            "Core Set",
            DashboardFilters(entity_mode="game", ranking_metric="offensive_share"),
            ["game:g1:1"],
        )
        normalized = normalize_saved_bundles(
            [
                {"id": bundle.id, "name": bundle.name, "search": bundle.search, "saved_at": bundle.saved_at},
                {"name": "bad"},
            ]
        )
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0].name, "Core Set")
        self.assertIn("rank=offensive_share", normalized[0].search)

    def test_secondary_analysis_figure_adds_projected_pace_benchmarks(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game", analysis_mode="projected_pace")
            frame = filter_summary_frame(datasets, filters)
            records, _, _ = build_leaderboard_table(frame, filters, limit=1)
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

    def test_build_leaderboard_table_promotes_metric_columns_and_styles(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game", ranking_metric="offensive_share")
            frame = filter_summary_frame(datasets, filters)
            records, columns, styles = build_leaderboard_table(frame, filters, limit=5)
            self.assertTrue(records)
            column_ids = [column["id"] for column in columns]
            self.assertIn("ts_pct_display", column_ids)
            self.assertIn("offensive_share_display", column_ids)
            self.assertIn("team_logo_display", column_ids)
            self.assertIn("opponent_team_logo_display", column_ids)
            self.assertEqual(styles["highlight_column_id"], "offensive_share_display")
            self.assertTrue(any(rule["if"]["column_id"] == "offensive_share_display" for rule in styles["style_header_conditional"]))
            self.assertIn("/assets/team_logos/", records[0]["team_logo_display"])

    def test_build_leaderboard_table_uses_mode_specific_columns(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180)
            frame = filter_summary_frame(datasets, filters)
            _, columns, styles = build_leaderboard_table(frame, filters, limit=5)
            column_ids = [column["id"] for column in columns]
            self.assertIn("window_points_per_minute_display", column_ids)
            self.assertIn("avg_abs_score_diff_in_window_display", column_ids)
            self.assertEqual(styles["highlight_column_id"], "points_in_window_display")

    def test_render_dashboard_view_empty_state_includes_active_filter_guidance(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            view = render_dashboard_view(
                datasets,
                tmpdir,
                DashboardFilters(entity_mode="game", min_points=99, competitive_only=True, include_ot=False),
                None,
            )
            self.assertIn("Current constraints", view["status"])
            self.assertIn("min points is 99", view["status"])

    def test_render_dashboard_view_includes_styles_for_active_metric(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            view = render_dashboard_view(
                datasets,
                tmpdir,
                DashboardFilters(entity_mode="game", ranking_metric="ts_pct"),
                None,
            )
            self.assertEqual(view["leaderboard_styles"]["highlight_column_id"], "ts_pct_display")
            self.assertTrue(
                any(rule.get("if", {}).get("column_id") == "ts_pct_display" for rule in view["leaderboard_styles"]["style_data_conditional"])
            )

    def test_trajectory_figure_shortens_legend_and_deemphasizes_secondary_selection(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game")
            frame = filter_summary_frame(datasets, filters)
            records, _, _ = build_leaderboard_table(frame, filters, limit=2)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )
            figure = build_trajectory_figure(records, timelines, filters)
            self.assertIsNone(figure.layout.title.text)
            self.assertNotIn("Full Game", figure.data[0].name)
            self.assertEqual(figure.data[0].opacity, 1.0)
            self.assertLess(float(figure.data[2].opacity), 1.0)

    def test_game_time_axis_marks_quarter_and_regulation_boundaries(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game")
            frame = filter_summary_frame(datasets, filters)
            records, _, _ = build_leaderboard_table(frame, filters, limit=1)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )
            figure = build_trajectory_figure(records, timelines, filters)
            self.assertEqual(list(figure.layout.xaxis.tickvals), [0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0, 42.0, 48.0])
            self.assertEqual(list(figure.layout.xaxis.ticktext), ["0", "6", "12", "18", "24", "30", "36", "42", "48"])
            self.assertEqual(float(figure.layout.xaxis.range[1]), 48.0)
            self.assertEqual(len(figure.layout.shapes), 4)
            annotation_texts = [annotation.text for annotation in figure.layout.annotations]
            self.assertIn("Q1", annotation_texts)
            self.assertIn("HT", annotation_texts)
            self.assertIn("Q3", annotation_texts)
            self.assertIn("REG", annotation_texts)

    def test_game_time_axis_includes_overtime_boundary_when_present(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            datasets = load_dashboard_datasets(tmpdir)
            filters = DashboardFilters(entity_mode="game")
            frame = filter_summary_frame(datasets, filters)
            records, _, _ = build_leaderboard_table(frame, filters, limit=1)
            timelines = pd.read_parquet(
                Path(tmpdir)
                / "player_scoring_timelines"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            ).copy()
            timelines["total_game_minutes"] = 53.0
            figure = build_trajectory_figure(records, timelines, filters)
            self.assertIn(53.0, list(figure.layout.xaxis.tickvals))
            self.assertIn("53", list(figure.layout.xaxis.ticktext))
            self.assertEqual(float(figure.layout.xaxis.range[1]), 53.0)
            annotation_texts = [annotation.text for annotation in figure.layout.annotations]
            self.assertIn("OT1", annotation_texts)


if __name__ == "__main__":
    unittest.main()
