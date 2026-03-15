from __future__ import annotations

import unittest

import pandas as pd

from nba_scoring_per_game.transforms import (
    add_game_time_columns,
    add_score_context_columns,
    build_player_scoring_timeline,
    extract_scoring_events,
    parse_clock_to_seconds_remaining,
    summarize_player_games,
)


class TransformTests(unittest.TestCase):
    def test_parse_clock_to_seconds_remaining(self) -> None:
        self.assertEqual(parse_clock_to_seconds_remaining("PT12M00.00S"), 720.0)
        self.assertEqual(parse_clock_to_seconds_remaining("PT00M14.40S"), 14.4)
        self.assertEqual(parse_clock_to_seconds_remaining("PT5M00.00S"), 300.0)

    def test_time_context_timeline_and_summary(self) -> None:
        scoring_events = pd.DataFrame(
            [
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 1,
                    "action_id": 10,
                    "player_id": 100,
                    "player_name": "Home Scorer",
                    "team_id": 1,
                    "team_tricode": "HOM",
                    "period": 1,
                    "clock": "PT11M30.00S",
                    "point_value": 2,
                    "is_field_goal": True,
                    "score_home": 2,
                    "score_away": 0,
                    "action_type": "Made Shot",
                    "sub_type": "Jump Shot",
                    "description": "Home Scorer 15' Jump Shot",
                    "location": "h",
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 2,
                    "action_id": 11,
                    "player_id": 200,
                    "player_name": "Away Scorer",
                    "team_id": 2,
                    "team_tricode": "AWY",
                    "period": 1,
                    "clock": "PT11M00.00S",
                    "point_value": 3,
                    "is_field_goal": True,
                    "score_home": 2,
                    "score_away": 3,
                    "action_type": "Made Shot",
                    "sub_type": "Jump Shot",
                    "description": "Away Scorer 25' 3PT Jump Shot",
                    "location": "v",
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 3,
                    "action_id": 12,
                    "player_id": 100,
                    "player_name": "Home Scorer",
                    "team_id": 1,
                    "team_tricode": "HOM",
                    "period": 2,
                    "clock": "PT10M00.00S",
                    "point_value": 1,
                    "is_field_goal": False,
                    "score_home": 3,
                    "score_away": 3,
                    "action_type": "Free Throw",
                    "sub_type": "Free Throw 1 of 1",
                    "description": "Home Scorer Free Throw 1 of 1",
                    "location": "h",
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 4,
                    "action_id": 13,
                    "player_id": 200,
                    "player_name": "Away Scorer",
                    "team_id": 2,
                    "team_tricode": "AWY",
                    "period": 4,
                    "clock": "PT00M30.00S",
                    "point_value": 2,
                    "is_field_goal": True,
                    "score_home": 3,
                    "score_away": 5,
                    "action_type": "Made Shot",
                    "sub_type": "Layup Shot",
                    "description": "Away Scorer Layup",
                    "location": "v",
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 5,
                    "action_id": 14,
                    "player_id": 100,
                    "player_name": "Home Scorer",
                    "team_id": 1,
                    "team_tricode": "HOM",
                    "period": 5,
                    "clock": "PT04M00.00S",
                    "point_value": 2,
                    "is_field_goal": True,
                    "score_home": 5,
                    "score_away": 5,
                    "action_type": "Made Shot",
                    "sub_type": "Layup Shot",
                    "description": "Home Scorer Layup",
                    "location": "h",
                },
                {
                    "season": "2023-24",
                    "season_type": "Regular Season",
                    "game_date": "2024-01-01",
                    "game_id": "game-1",
                    "action_number": 6,
                    "action_id": 15,
                    "player_id": 200,
                    "player_name": "Away Scorer",
                    "team_id": 2,
                    "team_tricode": "AWY",
                    "period": 5,
                    "clock": "PT00M10.00S",
                    "point_value": 2,
                    "is_field_goal": True,
                    "score_home": 5,
                    "score_away": 7,
                    "action_type": "Made Shot",
                    "sub_type": "Layup Shot",
                    "description": "Away Scorer Late Layup",
                    "location": "v",
                },
            ]
        )

        timeline = build_player_scoring_timeline(scoring_events, player_id=100, game_id="game-1")
        self.assertEqual(timeline["player_game_cumulative_points"].tolist(), [2, 3, 5])
        self.assertEqual(timeline["player_game_final_points"].tolist(), [5, 5, 5])
        self.assertEqual(timeline["player_team_margin_after"].tolist(), [2, 0, 0])
        self.assertEqual(timeline["scoring_type"].tolist(), ["2PT", "FT", "2PT"])
        self.assertEqual(timeline["competitiveness_bucket"].tolist(), ["very_close"] * 3)

        with_time = add_game_time_columns(scoring_events)
        self.assertEqual(
            with_time["elapsed_seconds_in_game"].round(1).tolist(),
            [30.0, 60.0, 840.0, 2850.0, 2940.0, 3170.0],
        )

        with_context = add_score_context_columns(scoring_events)
        self.assertEqual(with_context["player_team_margin_after"].tolist(), [2, 1, 0, 2, 0, 2])
        self.assertEqual(with_context["abs_margin_after"].tolist(), [2, 1, 0, 2, 0, 2])

        summary = summarize_player_games(scoring_events)
        home_row = summary.loc[summary["player_id"].eq(100)].iloc[0]
        away_row = summary.loc[summary["player_id"].eq(200)].iloc[0]
        self.assertEqual(int(home_row["final_points"]), 5)
        self.assertEqual(int(home_row["num_scoring_events"]), 3)
        self.assertEqual(int(home_row["max_cumulative_points"]), 5)
        self.assertEqual(int(home_row["final_player_team_margin"]), -2)
        self.assertEqual(float(home_row["pct_scoring_events_within_3"]), 1.0)
        self.assertEqual(int(home_row["max_lead_during_scoring_events"]), 2)
        self.assertEqual(int(home_row["max_deficit_during_scoring_events"]), 0)
        self.assertEqual(int(away_row["final_points"]), 7)
        self.assertEqual(int(away_row["final_player_team_margin"]), 2)
        self.assertEqual(int(away_row["max_deficit_during_scoring_events"]), 0)

    def test_extract_scoring_events_uses_score_deltas_and_action_id_order(self) -> None:
        raw_df = pd.DataFrame(
            [
                {
                    "gameId": "game-raw",
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
                    "gameId": "game-raw",
                    "actionNumber": 6,
                    "actionId": 11,
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
                    "gameId": "game-raw",
                    "actionNumber": 3,
                    "actionId": 12,
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
                    "gameId": "game-raw",
                    "actionNumber": 4,
                    "actionId": 13,
                    "teamId": 2,
                    "teamTricode": "AWY",
                    "personId": 200,
                    "playerName": "Away Scorer",
                    "period": 1,
                    "clock": "PT11M00.00S",
                    "isFieldGoal": 0,
                    "scoreHome": 0,
                    "scoreAway": 0,
                    "pointsTotal": 0,
                    "location": "v",
                    "description": "MISS Away Scorer Free Throw 1 of 1",
                    "actionType": "Free Throw",
                    "subType": "Free Throw 1 of 1",
                },
                {
                    "gameId": "game-raw",
                    "actionNumber": 5,
                    "actionId": 14,
                    "teamId": 2,
                    "teamTricode": "AWY",
                    "personId": 200,
                    "playerName": "Away Scorer",
                    "period": 1,
                    "clock": "PT10M59.00S",
                    "isFieldGoal": 0,
                    "scoreHome": 2,
                    "scoreAway": 4,
                    "pointsTotal": 6,
                    "location": "v",
                    "description": "Away Scorer Free Throw 1 of 1 (4 PTS)",
                    "actionType": "Free Throw",
                    "subType": "Free Throw 1 of 1",
                },
            ]
        )

        scoring = extract_scoring_events(
            raw_df,
            game_id="game-raw",
            season="2023-24",
            season_type="Regular Season",
            game_date="2024-01-01",
        )
        self.assertEqual(scoring["action_id"].tolist(), [11, 12, 14])
        self.assertEqual(scoring["action_number"].tolist(), [6, 3, 5])
        self.assertEqual(scoring["point_value"].tolist(), [2, 3, 1])
        self.assertEqual(scoring["is_field_goal"].tolist(), [True, True, False])
        self.assertEqual(scoring["player_name"].tolist(), ["Home Scorer", "Away Scorer", "Away Scorer"])

    def test_duplicate_action_id_is_rejected(self) -> None:
        raw_df = pd.DataFrame(
            [
                {
                    "gameId": "game-raw",
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
                    "gameId": "game-raw",
                    "actionNumber": 2,
                    "actionId": 10,
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
            ]
        )

        with self.assertRaisesRegex(ValueError, "duplicate `actionId`"):
            extract_scoring_events(raw_df, game_id="game-raw")

    def test_invalid_clock_bounds_are_rejected(self) -> None:
        scoring_events = pd.DataFrame(
            [
                {
                    "game_id": "game-1",
                    "action_id": 1,
                    "period": 5,
                    "clock": "PT06M00.00S",
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "Clock values fall outside expected"):
            add_game_time_columns(scoring_events)

    def test_missing_identity_is_rejected(self) -> None:
        raw_df = pd.DataFrame(
            [
                {
                    "gameId": "game-raw",
                    "actionNumber": 1,
                    "actionId": 1,
                    "teamId": 1,
                    "teamTricode": "",
                    "personId": 100,
                    "playerName": "",
                    "period": 1,
                    "clock": "PT11M30.00S",
                    "isFieldGoal": 1,
                    "scoreHome": 2,
                    "scoreAway": 0,
                    "pointsTotal": 2,
                    "location": "h",
                    "description": "Jump Shot",
                    "actionType": "Made Shot",
                    "subType": "Jump Shot",
                }
            ]
        )
        with self.assertRaisesRegex(ValueError, "missing player/team identity"):
            extract_scoring_events(raw_df, game_id="game-raw")


if __name__ == "__main__":
    unittest.main()
