from __future__ import annotations

import re

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog, playbyplayv3
import pandas as pd

BOX_SCORE_COLUMNS = [
    "game_id",
    "team_id",
    "team_tricode",
    "player_id",
    "player_name_boxscore",
    "official_points",
    "minutes_played_raw",
    "minutes_played",
    "field_goals_made",
    "field_goals_attempted",
    "three_pointers_made",
    "three_pointers_attempted",
    "free_throws_made",
    "free_throws_attempted",
]
ISO_DURATION_PATTERN = re.compile(r"^PT(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?$")


def fetch_playbyplay(game_id: str) -> pd.DataFrame:
    """Fetch official NBA play-by-play rows for a single game."""
    df = playbyplayv3.PlayByPlayV3(game_id=game_id).get_data_frames()[0].copy()
    if df.empty:
        raise ValueError(f"No play-by-play rows returned for game_id={game_id}")
    return df


def fetch_boxscore_player_totals(game_id: str) -> pd.DataFrame:
    """Fetch official player box score totals for one game."""
    players = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id).get_data_frames()[0].copy()
    if players.empty:
        raise ValueError(f"No box score rows returned for game_id={game_id}")
    renamed = players.rename(
        columns={
            "gameId": "game_id",
            "teamId": "team_id",
            "teamTricode": "team_tricode",
            "personId": "player_id",
            "points": "official_points",
            "nameI": "player_name_boxscore",
            "minutes": "minutes_played_raw",
            "fieldGoalsMade": "field_goals_made",
            "fieldGoalsAttempted": "field_goals_attempted",
            "threePointersMade": "three_pointers_made",
            "threePointersAttempted": "three_pointers_attempted",
            "freeThrowsMade": "free_throws_made",
            "freeThrowsAttempted": "free_throws_attempted",
        }
    ).copy()
    renamed["minutes_played"] = renamed.get("minutes_played_raw", pd.Series(index=renamed.index)).map(
        _parse_minutes_to_float
    )
    for column in [
        "team_id",
        "player_id",
        "official_points",
        "field_goals_made",
        "field_goals_attempted",
        "three_pointers_made",
        "three_pointers_attempted",
        "free_throws_made",
        "free_throws_attempted",
        "minutes_played",
    ]:
        if column in renamed.columns:
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
        else:
            renamed[column] = pd.NA
    for column in BOX_SCORE_COLUMNS:
        if column not in renamed.columns:
            renamed[column] = pd.NA
    return renamed[BOX_SCORE_COLUMNS].copy()


def fetch_game_manifest(
    season: str,
    season_type: str = "Regular Season",
    min_player_points: int | None = None,
) -> pd.DataFrame:
    """Build a season game manifest from official NBA team game logs.

    When ``min_player_points`` is provided, only games with at least one player-game
    at or above that official box score point total are returned.
    """
    team_logs = _fetch_league_game_log(
        season=season,
        season_type=season_type,
        player_or_team_abbreviation="T",
    )
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
    logs = logs.drop_duplicates(subset=["game_id", "team_id"]).reset_index(drop=True)
    manifest = _pair_team_logs_into_manifest(logs)

    if min_player_points is None:
        return manifest

    threshold = _normalize_min_player_points(min_player_points)
    player_logs = _fetch_league_game_log(
        season=season,
        season_type=season_type,
        player_or_team_abbreviation="P",
    )
    if player_logs.empty:
        raise ValueError(
            "No player game logs returned for threshold filtering "
            f"season={season} season_type={season_type}"
        )
    if "PTS" not in player_logs.columns or "GAME_ID" not in player_logs.columns:
        raise ValueError("Player game logs are missing required GAME_ID/PTS columns for threshold filtering.")

    qualifying_game_ids = (
        player_logs.loc[pd.to_numeric(player_logs["PTS"], errors="coerce").ge(threshold), "GAME_ID"]
        .astype(str)
        .dropna()
        .unique()
        .tolist()
    )
    if not qualifying_game_ids:
        return manifest.iloc[0:0].copy()

    filtered_manifest = manifest.loc[manifest["game_id"].astype(str).isin(qualifying_game_ids)].copy()
    return filtered_manifest.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def _fetch_league_game_log(
    *,
    season: str,
    season_type: str,
    player_or_team_abbreviation: str,
) -> pd.DataFrame:
    return leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star=season_type,
        player_or_team_abbreviation=player_or_team_abbreviation,
    ).get_data_frames()[0].copy()


def _pair_team_logs_into_manifest(logs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    grouped = logs.groupby(["season", "season_type", "game_id", "game_date"], sort=False, dropna=False)
    for (season, season_type, game_id, game_date), group in grouped:
        group = group.copy()
        group["matchup_side"] = group["matchup"].astype(str).map(_parse_matchup_side)
        home_rows = group.loc[group["matchup_side"].eq("home")]
        away_rows = group.loc[group["matchup_side"].eq("away")]

        if len(home_rows) == 1 and len(away_rows) == 1:
            home_row = home_rows.iloc[0]
            away_row = away_rows.iloc[0]
        elif len(group) >= 2:
            # Current official team logs occasionally mark both team rows as away.
            # Keep the two participating teams and let play-by-play resolve the true
            # home/away orientation during game processing.
            ordered = group.sort_values(["team_tricode", "team_id"], kind="stable").reset_index(drop=True)
            home_row = ordered.iloc[0]
            away_row = ordered.iloc[1]
        else:
            raise ValueError(
                "Could not derive both participating teams for game "
                f"{game_id} on {game_date}."
            )

        rows.append(
            {
                "season": season,
                "season_type": season_type,
                "game_id": game_id,
                "game_date": game_date,
                "home_team_id": home_row["team_id"],
                "home_team_tricode": home_row["team_tricode"],
                "away_team_id": away_row["team_id"],
                "away_team_tricode": away_row["team_tricode"],
            }
        )

    manifest = pd.DataFrame(rows)
    if manifest.empty:
        raise ValueError("No games could be derived from the team game logs.")
    return manifest.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def _parse_matchup_side(matchup: object) -> str | None:
    text = str(matchup).strip()
    if "vs." in text:
        return "home"
    if "@" in text:
        return "away"
    return None


def _normalize_min_player_points(value: int | None) -> int:
    try:
        threshold = int(value) if value is not None else None
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid min_player_points value: {value}") from exc
    if threshold is None or threshold < 0:
        raise ValueError(f"min_player_points must be a non-negative integer. Got: {value}")
    return threshold


def _parse_minutes_to_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None

    raw = str(value).strip()
    if not raw:
        return None

    iso_match = ISO_DURATION_PATTERN.fullmatch(raw)
    if iso_match:
        minutes = int(iso_match.group("minutes") or 0)
        seconds = float(iso_match.group("seconds") or 0.0)
        return minutes + (seconds / 60.0)

    if ":" in raw:
        minute_part, second_part = raw.split(":", maxsplit=1)
        try:
            minutes = int(minute_part)
            seconds = float(second_part)
        except ValueError:
            return None
        return minutes + (seconds / 60.0)

    try:
        return float(raw)
    except ValueError:
        return None
