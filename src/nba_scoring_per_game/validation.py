from __future__ import annotations

from typing import Any

import pandas as pd

from .source import fetch_boxscore_player_totals, fetch_playbyplay
from .transforms import (
    SCORING_ACTION_TYPES,
    build_player_scoring_timeline,
    extract_scoring_events,
    summarize_player_games,
)


def validate_game(
    game_id: str,
    scoring_events_df: pd.DataFrame | None = None,
    raw_df: pd.DataFrame | None = None,
    boxscore_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Run a compact set of empirical validation checks for one game."""
    if raw_df is None:
        raw_df = fetch_playbyplay(game_id)
    if scoring_events_df is None:
        scoring_events_df = extract_scoring_events(raw_df, game_id=game_id)
    if boxscore_df is None:
        boxscore_df = fetch_boxscore_player_totals(game_id)

    scoring_events_df = scoring_events_df.loc[scoring_events_df["game_id"].eq(str(game_id))].copy()
    if scoring_events_df.empty:
        raise ValueError(f"No scoring events available for game_id={game_id}")

    timeline = build_player_scoring_timeline(scoring_events_df)
    summary = summarize_player_games(scoring_events_df)

    player_check = summary[["game_id", "team_id", "player_id", "final_points"]].merge(
        boxscore_df[["game_id", "team_id", "player_id", "official_points"]],
        on=["game_id", "team_id", "player_id"],
        how="left",
    )
    player_mismatches = player_check.loc[
        player_check["final_points"].astype(float) != player_check["official_points"].astype(float)
    ]

    team_points = (
        boxscore_df.groupby("team_id", dropna=False)["official_points"]
        .sum()
        .astype(int)
        .to_dict()
    )
    ordered_scoring = scoring_events_df.sort_values(["game_id", "action_id"]).reset_index(drop=True)
    final_score_row = ordered_scoring.iloc[-1]
    home_team_rows = ordered_scoring.loc[ordered_scoring["location"].eq("h"), "team_id"]
    away_team_rows = ordered_scoring.loc[ordered_scoring["location"].eq("v"), "team_id"]
    home_team_id = home_team_rows.iloc[0] if not home_team_rows.empty else pd.NA
    away_team_id = away_team_rows.iloc[0] if not away_team_rows.empty else pd.NA
    final_score_matches_boxscore = bool(
        home_team_id in team_points
        and away_team_id in team_points
        and int(final_score_row["score_home"]) == int(team_points[home_team_id])
        and int(final_score_row["score_away"]) == int(team_points[away_team_id])
    )

    scoring_rows_raw = _sort_raw_playbyplay(raw_df).copy()
    scoring_rows_raw = scoring_rows_raw.loc[
        scoring_rows_raw["actionType"].isin(SCORING_ACTION_TYPES)
        & (pd.to_numeric(scoring_rows_raw["pointsTotal"], errors="coerce").fillna(0) > 0)
    ].copy()
    scoring_rows_raw["scoreHome"] = pd.to_numeric(scoring_rows_raw["scoreHome"], errors="coerce")
    scoring_rows_raw["scoreAway"] = pd.to_numeric(scoring_rows_raw["scoreAway"], errors="coerce")
    scoring_rows_raw["pointsTotal"] = pd.to_numeric(scoring_rows_raw["pointsTotal"], errors="coerce")
    source_is_field_goal_consistent = bool(
        (
            (scoring_rows_raw["actionType"].eq("Made Shot") & scoring_rows_raw["isFieldGoal"].eq(1))
            | (scoring_rows_raw["actionType"].eq("Free Throw") & scoring_rows_raw["isFieldGoal"].eq(0))
        ).all()
    )
    missing_identity_count = int(
        (
            pd.to_numeric(scoring_rows_raw["teamId"], errors="coerce").isna()
            | pd.to_numeric(scoring_rows_raw["personId"], errors="coerce").isna()
            | scoring_rows_raw["teamTricode"].fillna("").eq("")
            | scoring_rows_raw["playerName"].fillna("").eq("")
        ).sum()
    )
    points_total_matches_running_score = bool(
        (scoring_rows_raw["pointsTotal"] == scoring_rows_raw["scoreHome"] + scoring_rows_raw["scoreAway"]).all()
    )
    free_throw_point_values_all_one = bool(
        scoring_events_df.loc[scoring_events_df["action_type"].eq("Free Throw"), "point_value"].eq(1).all()
    )

    home_rows = timeline.loc[timeline["location"].eq("h")]
    away_rows = timeline.loc[timeline["location"].eq("v")]
    home_margin_check_passed = False
    away_margin_check_passed = False
    if not home_rows.empty:
        home_margin_row = home_rows.iloc[0]
        home_margin_check_passed = int(home_margin_row["player_team_margin_after"]) == int(
            home_margin_row["score_home"] - home_margin_row["score_away"]
        )
    if not away_rows.empty:
        away_margin_row = away_rows.iloc[0]
        away_margin_check_passed = int(away_margin_row["player_team_margin_after"]) == int(
            away_margin_row["score_away"] - away_margin_row["score_home"]
        )

    first_row = scoring_events_df.iloc[0]
    report = {
        "season": first_row.get("season"),
        "season_type": first_row.get("season_type"),
        "game_date": first_row.get("game_date"),
        "game_id": game_id,
        "num_scoring_events": int(len(scoring_events_df)),
        "points_total_matches_running_score": points_total_matches_running_score,
        "source_is_field_goal_consistent": source_is_field_goal_consistent,
        "free_throw_point_values_all_one": free_throw_point_values_all_one,
        "missing_scoring_identity_count": missing_identity_count,
        "action_number_is_monotonic": bool(
            pd.to_numeric(raw_df["actionNumber"], errors="coerce").is_monotonic_increasing
        ),
        "action_id_is_monotonic": bool(
            pd.to_numeric(raw_df["actionId"], errors="coerce").is_monotonic_increasing
        ),
        "action_number_duplicate_count": int(raw_df["actionNumber"].duplicated().sum()),
        "scoring_action_id_duplicate_count": int(
            scoring_events_df[["game_id", "action_id"]].duplicated().sum()
        ),
        "multiple_scoring_events_same_clock": bool(
            scoring_events_df.groupby(["period", "clock"]).size().gt(1).any()
        ),
        "home_margin_check_passed": home_margin_check_passed,
        "away_margin_check_passed": away_margin_check_passed,
        "num_player_total_mismatches": int(len(player_mismatches)),
        "final_score_matches_boxscore": final_score_matches_boxscore,
        "max_period": int(pd.to_numeric(raw_df["period"], errors="coerce").max()),
        "player_total_mismatch_rows": player_mismatches.to_dict(orient="records"),
    }
    report["validation_passed"] = bool(
        report["final_score_matches_boxscore"]
        and report["points_total_matches_running_score"]
        and report["source_is_field_goal_consistent"]
        and report["free_throw_point_values_all_one"]
        and report["missing_scoring_identity_count"] == 0
        and report["scoring_action_id_duplicate_count"] == 0
        and report["num_player_total_mismatches"] == 0
        and report["home_margin_check_passed"]
        and report["away_margin_check_passed"]
    )
    return report


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
