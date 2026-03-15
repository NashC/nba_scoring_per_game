from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from nba_scoring_per_game.pipeline import process_game


def make_manifest_row() -> dict[str, object]:
    return {
        "season": "2023-24",
        "season_type": "Regular Season",
        "game_id": "game-123",
        "game_date": "2024-01-01",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_tricode": "HOM",
        "away_team_tricode": "AWY",
    }


def make_raw_playbyplay() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gameId": "game-123",
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
                "gameId": "game-123",
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
                "gameId": "game-123",
                "actionNumber": 2,
                "actionId": 11,
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
                "gameId": "game-123",
                "actionNumber": 3,
                "actionId": 12,
                "teamId": 1,
                "teamTricode": "HOM",
                "personId": 100,
                "playerName": "Home Scorer",
                "period": 2,
                "clock": "PT10M00.00S",
                "isFieldGoal": 0,
                "scoreHome": 3,
                "scoreAway": 3,
                "pointsTotal": 6,
                "location": "h",
                "description": "Home Scorer Free Throw 1 of 1",
                "actionType": "Free Throw",
                "subType": "Free Throw 1 of 1",
            },
            {
                "gameId": "game-123",
                "actionNumber": 4,
                "actionId": 13,
                "teamId": 2,
                "teamTricode": "AWY",
                "personId": 200,
                "playerName": "Away Scorer",
                "period": 4,
                "clock": "PT00M10.00S",
                "isFieldGoal": 1,
                "scoreHome": 3,
                "scoreAway": 5,
                "pointsTotal": 8,
                "location": "v",
                "description": "Away Scorer Layup",
                "actionType": "Made Shot",
                "subType": "Layup Shot",
            },
        ]
    )


def make_boxscore_totals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "game-123",
                "team_id": 1,
                "team_tricode": "HOM",
                "player_id": 100,
                "player_name_boxscore": "Home Scorer",
                "official_points": 3,
                "minutes_played_raw": "PT30M00.00S",
                "minutes_played": 30.0,
                "field_goals_made": 1,
                "field_goals_attempted": 1,
                "three_pointers_made": 0,
                "three_pointers_attempted": 0,
                "free_throws_made": 1,
                "free_throws_attempted": 1,
            },
            {
                "game_id": "game-123",
                "team_id": 2,
                "team_tricode": "AWY",
                "player_id": 200,
                "player_name_boxscore": "Away Scorer",
                "official_points": 5,
                "minutes_played_raw": "PT32M00.00S",
                "minutes_played": 32.0,
                "field_goals_made": 2,
                "field_goals_attempted": 2,
                "three_pointers_made": 1,
                "three_pointers_attempted": 1,
                "free_throws_made": 0,
                "free_throws_attempted": 0,
            },
        ]
    )


def build_test_outputs(tmpdir: str) -> None:
    with patch("nba_scoring_per_game.pipeline.fetch_playbyplay", return_value=make_raw_playbyplay()), patch(
        "nba_scoring_per_game.pipeline.fetch_boxscore_player_totals",
        return_value=make_boxscore_totals(),
    ):
        process_game(make_manifest_row(), out_dir=tmpdir, write_mode="overwrite", raw_cache=False)


def find_component_by_id(component, component_id: str):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            found = find_component_by_id(child, component_id)
            if found is not None:
                return found
        return None
    return find_component_by_id(children, component_id)
