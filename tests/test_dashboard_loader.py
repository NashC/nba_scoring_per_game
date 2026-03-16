from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from nba_scoring_per_game.dashboard import loader as loader_module
from nba_scoring_per_game.dashboard.loader import _season_to_era, load_dashboard_datasets, load_selected_timelines
from nba_scoring_per_game.pipeline import DATASET_METADATA_FILENAME, DATASET_SCHEMA_VERSION
from tests.fixtures import build_test_outputs


class DashboardLoaderTests(unittest.TestCase):
    def test_load_dashboard_datasets_marks_empty_curated_outputs_unavailable(self) -> None:
        with TemporaryDirectory() as tmpdir:
            metadata_path = Path(tmpdir) / DATASET_METADATA_FILENAME
            metadata_path.write_text(f'{{"dataset_schema_version": "{DATASET_SCHEMA_VERSION}"}}\n', encoding="utf-8")

            datasets = load_dashboard_datasets(tmpdir)

        self.assertFalse(datasets.available)
        self.assertIn("they are empty", datasets.message or "")

    def test_load_selected_timelines_skips_missing_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            timelines = load_selected_timelines(
                tmpdir,
                [
                    {
                        "season": "2023-24",
                        "season_type": "Regular Season",
                        "game_id": "game-123",
                    },
                    {
                        "season": "2023-24",
                        "season_type": "Regular Season",
                        "game_id": "missing-game",
                    },
                ],
            )

        self.assertFalse(timelines.empty)
        self.assertEqual(set(timelines["game_id"].astype(str)), {"game-123"})

    def test_load_dashboard_datasets_reuses_cache_until_signature_changes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            game_summary_path = (
                Path(tmpdir)
                / "player_game_summaries"
                / "season=2023-24"
                / "season_type=Regular Season"
                / "part-game-123.parquet"
            )
            with patch("nba_scoring_per_game.dashboard.loader.load_dataset", wraps=loader_module.load_dataset) as mock_load:
                first = load_dashboard_datasets(tmpdir)
                self.assertFalse(first.game_summaries.empty)
                self.assertGreaterEqual(mock_load.call_count, 4)

                mock_load.reset_mock()
                second = load_dashboard_datasets(tmpdir)
                self.assertFalse(second.game_summaries.empty)
                self.assertEqual(mock_load.call_count, 0)

                time.sleep(0.01)
                os.utime(game_summary_path, None)
                third = load_dashboard_datasets(tmpdir)
                self.assertFalse(third.game_summaries.empty)
                self.assertGreaterEqual(mock_load.call_count, 4)

    def test_season_to_era_handles_valid_and_invalid_input(self) -> None:
        self.assertEqual(_season_to_era("2023-24"), "2020s")
        self.assertEqual(_season_to_era("1998-99"), "1990s")
        self.assertIsNone(_season_to_era(""))
        self.assertIsNone(_season_to_era("not-a-season"))


if __name__ == "__main__":
    unittest.main()
