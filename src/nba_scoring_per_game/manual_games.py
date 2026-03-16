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


@dataclass(frozen=True, slots=True, kw_only=True)
class LegacyGameApproximation:
    game_id: str
    player_name: str
    player_full_name: str
    player_id: int
    season: str
    season_type: str
    game_date: str
    team_tricode: str
    team_id: int | None
    opponent_team_tricode: str
    opponent_team_id: int | None
    final_player_team_score: int
    final_opponent_score: int
    minutes_played: float
    field_goals_made: int
    field_goals_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    period_points: tuple[int, ...]
    source_note: str
    primary_detail_source_url: str
    secondary_detail_source_url: str | None = None
    period_team_points: tuple[int, ...] | None = None
    period_opponent_points: tuple[int, ...] | None = None
    model_label: str = "quarter_even_model"
    period_box_stats: tuple[QuarterApproximation, ...] = ()


WILT_100_GAME_ID = "LG19620302WILT100"
WILT_100_PLAYER_ID = 76375
WILT_100_TEAM_ID = 990001
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
WILT_100_QUARTERS = (
    QuarterApproximation(1, 7, 14, 9, 9, 10, 0, 0, 23),
    QuarterApproximation(2, 7, 12, 4, 5, 4, 1, 1, 18),
    QuarterApproximation(3, 10, 16, 8, 8, 6, 1, 0, 28),
    QuarterApproximation(4, 12, 21, 7, 10, 5, 0, 1, 31),
)

LEGACY_NEW_ORLEANS_JAZZ_TEAM_ID = 990002

