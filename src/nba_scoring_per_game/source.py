from __future__ import annotations

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog, playbyplayv3
import pandas as pd


def fetch_playbyplay(game_id: str) -> pd.DataFrame:
    """Fetch official NBA play-by-play rows for a single game."""
    df = playbyplayv3.PlayByPlayV3(game_id=game_id).get_data_frames()[0].copy()
    if df.empty:
        raise ValueError(f"No play-by-play rows returned for game_id={game_id}")
    return df


def fetch_boxscore_player_totals(game_id: str) -> pd.DataFrame:
    """Fetch official player point totals for one game."""
    players = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id).get_data_frames()[0].copy()
    if players.empty:
        raise ValueError(f"No box score rows returned for game_id={game_id}")
    return players.rename(
        columns={
            "gameId": "game_id",
            "teamId": "team_id",
            "teamTricode": "team_tricode",
            "personId": "player_id",
            "points": "official_points",
            "nameI": "player_name_boxscore",
        }
    )[
        ["game_id", "team_id", "team_tricode", "player_id", "player_name_boxscore", "official_points"]
    ]


def fetch_game_manifest(season: str, season_type: str = "Regular Season") -> pd.DataFrame:
    """Build a season game manifest from official NBA team game logs."""
    team_logs = leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star=season_type,
        player_or_team_abbreviation="T",
    ).get_data_frames()[0].copy()
    if team_logs.empty:
        raise ValueError(f"No game logs returned for season={season} season_type={season_type}")

    logs = team_logs.rename(
        columns={
            "GAME_ID": "game_id",
            "GAME_DATE": "game_date",
            "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_tricode",
            "MATCHUP": "matchup",
        }
    )[["game_id", "game_date", "team_id", "team_tricode", "matchup"]].copy()
    logs["season"] = season
    logs["season_type"] = season_type
    logs["is_home"] = logs["matchup"].astype(str).str.contains("vs.", regex=False)
    logs = logs.drop_duplicates(subset=["game_id", "team_id"]).reset_index(drop=True)

    home = logs.loc[logs["is_home"]].rename(
        columns={"team_id": "home_team_id", "team_tricode": "home_team_tricode"}
    )[["season", "season_type", "game_id", "game_date", "home_team_id", "home_team_tricode"]]
    away = logs.loc[~logs["is_home"]].rename(
        columns={"team_id": "away_team_id", "team_tricode": "away_team_tricode"}
    )[["season", "season_type", "game_id", "game_date", "away_team_id", "away_team_tricode"]]

    manifest = home.merge(
        away,
        on=["season", "season_type", "game_id", "game_date"],
        how="outer",
        validate="one_to_one",
    ).sort_values(["game_date", "game_id"]).reset_index(drop=True)

    missing_home = manifest["home_team_id"].isna() | manifest["home_team_tricode"].isna()
    missing_away = manifest["away_team_id"].isna() | manifest["away_team_tricode"].isna()
    if (missing_home | missing_away).any():
        sample = manifest.loc[missing_home | missing_away].head(5)
        raise ValueError(
            "Could not derive complete home/away team metadata for all games. "
            f"Sample rows:\n{sample.to_string(index=False)}"
        )

    return manifest
