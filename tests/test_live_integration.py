from __future__ import annotations

import os
import unittest

from nba_scoring_per_game import (
    build_player_scoring_timeline,
    extract_scoring_events,
    fetch_boxscore_player_totals,
    fetch_playbyplay,
    validate_game,
)


LIVE_TESTS_ENABLED = os.getenv("NBA_API_LIVE_TESTS") == "1"


@unittest.skipUnless(LIVE_TESTS_ENABLED, "Set NBA_API_LIVE_TESTS=1 to run live NBA API integration tests.")
class LiveIntegrationTests(unittest.TestCase):
    def test_kobe_81_matches_boxscore(self) -> None:
        game_id = "0020500591"
        raw_df = fetch_playbyplay(game_id)
        scoring = extract_scoring_events(
            raw_df,
            game_id=game_id,
            season="2005-06",
            season_type="Regular Season",
            game_date="2006-01-22",
        )
        timeline = build_player_scoring_timeline(scoring, player_id=977, game_id=game_id)
        validation = validate_game(game_id, scoring_events_df=scoring, raw_df=raw_df, boxscore_df=fetch_boxscore_player_totals(game_id))
        self.assertEqual(int(timeline["player_game_final_points"].iloc[-1]), 81)
        self.assertTrue(validation["validation_passed"])

    def test_overtime_game_validates(self) -> None:
        game_id = "0022301070"
        raw_df = fetch_playbyplay(game_id)
        scoring = extract_scoring_events(
            raw_df,
            game_id=game_id,
            season="2023-24",
            season_type="Regular Season",
            game_date="2024-03-29",
        )
        validation = validate_game(game_id, scoring_events_df=scoring, raw_df=raw_df, boxscore_df=fetch_boxscore_player_totals(game_id))
        self.assertEqual(validation["max_period"], 5)
        self.assertTrue(validation["validation_passed"])


if __name__ == "__main__":
    unittest.main()