LEGACY_GAME_APPROXIMATIONS: tuple[LegacyGameApproximation, ...] = (
    LegacyGameApproximation(
        game_id=WILT_100_GAME_ID,
        player_name=WILT_100_PLAYER_NAME,
        player_full_name="Wilt Chamberlain",
        player_id=WILT_100_PLAYER_ID,
        season=WILT_100_SEASON,
        season_type=WILT_100_SEASON_TYPE,
        game_date=WILT_100_GAME_DATE,
        team_tricode=WILT_100_TEAM_TRICODE,
        team_id=WILT_100_TEAM_ID,
        opponent_team_tricode=WILT_100_OPPONENT_TRICODE,
        opponent_team_id=WILT_100_OPPONENT_TEAM_ID,
        final_player_team_score=WILT_100_FINAL_HOME_SCORE,
        final_opponent_score=WILT_100_FINAL_AWAY_SCORE,
        minutes_played=WILT_100_TOTAL_MINUTES,
        field_goals_made=sum(quarter.field_goals_made for quarter in WILT_100_QUARTERS),
        field_goals_attempted=sum(quarter.field_goals_attempted for quarter in WILT_100_QUARTERS),
        three_pointers_made=0,
        three_pointers_attempted=0,
        free_throws_made=sum(quarter.free_throws_made for quarter in WILT_100_QUARTERS),
        free_throws_attempted=sum(quarter.free_throws_attempted for quarter in WILT_100_QUARTERS),
        period_points=tuple(quarter.points for quarter in WILT_100_QUARTERS),
        period_team_points=(42, 37, 46, 44),
        period_opponent_points=(26, 42, 38, 41),
        source_note=(
            "Wilt Chamberlain's 100-point game uses published quarter box-score splits. "
            "Scoring events are evenly spaced within each quarter. "
            "Philadelphia and New York quarter scoring totals use the supplied split of "
            "42-26, 37-42, 46-38, and 44-41 to estimate score context within each quarter."
        ),
        primary_detail_source_url="https://www.espn.com/nba/dailydime/_/page/dime-120302-03/weekend-dime-half-century-later-wilt-100-stands-tallest",
        secondary_detail_source_url="https://www.sfgate.com/sports/ostler/article/Golden-anniversary-of-Chamberlain-s-100-point-game-3375905.php",
        model_label="existing_manual_model",
        period_box_stats=WILT_100_QUARTERS,
    ),
    LegacyGameApproximation(
        game_id="LG19601115BAYLOR71",
        player_name="Baylor",
        player_full_name="Elgin Baylor",
        player_id=76127,
        season="1960-61",
        season_type="Regular Season",
        game_date="1960-11-15",
        team_tricode="LAL",
        team_id=1610612747,
        opponent_team_tricode="NYK",
        opponent_team_id=1610612752,
        final_player_team_score=123,
        final_opponent_score=108,
        minutes_played=45.0,
        field_goals_made=28,
        field_goals_attempted=48,
        three_pointers_made=0,
        three_pointers_attempted=0,
        free_throws_made=15,
        free_throws_attempted=18,
        period_points=(15, 19, 13, 24),
        source_note=(
            "Quarter checkpoints from contemporary reporting give 15 in the first quarter, 34 by halftime, "
            "47 after three quarters, and 71 final. Box-score makes, attempts, and minutes are taken from the "
            "historical scoring-leaders table. Quarter shot-type splits are allocated to match the known game totals."
        ),
        primary_detail_source_url="https://time.com/archive/6809471/sport-fantastic-2/",
        secondary_detail_source_url="https://en.wikipedia.org/wiki/List_of_NBA_single-game_scoring_leaders",
    ),
    LegacyGameApproximation(
        game_id="LG19780409THOMPSON73",
        player_name="Thompson",
        player_full_name="David Thompson",
        player_id=78326,
        season="1977-78",
        season_type="Regular Season",
        game_date="1978-04-09",
        team_tricode="DEN",
        team_id=1610612743,
        opponent_team_tricode="DET",
        opponent_team_id=1610612765,
        final_player_team_score=137,
        final_opponent_score=139,
        minutes_played=43.0,
        field_goals_made=28,
        field_goals_attempted=38,
        three_pointers_made=0,
        three_pointers_attempted=0,
        free_throws_made=17,
        free_throws_attempted=20,
        period_points=(32, 21, 6, 14),
        source_note=(
            "Quarter scoring checkpoints are reconstructed from reports confirming 32 in the first quarter, "
            "53 at halftime, and the remaining second-half split of 6 and 14. Box-score makes, attempts, and minutes "
            "are taken from the historical scoring-leaders table."
        ),
        primary_detail_source_url="https://www.espn.com/classic/s/moment010409-gervin-thompson.html",
        secondary_detail_source_url="https://en.wikipedia.org/wiki/List_of_NBA_single-game_scoring_leaders",
    ),
    LegacyGameApproximation(
        game_id="LG19940424ROBINSON71",
        player_name="Robinson",
        player_full_name="David Robinson",
        player_id=764,
        season="1993-94",
        season_type="Regular Season",
        game_date="1994-04-24",
        team_tricode="SAS",
        team_id=1610612759,
        opponent_team_tricode="LAC",
        opponent_team_id=1610612746,
        final_player_team_score=112,
        final_opponent_score=97,
        minutes_played=44.0,
        field_goals_made=26,
        field_goals_attempted=41,
        three_pointers_made=1,
        three_pointers_attempted=2,
        free_throws_made=18,
        free_throws_attempted=25,
        period_points=(18, 6, 19, 28),
        source_note=(
            "Quarter scoring splits come from ESPN's recap: 18, 6, 19, and 28. "
            "Game-level shooting totals and minutes come from the historical scoring-leaders table. "
            "The lone three-pointer is allocated across quarters to match the known total."
        ),
        primary_detail_source_url="https://www.espn.com/classic/s/moment010424robinson.html",
        secondary_detail_source_url="https://en.wikipedia.org/wiki/List_of_NBA_single-game_scoring_leaders",
    ),
    LegacyGameApproximation(
        game_id="LG19900328JORDAN69",
        player_name="Jordan",
        player_full_name="Michael Jordan",
        player_id=893,
        season="1989-90",
        season_type="Regular Season",
        game_date="1990-03-28",
        team_tricode="CHI",
        team_id=1610612741,
        opponent_team_tricode="CLE",
        opponent_team_id=1610612739,
        final_player_team_score=117,
        final_opponent_score=113,
        minutes_played=50.0,
        field_goals_made=23,
        field_goals_attempted=37,
        three_pointers_made=2,
        three_pointers_attempted=6,
        free_throws_made=21,
        free_throws_attempted=23,
        period_points=(16, 15, 20, 10, 8),
        source_note=(
            "Quarter and overtime scoring splits come directly from NBA.com: 16, 15, 20, 10, and 8 in overtime. "
            "Game-level shooting totals and minutes come from the historical scoring-leaders table. "
            "Two made threes and the free throws are distributed across periods to match the published totals."
        ),
        primary_detail_source_url="https://www.nba.com/news/legendary-moments-history-michael-jordan-69-points-vs-cleveland-cavs-1990",
        secondary_detail_source_url="https://en.wikipedia.org/wiki/List_of_NBA_single-game_scoring_leaders",
    ),
    LegacyGameApproximation(
        game_id="LG19770225MARAVICH68",
        player_name="Maravich",
        player_full_name="Pete Maravich",
        player_id=77459,
        season="1976-77",
        season_type="Regular Season",
        game_date="1977-02-25",
        team_tricode="NOP",
        team_id=LEGACY_NEW_ORLEANS_JAZZ_TEAM_ID,
        opponent_team_tricode="NYK",
        opponent_team_id=1610612752,
        final_player_team_score=124,
        final_opponent_score=107,
        minutes_played=43.0,
        field_goals_made=26,
        field_goals_attempted=43,
        three_pointers_made=0,
        three_pointers_attempted=0,
        free_throws_made=16,
        free_throws_attempted=19,
        period_points=(17, 14, 17, 20),
        source_note=(
            "ESPN's recap gives a full quarter scoring breakdown of 17, 14, 17, and 20. "
            "Game-level shooting totals and minutes come from the historical scoring-leaders table. "
            "This row uses a text fallback for the New Orleans Jazz because the app only ships current team-logo assets."
        ),
        primary_detail_source_url="https://www.espn.com/classic/s/moment010225maravich.html",
        secondary_detail_source_url="https://en.wikipedia.org/wiki/List_of_NBA_single-game_scoring_leaders",
    ),
)


