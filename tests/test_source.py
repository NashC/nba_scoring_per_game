from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from nba_scoring_per_game.source import (
    BOX_SCORE_COLUMNS,
    _normalize_min_player_points,
    _parse_matchup_side,
    _parse_minutes_to_float,
    fetch_boxscore_player_totals,
    fetch_game_manifest,
    fetch_playbyplay,
)


class SourceTests(unittest.TestCase):
    def test_fetch_playbyplay_raises_when_endpoint_returns_no_rows(self) -> None:
        with patch("nba_scoring_per_game.source.playbyplayv3.PlayByPlayV3") as mock_endpoint:
            mock_endpoint.return_value.get_data_frames.return_value = [pd.DataFrame()]

            with self.assertRaisesRegex(ValueError, "No play-by-play rows returned"):
                fetch_playbyplay("game-123")

    def test_fetch_boxscore_player_totals_normalizes_columns_and_minutes(self) -> None:
        players = pd.DataFrame(
            [
                {
                    "gameId": "game-123",
                    "teamId": 1,
                    "teamTricode": "HOM",
                    "personId": 100,
                    "points": 30,
                    "nameI": "Home Scorer",
                    "minutes": "PT12M30.00S",
                    "fieldGoalsMade": 10,
                    "fieldGoalsAttempted": 18,
                    "threePointersMade": 4,
                    "threePointersAttempted": 7,
                    "freeThrowsMade": 6,
                    "freeThrowsAttempted": 7,
                },
                {
                    "gameId": "game-123",
                    "teamId": 2,
                    "teamTricode": "AWY",
                    "personId": 200,
                    "points": 22,
                    "nameI": "Away Scorer",
                    "minutes": "9:15",
                    "fieldGoalsMade": 9,
                    "fieldGoalsAttempted": 15,
                    "threePointersMade": 2,
                    "threePointersAttempted": 4,
                    "freeThrowsMade": 2,
                    "freeThrowsAttempted": 3,
                },
            ]
        )

        with patch("nba_scoring_per_game.source.boxscoretraditionalv3.BoxScoreTraditionalV3") as mock_endpoint:
            mock_endpoint.return_value.get_data_frames.return_value = [players]
            totals = fetch_boxscore_player_totals("game-123")

        self.assertEqual(totals.columns.tolist(), BOX_SCORE_COLUMNS)
        self.assertEqual(int(totals.iloc[0]["official_points"]), 30)
        self.assertAlmostEqual(float(totals.iloc[0]["minutes_played"]), 12.5, places=6)
        self.assertAlmostEqual(float(totals.iloc[1]["minutes_played"]), 9.25, places=6)
        self.assertEqual(int(totals.iloc[1]["three_pointers_made"]), 2)

    def test_fetch_boxscore_player_totals_raises_when_endpoint_returns_no_rows(self) -> None:
        with patch("nba_scoring_per_game.source.boxscoretraditionalv3.BoxScoreTraditionalV3") as mock_endpoint:
            mock_endpoint.return_value.get_data_frames.return_value = [pd.DataFrame()]

            with self.assertRaisesRegex(ValueError, "No box score rows returned"):
                fetch_boxscore_player_totals("game-123")

    def test_normalize_min_player_points_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            _normalize_min_player_points(-1)

        with self.assertRaisesRegex(ValueError, "Invalid min_player_points value"):
            _normalize_min_player_points("bad")

    def test_fetch_game_manifest_rejects_player_logs_missing_required_columns(self) -> None:
        team_logs = pd.DataFrame(
            [
                {
                    "GAME_ID": "game-123",
                    "GAME_DATE": "2024-01-01",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "W",
                },
                {
                    "GAME_ID": "game-123",
                    "GAME_DATE": "2024-01-01",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY @ HOM",
                    "WL": "L",
                },
            ]
        )
        bad_player_logs = pd.DataFrame([{"GAME_ID": "game-123"}])

        def fake_fetch(*, season: str, season_type: str, player_or_team_abbreviation: str) -> pd.DataFrame:
            if player_or_team_abbreviation == "T":
                return team_logs
            return bad_player_logs

        with patch("nba_scoring_per_game.source._fetch_league_game_log", side_effect=fake_fetch):
            with self.assertRaisesRegex(ValueError, "missing required GAME_ID/PTS columns"):
                fetch_game_manifest("2023-24", min_player_points=20)

    def test_fetch_game_manifest_orders_pregame_context_by_parsed_game_date(self) -> None:
        team_logs = pd.DataFrame(
            [
                {
                    "GAME_ID": "game-apr",
                    "GAME_DATE": "APR 01, 2024",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY vs. HOM",
                    "WL": "W",
                },
                {
                    "GAME_ID": "game-apr",
                    "GAME_DATE": "APR 01, 2024",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM @ AWY",
                    "WL": "L",
                },
                {
                    "GAME_ID": "game-dec",
                    "GAME_DATE": "DEC 01, 2023",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "W",
                },
                {
                    "GAME_ID": "game-dec",
                    "GAME_DATE": "DEC 01, 2023",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY @ HOM",
                    "WL": "L",
                },
            ]
        )

        with patch("nba_scoring_per_game.source._fetch_league_game_log", return_value=team_logs):
            manifest = fetch_game_manifest("2023-24")

        self.assertEqual(manifest["game_id"].tolist(), ["game-dec", "game-apr"])
        april_game = manifest.loc[manifest["game_id"].eq("game-apr")].iloc[0]
        self.assertEqual(int(april_game["away_team_context_wins"]), 1)
        self.assertEqual(int(april_game["away_team_context_losses"]), 0)
        self.assertAlmostEqual(float(april_game["away_team_context_win_pct"]), 1.0, places=6)

    def test_fetch_game_manifest_ignores_blank_wl_team_log_rows(self) -> None:
        team_logs = pd.DataFrame(
            [
                {
                    "GAME_ID": "game-1",
                    "GAME_DATE": "2024-01-01",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "W",
                },
                {
                    "GAME_ID": "game-1",
                    "GAME_DATE": "2024-01-01",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY @ HOM",
                    "WL": "L",
                },
                {
                    "GAME_ID": "game-cancelled",
                    "GAME_DATE": "2024-01-02",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "",
                },
                {
                    "GAME_ID": "game-cancelled",
                    "GAME_DATE": "2024-01-02",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY @ HOM",
                    "WL": pd.NA,
                },
                {
                    "GAME_ID": "game-2",
                    "GAME_DATE": "2024-01-03",
                    "TEAM_ID": 1,
                    "TEAM_ABBREVIATION": "HOM",
                    "MATCHUP": "HOM vs. AWY",
                    "WL": "L",
                },
                {
                    "GAME_ID": "game-2",
                    "GAME_DATE": "2024-01-03",
                    "TEAM_ID": 2,
                    "TEAM_ABBREVIATION": "AWY",
                    "MATCHUP": "AWY @ HOM",
                    "WL": "W",
                },
            ]
        )

        with patch("nba_scoring_per_game.source._fetch_league_game_log", return_value=team_logs):
            manifest = fetch_game_manifest("2023-24")

        self.assertEqual(manifest["game_id"].tolist(), ["game-1", "game-2"])
        second_game = manifest.loc[manifest["game_id"].eq("game-2")].iloc[0]
        self.assertEqual(int(second_game["home_team_context_wins"]), 1)
        self.assertEqual(int(second_game["home_team_context_losses"]), 0)
        self.assertEqual(int(second_game["away_team_context_wins"]), 0)
        self.assertEqual(int(second_game["away_team_context_losses"]), 1)

    def test_parse_minutes_to_float_supports_multiple_input_formats(self) -> None:
        self.assertAlmostEqual(_parse_minutes_to_float("PT05M30.00S") or 0.0, 5.5, places=6)
        self.assertAlmostEqual(_parse_minutes_to_float("12:30") or 0.0, 12.5, places=6)
        self.assertAlmostEqual(_parse_minutes_to_float("18.75") or 0.0, 18.75, places=6)
        self.assertIsNone(_parse_minutes_to_float(""))
        self.assertIsNone(_parse_minutes_to_float("garbage"))

    def test_parse_matchup_side_returns_none_for_unrecognized_matchups(self) -> None:
        self.assertEqual(_parse_matchup_side("HOM vs. AWY"), "home")
        self.assertEqual(_parse_matchup_side("AWY @ HOM"), "away")
        self.assertIsNone(_parse_matchup_side("Neutral Site"))


if __name__ == "__main__":
    unittest.main()
