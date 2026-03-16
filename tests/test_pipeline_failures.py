from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from nba_scoring_per_game.pipeline import (
    GameArtifacts,
    _write_parquet as original_write_parquet,
    build_dataset,
    load_dataset,
    process_game,
    query_player_games,
)
from tests.fixtures import make_boxscore_totals, make_manifest_row, make_raw_playbyplay


class PipelineFailureTests(unittest.TestCase):
    def test_process_game_rejects_invalid_write_mode(self) -> None:
        artifact = process_game(make_manifest_row(), write_mode="invalid_mode")

        self.assertEqual(artifact.status, "write_error")
        self.assertEqual(artifact.error_type, "ValueError")

    def test_process_game_error_if_exists_refuses_existing_curated_outputs(self) -> None:
        manifest_row = make_manifest_row()
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ):
                first = process_game(manifest_row, out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(first.status, "success")
            second = process_game(manifest_row, out_dir=tmpdir, write_mode="error_if_exists", raw_cache=False)

        self.assertEqual(second.status, "write_error")
        self.assertEqual(second.error_type, "FileExistsError")

    def test_process_game_network_failure_sets_network_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", side_effect=ConnectionError("offline")) as mock_fetch, patch(
                "nba_scoring_per_game.pipeline.time.sleep",
                return_value=None,
            ):
                artifact = process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(mock_fetch.call_count, 3)
            self.assertEqual(artifact.status, "network_error")
            self.assertFalse((Path(tmpdir) / "raw_scoring_events").exists())

    def test_process_game_transform_failure_sets_transform_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ), patch(
                "nba_scoring_per_game.pipeline.extract_scoring_events",
                side_effect=ValueError("broken transform"),
            ):
                artifact = process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(artifact.status, "transform_error")
            self.assertFalse((Path(tmpdir) / "raw_scoring_events").exists())

    def test_process_game_validation_exception_sets_validation_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ), patch(
                "nba_scoring_per_game.pipeline.validate_game",
                side_effect=RuntimeError("bad validation"),
            ):
                artifact = process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(artifact.status, "validation_error")
            self.assertFalse((Path(tmpdir) / "validation_reports").exists())
            self.assertFalse((Path(tmpdir) / "raw_scoring_events").exists())

    def test_process_game_write_failure_sets_write_error(self) -> None:
        def flaky_write(df: pd.DataFrame, path: Path) -> None:
            if "validation_reports" in str(path):
                raise OSError("disk full")
            original_write_parquet(df, path)

        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
                "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
                return_value=make_boxscore_totals(),
            ), patch(
                "nba_scoring_per_game.pipeline._write_parquet",
                side_effect=flaky_write,
            ):
                artifact = process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)

            self.assertEqual(artifact.status, "write_error")
            self.assertEqual(artifact.error_type, "OSError")
            self.assertFalse((Path(tmpdir) / "raw_scoring_events").exists())

    def test_build_dataset_fail_fast_raises_for_unsuccessful_artifact(self) -> None:
        manifest_df = pd.DataFrame([make_manifest_row()])
        artifact = GameArtifacts(
            manifest_row=make_manifest_row(),
            status="network_error",
            error_type="ConnectionError",
            error_message="offline",
        )

        with TemporaryDirectory() as tmpdir:
            with patch("nba_scoring_per_game.pipeline.process_game", return_value=artifact):
                with self.assertRaisesRegex(RuntimeError, "Failed processing game"):
                    build_dataset(manifest_df, out_dir=tmpdir, fail_fast=True)

    def test_load_dataset_returns_empty_frame_for_missing_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dataset = load_dataset(Path(tmpdir) / "missing_dataset")

        self.assertTrue(dataset.empty)

    def test_query_player_games_rejects_invalid_ranking_metric(self) -> None:
        summary_df = pd.DataFrame([{"game_id": "g1", "player_id": 1, "final_points": 10}])

        with self.assertRaisesRegex(ValueError, "ranking metric"):
            query_player_games(summary_df, ranking_metric="not_a_metric")


if __name__ == "__main__":
    unittest.main()