def build_supported_legacy_approximations() -> dict[str, dict[str, pd.DataFrame]]:
    return {
        game.game_id: build_legacy_game_approximation(game)
        for game in LEGACY_GAME_APPROXIMATIONS
    }


def build_wilt_100_approximation() -> dict[str, pd.DataFrame]:
    return build_legacy_game_approximation(_legacy_game_by_id(WILT_100_GAME_ID))


def write_wilt_100_approximation(out_dir: str | Path = "data") -> dict[str, Path]:
    return write_legacy_game_approximation(WILT_100_GAME_ID, out_dir)


def build_legacy_game_approximation(
    game: LegacyGameApproximation | str,
) -> dict[str, pd.DataFrame]:
    config = _legacy_game_by_id(game) if isinstance(game, str) else game
    player_period_points = list(config.period_points)
    team_period_points = (
        list(config.period_team_points)
        if config.period_team_points is not None
        else _distribute_evenly(config.final_player_team_score, len(player_period_points))
    )
    opponent_period_points = (
        list(config.period_opponent_points)
        if config.period_opponent_points is not None
        else _distribute_evenly(config.final_opponent_score, len(player_period_points))
    )
    if len(team_period_points) != len(player_period_points) or len(opponent_period_points) != len(player_period_points):
        raise ValueError(f"Period score splits must match period_points length for {config.game_id}")
    if sum(team_period_points) != config.final_player_team_score:
        raise ValueError(f"Team period points must sum to final score for {config.game_id}")
    if sum(opponent_period_points) != config.final_opponent_score:
        raise ValueError(f"Opponent period points must sum to final score for {config.game_id}")
    teammate_period_points = [
        int(team_points) - int(player_points)
        for team_points, player_points in zip(team_period_points, player_period_points, strict=True)
    ]
    if any(points < 0 for points in teammate_period_points):
        raise ValueError(f"Player period points exceed team period points for {config.game_id}")
    period_scoring_breakdown = _build_period_scoring_breakdown(config)
    raw_scoring_events = _build_legacy_raw_scoring_events(
        config,
        period_scoring_breakdown,
        teammate_period_points,
        opponent_period_points,
    )
    timeline = build_player_scoring_timeline(raw_scoring_events)
    boxscore_df = _build_legacy_boxscore_totals(config)
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
        "approximation_note": pd.DataFrame(
            [
                _legacy_approximation_note(
                    config,
                    period_scoring_breakdown,
                    teammate_period_points,
                    opponent_period_points,
                )
            ]
        ),
    }


