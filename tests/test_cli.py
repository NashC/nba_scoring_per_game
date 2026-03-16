from __future__ import annotations

from contextlib import redirect_stdout
import io
import sys
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from nba_scoring_per_game import cli
from nba_scoring_per_game.pipeline import GameArtifacts
from nba_scoring_per_game.transforms import extract_scoring_events
from tests.fixtures import make_manifest_row, make_raw_playbyplay


def _make_scoring_events() -> pd.DataFrame:
    manifest = make_manifest_row()
    return extract_scoring_events(
        make_raw_playbyplay(),
        game_id=str(manifest["game_id"]),
        season=str(manifest["season"]),
        season_type=str(manifest["season_type"]),
        game_date=str(manifest["game_date"]),
    )


def _artifact() -> GameArtifacts:
    return GameArtifacts(
        manifest_row=make_manifest_row(),
        raw_scoring_events=_make_scoring_events(),
        player_quarter_summaries=pd.DataFrame([{"quarter_number": 1}]),
        player_half_summaries=pd.DataFrame([{"half_index": 1}]),
        player_burst_summaries=pd.DataFrame([{"burst_window_seconds": 60}]),
        validation_report={"validation_passed": True},
        status="success",
    )


class CliTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> str:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["nba-scoring-per-game", *args]), redirect_stdout(stdout):
            cli.main()
        return stdout.getvalue()

    def test_inspect_game_prints_summary_sections(self) -> None:
        with patch("nba_scoring_per_game.cli.fetch_playbyplay", return_value=make_raw_playbyplay()):
            output = self._run_cli("inspect-game", "--game-id", "game-123")

        self.assertIn("Columns:", output)
        self.assertIn("Sample raw rows:", output)
        self.assertIn("Sample apparent scoring rows:", output)

    def test_inspect_game_surfaces_fetch_errors(self) -> None:
        with patch("nba_scoring_per_game.cli.fetch_playbyplay", side_effect=ValueError("missing game")):
            with self.assertRaisesRegex(ValueError, "missing game"):
                self._run_cli("inspect-game", "--game-id", "game-123")

    def test_describe_datasets_prints_metadata_json(self) -> None:
        with patch("nba_scoring_per_game.cli.get_dataset_metadata", return_value={"dataset_schema_version": "2.3.0"}):
            output = self._run_cli("describe-datasets", "--out-dir", "data")

        self.assertIn('"dataset_schema_version": "2.3.0"', output)

    def test_describe_datasets_surfaces_metadata_errors(self) -> None:
        with patch("nba_scoring_per_game.cli.get_dataset_metadata", side_effect=FileNotFoundError("missing metadata")):
            with self.assertRaisesRegex(FileNotFoundError, "missing metadata"):
                self._run_cli("describe-datasets")

    def test_serve_app_runs_dash_server_with_parsed_debug_flag(self) -> None:
        app = Mock()
        with patch("nba_scoring_per_game.cli.create_dashboard_app", return_value=app) as mock_create:
            self._run_cli(
                "serve-app",
                "--out-dir",
                "custom-data",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--debug",
                "yes",
            )

        mock_create.assert_called_once_with("custom-data")
        app.run.assert_called_once_with(host="0.0.0.0", port=9000, debug=True)

    def test_serve_app_rejects_invalid_debug_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not parse boolean value"):
            self._run_cli("serve-app", "--debug", "maybe")

    def test_process_game_prints_artifact_manifest_row(self) -> None:
        manifest = pd.DataFrame([make_manifest_row()])
        with patch("nba_scoring_per_game.cli.fetch_game_manifest", return_value=manifest), patch(
            "nba_scoring_per_game.cli.process_game",
            return_value=_artifact(),
        ):
            output = self._run_cli("process-game", "--game-id", "game-123", "--season", "2023-24")

        self.assertIn("game-123", output)
        self.assertIn("success", output)

    def test_process_game_raises_when_game_is_missing_from_manifest(self) -> None:
        manifest = pd.DataFrame([{**make_manifest_row(), "game_id": "other-game"}])
        with patch("nba_scoring_per_game.cli.fetch_game_manifest", return_value=manifest):
            with self.assertRaisesRegex(ValueError, "was not found in manifest"):
                self._run_cli("process-game", "--game-id", "game-123", "--season", "2023-24")

    def test_backfill_season_prints_processing_manifest(self) -> None:
        manifest = pd.DataFrame([make_manifest_row()])
        processing_manifest = pd.DataFrame([{"game_id": "game-123", "status": "success"}])
        with patch("nba_scoring_per_game.cli.fetch_game_manifest", return_value=manifest), patch(
            "nba_scoring_per_game.cli.build_dataset",
            return_value=processing_manifest,
        ):
            output = self._run_cli("backfill-season", "--season", "2023-24")

        self.assertIn("game-123", output)
        self.assertIn("success", output)

    def test_backfill_season_prints_empty_threshold_message(self) -> None:
        with patch("nba_scoring_per_game.cli.fetch_game_manifest", return_value=pd.DataFrame()):
            output = self._run_cli("backfill-season", "--season", "2023-24", "--min-player-points", "30")

        self.assertIn("No games matched the requested season manifest after applying --min-player-points 30.", output)

    def test_query_summaries_prints_ranked_rows(self) -> None:
        with patch("nba_scoring_per_game.cli.load_dataset", return_value=pd.DataFrame([{"final_points": 70}])), patch(
            "nba_scoring_per_game.cli.query_player_games",
            return_value=pd.DataFrame([{"game_id": "game-123", "final_points": 70}]),
        ):
            output = self._run_cli("query-summaries", "--out-dir", "data")

        self.assertIn("game-123", output)
        self.assertIn("70", output)

    def test_query_summaries_prints_empty_data_message(self) -> None:
        with patch("nba_scoring_per_game.cli.load_dataset", return_value=pd.DataFrame()):
            output = self._run_cli("query-summaries", "--out-dir", "data")

        self.assertIn("No summary data found.", output)


if __name__ == "__main__":
    unittest.main()
