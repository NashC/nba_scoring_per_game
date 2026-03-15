from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from nba_api.stats.endpoints import boxscoretraditionalv3, leaguegamelog, playbyplayv3
import pandas as pd

from nba_scoring_per_game.pipeline import process_game
from nba_scoring_per_game.source import (
    BOX_SCORE_COLUMNS,
    _normalize_min_player_points,
    _pair_team_logs_into_manifest,
    _parse_minutes_to_float,
)
import nba_scoring_per_game.pipeline as pipeline_module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry failed historical 50+ buckets with longer NBA Stats timeouts.")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--summary-path", default="data/historical_50_plus_backfill_summary.json")
    parser.add_argument("--min-player-points", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--manifest-attempts", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--run-date", default=f"{datetime.now().date().isoformat()}-retry")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    summary_path = Path(args.summary_path)
    threshold = _normalize_min_player_points(args.min_player_points)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    failed_buckets = [
        {"season": row["season"], "season_type": row["season_type"]}
        for row in summary.get("season_runs", [])
        if row.get("status") == "manifest_error"
    ]
    if not failed_buckets:
        print("NO_FAILED_BUCKETS")
        return

    existing_game_ids = _load_existing_game_ids(out_dir)
    results: list[dict[str, Any]] = []
    bucket_summaries: list[dict[str, Any]] = []

    original_fetch_playbyplay = pipeline_module.fetch_playbyplay
    original_fetch_boxscore_player_totals = pipeline_module.fetch_boxscore_player_totals
    pipeline_module.fetch_playbyplay = lambda game_id: _fetch_playbyplay_with_timeout(str(game_id), args.timeout)
    pipeline_module.fetch_boxscore_player_totals = (
        lambda game_id: _fetch_boxscore_player_totals_with_timeout(str(game_id), args.timeout)
    )

    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        for bucket in failed_buckets:
            season = bucket["season"]
            season_type = bucket["season_type"]
            print(f"RETRY_BUCKET {season} | {season_type}", flush=True)
            try:
                manifest = _fetch_manifest_with_timeout(
                    season=season,
                    season_type=season_type,
                    min_player_points=threshold,
                    timeout=args.timeout,
                    max_attempts=args.manifest_attempts,
                    sleep_seconds=args.sleep_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                bucket_summary = {
                    "season": season,
                    "season_type": season_type,
                    "status": "manifest_error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                bucket_summaries.append(bucket_summary)
                print(
                    f"RETRY_BUCKET_FAILED {season} | {season_type} | {type(exc).__name__}: {exc}",
                    flush=True,
                )
                _write_retry_outputs(out_dir, args.run_date, started_at, bucket_summaries, results)
                continue

            if manifest.empty:
                bucket_summary = {
                    "season": season,
                    "season_type": season_type,
                    "status": "no_games",
                    "manifest_games": 0,
                }
                bucket_summaries.append(bucket_summary)
                print(f"RETRY_BUCKET_NO_GAMES {season} | {season_type}", flush=True)
                _write_retry_outputs(out_dir, args.run_date, started_at, bucket_summaries, results)
                continue

            bucket_rows: list[dict[str, Any]] = []
            manifest = manifest.sort_values(["game_date", "game_id"]).reset_index(drop=True)
            for _, row in manifest.iterrows():
                row_dict = {key: row[key] for key in row.index}
                game_id = str(row_dict["game_id"])
                processed_at = datetime.now().isoformat(timespec="seconds")

                if game_id in existing_game_ids:
                    result = {
                        **row_dict,
                        "run_date": args.run_date,
                        "processed_at": processed_at,
                        "status": "success",
                        "skipped_existing": True,
                        "error_type": None,
                        "error_message": None,
                        "num_scoring_events": None,
                        "validation_passed": True,
                    }
                    bucket_rows.append(result)
                    results.append(result)
                    print(f"SKIP_EXISTING {season} | {season_type} | {game_id}", flush=True)
                    continue

                artifact = process_game(
                    row_dict,
                    out_dir=out_dir,
                    write_mode="skip_existing",
                    raw_cache=True,
                    run_date=args.run_date,
                )
                if artifact.status == "success":
                    existing_game_ids.add(game_id)

                result = {
                    **artifact.manifest_row,
                    "run_date": args.run_date,
                    "processed_at": processed_at,
                    "status": artifact.status,
                    "skipped_existing": artifact.skipped_existing,
                    "error_type": artifact.error_type,
                    "error_message": artifact.error_message,
                    "num_scoring_events": int(len(artifact.raw_scoring_events)),
                    "validation_passed": artifact.validation_report.get("validation_passed"),
                }
                result.update(
                    {
                        key: value
                        for key, value in artifact.validation_report.items()
                        if key not in {"season", "season_type", "game_date", "game_id"}
                    }
                )
                bucket_rows.append(result)
                results.append(result)
                print(
                    f"GAME_RESULT {season} | {season_type} | {game_id} | {artifact.status}"
                    f"{' | skipped_existing' if artifact.skipped_existing else ''}",
                    flush=True,
                )

            counter = Counter(row["status"] for row in bucket_rows)
            bucket_summary = {
                "season": season,
                "season_type": season_type,
                "status": "ok",
                "manifest_games": int(len(manifest)),
                "processed_rows": int(len(bucket_rows)),
                "status_counts": dict(counter),
                "success_games": int(counter.get("success", 0)),
                "skipped_existing_games": int(sum(1 for row in bucket_rows if row.get("skipped_existing"))),
            }
            bucket_summaries.append(bucket_summary)
            _write_retry_outputs(out_dir, args.run_date, started_at, bucket_summaries, results)
            print(
                "RETRY_BUCKET_DONE "
                f"{season} | {season_type} | manifest_games={len(manifest)} | status_counts={dict(counter)}",
                flush=True,
            )
    finally:
        pipeline_module.fetch_playbyplay = original_fetch_playbyplay
        pipeline_module.fetch_boxscore_player_totals = original_fetch_boxscore_player_totals

    final_summary = _build_retry_summary_payload(out_dir, args.run_date, started_at, bucket_summaries, results)
    summary_out = out_dir / "historical_50_plus_retry_summary.json"
    summary_out.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RETRY_SUMMARY_WRITTEN {summary_out}", flush=True)
    print(json.dumps(final_summary, indent=2, sort_keys=True), flush=True)


def _fetch_manifest_with_timeout(
    *,
    season: str,
    season_type: str,
    min_player_points: int,
    timeout: int,
    max_attempts: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    team_logs = _retry_leaguegamelog(
        season=season,
        season_type=season_type,
        player_or_team_abbreviation="T",
        timeout=timeout,
        max_attempts=max_attempts,
        sleep_seconds=sleep_seconds,
    )
    if team_logs.empty:
        raise ValueError(f"No team game logs returned for season={season} season_type={season_type}")

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

    player_logs = _retry_leaguegamelog(
        season=season,
        season_type=season_type,
        player_or_team_abbreviation="P",
        timeout=timeout,
        max_attempts=max_attempts,
        sleep_seconds=sleep_seconds,
    )
    if player_logs.empty:
        raise ValueError(f"No player game logs returned for season={season} season_type={season_type}")
    if "PTS" not in player_logs.columns or "GAME_ID" not in player_logs.columns:
        raise ValueError("Player game logs are missing required GAME_ID/PTS columns for threshold filtering.")

    qualifying_game_ids = (
        player_logs.loc[pd.to_numeric(player_logs["PTS"], errors="coerce").ge(min_player_points), "GAME_ID"]
        .astype(str)
        .dropna()
        .unique()
        .tolist()
    )
    if not qualifying_game_ids:
        return manifest.iloc[0:0].copy()
    return manifest.loc[manifest["game_id"].astype(str).isin(qualifying_game_ids)].reset_index(drop=True)


def _retry_leaguegamelog(
    *,
    season: str,
    season_type: str,
    player_or_team_abbreviation: str,
    timeout: int,
    max_attempts: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star=season_type,
                player_or_team_abbreviation=player_or_team_abbreviation,
                timeout=timeout,
            ).get_data_frames()[0].copy()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(
                "MANIFEST_RETRY "
                f"{season} | {season_type} | {player_or_team_abbreviation} | attempt={attempt}/{max_attempts}"
                f" | {type(exc).__name__}: {exc}",
                flush=True,
            )
            if attempt == max_attempts:
                break
            time.sleep(sleep_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error


def _fetch_playbyplay_with_timeout(game_id: str, timeout: int) -> pd.DataFrame:
    df = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=timeout).get_data_frames()[0].copy()
    if df.empty:
        raise ValueError(f"No play-by-play rows returned for game_id={game_id}")
    return df


def _fetch_boxscore_player_totals_with_timeout(game_id: str, timeout: int) -> pd.DataFrame:
    players = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id, timeout=timeout).get_data_frames()[0].copy()
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
        if column not in renamed.columns:
            renamed[column] = pd.NA
        else:
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    for column in BOX_SCORE_COLUMNS:
        if column not in renamed.columns:
            renamed[column] = pd.NA
    return renamed[BOX_SCORE_COLUMNS].copy()


def _load_existing_game_ids(out_dir: Path) -> set[str]:
    summary_dir = out_dir / "player_game_summaries"
    parquet_paths = sorted(summary_dir.rglob("*.parquet"))
    if not parquet_paths:
        return set()
    frames = []
    for path in parquet_paths:
        frames.append(pd.read_parquet(path, columns=["game_id"]))
    if not frames:
        return set()
    return set(pd.concat(frames, ignore_index=True)["game_id"].astype(str).unique().tolist())


def _write_retry_outputs(
    out_dir: Path,
    run_date: str,
    started_at: str,
    bucket_summaries: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> None:
    processing_manifest_dir = out_dir / "processing_manifest"
    processing_manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = processing_manifest_dir / f"run_date={run_date}.parquet"
    pd.DataFrame(results).to_parquet(manifest_path, index=False)

    summary_payload = _build_retry_summary_payload(out_dir, run_date, started_at, bucket_summaries, results)
    summary_path = out_dir / "historical_50_plus_retry_summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_retry_summary_payload(
    out_dir: Path,
    run_date: str,
    started_at: str,
    bucket_summaries: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    result_counter = Counter(row["status"] for row in results)
    on_disk_counts = _read_on_disk_counts(out_dir)
    return {
        "started_at": started_at,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "run_date": run_date,
        "out_dir": str(out_dir),
        "season_runs": bucket_summaries,
        "requested_season_runs": len(bucket_summaries),
        "successful_season_runs": sum(1 for row in bucket_summaries if row.get("status") == "ok"),
        "failed_season_runs": sum(1 for row in bucket_summaries if row.get("status") == "manifest_error"),
        "requested_games": len(results),
        "success_games": result_counter.get("success", 0),
        "skipped_existing_games": sum(1 for row in results if row.get("skipped_existing")),
        "network_error_games": result_counter.get("network_error", 0),
        "transform_error_games": result_counter.get("transform_error", 0),
        "validation_error_games": result_counter.get("validation_error", 0),
        "write_error_games": result_counter.get("write_error", 0),
        "other_error_games": sum(
            count
            for status, count in result_counter.items()
            if status not in {"success", "network_error", "transform_error", "validation_error", "write_error"}
        ),
        "on_disk_unique_games": on_disk_counts["unique_games"],
        "on_disk_player_game_rows": on_disk_counts["player_game_rows"],
        "on_disk_unique_players": on_disk_counts["unique_players"],
    }


def _read_on_disk_counts(out_dir: Path) -> dict[str, int]:
    summary_dir = out_dir / "player_game_summaries"
    parquet_paths = sorted(summary_dir.rglob("*.parquet"))
    if not parquet_paths:
        return {"unique_games": 0, "player_game_rows": 0, "unique_players": 0}
    df = pd.concat((pd.read_parquet(path) for path in parquet_paths), ignore_index=True)
    return {
        "unique_games": int(df["game_id"].astype(str).nunique()),
        "player_game_rows": int(len(df)),
        "unique_players": int(df["player_id"].astype(str).nunique()),
    }


if __name__ == "__main__":
    main()