def write_legacy_game_approximation(
    game: LegacyGameApproximation | str,
    out_dir: str | Path = "data",
) -> dict[str, Path]:
    config = _legacy_game_by_id(game) if isinstance(game, str) else game
    out_path = Path(out_dir)
    data = build_legacy_game_approximation(config)
    _ensure_dataset_metadata(out_path)

    season = config.season
    season_type = config.season_type
    game_id = config.game_id
    partition_dir = lambda dataset: out_path / dataset / f"season={season}" / f"season_type={season_type}"
    targets = {
        "raw_scoring_events": partition_dir("raw_scoring_events") / f"part-{game_id}.parquet",
        "player_scoring_timelines": partition_dir("player_scoring_timelines") / f"part-{game_id}.parquet",
        "player_game_summaries": partition_dir("player_game_summaries") / f"part-{game_id}.parquet",
        "player_quarter_summaries": partition_dir("player_quarter_summaries") / f"part-{game_id}.parquet",
        "player_half_summaries": partition_dir("player_half_summaries") / f"part-{game_id}.parquet",
        "player_burst_summaries": partition_dir("player_burst_summaries") / f"part-{game_id}.parquet",
        "approximation_note": out_path / "manual_approximations" / f"part-{game_id}.parquet",
    }
    for key, path in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data[key].to_parquet(path, index=False)
    return targets


def write_supported_legacy_approximations(
    out_dir: str | Path = "data",
    game_ids: list[str] | None = None,
) -> dict[str, dict[str, Path]]:
    selected_ids = set(game_ids) if game_ids else None
    written: dict[str, dict[str, Path]] = {}
    for game in LEGACY_GAME_APPROXIMATIONS:
        if selected_ids is not None and game.game_id not in selected_ids:
            continue
        written[game.game_id] = write_legacy_game_approximation(game, out_dir)
    return written


