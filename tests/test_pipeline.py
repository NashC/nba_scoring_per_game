from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from nba_scoring_per_game.pipeline import (
    DATASET_METADATA_FILENAME,
    DATASET_SCHEMA_VERSION,
    build_dataset,
    get_dataset_metadata,
    load_dataset,
    process_game,
    query_player_games,
)
from nba_scoring_per_game.source import fetch_game_manifest
from tests.fixtures import make_boxscore_totals, make_manifest_row, make_raw_playbyplay


class PipelineTests(unittest.TestCase):
    def test_process_game_writes_curated_outputs(self) -> None:
        manifest_row = make_manifest_row()
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ):
                artifact = process_game(manifest_row, out_dir=tmpdir, write_mode="overwrite", raw_cache=True)

            self.assertEqual(artifact.status, "success")
            self.assertTrue(artifact.validation_report["validation_passed"])

            base = Path(tmpdir)
            raw_scoring = load_dataset(base / "raw_scoring_events")
            timelines = load_dataset(base / "player_scoring_timelines")
            summaries = load_dataset(base / "player_game_summaries")
            quarter_summaries = load_dataset(base / "player_quarter_summaries")
            half_summaries = load_dataset(base / "player_half_summaries")
            burst_summaries = load_dataset(base / "player_burst_summaries")
            self.assertEqual(len(raw_scoring), 4)
            self.assertEqual(len(timelines), 4)
            self.assertEqual(len(summaries), 2)
            self.assertEqual(len(quarter_summaries), 4)
            self.assertEqual(len(half_summaries), 3)
            self.assertEqual(len(burst_summaries), 10)
            self.assertTrue((base / DATASET_METADATA_FILENAME).exists())
            metadata = get_dataset_metadata(base)
            self.assertEqual(metadata["dataset_schema_version"], DATASET_SCHEMA_VERSION)
            self.assertIn("points_from_3s", summaries.columns)
            self.assertIn("margin_bucket", timelines.columns)
            self.assertIn("opponent_team_tricode", raw_scoring.columns)
            self.assertIn("home_team_id", summaries.columns)
            self.assertIn("final_player_team_score", summaries.columns)
            home_row = summaries.loc[summaries["player_id"].eq(100)].iloc[0]
            away_row = summaries.loc[summaries["player_id"].eq(200)].iloc[0]
            self.assertEqual(int(home_row["home_team_id"]), 1)
            self.assertEqual(home_row["opponent_team_tricode"], "AWY")
            self.assertEqual(bool(home_row["is_home_team"]), True)
            self.assertEqual(int(home_row["final_player_team_score"]), 3)
            self.assertEqual(int(home_row["final_opponent_score"]), 5)
            self.assertEqual(int(away_row["opponent_team_id"]), 1)
            self.assertTrue((base / "validation_reports").exists())

    def test_build_dataset_skips_existing_after_success(self) -> None:
        manifest_df = pd.DataFrame([make_manifest_row()])
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ):
                first_manifest = build_dataset(manifest_df, out_dir=tmpdir, write_mode="overwrite", raw_cache=False)
                second_manifest = build_dataset(manifest_df, out_dir=tmpdir, write_mode="skip_existing", raw_cache=False)

            self.assertEqual(first_manifest.iloc[0]["status"], "success")
            self.assertTrue(bool(second_manifest.iloc[0]["skipped_existing"]))
            self.assertEqual(second_manifest.iloc[0]["status"], "success")

    def test_build_dataset_records_validation_failure_without_curated_outputs(self) -> None:
        manifest_df = pd.DataFrame([make_manifest_row()])
        bad_boxscore = make_boxscore_totals().copy()
        bad_boxscore.loc[bad_boxscore["player_id"].eq(100), "official_points"] = 99

        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=bad_boxscore,
            ):
                processing_manifest = build_dataset(manifest_df, out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(processing_manifest.iloc[0]["status"], "validation_error")
            self.assertFalse(bool(processing_manifest.iloc[0]["validation_passed"]))
            self.assertTrue(load_dataset(Path(tmpdir) / "raw_scoring_events").empty)

    def test_query_player_games_filters_and_sorts(self) -> None:
        summary_df = pd.DataFrame(
            [
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "g1",
                    "player_id": 1,
                    "player_name": "A",
                    "team_id": 10,
                    "team_tricode": "AAA",
                    "final_points": 70,
                    "num_scoring_events": 30,
                    "max_cumulative_points": 70,
                    "final_player_team_margin": 5,
                    "avg_margin_during_scoring_events": 1.0,
                    "median_margin_during_scoring_events": 1.0,
                    "avg_abs_margin_during_scoring_events": 4.0,
                    "median_abs_margin_during_scoring_events": 4.0,
                    "pct_scoring_events_within_3": 0.5,
                    "pct_scoring_events_within_5": 0.8,
                    "pct_scoring_events_within_10": 0.9,
                    "max_lead_during_scoring_events": 10,
                    "max_deficit_during_scoring_events": 3,
                    "competitive_points": 70,
                    "competitive_scoring_share": 1.0,
                    "went_to_overtime": False,
                    "points_per_minute": 1.8,
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-02",
                    "game_id": "g2",
                    "player_id": 2,
                    "player_name": "B",
                    "team_id": 20,
                    "team_tricode": "BBB",
                    "final_points": 60,
                    "num_scoring_events": 25,
                    "max_cumulative_points": 60,
                    "final_player_team_margin": -1,
                    "avg_margin_during_scoring_events": -1.0,
                    "median_margin_during_scoring_events": -1.0,
                    "avg_abs_margin_during_scoring_events": 8.0,
                    "median_abs_margin_during_scoring_events": 8.0,
                    "pct_scoring_events_within_3": 0.2,
                    "pct_scoring_events_within_5": 0.4,
                    "pct_scoring_events_within_10": 0.7,
                    "max_lead_during_scoring_events": 2,
                    "max_deficit_during_scoring_events": 12,
                    "competitive_points": 20,
                    "competitive_scoring_share": 0.333333,
                    "went_to_overtime": True,
                    "points_per_minute": 1.5,
                },
            ]
        )

        result = query_player_games(
            summary_df,
            min_points=65,
            max_avg_abs_margin=5.0,
            min_pct_within_10=0.8,
            sort_by="avg_abs_margin_during_scoring_events",
            ascending=True,
        )
        self.assertEqual(result["game_id"].tolist(), ["g1"])

    def test_query_player_games_supports_burst_entity_mode(self) -> None:
        burst_df = pd.DataFrame(
            [
                {
                    "game_id": "g1",
                    "player_id": 1,
                    "burst_window_seconds": 180,
                    "points_in_window": 15,
                    "competitive_scoring_share": 1.0,
                    "includes_overtime": False,
                    "window_points_per_minute": 5.0,
                    "avg_abs_score_diff_in_window": 4.0,
                },
                {
                    "game_id": "g2",
                    "player_id": 2,
                    "burst_window_seconds": 180,
                    "points_in_window": 12,
                    "competitive_scoring_share": 0.5,
                    "includes_overtime": True,
                    "window_points_per_minute": 4.0,
                    "avg_abs_score_diff_in_window": 8.0,
                },
            ]
        )

        result = query_player_games(
            burst_df,
            entity_mode="burst",
            burst_window=180,
            min_competitive_share=0.75,
            include_ot=False,
            max_avg_abs_margin=5.0,
            ranking_metric="points_per_minute",
        )
        self.assertEqual(result["game_id"].tolist(), ["g1"])

    def test_fetch_game_manifest_pairs_home_and_away_rows(self) -> None:
        mocked_logs = pd.DataFrame(
            [
                {
                    "SEASON_ID": "22023",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "TEAM_NAME": "Home",
                    "GAME_ID": "game-123",
                    "GAME_DATE": "2024-01-01",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "W",
                },
                {
                    "SEASON_ID": "22023",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "TEAM_NAME": "Away",
                    "GAME_ID": "game-123",
                    "GAME_DATE": "2024-01-01",
                    "MATCHUP": "AWY @ HOM",
                    "WL": "L",
                },
            ]
        )

        class FakeEndpoint:
            def get_data_frames(self) -> list[pd.DataFrame]:
                return [mocked_logs]

        with patch("nba_scoring_per_game.source.leaguegamelog.LeagueGameLog", return_value=FakeEndpoint()):
            manifest = fetch_game_manifest("2023-24")

        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest.iloc[0]["home_team_id"], 1)
        self.assertEqual(manifest.iloc[0]["away_team_id"], 2)


if __name__ == "__main__":
    unittest.main()
