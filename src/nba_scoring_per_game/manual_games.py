from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import DATASET_METADATA_FILENAME, get_dataset_metadata
from .transforms import (
    BURST_SUMMARY_COLUMNS,
    HALF_SUMMARY_COLUMNS,
    QUARTER_SUMMARY_COLUMNS,
    RAW_SCORING_COLUMNS,
    SUMMARY_COLUMNS,
    TIMELINE_COLUMNS,
    build_player_scoring_timeline,
    summarize_player_bursts,
    summarize_player_games,
    summarize_player_halves,
    summarize_player_quarters,
)
from .source import BOX_SCORE_COLUMNS


@dataclass(frozen=True, slots=True)
class QuarterApproximation:
    quarter_number: int
    field_goals_made: int
    field_goals_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    rebounds: int
    assists: int
    personal_fouls: int
    points: int


WILT_100_GAME_ID = "LG19620302WILT100"
WILT_100_PLAYER_ID = 90000100
WILT_100_TEAM_ID = 1610612744
WILT_100_OPPONENT_TEAM_ID = 1610612752
WILT_100_SEASON = "1961-62"
WILT_100_SEASON_TYPE = "Regular Season"
WILT_100_GAME_DATE = "1962-03-02"
WILT_100_PLAYER_NAME = "Chamberlain"
WILT_100_TEAM_TRICODE = "PHW"
WILT_100_OPPONENT_TRICODE = "NYK"
WILT_100_FINAL_HOME_SCORE = 169
WILT_100_FINAL_AWAY_SCORE = 147
WILT_100_TOTAL_MINUTES = 48.0
WILT_100_TEAMMATE_POINTS = WILT_100_FINAL_HOME_SCORE - 100
WILT_100_OPPONENT_POINTS = WILT_100_FINAL_AWAY_SCORE
WILT_100_QUARTERS = (
    QuarterApproximation(1, 7, 14, 9, 9, 10, 0, 0, 23),
    QuarterApproximation(2, 7, 12, 4, 5, 4, 1, 1, 18),
    QuarterApproximation(3, 10, 16, 8, 8, 6, 1, 0, 28),
    QuarterApproximation(4, 12, 21, 7, 10, 5, 0, 1, 31),
)


def build_wilt_100_approximation() -> dict[str, pd.DataFrame]:
    """Build a synthetic, chart-ready approximation for Wilt Chamberlain's 100-point game.

    Assumptions:
    - Wilt's made shots and made free throws are spaced evenly within each quarter.
    - Non-Wilt Philadelphia points are distributed evenly across quarters, then linearly
      within each quarter to approximate score context.
    - Knicks points are distributed evenly across quarters, then linearly within each
      quarter to approximate score context.
    - Rebounds/assists/personal fouls are preserved only in the metadata note, not in the
      scoring-event parquet outputs, because the current app is scoring-event-centric.
    """

    teammate_quarter_points = _distribute_evenly(WILT_100_TEAMMATE_POINTS, len(WILT_100_QUARTERS))
    opponent_quarter_points = _distribute_evenly(WILT_100_OPPONENT_POINTS, len(WILT_100_QUARTERS))
    raw_scoring_events = _build_wilt_raw_scoring_events(teammate_quarter_points, opponent_quarter_points)
    timeline = build_player_scoring_timeline(raw_scoring_events)
    boxscore_df = _build_wilt_boxscore_totals()
    game_summary = summarize_player_games(raw_scoring_events, boxscore_df=boxscore_df)
    quarter_summary = summarize_player_quarters(raw_scoring_events)
    half_summary = summarize_player_halves(raw_scoring_events)
    burst_summary = summarize_player_bursts(raw_scoring_events)
    return {
        "raw_scoring_events": raw_scoring_events[RAW_SCORING_COLUMNS].copy(),
        "player_scoring_timelines": timeline[TIMELINE_COLUMNS].copy(),
        "player_game_summaries": game_summary[SUMMARY_COLUMNS].copy(),
        "player_quarter_summaries": quarter_summary[QUARTER_SUMMARY_COLUMNS].copy(),
        "player_half_summaries": half_summary[HALF_SUMMARY_COLUMNS].copy(),
        "player_burst_summaries": burst_summary[BURST_SUMMARY_COLUMNS].copy(),
        "boxscore_reference": boxscore_df[BOX_SCORE_COLUMNS].copy(),
        "approximation_note": pd.DataFrame([_wilt_approximation_note(teammate_quarter_points, opponent_quarter_points)]),
    }