def _ensure_dataset_metadata(out_path: Path) -> None:
    metadata_path = out_path / DATASET_METADATA_FILENAME
    if metadata_path.exists():
        return
    metadata = get_dataset_metadata()
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_legacy_raw_scoring_events(
    config: LegacyGameApproximation,
    period_breakdown: list[dict[str, Any]],
    teammate_period_points: list[int],
    opponent_period_points: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    action_id = 1
    home_before = 0
    away_before = 0

    for period_info, teammate_points, opponent_points in zip(
        period_breakdown,
        teammate_period_points,
        opponent_period_points,
        strict=True,
    ):
        period_number = int(period_info["period"])
        period_duration_seconds = float(period_info["period_duration_seconds"])
        events = _spread_scoring_events(period_info)
        event_count = len(events)
        player_points_through = 0

        if event_count == 0:
            home_before += int(period_info["points"]) + teammate_points
            away_before += opponent_points
            continue

        for idx, event in enumerate(events, start=1):
            elapsed_seconds = (period_duration_seconds * idx) / event_count
            player_points_through += int(event["point_value"])
            teammate_points_through = round(teammate_points * (elapsed_seconds / period_duration_seconds))
            opponent_points_through = round(opponent_points * (elapsed_seconds / period_duration_seconds))
            rows.append(
                {
                    "season": config.season,
                    "season_type": config.season_type,
                    "game_date": config.game_date,
                    "game_id": config.game_id,
                    "home_team_id": config.team_id,
                    "home_team_tricode": config.team_tricode,
                    "away_team_id": config.opponent_team_id,
                    "away_team_tricode": config.opponent_team_tricode,
                    "is_home_team": True,
                    "opponent_team_id": config.opponent_team_id,
                    "opponent_team_tricode": config.opponent_team_tricode,
                    "opponent_wins": pd.NA,
                    "opponent_losses": pd.NA,
                    "opponent_win_pct": pd.NA,
                    "opponent_record_scope": pd.NA,
                    "is_playoff_game": str(config.season_type).lower() == "playoffs",
                    "action_number": action_id,
                    "action_id": action_id,
                    "player_id": config.player_id,
                    "player_name": config.player_name,
                    "team_id": config.team_id,
                    "team_tricode": config.team_tricode,
                    "period": period_number,
                    "clock": _clock_from_elapsed_seconds(elapsed_seconds, period_duration_seconds),
                    "point_value": event["point_value"],
                    "is_field_goal": event["is_field_goal"],
                    "score_home": home_before + player_points_through + teammate_points_through,
                    "score_away": away_before + opponent_points_through,
                    "action_type": "Made Shot" if event["is_field_goal"] else "Free Throw",
                    "sub_type": "Legacy Approximation",
                    "description": event["description"],
                    "location": "h",
                }
            )
            action_id += 1

        home_before += int(period_info["points"]) + teammate_points
        away_before += opponent_points

    return pd.DataFrame(rows, columns=RAW_SCORING_COLUMNS)


def _build_legacy_boxscore_totals(config: LegacyGameApproximation) -> pd.DataFrame:
    row = {
        "game_id": config.game_id,
        "team_id": config.team_id,
        "team_tricode": config.team_tricode,
        "player_id": config.player_id,
        "player_name_boxscore": config.player_full_name,
        "official_points": sum(config.period_points),
        "minutes_played_raw": _minutes_raw(config.minutes_played),
        "minutes_played": config.minutes_played,
        "field_goals_made": config.field_goals_made,
        "field_goals_attempted": config.field_goals_attempted,
        "three_pointers_made": config.three_pointers_made,
        "three_pointers_attempted": config.three_pointers_attempted,
        "free_throws_made": config.free_throws_made,
        "free_throws_attempted": config.free_throws_attempted,
    }
    return pd.DataFrame([row], columns=BOX_SCORE_COLUMNS)


def _legacy_approximation_note(
    config: LegacyGameApproximation,
    period_breakdown: list[dict[str, Any]],
    teammate_period_points: list[int],
    opponent_period_points: list[int],
) -> dict[str, Any]:
    note = {
        "game_id": config.game_id,
        "game_date": config.game_date,
        "season": config.season,
        "season_type": config.season_type,
        "player_name": config.player_full_name,
        "player_id": config.player_id,
        "team_tricode": config.team_tricode,
        "opponent_team_tricode": config.opponent_team_tricode,
        "source_type": "manual_approximation",
        "model_label": config.model_label,
        "source_note": config.source_note,
        "primary_detail_source_url": config.primary_detail_source_url,
        "secondary_detail_source_url": config.secondary_detail_source_url,
        "game_box_stats_json": json.dumps(
            {
                "minutes_played": config.minutes_played,
                "field_goals_made": config.field_goals_made,
                "field_goals_attempted": config.field_goals_attempted,
                "three_pointers_made": config.three_pointers_made,
                "three_pointers_attempted": config.three_pointers_attempted,
                "free_throws_made": config.free_throws_made,
                "free_throws_attempted": config.free_throws_attempted,
                "points": sum(config.period_points),
                "final_score": f"{config.final_player_team_score}-{config.final_opponent_score}",
            }
        ),
        "period_points_json": json.dumps(
            [
                {
                    "period": int(period_info["period"]),
                    "period_points": int(period_info["points"]),
                    "two_pt_points": int(period_info["two_pt_points"]),
                    "three_pt_points": int(period_info["three_pt_points"]),
                    "ft_points": int(period_info["ft_points"]),
                    "approx_two_pt_made": int(period_info["two_pt_made"]),
                    "approx_three_pt_made": int(period_info["three_pt_made"]),
                    "approx_ft_made": int(period_info["ft_made"]),
                    "teammate_points_estimate": teammate_points,
                    "opponent_points_estimate": opponent_points,
                }
                for period_info, teammate_points, opponent_points in zip(
                    period_breakdown,
                    teammate_period_points,
                    opponent_period_points,
                    strict=True,
                )
            ]
        ),
    }
    if config.period_box_stats:
        note["quarter_box_stats_json"] = json.dumps(
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
                }
                for quarter in config.period_box_stats
            ]
        )
    return note


