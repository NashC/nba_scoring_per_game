from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from nba_scoring_per_game.manual_games import (
    LEGACY_GAME_APPROXIMATIONS,
    WILT_100_GAME_ID,
    build_supported_legacy_approximations,
    build_wilt_100_approximation,
    write_supported_legacy_approximations,
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
        period_end_scores = (
            timeline.sort_values(["period", "action_id"])
            .groupby("period", as_index=False)
            .tail(1)[["period", "score_home", "score_away"]]
        )
        self.assertEqual(
            period_end_scores.to_records(index=False).tolist(),
            [(1, 42, 26), (2, 79, 68), (3, 125, 106), (4, 169, 147)],
        )
        self.assertEqual(int(game_summary.iloc[0]["competitive_points"]), 14)
        self.assertEqual(int(game_summary.iloc[0]["best_quarter_points"]), 31)
        self.assertEqual(int(game_summary.iloc[0]["best_half_points"]), 59)

    def test_supported_legacy_games_match_known_period_and_boxscore_totals(self) -> None:
        outputs = build_supported_legacy_approximations()
        expected_period_points = {game.game_id: list(game.period_points) for game in LEGACY_GAME_APPROXIMATIONS}
        expected_totals = {game.game_id: sum(game.period_points) for game in LEGACY_GAME_APPROXIMATIONS}
        expected_full_names = {game.game_id: game.player_full_name for game in LEGACY_GAME_APPROXIMATIONS}
        expected_three_point_values = {
            game.game_id: game.three_pointers_made * 3 for game in LEGACY_GAME_APPROXIMATIONS
        }
        expected_ft_values = {
            game.game_id: game.free_throws_made for game in LEGACY_GAME_APPROXIMATIONS
        }

        self.assertEqual(set(outputs), {game.game_id for game in LEGACY_GAME_APPROXIMATIONS})

        for game_id, artifact in outputs.items():
            raw_scoring = artifact["raw_scoring_events"]
            game_summary = artifact["player_game_summaries"]
            quarter_summary = artifact["player_quarter_summaries"]
            boxscore_reference = artifact["boxscore_reference"]

            self.assertEqual(int(raw_scoring["point_value"].sum()), expected_totals[game_id], game_id)
            self.assertEqual(int(game_summary.iloc[0]["final_points"]), expected_totals[game_id], game_id)
            self.assertEqual(raw_scoring["player_name"].dropna().unique().tolist(), [expected_full_names[game_id]], game_id)
            self.assertEqual(str(game_summary.iloc[0]["player_name"]), expected_full_names[game_id], game_id)
            self.assertEqual(
                quarter_summary.sort_values("quarter_number")["quarter_points"].astype(int).tolist(),
                expected_period_points[game_id],
                game_id,
            )
            self.assertEqual(
                int(
                    raw_scoring.loc[
                        raw_scoring["is_field_goal"].astype(bool) & raw_scoring["point_value"].eq(3),
                        "point_value",
                    ].sum()
                ),
                expected_three_point_values[game_id],
                game_id,
            )
            self.assertEqual(
                int(
                    raw_scoring.loc[
                        ~raw_scoring["is_field_goal"].astype(bool),
                        "point_value",
                    ].sum()
                ),
                expected_ft_values[game_id],
                game_id,
            )
            self.assertEqual(int(boxscore_reference.iloc[0]["official_points"]), expected_totals[game_id], game_id)

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

    def test_write_supported_legacy_approximations_writes_all_games(self) -> None:
        with TemporaryDirectory() as tmpdir:
            written = write_supported_legacy_approximations(tmpdir)
            self.assertEqual(set(written), {game.game_id for game in LEGACY_GAME_APPROXIMATIONS})
            for game_id in written:
                summary_path = next(
                    Path(tmpdir)
                    .glob(f"player_game_summaries/season=*/season_type=*/part-{game_id}.parquet")
                )
                summary = pd.read_parquet(summary_path)
                self.assertEqual(str(summary.iloc[0]["game_id"]), game_id)


if __name__ == "__main__":
    unittest.main()
