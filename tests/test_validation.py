from __future__ import annotations

import unittest

import pandas as pd

from nba_scoring_per_game.transforms import extract_scoring_events
from nba_scoring_per_game.validation import validate_game
from tests.fixtures import make_boxscore_totals, make_manifest_row, make_raw_playbyplay


def _make_scoring_events() -> pd.DataFrame:
    manifest = make_manifest_row()
    return extract_scoring_events(
        make_raw_playbyplay(),
        game_id=str(manifest["game_id"]),
        season=str(manifest["season"]),
        season_type=str(manifest["season_type"]),
        game_date=str(manifest["game_date"]),
    )


class ValidationTests(unittest.TestCase):
    def test_validate_game_raises_when_scoring_events_are_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "No scoring events available"):
            validate_game(
                "game-123",
                scoring_events_df=_make_scoring_events().iloc[0:0].copy(),
                raw_df=make_raw_playbyplay(),
                boxscore_df=make_boxscore_totals(),
            )

    def test_validate_game_reports_player_total_mismatch(self) -> None:
        bad_boxscore = make_boxscore_totals().copy()
        bad_boxscore.loc[bad_boxscore["player_id"].eq(100), "official_points"] = 99

        report = validate_game(
            "game-123",
            scoring_events_df=_make_scoring_events(),
            raw_df=make_raw_playbyplay(),
            boxscore_df=bad_boxscore,
        )

        self.assertFalse(report["validation_passed"])
        self.assertEqual(report["num_player_total_mismatches"], 1)
        self.assertEqual(len(report["player_total_mismatch_rows"]), 1)

    def test_validate_game_reports_final_score_mismatch_without_player_mismatch(self) -> None:
        extra_player = pd.DataFrame(
            [
                {
                    "game_id": "game-123",
                    "team_id": 1,
                    "team_tricode": "HOM",
                    "player_id": 300,
                    "player_name_boxscore": "Bench Player",
                    "official_points": 1,
                    "minutes_played_raw": "PT01M00.00S",
                    "minutes_played": 1.0,
                    "field_goals_made": 0,
                    "field_goals_attempted": 0,
                    "three_pointers_made": 0,
                    "three_pointers_attempted": 0,
                    "free_throws_made": 1,
                    "free_throws_attempted": 1,
                }
            ]
        )
        boxscore = pd.concat([make_boxscore_totals(), extra_player], ignore_index=True)

        report = validate_game(
            "game-123",
            scoring_events_df=_make_scoring_events(),
            raw_df=make_raw_playbyplay(),
            boxscore_df=boxscore,
        )

        self.assertFalse(report["validation_passed"])
        self.assertEqual(report["num_player_total_mismatches"], 0)
        self.assertFalse(report["final_score_matches_boxscore"])

    def test_validate_game_reports_duplicate_scoring_action_ids(self) -> None:
        bad_scoring = _make_scoring_events().copy()
        bad_scoring.loc[1, "action_id"] = bad_scoring.loc[0, "action_id"]

        report = validate_game(
            "game-123",
            scoring_events_df=bad_scoring,
            raw_df=make_raw_playbyplay(),
            boxscore_df=make_boxscore_totals(),
        )

        self.assertFalse(report["validation_passed"])
        self.assertEqual(report["scoring_action_id_duplicate_count"], 1)

    def test_validate_game_reports_missing_scoring_identity(self) -> None:
        bad_raw = make_raw_playbyplay().copy()
        bad_raw.loc[bad_raw["actionId"].eq(10), "playerName"] = ""
        bad_raw.loc[bad_raw["actionId"].eq(10), "teamTricode"] = ""

        report = validate_game(
            "game-123",
            scoring_events_df=_make_scoring_events(),
            raw_df=bad_raw,
            boxscore_df=make_boxscore_totals(),
        )

        self.assertFalse(report["validation_passed"])
        self.assertEqual(report["missing_scoring_identity_count"], 1)

    def test_validate_game_reports_bad_margin_checks(self) -> None:
        bad_scoring = _make_scoring_events().copy()
        bad_scoring["location"] = "v"

        report = validate_game(
            "game-123",
            scoring_events_df=bad_scoring,
            raw_df=make_raw_playbyplay(),
            boxscore_df=make_boxscore_totals(),
        )

        self.assertFalse(report["validation_passed"])
        self.assertFalse(report["home_margin_check_passed"])
        self.assertTrue(report["away_margin_check_passed"])


if __name__ == "__main__":
    unittest.main()