def _build_period_scoring_breakdown(config: LegacyGameApproximation) -> list[dict[str, Any]]:
    if config.period_box_stats:
        return [
            {
                "period": quarter.quarter_number,
                "period_duration_seconds": 720.0 if quarter.quarter_number <= 4 else 300.0,
                "points": quarter.points,
                "two_pt_made": quarter.field_goals_made,
                "three_pt_made": 0,
                "ft_made": quarter.free_throws_made,
                "two_pt_points": quarter.field_goals_made * 2,
                "three_pt_points": 0,
                "ft_points": quarter.free_throws_made,
            }
            for quarter in config.period_box_stats
        ]

    allocation = _allocate_period_scoring_breakdown(
        list(config.period_points),
        two_pt_made=config.field_goals_made - config.three_pointers_made,
        three_pt_made=config.three_pointers_made,
        ft_made=config.free_throws_made,
    )
    return [
        {
            "period": period_number,
            "period_duration_seconds": _period_duration_seconds(period_number),
            "points": config.period_points[period_number - 1],
            "two_pt_made": period["two_pt_made"],
            "three_pt_made": period["three_pt_made"],
            "ft_made": period["ft_made"],
            "two_pt_points": period["two_pt_made"] * 2,
            "three_pt_points": period["three_pt_made"] * 3,
            "ft_points": period["ft_made"],
        }
        for period_number, period in enumerate(allocation, start=1)
    ]


