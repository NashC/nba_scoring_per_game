from __future__ import annotations

import re
from typing import Any

import pandas as pd

SCORING_ACTION_TYPES = {"Made Shot", "Free Throw"}
RAW_SCORING_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    "action_number",
    "action_id",
    "player_id",
    "player_name",
    "team_id",
    "team_tricode",
    "period",
    "clock",
    "point_value",
    "is_field_goal",
    "score_home",
    "score_away",
    "action_type",
    "sub_type",
    "description",
    "location",
]
TIMELINE_COLUMNS = RAW_SCORING_COLUMNS + [
    "seconds_remaining_in_period",
    "elapsed_seconds_in_game",
    "elapsed_minutes_in_game",
    "player_game_cumulative_points",
    "player_game_final_points",
    "player_team_score_after",
    "opponent_score_after",
    "player_team_margin_after",
    "abs_margin_after",
    "scoring_type",
    "competitiveness_bucket",
]
SUMMARY_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    "player_id",
    "player_name",
    "team_id",
    "team_tricode",
    "final_points",
    "num_scoring_events",
    "max_cumulative_points",
    "final_player_team_margin",
    "avg_margin_during_scoring_events",
    "median_margin_during_scoring_events",
    "avg_abs_margin_during_scoring_events",
    "median_abs_margin_during_scoring_events",
    "pct_scoring_events_within_3",
    "pct_scoring_events_within_5",
    "pct_scoring_events_within_10",
    "max_lead_during_scoring_events",
    "max_deficit_during_scoring_events",
]
METADATA_COLUMNS = ["season", "season_type", "game_date"]
CLOCK_PATTERN = re.compile(r"^PT(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?$")


def inspect_playbyplay(
    raw_df: pd.DataFrame,
    *,
    sample_rows: int = 15,
    sample_scoring_rows: int = 15,
) -> dict[str, Any]:
    """Return a compact inspection payload for exploratory validation."""
    ordered = _sort_raw_playbyplay(raw_df)
    scoring_mask = ordered["actionType"].isin(SCORING_ACTION_TYPES) & (
        pd.to_numeric(ordered["pointsTotal"], errors="coerce").fillna(0) > 0
    )
    preview_columns = [
        "gameId",
        "period",
        "clock",
        "actionNumber",
        "actionId",
        "teamTricode",
        "playerName",
        "pointsTotal",
        "scoreHome",
        "scoreAway",
        "actionType",
        "subType",
        "description",
    ]
    available_preview_columns = [col for col in preview_columns if col in ordered.columns]
    return {
        "columns": ordered.columns.tolist(),
        "sample_rows": ordered.head(sample_rows),
        "sample_scoring_rows": ordered.loc[scoring_mask, available_preview_columns].head(
            sample_scoring_rows
        ),
    }