def write_wilt_100_approximation(out_dir: str | Path = "data") -> dict[str, Path]:
    out_path = Path(out_dir)
    data = build_wilt_100_approximation()
    if not (out_path / DATASET_METADATA_FILENAME).exists():
        metadata = get_dataset_metadata()
        (out_path / DATASET_METADATA_FILENAME).write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    season = WILT_100_SEASON
    season_type = WILT_100_SEASON_TYPE
    game_id = WILT_100_GAME_ID
    partition_dir = lambda dataset: out_path / dataset / f"season={season}" / f"season_type={season_type}"
    targets = {
        "raw_scoring_events": partition_dir("raw_scoring_events") / f"part-{game_id}.parquet",
        "player_scoring_timelines": partition_dir("player_scoring_timelines") / f"part-{game_id}.parquet",
        "player_game_summaries": partition_dir("player_game_summaries") / f"part-{game_id}.parquet",
        "player_quarter_summaries": partition_dir("player_quarter_summaries") / f"part-{game_id}.parquet",
        "player_half_summaries": partition_dir("player_half_summaries") / f"part-{game_id}.parquet",
        "player_burst_summaries": partition_dir("player_burst_summaries") / f"part-{game_id}.parquet",
        "manual_notes": out_path / "manual_approximations" / "wilt_100_approximation_note.parquet",
    }
    for key, path in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if key == "manual_notes":
            data["approximation_note"].to_parquet(path, index=False)
        else:
            data[key].to_parquet(path, index=False)
    return targets