def _allocate_period_scoring_breakdown(
    period_points: list[int],
    *,
    two_pt_made: int,
    three_pt_made: int,
    ft_made: int,
) -> list[dict[str, int]]:
    total_points = sum(period_points)
    expected_two_pt_points = [(points * (two_pt_made * 2)) / total_points for points in period_points]
    expected_three_pt_points = [(points * (three_pt_made * 3)) / total_points for points in period_points]
    expected_ft_points = [(points * ft_made) / total_points for points in period_points]
    best_score: float | None = None
    best_allocation: list[dict[str, int]] | None = None

    def search(
        index: int,
        remaining_two_pt_made: int,
        remaining_three_pt_made: int,
        remaining_ft_made: int,
        current: list[dict[str, int]],
        current_score: float,
    ) -> None:
        nonlocal best_score, best_allocation
        if best_score is not None and current_score >= best_score:
            return
        if index == len(period_points):
            if remaining_two_pt_made == 0 and remaining_three_pt_made == 0 and remaining_ft_made == 0:
                best_score = current_score
                best_allocation = list(current)
            return

        points = period_points[index]
        max_three = min(remaining_three_pt_made, points // 3)
        for three_made in range(max_three + 1):
            points_after_threes = points - (3 * three_made)
            max_ft = min(remaining_ft_made, points_after_threes)
            for ft in range(max_ft + 1):
                remaining_points = points_after_threes - ft
                if remaining_points < 0 or remaining_points % 2 != 0:
                    continue
                two_made = remaining_points // 2
                if two_made > remaining_two_pt_made:
                    continue
                step_score = (
                    ((two_made * 2) - expected_two_pt_points[index]) ** 2
                    + ((three_made * 3) - expected_three_pt_points[index]) ** 2
                    + (ft - expected_ft_points[index]) ** 2
                )
                current.append(
                    {
                        "two_pt_made": two_made,
                        "three_pt_made": three_made,
                        "ft_made": ft,
                    }
                )
                search(
                    index + 1,
                    remaining_two_pt_made - two_made,
                    remaining_three_pt_made - three_made,
                    remaining_ft_made - ft,
                    current,
                    current_score + step_score,
                )
                current.pop()

    search(0, two_pt_made, three_pt_made, ft_made, [], 0.0)
    if best_allocation is None:
        raise ValueError(
            "Could not allocate legacy scoring breakdown "
            f"for period_points={period_points} two_pt_made={two_pt_made} "
            f"three_pt_made={three_pt_made} ft_made={ft_made}"
        )
    return best_allocation


def _spread_scoring_events(period_info: dict[str, Any]) -> list[dict[str, Any]]:
    event_counts = {
        "2PT": int(period_info["two_pt_made"]),
        "3PT": int(period_info["three_pt_made"]),
        "FT": int(period_info["ft_made"]),
    }
    total_events = sum(event_counts.values())
    used = {key: 0 for key in event_counts}
    events: list[dict[str, Any]] = []

    for position in range(1, total_events + 1):
        best_type: str | None = None
        best_gap: float | None = None
        for event_type, target_count in event_counts.items():
            if used[event_type] >= target_count:
                continue
            target_gap = (position * target_count / total_events) - used[event_type]
            if best_gap is None or target_gap > best_gap:
                best_gap = target_gap
                best_type = event_type
        if best_type is None:
            raise ValueError(f"Could not assign legacy scoring event for period={period_info['period']}")
        used[best_type] += 1
        events.append(_event_payload(best_type))
    return events


def _event_payload(event_type: str) -> dict[str, Any]:
    if event_type == "2PT":
        return {
            "point_value": 2,
            "is_field_goal": True,
            "description": "Legacy approximation: 2PT make from quarter/period split",
        }
    if event_type == "3PT":
        return {
            "point_value": 3,
            "is_field_goal": True,
            "description": "Legacy approximation: 3PT make from game box-score total",
        }
    return {
        "point_value": 1,
        "is_field_goal": False,
        "description": "Legacy approximation: FT make from game box-score total",
    }


def _legacy_game_by_id(game: str | LegacyGameApproximation) -> LegacyGameApproximation:
    if isinstance(game, LegacyGameApproximation):
        return game
    game_id = str(game)
    for config in LEGACY_GAME_APPROXIMATIONS:
        if config.game_id == game_id:
            return config
    raise KeyError(f"Unknown legacy manual game_id={game_id}")


def _distribute_evenly(total: int, buckets: int) -> list[int]:
    base = total // buckets
    remainder = total % buckets
    values = [base] * buckets
    for idx in range(remainder):
        values[-(idx + 1)] += 1
    return values


def _period_duration_seconds(period_number: int) -> float:
    return 720.0 if int(period_number) <= 4 else 300.0


def _minutes_raw(minutes_played: float) -> str:
    total_seconds = int(round(float(minutes_played) * 60))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def _clock_from_elapsed_seconds(elapsed_seconds: float, period_duration_seconds: float) -> str:
    remaining = max(0.0, period_duration_seconds - elapsed_seconds)
    minutes = int(remaining // 60)
    seconds = remaining - (minutes * 60)
    return f"PT{minutes:02d}M{seconds:05.2f}S"
