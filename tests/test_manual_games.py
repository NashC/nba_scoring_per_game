from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from nba_scoring_per_game.manual_games import (
    WILT_100_GAME_ID,
    build_wilt_100_approximation,
    write_wilt_100_approximation,
)


class ManualGamesTests(unittest.TestCase):
    def test_build_wilt_100_approximation_matches_known_quarter_totals(self) -> None:
        outputs = build_wilt_100_approximation()

        raw_scoring = outputs["raw_scoring_events"]
        timeline = outputs["player_scoring_timelines"]
        game_summary = outputs["player_game_summaries"]
        quarter_summary = outputs["player_quarter_summaries"]

        self.assertEqual(int(raw_scoring["point_value"].sum()), 100)
        self.assertEqual(int(game_summary.iloc[0]["final_points"]), 100)
        self.assertEqual(int(game_summary.iloc[0]["final_player_team_score"]), 169)
        self.assertEqual(int(game_summary.iloc[0]["final_opponent_score"]), 147)
        self.assertEqual(int(timeline["player_game_cumulative_points"].iloc[-1]), 100)
        self.assertEqual(quarter_summary["quarter_points"].astype(int).tolist(), [23, 18, 28, 31])
        self.assertEqual(int(game_summary.iloc[0]["best_quarter_points"]), 31)
        self.assertEqual(int(game_summary.iloc[0]["best_half_points"]), 59)

    def test_write_wilt_100_approximation_writes_curated_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            written = write_wilt_100_approximation(tmpdir)
            for path in written.values():
                self.assertTrue(Path(path).exists())

            summary_path = (
                Path(tmpdir)
                / "player_game_summaries"
                / "season=1961-62"
                / "season_type=Regular Season"
                / f"part-{WILT_100_GAME_ID}.parquet"
            )
            summary = pd.read_parquet(summary_path)
            self.assertEqual(int(summary.iloc[0]["final_points"]), 100)


if __name__ == "__main__":
    unittest.main()