def _build_wilt_raw_scoring_events(
    teammate_quarter_points: list[int],
    opponent_quarter_points: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    action_id = 1
    home_before = 0
    away_before = 0

    for quarter, teammate_points, opponent_points in zip(
        WILT_100_QUARTERS,
        teammate_quarter_points,
        opponent_quarter_points,
        strict=True,
    ):
        event_values = _spread_scoring_events(quarter.field_goals_made, quarter.free_throws_made)
        event_count = len(event_values)
        wilt_points_through = 0
        for idx, event in enumerate(event_values, start=1):
            elapsed_seconds = (720.0 * idx) / event_count
            wilt_points_through += event["point_value"]
            teammate_points_through = round(teammate_points * (elapsed_seconds / 720.0))
            opponent_points_through = round(opponent_points * (elapsed_seconds / 720.0))
            rows.append(
                {
                    "season": WILT_100_SEASON,
                    "season_type": WILT_100_SEASON_TYPE,
                    "game_date": WILT_100_GAME_DATE,
                    "game_id": WILT_100_GAME_ID,
                    "home_team_id": WILT_100_TEAM_ID,
                    "home_team_tricode": WILT_100_TEAM_TRICODE,
                    "away_team_id": WILT_100_OPPONENT_TEAM_ID,
                    "away_team_tricode": WILT_100_OPPONENT_TRICODE,
                    "is_home_team": True,
                    "opponent_team_id": WILT_100_OPPONENT_TEAM_ID,
                    "opponent_team_tricode": WILT_100_OPPONENT_TRICODE,
                    "action_number": action_id,
                    "action_id": action_id,
                    "player_id": WILT_100_PLAYER_ID,
                    "player_name": WILT_100_PLAYER_NAME,
                    "team_id": WILT_100_TEAM_ID,
                    "team_tricode": WILT_100_TEAM_TRICODE,
                    "period": quarter.quarter_number,
                    "clock": _clock_from_elapsed_seconds(elapsed_seconds, 720.0),
                    "point_value": event["point_value"],
                    "is_field_goal": event["is_field_goal"],
                    "score_home": home_before + wilt_points_through + teammate_points_through,
                    "score_away": away_before + opponent_points_through,
                    "action_type": "Made Shot" if event["is_field_goal"] else "Free Throw",
                    "sub_type": "Legacy Approximation",
                    "description": event["description"],
                    "location": "h",
                }
            )
            action_id += 1

        home_before += quarter.points + teammate_points
        away_before += opponent_points

    return pd.DataFrame(rows, columns=RAW_SCORING_COLUMNS)


def _build_wilt_boxscore_totals() -> pd.DataFrame:
    total_fgm = sum(quarter.field_goals_made for quarter in WILT_100_QUARTERS)
    total_fga = sum(quarter.field_goals_attempted for quarter in WILT_100_QUARTERS)
    total_ftm = sum(quarter.free_throws_made for quarter in WILT_100_QUARTERS)
    total_fta = sum(quarter.free_throws_attempted for quarter in WILT_100_QUARTERS)
    row = {
        "game_id": WILT_100_GAME_ID,
        "team_id": WILT_100_TEAM_ID,
        "team_tricode": WILT_100_TEAM_TRICODE,
        "player_id": WILT_100_PLAYER_ID,
        "player_name_boxscore": WILT_100_PLAYER_NAME,
        "official_points": 100,
        "minutes_played_raw": "48:00",
        "minutes_played": WILT_100_TOTAL_MINUTES,
        "field_goals_made": total_fgm,
        "field_goals_attempted": total_fga,
        "three_pointers_made": 0,
        "three_pointers_attempted": 0,
        "free_throws_made": total_ftm,
        "free_throws_attempted": total_fta,
    }
    return pd.DataFrame([row], columns=BOX_SCORE_COLUMNS)


def _wilt_approximation_note(
    teammate_quarter_points: list[int],
    opponent_quarter_points: list[int],
) -> dict[str, Any]:
    return {
        "game_id": WILT_100_GAME_ID,
        "game_date": WILT_100_GAME_DATE,
        "season": WILT_100_SEASON,
        "season_type": WILT_100_SEASON_TYPE,
        "player_name": WILT_100_PLAYER_NAME,
        "player_id": WILT_100_PLAYER_ID,
        "team_tricode": WILT_100_TEAM_TRICODE,
        "opponent_team_tricode": WILT_100_OPPONENT_TRICODE,
        "source_type": "manual_approximation",
        "source_note": (
            "Wilt Chamberlain's 100-point game is approximated from published quarter box-score splits. "
            "Wilt scoring events are spaced evenly within each quarter. "
            "Non-Wilt Philadelphia points and Knicks points are distributed evenly across quarters, "
            "then linearly within each quarter to estimate score context."
        ),
        "quarter_box_stats_json": json.dumps(
            [
                {
                    "quarter": quarter.quarter_number,
                    "minutes": 12,
                    "fgm": quarter.field_goals_made,
                    "fga": quarter.field_goals_attempted,
                    "ftm": quarter.free_throws_made,
                    "fta": quarter.free_throws_attempted,
                    "reb": quarter.rebounds,
                    "ast": quarter.assists,
                    "pf": quarter.personal_fouls,
                    "pts": quarter.points,
                    "teammate_points_estimate": teammate_points,
                    "opponent_points_estimate": opponent_points,
                }
                for quarter, teammate_points, opponent_points in zip(
                    WILT_100_QUARTERS,
                    teammate_quarter_points,
                    opponent_quarter_points,
                    strict=True,
                )
            ]
        ),
    }


def _spread_scoring_events(field_goals_made: int, free_throws_made: int) -> list[dict[str, Any]]:
    total_events = field_goals_made + free_throws_made
    fg_used = 0
    ft_used = 0
    events: list[dict[str, Any]] = []
    for position in range(1, total_events + 1):
        fg_gap = (position * field_goals_made / total_events) - fg_used
        ft_gap = (position * free_throws_made / total_events) - ft_used
        use_field_goal = fg_gap >= ft_gap and fg_used < field_goals_made
        if ft_used >= free_throws_made:
            use_field_goal = True
        if fg_used >= field_goals_made:
            use_field_goal = False

        if use_field_goal:
            fg_used += 1
            events.append(
                {
                    "point_value": 2,
                    "is_field_goal": True,
                    "description": "Legacy approximation: Wilt 2PT make from quarter split",
                }
            )
        else:
            ft_used += 1
            events.append(
                {
                    "point_value": 1,
                    "is_field_goal": False,
                    "description": "Legacy approximation: Wilt FT make from quarter split",
                }
            )
    return events


def _distribute_evenly(total: int, buckets: int) -> list[int]:
    base = total // buckets
    remainder = total % buckets
    values = [base] * buckets
    for idx in range(remainder):
        values[-(idx + 1)] += 1
    return values


def _clock_from_elapsed_seconds(elapsed_seconds: float, period_duration_seconds: float) -> str:
    remaining = max(0.0, period_duration_seconds - elapsed_seconds)
    minutes = int(remaining // 60)
    seconds = remaining - (minutes * 60)
    return f"PT{minutes:02d}M{seconds:05.2f}S"