def extract_scoring_events(
    raw_df: pd.DataFrame,
    game_id: str | None = None,
    season: str | None = None,
    season_type: str | None = None,
    game_date: str | None = None,
) -> pd.DataFrame:
    """
    Convert raw play-by-play into one row per made player scoring event.

    Notes from empirical validation against PlayByPlayV3:
    - `pointsTotal` is the running game score total, not event-level points.
    - `actionNumber` is not a safe chronological sort key on its own.
    - `actionId` is monotonic and works as the ordering tiebreaker.
    """
    ordered = _sort_raw_playbyplay(raw_df)
    _require_columns(
        ordered,
        [
            "gameId",
            "actionNumber",
            "actionId",
            "teamId",
            "teamTricode",
            "personId",
            "playerName",
            "period",
            "clock",
            "isFieldGoal",
            "scoreHome",
            "scoreAway",
            "pointsTotal",
            "location",
            "description",
            "actionType",
            "subType",
        ],
    )

    scoring = ordered.loc[
        ordered["actionType"].isin(SCORING_ACTION_TYPES)
        & (pd.to_numeric(ordered["pointsTotal"], errors="coerce").fillna(0) > 0)
    ].copy()

    if scoring.empty:
        empty_df = pd.DataFrame(columns=RAW_SCORING_COLUMNS)
        return _ensure_metadata_columns(empty_df, season=season, season_type=season_type, game_date=game_date)

    scoring["game_id"] = scoring["gameId"].astype(str)
    if game_id is not None and not scoring["game_id"].eq(str(game_id)).all():
        raise ValueError("raw_df contains rows for a different game_id than requested")

    for column in [
        "actionNumber",
        "actionId",
        "teamId",
        "personId",
        "period",
        "isFieldGoal",
        "scoreHome",
        "scoreAway",
        "pointsTotal",
    ]:
        scoring[column] = pd.to_numeric(scoring[column], errors="coerce")

    invalid_action_ids = scoring.loc[scoring["actionId"].isna()]
    if not invalid_action_ids.empty:
        sample = invalid_action_ids[["gameId", "actionNumber", "description"]].head(5)
        raise ValueError(
            "Scoring rows are missing `actionId`, which is required for safe event ordering. "
            f"Sample problem rows:\n{sample.to_string(index=False)}"
        )

    duplicated_action_ids = scoring.loc[scoring.duplicated(subset=["game_id", "actionId"], keep=False)]
    if not duplicated_action_ids.empty:
        sample = duplicated_action_ids[
            ["game_id", "actionId", "actionNumber", "clock", "description"]
        ].head(5)
        raise ValueError(
            "Scoring rows contain duplicate `actionId` values within a game. "
            f"Sample problem rows:\n{sample.to_string(index=False)}"
        )

    source_field_goal_mismatches = scoring.loc[
        (scoring["actionType"].eq("Made Shot") & scoring["isFieldGoal"].ne(1))
        | (scoring["actionType"].eq("Free Throw") & scoring["isFieldGoal"].ne(0))
    ]
    if not source_field_goal_mismatches.empty:
        sample = source_field_goal_mismatches[
            ["game_id", "actionId", "actionType", "isFieldGoal", "description"]
        ].head(5)
        raise ValueError(
            "Source `isFieldGoal` values do not align with scoring action types. "
            f"Sample problem rows:\n{sample.to_string(index=False)}"
        )

    scoring["score_home"] = scoring["scoreHome"].astype("Int64")
    scoring["score_away"] = scoring["scoreAway"].astype("Int64")
    scoring["game_points_after"] = scoring["score_home"] + scoring["score_away"]
    scoring["point_value"] = (
        scoring.groupby("game_id", dropna=False)["game_points_after"]
        .diff()
        .fillna(scoring["game_points_after"])
        .astype("Int64")
    )

    invalid_point_values = scoring.loc[~scoring["point_value"].isin([1, 2, 3])]
    if not invalid_point_values.empty:
        sample = invalid_point_values[
            ["game_id", "period", "clock", "actionId", "pointsTotal", "scoreHome", "scoreAway"]
        ].head(5)
        raise ValueError(
            "Expected scoring events to resolve to 1, 2, or 3 points. "
            f"Found invalid rows:\n{sample.to_string(index=False)}"
        )

    missing_identity = scoring.loc[
        scoring["teamId"].isna()
        | scoring["personId"].isna()
        | scoring["playerName"].fillna("").eq("")
        | scoring["teamTricode"].fillna("").eq("")
    ]
    if not missing_identity.empty:
        sample = missing_identity[
            ["game_id", "actionId", "teamId", "personId", "teamTricode", "playerName", "description"]
        ].head(5)
        raise ValueError(
            "Scoring rows are missing player/team identity fields. "
            f"Sample problem rows:\n{sample.to_string(index=False)}"
        )

    scoring["season"] = season
    scoring["season_type"] = season_type
    scoring["game_date"] = game_date
    scoring["action_number"] = scoring["actionNumber"].astype("Int64")
    scoring["action_id"] = scoring["actionId"].astype("Int64")
    scoring["player_id"] = scoring["personId"].astype("Int64")
    scoring["player_name"] = scoring["playerName"].astype(str)
    scoring["team_id"] = scoring["teamId"].astype("Int64")
    scoring["team_tricode"] = scoring["teamTricode"].astype(str)
    scoring["period"] = scoring["period"].astype("Int64")
    scoring["clock"] = scoring["clock"].astype(str)
    scoring["is_field_goal"] = scoring["actionType"].eq("Made Shot")
    scoring["action_type"] = scoring["actionType"].astype(str)
    scoring["sub_type"] = scoring["subType"].fillna("").astype(str)
    scoring["description"] = scoring["description"].fillna("").astype(str)
    scoring["location"] = scoring["location"].fillna("").astype(str).str.lower()

    result = scoring[RAW_SCORING_COLUMNS].sort_values(["game_id", "action_id"]).reset_index(drop=True)
    return _ensure_metadata_columns(result, season=season, season_type=season_type, game_date=game_date)


