from __future__ import annotations

import re
from typing import Any, Iterable

import pandas as pd

SCORING_ACTION_TYPES = {"Made Shot", "Free Throw"}
COMPETITIVE_MARGIN_THRESHOLD = 10
BURST_WINDOW_SECONDS = (60, 120, 180, 300, 600)
MATCHUP_CONTEXT_COLUMNS = [
    "home_team_id",
    "home_team_tricode",
    "away_team_id",
    "away_team_tricode",
    "is_home_team",
    "opponent_team_id",
    "opponent_team_tricode",
]
RAW_SCORING_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    *MATCHUP_CONTEXT_COLUMNS,
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
    "period_duration_seconds",
    "quarter_time_elapsed",
    "quarter_time_normalized",
    "elapsed_seconds_in_game",
    "elapsed_minutes_in_game",
    "game_minute",
    "total_game_seconds",
    "total_game_minutes",
    "game_time_normalized",
    "half_index",
    "half_label",
    "half_time_elapsed",
    "half_time_normalized",
    "is_overtime",
    "player_game_cumulative_points",
    "player_game_final_points",
    "player_quarter_cumulative_points",
    "player_quarter_final_points",
    "player_half_cumulative_points",
    "player_half_final_points",
    "cumulative_2pt_points",
    "cumulative_3pt_points",
    "cumulative_ft_points",
    "player_team_score_after",
    "opponent_score_after",
    "player_team_margin_after",
    "abs_margin_after",
    "score_diff",
    "abs_score_diff",
    "is_competitive_moment",
    "margin_bucket",
    "scoring_type",
    "competitiveness_bucket",
    "projected_48",
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
    *MATCHUP_CONTEXT_COLUMNS,
    "final_points",
    "num_scoring_events",
    "max_cumulative_points",
    "final_player_team_score",
    "final_opponent_score",
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
    "points_from_2s",
    "points_from_3s",
    "points_from_fts",
    "share_points_from_2s",
    "share_points_from_3s",
    "share_points_from_fts",
    "minutes_played",
    "points_per_minute",
    "offensive_share",
    "competitive_points",
    "competitive_scoring_share",
    "trailing_points",
    "trailing_scoring_rate",
    "peak_projected_48",
    "best_60_sec_points",
    "best_2_min_points",
    "best_3_min_points",
    "best_5_min_points",
    "best_10_min_points",
    "best_quarter_points",
    "best_half_points",
    "ts_pct",
    "efg_pct",
    "went_to_overtime",
    "total_game_minutes",
]
QUARTER_SUMMARY_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    "player_id",
    "player_name",
    "team_id",
    "team_tricode",
    *MATCHUP_CONTEXT_COLUMNS,
    "quarter_number",
    "quarter_label",
    "is_overtime_quarter",
    "quarter_points",
    "num_scoring_events",
    "quarter_duration_minutes",
    "points_per_minute",
    "interval_start_seconds_in_game",
    "interval_end_seconds_in_game",
    "avg_margin_during_scoring_events",
    "median_margin_during_scoring_events",
    "avg_abs_margin_during_scoring_events",
    "median_abs_margin_during_scoring_events",
    "competitive_points",
    "competitive_scoring_share",
    "points_from_2s",
    "points_from_3s",
    "points_from_fts",
    "share_points_from_2s",
    "share_points_from_3s",
    "share_points_from_fts",
]
HALF_SUMMARY_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    "player_id",
    "player_name",
    "team_id",
    "team_tricode",
    *MATCHUP_CONTEXT_COLUMNS,
    "half_index",
    "half_label",
    "half_points",
    "num_scoring_events",
    "half_duration_minutes",
    "points_per_minute",
    "interval_start_seconds_in_game",
    "interval_end_seconds_in_game",
    "avg_margin_during_scoring_events",
    "median_margin_during_scoring_events",
    "avg_abs_margin_during_scoring_events",
    "median_abs_margin_during_scoring_events",
    "competitive_points",
    "competitive_scoring_share",
    "points_from_2s",
    "points_from_3s",
    "points_from_fts",
    "share_points_from_2s",
    "share_points_from_3s",
    "share_points_from_fts",
]
BURST_SUMMARY_COLUMNS = [
    "season",
    "season_type",
    "game_date",
    "game_id",
    "player_id",
    "player_name",
    "team_id",
    "team_tricode",
    *MATCHUP_CONTEXT_COLUMNS,
    "burst_window_seconds",
    "burst_window_label",
    "points_in_window",
    "num_scoring_events",
    "window_start_seconds_in_game",
    "window_end_seconds_in_game",
    "start_period",
    "start_clock",
    "end_period",
    "end_clock",
    "includes_overtime",
    "window_points_per_minute",
    "avg_score_diff_in_window",
    "median_score_diff_in_window",
    "avg_abs_score_diff_in_window",
    "competitive_points_in_window",
    "competitive_scoring_share",
    "trailing_points_in_window",
    "points_from_2s",
    "points_from_3s",
    "points_from_fts",
    "share_points_from_2s",
    "share_points_from_3s",
    "share_points_from_fts",
]
BURST_TIMELINE_COLUMNS = TIMELINE_COLUMNS + [
    "burst_elapsed_seconds",
    "burst_elapsed_minutes",
    "burst_cumulative_points",
    "burst_window_seconds",
    "burst_window_label",
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
        return _ensure_metadata_columns(
            empty_df,
            season=season,
            season_type=season_type,
            game_date=game_date,
        )

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
    scoring = _ensure_matchup_context_columns(scoring)

    result = scoring[RAW_SCORING_COLUMNS].sort_values(["game_id", "action_id"]).reset_index(drop=True)
    return _ensure_metadata_columns(result, season=season, season_type=season_type, game_date=game_date)


def add_game_time_columns(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Add forward-moving and normalized game/quarter/half time columns."""
    if scoring_events_df.empty:
        return _ensure_matchup_context_columns(_ensure_metadata_columns(scoring_events_df.copy()))

    df = _ensure_matchup_context_columns(_ensure_metadata_columns(scoring_events_df.copy()))
    _require_columns(df, ["game_id", "period", "clock"])
    df["seconds_remaining_in_period"] = df["clock"].map(parse_clock_to_seconds_remaining)
    df["period_duration_seconds"] = df["period"].map(_period_duration_seconds).astype(float)
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

    quarter_elapsed_seconds = df["period_duration_seconds"] - df["seconds_remaining_in_period"]
    df["quarter_time_elapsed"] = quarter_elapsed_seconds / 60.0
    df["quarter_time_normalized"] = quarter_elapsed_seconds / df["period_duration_seconds"]

    df["elapsed_seconds_in_game"] = 0.0
    df.loc[regulation_mask, "elapsed_seconds_in_game"] = (
        (df.loc[regulation_mask, "period"] - 1) * 720
        + quarter_elapsed_seconds.loc[regulation_mask]
    )
    df.loc[~regulation_mask, "elapsed_seconds_in_game"] = (
        2880
        + (df.loc[~regulation_mask, "period"] - 5) * 300
        + quarter_elapsed_seconds.loc[~regulation_mask]
    )
    df["elapsed_minutes_in_game"] = df["elapsed_seconds_in_game"] / 60.0
    df["game_minute"] = df["elapsed_minutes_in_game"]
    game_max_period = (
        df.groupby("game_id", dropna=False)["period"].transform("max").astype("Int64")
    )
    df["total_game_seconds"] = game_max_period.map(_total_game_seconds_from_period).astype(float)
    df["total_game_minutes"] = df["total_game_seconds"] / 60.0
    df["game_time_normalized"] = df["elapsed_seconds_in_game"] / df["total_game_seconds"]
    df["is_overtime"] = df["period"] > 4

    df["half_index"] = pd.NA
    df.loc[df["period"].between(1, 2), "half_index"] = 1
    df.loc[df["period"].between(3, 4), "half_index"] = 2
    df["half_label"] = df["half_index"].map({1: "1H", 2: "2H"})
    df.loc[df["is_overtime"], "half_label"] = "OT"
    df["half_time_elapsed"] = pd.NA
    df.loc[df["period"].between(1, 2), "half_time_elapsed"] = (
        df.loc[df["period"].between(1, 2), "elapsed_seconds_in_game"] / 60.0
    )
    df.loc[df["period"].between(3, 4), "half_time_elapsed"] = (
        (df.loc[df["period"].between(3, 4), "elapsed_seconds_in_game"] - 1440.0) / 60.0
    )
    df["half_time_normalized"] = pd.NA
    half_mask = df["half_index"].notna()
    df.loc[half_mask, "half_time_normalized"] = pd.to_numeric(
        df.loc[half_mask, "half_time_elapsed"], errors="coerce"
    ) / 24.0
    return df


def add_score_context_columns(
    scoring_events_df: pd.DataFrame,
    competitive_margin_threshold: int = COMPETITIVE_MARGIN_THRESHOLD,
) -> pd.DataFrame:
    """Add scorer-perspective score differential context columns."""
    if scoring_events_df.empty:
        return _ensure_matchup_context_columns(_ensure_metadata_columns(scoring_events_df.copy()))

    df = _ensure_matchup_context_columns(_ensure_metadata_columns(scoring_events_df.copy()))
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
    df["score_diff"] = df["player_team_margin_after"]
    df["abs_score_diff"] = df["abs_margin_after"]
    df["is_competitive_moment"] = df["abs_score_diff"] <= competitive_margin_threshold
    df["scoring_type"] = df.apply(_scoring_type_label, axis=1)
    df["competitiveness_bucket"] = df["abs_margin_after"].map(_competitiveness_bucket)
    df["margin_bucket"] = df["score_diff"].map(_margin_bucket)
    return df


def build_player_scoring_timeline(
    scoring_events_df: pd.DataFrame,
    player_id: int | None = None,
    player_name: str | None = None,
    game_id: str | None = None,
) -> pd.DataFrame:
    """Build a chart-ready cumulative scoring timeline with normalized analytics fields."""
    df = _ensure_matchup_context_columns(_ensure_metadata_columns(scoring_events_df.copy()))
    _require_columns(df, ["game_id", "action_id", "player_id", "player_name", "point_value"])
    if "seconds_remaining_in_period" not in df.columns:
        df = add_game_time_columns(df)
    if "player_team_margin_after" not in df.columns:
        df = add_score_context_columns(df)

    df = df.sort_values(["game_id", "action_id"]).reset_index(drop=True)
    df = _with_point_component_columns(df)
    player_game_columns = ["season", "season_type", "game_date", "game_id", "player_id"]
    player_quarter_columns = player_game_columns + ["period"]
    player_half_columns = player_game_columns + ["half_index"]

    df["player_game_cumulative_points"] = (
        df.groupby(player_game_columns, dropna=False)["point_value"].cumsum().astype("Int64")
    )
    df["player_game_final_points"] = (
        df.groupby(player_game_columns, dropna=False)["point_value"].transform("sum").astype("Int64")
    )
    df["player_quarter_cumulative_points"] = (
        df.groupby(player_quarter_columns, dropna=False)["point_value"].cumsum().astype("Int64")
    )
    df["player_quarter_final_points"] = (
        df.groupby(player_quarter_columns, dropna=False)["point_value"].transform("sum").astype("Int64")
    )
    df["player_half_cumulative_points"] = pd.NA
    df["player_half_final_points"] = pd.NA
    half_mask = df["half_index"].notna()
    df.loc[half_mask, "player_half_cumulative_points"] = (
        df.loc[half_mask]
        .groupby(player_half_columns, dropna=False)["point_value"]
        .cumsum()
        .astype("Int64")
    )
    df.loc[half_mask, "player_half_final_points"] = (
        df.loc[half_mask]
        .groupby(player_half_columns, dropna=False)["point_value"]
        .transform("sum")
        .astype("Int64")
    )

    df["cumulative_2pt_points"] = (
        df.groupby(player_game_columns, dropna=False)["points_2pt"].cumsum().astype("Int64")
    )
    df["cumulative_3pt_points"] = (
        df.groupby(player_game_columns, dropna=False)["points_3pt"].cumsum().astype("Int64")
    )
    df["cumulative_ft_points"] = (
        df.groupby(player_game_columns, dropna=False)["points_ft"].cumsum().astype("Int64")
    )
    elapsed_minutes = df["elapsed_minutes_in_game"].astype(float)
    df["projected_48"] = pd.NA
    valid_projection = elapsed_minutes >= 1.0
    df.loc[valid_projection, "projected_48"] = (
        df.loc[valid_projection, "player_game_cumulative_points"].astype(float)
        / elapsed_minutes.loc[valid_projection]
        * 48.0
    )

    if game_id is not None:
        df = df.loc[df["game_id"].eq(str(game_id))]
    if player_id is not None:
        df = df.loc[df["player_id"].eq(player_id)]
    if player_name is not None:
        df = df.loc[df["player_name"].str.casefold().eq(player_name.casefold())]

    return df[TIMELINE_COLUMNS].reset_index(drop=True)


def build_quarter_timeline(
    timeline_df: pd.DataFrame,
    game_id: str,
    player_id: int,
    quarter_number: int,
) -> pd.DataFrame:
    """Select one player-quarter trajectory from the chart-ready timeline dataset."""
    df = _coerce_to_timeline(timeline_df)
    quarter_df = df.loc[
        df["game_id"].eq(str(game_id))
        & df["player_id"].eq(player_id)
        & df["period"].eq(int(quarter_number))
    ].copy()
    return quarter_df.sort_values(["game_id", "action_id"]).reset_index(drop=True)


def build_half_timeline(
    timeline_df: pd.DataFrame,
    game_id: str,
    player_id: int,
    half_index: int,
) -> pd.DataFrame:
    """Select one player-half trajectory from the chart-ready timeline dataset."""
    df = _coerce_to_timeline(timeline_df)
    half_df = df.loc[
        df["game_id"].eq(str(game_id))
        & df["player_id"].eq(player_id)
        & df["half_index"].eq(int(half_index))
    ].copy()
    return half_df.sort_values(["game_id", "action_id"]).reset_index(drop=True)


def build_burst_timeline(
    timeline_df: pd.DataFrame,
    burst_summary_row: dict[str, Any] | pd.Series,
) -> pd.DataFrame:
    """Select one player-burst trajectory and derive burst-local chart fields."""
    df = _coerce_to_timeline(timeline_df)
    burst = dict(burst_summary_row)
    required = [
        "game_id",
        "player_id",
        "window_start_seconds_in_game",
        "window_end_seconds_in_game",
        "burst_window_seconds",
        "burst_window_label",
    ]
    missing = [column for column in required if column not in burst]
    if missing:
        raise ValueError(f"burst_summary_row is missing required fields: {missing}")

    start_seconds = float(burst["window_start_seconds_in_game"])
    end_seconds = float(burst["window_end_seconds_in_game"])
    burst_df = df.loc[
        df["game_id"].eq(str(burst["game_id"]))
        & df["player_id"].eq(int(burst["player_id"]))
        & df["elapsed_seconds_in_game"].between(start_seconds, end_seconds, inclusive="both")
    ].copy()
    burst_df = burst_df.sort_values(["game_id", "action_id"]).reset_index(drop=True)
    if burst_df.empty:
        empty = df.iloc[0:0].copy()
        empty["burst_elapsed_seconds"] = pd.Series(dtype="float64")
        empty["burst_elapsed_minutes"] = pd.Series(dtype="float64")
        empty["burst_cumulative_points"] = pd.Series(dtype="Int64")
        empty["burst_window_seconds"] = pd.Series(dtype="Int64")
        empty["burst_window_label"] = pd.Series(dtype="string")
        return empty[BURST_TIMELINE_COLUMNS]

    baseline = int(burst_df.iloc[0]["player_game_cumulative_points"]) - int(burst_df.iloc[0]["point_value"])
    burst_df["burst_elapsed_seconds"] = burst_df["elapsed_seconds_in_game"] - start_seconds
    burst_df["burst_elapsed_minutes"] = burst_df["burst_elapsed_seconds"] / 60.0
    burst_df["burst_cumulative_points"] = (
        burst_df["player_game_cumulative_points"].astype(int) - baseline
    ).astype("Int64")
    burst_df["burst_window_seconds"] = int(burst["burst_window_seconds"])
    burst_df["burst_window_label"] = str(burst["burst_window_label"])
    return burst_df[BURST_TIMELINE_COLUMNS]


def summarize_player_games(
    scoring_events_df: pd.DataFrame,
    boxscore_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate one row per player-game for ranking and filtering."""
    timeline = build_player_scoring_timeline(scoring_events_df)
    if timeline.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    timeline = timeline.sort_values(["game_id", "player_id", "action_id"]).reset_index(drop=True)
    timeline = _with_point_component_columns(timeline)
    game_columns = ["season", "season_type", "game_date", "game_id"]
    group_columns = game_columns + ["player_id", "player_name", "team_id", "team_tricode"]

    game_final_scores = (
        timeline.groupby(game_columns, dropna=False, as_index=False)
        .agg(
            final_score_home=("score_home", "last"),
            final_score_away=("score_away", "last"),
            total_game_minutes=("total_game_minutes", "max"),
        )
    )
    summary = (
        timeline.groupby(group_columns, dropna=False, as_index=False)
        .agg(
            player_location=("location", "first"),
            home_team_id=("home_team_id", "first"),
            home_team_tricode=("home_team_tricode", "first"),
            away_team_id=("away_team_id", "first"),
            away_team_tricode=("away_team_tricode", "first"),
            is_home_team=("is_home_team", "first"),
            opponent_team_id=("opponent_team_id", "first"),
            opponent_team_tricode=("opponent_team_tricode", "first"),
            final_points=("point_value", "sum"),
            num_scoring_events=("point_value", "size"),
            max_cumulative_points=("player_game_cumulative_points", "max"),
            avg_margin_during_scoring_events=("player_team_margin_after", "mean"),
            median_margin_during_scoring_events=("player_team_margin_after", "median"),
            avg_abs_margin_during_scoring_events=("abs_margin_after", "mean"),
            median_abs_margin_during_scoring_events=("abs_margin_after", "median"),
            pct_scoring_events_within_3=("abs_score_diff", lambda s: float((s <= 3).mean())),
            pct_scoring_events_within_5=("abs_score_diff", lambda s: float((s <= 5).mean())),
            pct_scoring_events_within_10=("abs_score_diff", lambda s: float((s <= 10).mean())),
            max_lead_during_scoring_events=("score_diff", lambda s: int(s.clip(lower=0).max())),
            max_deficit_during_scoring_events=("score_diff", lambda s: int((-s.clip(upper=0)).max())),
            points_from_2s=("points_2pt", "sum"),
            points_from_3s=("points_3pt", "sum"),
            points_from_fts=("points_ft", "sum"),
            competitive_points=("competitive_point_value", "sum"),
            trailing_points=("trailing_point_value", "sum"),
            peak_projected_48=("projected_48", lambda s: float(pd.to_numeric(s, errors="coerce").max()) if pd.to_numeric(s, errors="coerce").notna().any() else pd.NA),
        )
        .sort_values(["final_points", "game_id", "player_id"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    summary = summary.merge(game_final_scores, on=game_columns, how="left")
    is_home = summary["player_location"].eq("h")
    summary["final_player_team_score"] = (
        summary["final_score_home"].where(is_home, summary["final_score_away"])
    ).astype("Int64")
    summary["final_opponent_score"] = (
        summary["final_score_away"].where(is_home, summary["final_score_home"])
    ).astype("Int64")
    summary["final_player_team_margin"] = (
        summary["final_player_team_score"] - summary["final_opponent_score"]
    ).astype("Int64")
    summary["offensive_share"] = (
        summary["final_points"].astype(float)
        / summary["final_player_team_score"].astype(float)
    )
    summary["share_points_from_2s"] = _safe_ratio(summary["points_from_2s"], summary["final_points"])
    summary["share_points_from_3s"] = _safe_ratio(summary["points_from_3s"], summary["final_points"])
    summary["share_points_from_fts"] = _safe_ratio(summary["points_from_fts"], summary["final_points"])
    summary["competitive_scoring_share"] = _safe_ratio(summary["competitive_points"], summary["final_points"])
    summary["went_to_overtime"] = summary["total_game_minutes"].astype(float) > 48.0

    if boxscore_df is not None and not boxscore_df.empty:
        metrics = _prepare_boxscore_metrics(boxscore_df)
        summary = summary.merge(metrics, on=["game_id", "team_id", "player_id"], how="left")
    else:
        summary["minutes_played"] = pd.NA
        summary["ts_pct"] = pd.NA
        summary["efg_pct"] = pd.NA

    summary["points_per_minute"] = _safe_ratio(summary["final_points"], summary["minutes_played"])
    summary["trailing_scoring_rate"] = _safe_ratio(summary["trailing_points"], summary["minutes_played"])

    quarter_summary = summarize_player_quarters(scoring_events_df)
    half_summary = summarize_player_halves(scoring_events_df)
    burst_summary = summarize_player_bursts(scoring_events_df)

    summary = summary.merge(
        quarter_summary.groupby(["game_id", "player_id"], as_index=False)
        .agg(best_quarter_points=("quarter_points", "max")),
        on=["game_id", "player_id"],
        how="left",
    )
    summary = summary.merge(
        half_summary.groupby(["game_id", "player_id"], as_index=False)
        .agg(best_half_points=("half_points", "max")),
        on=["game_id", "player_id"],
        how="left",
    )
    burst_pivot = (
        burst_summary.pivot_table(
            index=["game_id", "player_id"],
            columns="burst_window_seconds",
            values="points_in_window",
            aggfunc="first",
        )
        .rename(
            columns={
                60: "best_60_sec_points",
                120: "best_2_min_points",
                180: "best_3_min_points",
                300: "best_5_min_points",
                600: "best_10_min_points",
            }
        )
        .reset_index()
    )
    summary = summary.merge(burst_pivot, on=["game_id", "player_id"], how="left")
    for column in [
        "best_60_sec_points",
        "best_2_min_points",
        "best_3_min_points",
        "best_5_min_points",
        "best_10_min_points",
        "best_quarter_points",
        "best_half_points",
    ]:
        if column not in summary.columns:
            summary[column] = pd.NA

    summary = summary.drop(columns=["player_location", "final_score_home", "final_score_away"])
    return summary[SUMMARY_COLUMNS]


def summarize_player_quarters(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one row per player-quarter."""
    timeline = build_player_scoring_timeline(scoring_events_df)
    if timeline.empty:
        return pd.DataFrame(columns=QUARTER_SUMMARY_COLUMNS)

    group_columns = [
        "season",
        "season_type",
        "game_date",
        "game_id",
        "player_id",
        "player_name",
        "team_id",
        "team_tricode",
        *MATCHUP_CONTEXT_COLUMNS,
        "period",
    ]
    summary = (
        timeline.groupby(group_columns, dropna=False, as_index=False)
        .apply(_aggregate_interval_summary, entity="quarter")
        .reset_index(drop=True)
    )
    summary["quarter_number"] = summary["period"].astype("Int64")
    summary["quarter_label"] = summary["quarter_number"].map(_period_label)
    summary["is_overtime_quarter"] = summary["quarter_number"].astype(int) > 4
    summary = summary.rename(
        columns={
            "interval_points": "quarter_points",
            "interval_duration_minutes": "quarter_duration_minutes",
        }
    )
    return summary[QUARTER_SUMMARY_COLUMNS]


def summarize_player_halves(scoring_events_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one row per player-half for regulation halves only."""
    timeline = build_player_scoring_timeline(scoring_events_df)
    if timeline.empty:
        return pd.DataFrame(columns=HALF_SUMMARY_COLUMNS)

    timeline = timeline.loc[timeline["half_index"].notna()].copy()
    if timeline.empty:
        return pd.DataFrame(columns=HALF_SUMMARY_COLUMNS)

    group_columns = [
        "season",
        "season_type",
        "game_date",
        "game_id",
        "player_id",
        "player_name",
        "team_id",
        "team_tricode",
        *MATCHUP_CONTEXT_COLUMNS,
        "half_index",
        "half_label",
    ]
    summary = (
        timeline.groupby(group_columns, dropna=False, as_index=False)
        .apply(_aggregate_interval_summary, entity="half")
        .reset_index(drop=True)
    )
    summary = summary.rename(
        columns={
            "interval_points": "half_points",
            "interval_duration_minutes": "half_duration_minutes",
        }
    )
    return summary[HALF_SUMMARY_COLUMNS]


def summarize_player_bursts(
    scoring_events_df: pd.DataFrame,
    window_seconds: Iterable[int] = BURST_WINDOW_SECONDS,
) -> pd.DataFrame:
    """Aggregate one row per player-game burst window."""
    timeline = build_player_scoring_timeline(scoring_events_df)
    if timeline.empty:
        return pd.DataFrame(columns=BURST_SUMMARY_COLUMNS)

    results: list[dict[str, Any]] = []
    for (_, _, _, game_id, player_id), player_df in timeline.groupby(
        ["season", "season_type", "game_date", "game_id", "player_id"],
        dropna=False,
    ):
        player_df = player_df.sort_values(["elapsed_seconds_in_game", "action_id"]).reset_index(drop=True)
        base_row = player_df.iloc[0]
        for window in window_seconds:
            burst = _best_burst_window(player_df, int(window))
            results.append(
                {
                    "season": base_row["season"],
                    "season_type": base_row["season_type"],
                    "game_date": base_row["game_date"],
                    "game_id": game_id,
                    "player_id": player_id,
                    "player_name": base_row["player_name"],
                    "team_id": base_row["team_id"],
                    "team_tricode": base_row["team_tricode"],
                    "home_team_id": base_row["home_team_id"],
                    "home_team_tricode": base_row["home_team_tricode"],
                    "away_team_id": base_row["away_team_id"],
                    "away_team_tricode": base_row["away_team_tricode"],
                    "is_home_team": base_row["is_home_team"],
                    "opponent_team_id": base_row["opponent_team_id"],
                    "opponent_team_tricode": base_row["opponent_team_tricode"],
                    "burst_window_seconds": int(window),
                    "burst_window_label": _burst_window_label(int(window)),
                    **burst,
                }
            )
    if not results:
        return pd.DataFrame(columns=BURST_SUMMARY_COLUMNS)
    return pd.DataFrame(results)[BURST_SUMMARY_COLUMNS]


def parse_clock_to_seconds_remaining(clock: str) -> float:
    """Parse PlayByPlayV3 clock strings like PT11M47.00S into seconds remaining."""
    match = CLOCK_PATTERN.fullmatch(str(clock))
    if not match:
        raise ValueError(f"Unsupported clock format: {clock!r}")

    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0.0)
    return minutes * 60 + seconds


def _aggregate_interval_summary(group_df: pd.DataFrame, entity: str) -> pd.Series:
    interval_points = int(group_df["point_value"].sum())
    duration_minutes = _interval_duration_minutes(group_df, entity)
    points_from_2s = int(group_df.loc[group_df["scoring_type"].eq("2PT"), "point_value"].sum())
    points_from_3s = int(group_df.loc[group_df["scoring_type"].eq("3PT"), "point_value"].sum())
    points_from_fts = int(group_df.loc[group_df["scoring_type"].eq("FT"), "point_value"].sum())
    competitive_points = int(group_df.loc[group_df["is_competitive_moment"], "point_value"].sum())
    return pd.Series(
        {
            "interval_points": interval_points,
            "num_scoring_events": int(len(group_df)),
            "interval_duration_minutes": duration_minutes,
            "points_per_minute": _safe_scalar_ratio(interval_points, duration_minutes),
            "interval_start_seconds_in_game": float(group_df["elapsed_seconds_in_game"].min()),
            "interval_end_seconds_in_game": float(group_df["elapsed_seconds_in_game"].max()),
            "avg_margin_during_scoring_events": float(group_df["score_diff"].mean()),
            "median_margin_during_scoring_events": float(group_df["score_diff"].median()),
            "avg_abs_margin_during_scoring_events": float(group_df["abs_score_diff"].mean()),
            "median_abs_margin_during_scoring_events": float(group_df["abs_score_diff"].median()),
            "competitive_points": competitive_points,
            "competitive_scoring_share": _safe_scalar_ratio(competitive_points, interval_points),
            "points_from_2s": points_from_2s,
            "points_from_3s": points_from_3s,
            "points_from_fts": points_from_fts,
            "share_points_from_2s": _safe_scalar_ratio(points_from_2s, interval_points),
            "share_points_from_3s": _safe_scalar_ratio(points_from_3s, interval_points),
            "share_points_from_fts": _safe_scalar_ratio(points_from_fts, interval_points),
        }
    )


def _best_burst_window(player_df: pd.DataFrame, window_seconds: int) -> dict[str, Any]:
    times = player_df["elapsed_seconds_in_game"].astype(float).tolist()
    points = player_df["point_value"].astype(int).tolist()
    left = 0
    running_points = 0
    best_left = 0
    best_right = 0
    best_points = -1

    for right, point_value in enumerate(points):
        running_points += point_value
        while times[right] - times[left] > window_seconds:
            running_points -= points[left]
            left += 1
        current_points = running_points
        current_span = times[right] - times[left]
        best_span = times[best_right] - times[best_left]
        if (
            current_points > best_points
            or (
                current_points == best_points
                and (
                    current_span < best_span
                    or (
                        current_span == best_span
                        and times[left] < times[best_left]
                    )
                )
            )
        ):
            best_points = current_points
            best_left = left
            best_right = right

    interval_df = player_df.iloc[best_left : best_right + 1].copy()
    start_row = interval_df.iloc[0]
    end_row = interval_df.iloc[-1]
    points_from_2s = int(interval_df.loc[interval_df["scoring_type"].eq("2PT"), "point_value"].sum())
    points_from_3s = int(interval_df.loc[interval_df["scoring_type"].eq("3PT"), "point_value"].sum())
    points_from_fts = int(interval_df.loc[interval_df["scoring_type"].eq("FT"), "point_value"].sum())
    competitive_points = int(interval_df.loc[interval_df["is_competitive_moment"], "point_value"].sum())
    trailing_points = int(interval_df.loc[interval_df["score_diff"] < 0, "point_value"].sum())
    return {
        "points_in_window": int(interval_df["point_value"].sum()),
        "num_scoring_events": int(len(interval_df)),
        "window_start_seconds_in_game": float(start_row["elapsed_seconds_in_game"]),
        "window_end_seconds_in_game": float(
            min(
                float(start_row["elapsed_seconds_in_game"]) + float(window_seconds),
                float(player_df["total_game_seconds"].iloc[0]),
            )
        ),
        "start_period": int(start_row["period"]),
        "start_clock": str(start_row["clock"]),
        "end_period": int(end_row["period"]),
        "end_clock": str(end_row["clock"]),
        "includes_overtime": bool(interval_df["is_overtime"].any()),
        "window_points_per_minute": _safe_scalar_ratio(interval_df["point_value"].sum(), window_seconds / 60.0),
        "avg_score_diff_in_window": float(interval_df["score_diff"].mean()),
        "median_score_diff_in_window": float(interval_df["score_diff"].median()),
        "avg_abs_score_diff_in_window": float(interval_df["abs_score_diff"].mean()),
        "competitive_points_in_window": competitive_points,
        "competitive_scoring_share": _safe_scalar_ratio(competitive_points, interval_df["point_value"].sum()),
        "trailing_points_in_window": trailing_points,
        "points_from_2s": points_from_2s,
        "points_from_3s": points_from_3s,
        "points_from_fts": points_from_fts,
        "share_points_from_2s": _safe_scalar_ratio(points_from_2s, interval_df["point_value"].sum()),
        "share_points_from_3s": _safe_scalar_ratio(points_from_3s, interval_df["point_value"].sum()),
        "share_points_from_fts": _safe_scalar_ratio(points_from_fts, interval_df["point_value"].sum()),
    }


def _prepare_boxscore_metrics(boxscore_df: pd.DataFrame) -> pd.DataFrame:
    metrics = boxscore_df.copy()
    required = ["game_id", "team_id", "player_id"]
    _require_columns(metrics, required)
    metrics["minutes_played"] = pd.to_numeric(metrics.get("minutes_played"), errors="coerce")
    metrics["field_goals_made"] = pd.to_numeric(metrics.get("field_goals_made"), errors="coerce")
    metrics["field_goals_attempted"] = pd.to_numeric(metrics.get("field_goals_attempted"), errors="coerce")
    metrics["three_pointers_made"] = pd.to_numeric(metrics.get("three_pointers_made"), errors="coerce")
    metrics["free_throws_attempted"] = pd.to_numeric(metrics.get("free_throws_attempted"), errors="coerce")
    metrics["official_points"] = pd.to_numeric(metrics.get("official_points"), errors="coerce")

    metrics["ts_pct"] = pd.NA
    ts_denom = 2 * (metrics["field_goals_attempted"] + 0.44 * metrics["free_throws_attempted"])
    valid_ts = ts_denom > 0
    metrics.loc[valid_ts, "ts_pct"] = metrics.loc[valid_ts, "official_points"] / ts_denom.loc[valid_ts]

    metrics["efg_pct"] = pd.NA
    valid_efg = metrics["field_goals_attempted"] > 0
    metrics.loc[valid_efg, "efg_pct"] = (
        metrics.loc[valid_efg, "field_goals_made"]
        + 0.5 * metrics.loc[valid_efg, "three_pointers_made"]
    ) / metrics.loc[valid_efg, "field_goals_attempted"]
    return metrics[["game_id", "team_id", "player_id", "minutes_played", "ts_pct", "efg_pct"]]


def _interval_duration_minutes(group_df: pd.DataFrame, entity: str) -> float:
    first_row = group_df.iloc[0]
    if entity == "quarter":
        return float(first_row["period_duration_seconds"]) / 60.0
    if entity == "half":
        return 24.0
    raise ValueError(f"Unsupported entity for interval summary: {entity}")


def _period_duration_seconds(period: int) -> int:
    return 720 if int(period) <= 4 else 300


def _total_game_seconds_from_period(max_period: int) -> int:
    max_period_int = int(max_period)
    if max_period_int <= 4:
        return 2880
    return 2880 + ((max_period_int - 4) * 300)


def _period_label(period: int) -> str:
    period_int = int(period)
    if period_int <= 4:
        return f"Q{period_int}"
    return f"OT{period_int - 4}"


def _burst_window_label(window_seconds: int) -> str:
    if window_seconds < 60:
        return f"{window_seconds}s"
    if window_seconds % 60 == 0:
        minutes = window_seconds // 60
        return f"{minutes}m"
    return f"{window_seconds / 60.0:.1f}m"


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


def _ensure_matchup_context_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    for column in MATCHUP_CONTEXT_COLUMNS:
        if column not in enriched.columns:
            enriched[column] = pd.NA
    return enriched


def _coerce_to_timeline(df: pd.DataFrame) -> pd.DataFrame:
    if "player_game_cumulative_points" in df.columns:
        return _ensure_matchup_context_columns(df.copy())
    return build_player_scoring_timeline(df)


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


def _with_point_component_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    point_values = pd.to_numeric(enriched["point_value"], errors="coerce").fillna(0).astype(int)
    enriched["points_2pt"] = point_values.where(enriched["scoring_type"].eq("2PT"), 0)
    enriched["points_3pt"] = point_values.where(enriched["scoring_type"].eq("3PT"), 0)
    enriched["points_ft"] = point_values.where(enriched["scoring_type"].eq("FT"), 0)
    enriched["competitive_point_value"] = point_values.where(enriched["is_competitive_moment"], 0)
    enriched["trailing_point_value"] = point_values.where(enriched["score_diff"] < 0, 0)
    return enriched


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


def _margin_bucket(score_diff: int) -> str:
    if abs(int(score_diff)) <= 3:
        return "within_3"
    if int(score_diff) <= -10:
        return "trailing_10_plus"
    if int(score_diff) < 0:
        return "trailing_1_9"
    if int(score_diff) >= 10:
        return "leading_10_plus"
    return "leading_1_9"


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator_values = pd.to_numeric(numerator, errors="coerce")
    denominator_values = pd.to_numeric(denominator, errors="coerce")
    result = pd.Series(pd.NA, index=numerator.index, dtype="Float64")
    valid = denominator_values.notna() & denominator_values.ne(0)
    result.loc[valid] = numerator_values.loc[valid] / denominator_values.loc[valid]
    return result


def _safe_scalar_ratio(numerator: float | int, denominator: float | int) -> float | None:
    if denominator in {0, 0.0} or pd.isna(denominator):
        return None
    return float(numerator) / float(denominator)
