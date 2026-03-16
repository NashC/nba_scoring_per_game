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
TEAM_CONTEXT_VALUE_COLUMNS = [
    "team_context_wins",
    "team_context_losses",
    "team_context_win_pct",
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

    logs = _prepare_team_logs(team_logs, season=season, season_type=season_type)
    logs = _with_team_record_context(logs, season=season, season_type=season_type)
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
    return _sort_by_game_date(filtered_manifest)


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


def _prepare_team_logs(
    team_logs: pd.DataFrame,
    *,
    season: str,
    season_type: str,
) -> pd.DataFrame:
    logs = team_logs.rename(
        columns={
            "GAME_ID": "game_id",
            "GAME_DATE": "game_date",
            "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_tricode",
            "MATCHUP": "matchup",
            "WL": "wl",
        }
    ).copy()
    for column in ["game_id", "game_date", "team_id", "team_tricode", "matchup", "wl"]:
        if column not in logs.columns:
            logs[column] = pd.NA
    logs = logs[["game_id", "game_date", "team_id", "team_tricode", "matchup", "wl"]].copy()
    # The NBA API occasionally includes canceled or otherwise incomplete team-log rows
    # with no result. Exclude them so manifests and record context only reflect played games.
    logs = logs.loc[~logs["wl"].isna() & logs["wl"].astype(str).str.strip().ne("")].copy()
    logs["season"] = season
    logs["season_type"] = season_type
    return logs.drop_duplicates(subset=["game_id", "team_id"]).reset_index(drop=True)


def _with_team_record_context(
    logs: pd.DataFrame,
    *,
    season: str,
    season_type: str,
) -> pd.DataFrame:
    if _is_playoff_season_type(season_type):
        regular_season_logs = _prepare_team_logs(
            _fetch_league_game_log(
                season=season,
                season_type="Regular Season",
                player_or_team_abbreviation="T",
            ),
            season=season,
            season_type="Regular Season",
        )
        context = _final_team_record_context(regular_season_logs)
        enriched = logs.merge(context, on="team_id", how="left")
        enriched["record_context_scope"] = "regular_season_final"
        enriched["is_playoff_game"] = True
        return enriched

    enriched = _with_pregame_team_record_context(logs)
    enriched["record_context_scope"] = "pregame"
    enriched["is_playoff_game"] = False
    return enriched


def _with_pregame_team_record_context(logs: pd.DataFrame) -> pd.DataFrame:
    if logs.empty:
        empty = logs.copy()
        for column in TEAM_CONTEXT_VALUE_COLUMNS:
            empty[column] = pd.Series(dtype="float64" if column.endswith("win_pct") else "Int64")
        return empty

    ordered = _sort_by_game_date(logs, "team_id")
    results = _normalize_wl_series(ordered["wl"])
    wins = results.eq("W").astype(int)
    losses = results.eq("L").astype(int)
    ordered["team_context_wins"] = (wins.groupby(ordered["team_id"], dropna=False).cumsum() - wins).astype("Int64")
    ordered["team_context_losses"] = (losses.groupby(ordered["team_id"], dropna=False).cumsum() - losses).astype("Int64")
    games_before = ordered["team_context_wins"].astype(int) + ordered["team_context_losses"].astype(int)
    ordered["team_context_win_pct"] = _record_win_pct(
        ordered["team_context_wins"].astype(float),
        ordered["team_context_losses"].astype(float),
    )
    ordered.loc[games_before.eq(0), "team_context_win_pct"] = 0.0
    return ordered


def _final_team_record_context(logs: pd.DataFrame) -> pd.DataFrame:
    if logs.empty:
        return pd.DataFrame(columns=["team_id", *TEAM_CONTEXT_VALUE_COLUMNS])

    results = _normalize_wl_series(logs["wl"])
    normalized = logs.copy()
    normalized["_win"] = results.eq("W").astype(int)
    normalized["_loss"] = results.eq("L").astype(int)
    summary = (
        normalized.groupby("team_id", as_index=False, dropna=False)
        .agg(
            team_context_wins=("_win", "sum"),
            team_context_losses=("_loss", "sum"),
        )
    )
    summary["team_context_wins"] = summary["team_context_wins"].astype("Int64")
    summary["team_context_losses"] = summary["team_context_losses"].astype("Int64")
    summary["team_context_win_pct"] = _record_win_pct(
        summary["team_context_wins"].astype(float),
        summary["team_context_losses"].astype(float),
    )
    return summary[["team_id", *TEAM_CONTEXT_VALUE_COLUMNS]]


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
                "home_team_context_wins": home_row.get("team_context_wins", pd.NA),
                "home_team_context_losses": home_row.get("team_context_losses", pd.NA),
                "home_team_context_win_pct": home_row.get("team_context_win_pct", pd.NA),
                "away_team_id": away_row["team_id"],
                "away_team_tricode": away_row["team_tricode"],
                "away_team_context_wins": away_row.get("team_context_wins", pd.NA),
                "away_team_context_losses": away_row.get("team_context_losses", pd.NA),
                "away_team_context_win_pct": away_row.get("team_context_win_pct", pd.NA),
                "record_context_scope": home_row.get("record_context_scope", "pregame"),
                "is_playoff_game": bool(home_row.get("is_playoff_game", False)),
            }
        )

    manifest = pd.DataFrame(rows)
    if manifest.empty:
        raise ValueError("No games could be derived from the team game logs.")
    return _sort_by_game_date(manifest)


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


def _normalize_wl_series(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.upper()
    invalid = normalized.loc[~normalized.isin({"W", "L"})]
    if not invalid.empty:
        raise ValueError(f"Team logs are missing valid WL values for record context: {sorted(set(invalid.tolist()))}")
    return normalized


def _record_win_pct(wins: pd.Series, losses: pd.Series) -> pd.Series:
    total_games = wins + losses
    pct = wins.div(total_games.where(total_games.ne(0)))
    return pct.fillna(0.0)


def _is_playoff_season_type(season_type: str) -> bool:
    return str(season_type).strip().lower() == "playoffs"


def _sort_by_game_date(df: pd.DataFrame, *leading_columns: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    ordered = df.copy()
    ordered["_game_date_sort"] = _parse_game_date_series(ordered["game_date"])
    sort_columns = [*leading_columns, "_game_date_sort"]
    if "game_date" in ordered.columns:
        sort_columns.append("game_date")
    if "game_id" in ordered.columns:
        sort_columns.append("game_id")
    return (
        ordered.sort_values(sort_columns, kind="stable", na_position="last")
        .drop(columns="_game_date_sort")
        .reset_index(drop=True)
    )


def _parse_game_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    remaining = parsed.isna() & series.notna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(series.loc[remaining], format="%b %d, %Y", errors="coerce")
    remaining = parsed.isna() & series.notna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(series.loc[remaining], format="%Y-%m-%dT%H:%M:%S", errors="coerce")
    remaining = parsed.isna() & series.notna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(series.loc[remaining], errors="coerce")
    return parsed


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