def add_game_time_columns(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Add forward-moving game time columns for regulation and overtime."""
    if scoring_events_df.empty:
        return _ensure_metadata_columns(scoring_events_df.copy())

    df = _ensure_metadata_columns(scoring_events_df.copy())
    _require_columns(df, ["period", "clock"])
    df["seconds_remaining_in_period"] = df["clock"].map(parse_clock_to_seconds_remaining)
    regulation_mask = df["period"] <= 4

    invalid_regulation_clock = regulation_mask & ~df["seconds_remaining_in_period"].between(0, 720)
    invalid_overtime_clock = ~regulation_mask & ~df["seconds_remaining_in_period"].between(0, 300)
    invalid_clock = invalid_regulation_clock | invalid_overtime_clock
    if invalid_clock.any():
        sample = df.loc[
            invalid_clock, ["game_id", "period", "clock", "seconds_remaining_in_period"]
        ].head(5)
        raise ValueError(
            "Clock values fall outside expected regulation/overtime bounds. "
            f"Sample problem rows:\n{sample.to_string(index=False)}"
        )

    df["elapsed_seconds_in_game"] = 0.0
    df.loc[regulation_mask, "elapsed_seconds_in_game"] = (
        (df.loc[regulation_mask, "period"] - 1) * 720
        + (720 - df.loc[regulation_mask, "seconds_remaining_in_period"])
    )
    df.loc[~regulation_mask, "elapsed_seconds_in_game"] = (
        2880
        + (df.loc[~regulation_mask, "period"] - 5) * 300
        + (300 - df.loc[~regulation_mask, "seconds_remaining_in_period"])
    )
    df["elapsed_minutes_in_game"] = df["elapsed_seconds_in_game"] / 60.0
    return df


def add_score_context_columns(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Add scorer-perspective score differential context columns."""
    if scoring_events_df.empty:
        return _ensure_metadata_columns(scoring_events_df.copy())

    df = _ensure_metadata_columns(scoring_events_df.copy())
    _require_columns(
        df,
        ["game_id", "action_id", "score_home", "score_away", "point_value", "is_field_goal", "location", "description"],
    )
    is_home = df["location"].str.lower().eq("h")
    is_away = df["location"].str.lower().eq("v")
    invalid_location = ~(is_home | is_away)
    if invalid_location.any():
        sample = df.loc[invalid_location, ["game_id", "action_id", "location", "description"]].head(5)
        raise ValueError(
            "Expected scoring rows to include home/away location flags. "
            f"Sample invalid rows:\n{sample.to_string(index=False)}"
        )

    df["player_team_score_after"] = df["score_home"].where(is_home, df["score_away"]).astype("Int64")
    df["opponent_score_after"] = df["score_away"].where(is_home, df["score_home"]).astype("Int64")
    df["player_team_margin_after"] = (
        df["player_team_score_after"] - df["opponent_score_after"]
    ).astype("Int64")
    df["abs_margin_after"] = df["player_team_margin_after"].abs().astype("Int64")
    df["scoring_type"] = df.apply(_scoring_type_label, axis=1)
    df["competitiveness_bucket"] = df["abs_margin_after"].map(_competitiveness_bucket)
    return df


def build_player_scoring_timeline(
    scoring_events_df: pd.DataFrame,
    player_id: int | None = None,
    player_name: str | None = None,
    game_id: str | None = None,
) -> pd.DataFrame:
    """Build a chart-ready cumulative scoring timeline."""
    df = _ensure_metadata_columns(scoring_events_df.copy())
    _require_columns(df, ["game_id", "action_id", "player_id", "player_name", "point_value"])
    if "seconds_remaining_in_period" not in df.columns:
        df = add_game_time_columns(df)
    if "player_team_margin_after" not in df.columns:
        df = add_score_context_columns(df)

    df = df.sort_values(["game_id", "action_id"]).reset_index(drop=True)
    group_columns = ["season", "season_type", "game_date", "game_id", "player_id"]
    df["player_game_cumulative_points"] = (
        df.groupby(group_columns, dropna=False)["point_value"].cumsum().astype("Int64")
    )
    df["player_game_final_points"] = (
        df.groupby(group_columns, dropna=False)["point_value"].transform("sum").astype("Int64")
    )

    if game_id is not None:
        df = df.loc[df["game_id"].eq(str(game_id))]
    if player_id is not None:
        df = df.loc[df["player_id"].eq(player_id)]
    if player_name is not None:
        df = df.loc[df["player_name"].str.casefold().eq(player_name.casefold())]

    return df[TIMELINE_COLUMNS].reset_index(drop=True)


def summarize_player_games(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one row per player-game for ranking and filtering."""
    timeline = build_player_scoring_timeline(scoring_events_df)
    if timeline.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    timeline = timeline.sort_values(["game_id", "player_id", "action_id"]).reset_index(drop=True)
    game_columns = ["season", "season_type", "game_date", "game_id"]
    group_columns = game_columns + ["player_id", "player_name", "team_id", "team_tricode"]

    game_final_scores = (
        timeline.sort_values(["game_id", "action_id"])
        .groupby(game_columns, dropna=False, as_index=False)
        .agg(final_score_home=("score_home", "last"), final_score_away=("score_away", "last"))
    )
    summary = (
        timeline.groupby(group_columns, dropna=False, as_index=False)
        .agg(
            player_location=("location", "first"),
            final_points=("point_value", "sum"),
            num_scoring_events=("point_value", "size"),
            max_cumulative_points=("player_game_cumulative_points", "max"),
            avg_margin_during_scoring_events=("player_team_margin_after", "mean"),
            median_margin_during_scoring_events=("player_team_margin_after", "median"),
            avg_abs_margin_during_scoring_events=("abs_margin_after", "mean"),
            median_abs_margin_during_scoring_events=("abs_margin_after", "median"),
            pct_scoring_events_within_3=("abs_margin_after", lambda s: float((s <= 3).mean())),
            pct_scoring_events_within_5=("abs_margin_after", lambda s: float((s <= 5).mean())),
            pct_scoring_events_within_10=("abs_margin_after", lambda s: float((s <= 10).mean())),
            max_lead_during_scoring_events=("player_team_margin_after", lambda s: int(s.clip(lower=0).max())),
            max_deficit_during_scoring_events=("player_team_margin_after", lambda s: int((-s.clip(upper=0)).max())),
        )
        .sort_values(["final_points", "game_id", "player_id"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    summary = summary.merge(game_final_scores, on=game_columns, how="left")
    is_home = summary["player_location"].eq("h")
    summary["final_player_team_margin"] = (
        (summary["final_score_home"] - summary["final_score_away"]).where(
            is_home,
            summary["final_score_away"] - summary["final_score_home"],
        )
    ).astype("Int64")
    summary = summary.drop(columns=["player_location", "final_score_home", "final_score_away"])
    return summary[SUMMARY_COLUMNS]


def parse_clock_to_seconds_remaining(clock: str) -> float:
    """Parse PlayByPlayV3 clock strings like PT11M47.00S into seconds remaining."""
    match = CLOCK_PATTERN.fullmatch(str(clock))
    if not match:
        raise ValueError(f"Unsupported clock format: {clock!r}")

    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0.0)
    return minutes * 60 + seconds


def _ensure_metadata_columns(
    df: pd.DataFrame,
    *,
    season: str | None = None,
    season_type: str | None = None,
    game_date: str | None = None,
) -> pd.DataFrame:
    for column, value in {
        "season": season,
        "season_type": season_type,
        "game_date": game_date,
    }.items():
        if column not in df.columns:
            df[column] = value
        elif value is not None:
            df[column] = df[column].fillna(value)
    return df


def _require_columns(df: pd.DataFrame, expected_columns: list[str]) -> None:
    missing = [column for column in expected_columns if column not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")


def _sort_raw_playbyplay(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["_api_order"] = range(len(df))
    sort_columns = ["_api_order"]
    if "gameId" in df.columns:
        df["gameId"] = df["gameId"].astype(str)
        sort_columns = ["gameId"] + sort_columns
    if "actionId" in df.columns:
        df["actionId"] = pd.to_numeric(df["actionId"], errors="coerce")
        sort_columns = ["gameId", "actionId", "_api_order"] if "gameId" in df.columns else ["actionId", "_api_order"]
    return df.sort_values(sort_columns).drop(columns="_api_order").reset_index(drop=True)


def _scoring_type_label(row: pd.Series) -> str:
    if int(row["point_value"]) == 1 and not bool(row["is_field_goal"]):
        return "FT"
    if int(row["point_value"]) == 2 and bool(row["is_field_goal"]):
        return "2PT"
    if int(row["point_value"]) == 3 and bool(row["is_field_goal"]):
        return "3PT"
    return f"{row['point_value']}PT"


def _competitiveness_bucket(abs_margin: int) -> str:
    if abs_margin <= 3:
        return "very_close"
    if abs_margin <= 6:
        return "close"
    if abs_margin <= 10:
        return "competitive"
    if abs_margin <= 19:
        return "comfortable"
    return "blowout"
