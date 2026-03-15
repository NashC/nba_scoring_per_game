from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import time
from typing import Any

import pandas as pd

from .source import fetch_boxscore_player_totals, fetch_playbyplay
from .transforms import (
    RAW_SCORING_COLUMNS,
    SUMMARY_COLUMNS,
    TIMELINE_COLUMNS,
    build_player_scoring_timeline,
    extract_scoring_events,
    summarize_player_games,
)
from .validation import validate_game

WRITE_MODES = {"skip_existing", "overwrite", "error_if_exists"}
CURATED_DATASET_NAMES = (
    "raw_scoring_events",
    "player_scoring_timelines",
    "player_game_summaries",
)


@dataclass
class GameArtifacts:
    manifest_row: dict[str, Any]
    raw_playbyplay: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_scoring_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_scoring_timelines: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_game_summaries: pd.DataFrame = field(default_factory=pd.DataFrame)
    validation_report: dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    skipped_existing: bool = False
    error_type: str | None = None
    error_message: str | None = None
    written_paths: dict[str, str] = field(default_factory=dict)


def process_game(
    manifest_row: Mapping[str, Any] | pd.Series,
    out_dir: str | Path = "data",
    write_mode: str = "skip_existing",
    raw_cache: bool = True,
    run_date: str | None = None,
) -> GameArtifacts:
    """Process one game end to end and write outputs when validation passes."""
    row = _normalize_manifest_row(manifest_row)
    out_path = Path(out_dir)
    current_run_date = run_date or datetime.now().date().isoformat()
    artifact = GameArtifacts(manifest_row=row)

    try:
        _validate_write_mode(write_mode)
    except Exception as exc:
        artifact.status = "write_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    output_paths = _build_output_paths(out_path, row, current_run_date)

    if write_mode == "skip_existing" and _should_skip_existing(row["game_id"], out_path, output_paths):
        artifact.skipped_existing = True
        artifact.status = "success"
        artifact.raw_scoring_events = _read_parquet_if_exists(output_paths["raw_scoring_events"])
        artifact.player_scoring_timelines = _read_parquet_if_exists(output_paths["player_scoring_timelines"])
        artifact.player_game_summaries = _read_parquet_if_exists(output_paths["player_game_summaries"])
        artifact.validation_report = _read_validation_report(output_paths["validation_report"], row)
        artifact.written_paths = {key: str(path) for key, path in output_paths.items() if path.exists()}
        return artifact

    if write_mode == "error_if_exists":
        existing_paths = [path for key, path in output_paths.items() if key in CURATED_DATASET_NAMES and path.exists()]
        if existing_paths:
            artifact.status = "write_error"
            artifact.error_type = "FileExistsError"
            artifact.error_message = f"Curated dataset files already exist: {', '.join(str(path) for path in existing_paths)}"
            return artifact

    try:
        raw_playbyplay = _retry_call(fetch_playbyplay, row["game_id"])
        boxscore_df = _retry_call(fetch_boxscore_player_totals, row["game_id"])
    except Exception as exc:
        artifact.status = "network_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    artifact.raw_playbyplay = raw_playbyplay
    if raw_cache:
        try:
            _write_parquet(raw_playbyplay, output_paths["raw_playbyplay_cache"])
            artifact.written_paths["raw_playbyplay_cache"] = str(output_paths["raw_playbyplay_cache"])
        except Exception as exc:
            artifact.status = "write_error"
            artifact.error_type = type(exc).__name__
            artifact.error_message = str(exc)
            return artifact

    try:
        raw_scoring_events = extract_scoring_events(
            raw_playbyplay,
            game_id=row["game_id"],
            season=row["season"],
            season_type=row["season_type"],
            game_date=row["game_date"],
        )
        player_scoring_timelines = build_player_scoring_timeline(raw_scoring_events)
        player_game_summaries = summarize_player_games(raw_scoring_events)
    except Exception as exc:
        artifact.status = "transform_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    artifact.raw_scoring_events = raw_scoring_events
    artifact.player_scoring_timelines = player_scoring_timelines
    artifact.player_game_summaries = player_game_summaries

    try:
        validation_report = validate_game(
            row["game_id"],
            scoring_events_df=raw_scoring_events,
            raw_df=raw_playbyplay,
            boxscore_df=boxscore_df,
        )
    except Exception as exc:
        artifact.status = "validation_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    artifact.validation_report = validation_report
    try:
        _write_parquet(pd.DataFrame([validation_report]), output_paths["validation_report"])
        artifact.written_paths["validation_report"] = str(output_paths["validation_report"])
    except Exception as exc:
        artifact.status = "write_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    if not validation_report["validation_passed"]:
        artifact.status = "validation_error"
        artifact.error_type = "ValidationFailed"
        artifact.error_message = "Validation gating failed; curated outputs were not written."
        return artifact

    try:
        _write_parquet(raw_scoring_events[RAW_SCORING_COLUMNS], output_paths["raw_scoring_events"])
        _write_parquet(player_scoring_timelines[TIMELINE_COLUMNS], output_paths["player_scoring_timelines"])
        _write_parquet(player_game_summaries[SUMMARY_COLUMNS], output_paths["player_game_summaries"])
    except Exception as exc:
        artifact.status = "write_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    for name in CURATED_DATASET_NAMES:
        artifact.written_paths[name] = str(output_paths[name])
    return artifact


def build_dataset(
    manifest_df: pd.DataFrame,
    out_dir: str | Path,
    write_mode: str = "skip_existing",
    fail_fast: bool = False,
    raw_cache: bool = True,
) -> pd.DataFrame:
    """Process a manifest of games and persist a processing manifest for the run."""
    out_path = Path(out_dir)
    current_run_date = datetime.now().date().isoformat()
    results: list[dict[str, Any]] = []
    sorted_manifest = manifest_df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    for _, row in sorted_manifest.iterrows():
        processed_at = datetime.now().isoformat(timespec="seconds")
        try:
            artifact = process_game(
                row,
                out_dir=out_path,
                write_mode=write_mode,
                raw_cache=raw_cache,
                run_date=current_run_date,
            )
        except Exception as exc:
            if fail_fast:
                raise
            artifact = GameArtifacts(
                manifest_row=_normalize_manifest_row(row),
                status="write_error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        manifest_row = {
            **artifact.manifest_row,
            "run_date": current_run_date,
            "processed_at": processed_at,
            "status": artifact.status,
            "skipped_existing": artifact.skipped_existing,
            "error_type": artifact.error_type,
            "error_message": artifact.error_message,
            "num_scoring_events": int(len(artifact.raw_scoring_events)),
            "validation_passed": artifact.validation_report.get("validation_passed"),
        }
        manifest_row.update(
            {
                key: value
                for key, value in artifact.validation_report.items()
                if key not in {"season", "season_type", "game_date", "game_id"}
            }
        )
        results.append(manifest_row)

        if fail_fast and artifact.status not in {"success"}:
            raise RuntimeError(f"Failed processing game {artifact.manifest_row['game_id']}: {artifact.error_message}")

    processing_manifest = pd.DataFrame(results)
    manifest_path = out_path / "processing_manifest" / f"run_date={current_run_date}.parquet"
    _write_parquet(processing_manifest, manifest_path)
    return processing_manifest


def query_player_games(
    summary_df: pd.DataFrame,
    *,
    min_points: int | None = None,
    max_points: int | None = None,
    max_avg_abs_margin: float | None = None,
    max_median_abs_margin: float | None = None,
    min_pct_within_3: float | None = None,
    min_pct_within_5: float | None = None,
    min_pct_within_10: float | None = None,
    sort_by: str = "final_points",
    ascending: bool = False,
) -> pd.DataFrame:
    """Filter and rank player-game summaries."""
    df = summary_df.copy()
    if min_points is not None:
        df = df.loc[df["final_points"] >= min_points]
    if max_points is not None:
        df = df.loc[df["final_points"] <= max_points]
    if max_avg_abs_margin is not None:
        df = df.loc[df["avg_abs_margin_during_scoring_events"] <= max_avg_abs_margin]
    if max_median_abs_margin is not None:
        df = df.loc[df["median_abs_margin_during_scoring_events"] <= max_median_abs_margin]
    if min_pct_within_3 is not None:
        df = df.loc[df["pct_scoring_events_within_3"] >= min_pct_within_3]
    if min_pct_within_5 is not None:
        df = df.loc[df["pct_scoring_events_within_5"] >= min_pct_within_5]
    if min_pct_within_10 is not None:
        df = df.loc[df["pct_scoring_events_within_10"] >= min_pct_within_10]

    valid_sort_columns = {
        "final_points",
        "avg_abs_margin_during_scoring_events",
        "median_abs_margin_during_scoring_events",
    }
    if sort_by not in valid_sort_columns:
        raise ValueError(f"sort_by must be one of {sorted(valid_sort_columns)}")
    return df.sort_values([sort_by, "game_id", "player_id"], ascending=[ascending, True, True]).reset_index(drop=True)


def load_dataset(dataset_dir: str | Path) -> pd.DataFrame:
    """Load all parquet files recursively from a dataset directory."""
    root = Path(dataset_dir)
    parquet_paths = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not parquet_paths:
        return pd.DataFrame()
    return pd.concat((pd.read_parquet(path) for path in parquet_paths), ignore_index=True)


def _normalize_manifest_row(manifest_row: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
    row = dict(manifest_row)
    required = ["season", "season_type", "game_id", "game_date"]
    missing = [key for key in required if key not in row or pd.isna(row[key])]
    if missing:
        raise ValueError(f"Manifest row is missing required fields: {missing}")
    return {key: row.get(key) for key in row}


def _validate_write_mode(write_mode: str) -> None:
    if write_mode not in WRITE_MODES:
        raise ValueError(f"write_mode must be one of {sorted(WRITE_MODES)}")


def _build_output_paths(out_dir: Path, row: Mapping[str, Any], run_date: str) -> dict[str, Path]:
    season = str(row["season"])
    season_type = str(row["season_type"])
    game_id = str(row["game_id"])
    partition_dir = lambda dataset: out_dir / dataset / f"season={season}" / f"season_type={season_type}"
    return {
        "raw_playbyplay_cache": partition_dir("raw_playbyplay_cache") / f"game_id={game_id}.parquet",
        "raw_scoring_events": partition_dir("raw_scoring_events") / f"part-{game_id}.parquet",
        "player_scoring_timelines": partition_dir("player_scoring_timelines") / f"part-{game_id}.parquet",
        "player_game_summaries": partition_dir("player_game_summaries") / f"part-{game_id}.parquet",
        "validation_report": out_dir / "validation_reports" / f"run_date={run_date}" / f"part-{game_id}.parquet",
    }


def _should_skip_existing(game_id: str, out_dir: Path, output_paths: Mapping[str, Path]) -> bool:
    curated_exist = all(output_paths[name].exists() for name in CURATED_DATASET_NAMES)
    return curated_exist and _has_prior_success(game_id, out_dir)


def _has_prior_success(game_id: str, out_dir: Path) -> bool:
    processing_manifest_dir = out_dir / "processing_manifest"
    parquet_paths = sorted(processing_manifest_dir.glob("*.parquet"))
    if not parquet_paths:
        return False
    for path in parquet_paths:
        df = pd.read_parquet(path)
        matches = df.loc[df["game_id"].astype(str).eq(str(game_id))]
        if not matches.empty and bool(matches.iloc[-1].get("validation_passed")) and matches.iloc[-1]["status"] == "success":
            return True
    return False


def _read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _read_validation_report(path: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return {
            "season": row.get("season"),
            "season_type": row.get("season_type"),
            "game_date": row.get("game_date"),
            "game_id": row.get("game_id"),
            "validation_passed": True,
        }
    df = pd.read_parquet(path)
    if df.empty:
        return {
            "season": row.get("season"),
            "season_type": row.get("season_type"),
            "game_date": row.get("game_date"),
            "game_id": row.get("game_id"),
            "validation_passed": True,
        }
    return df.iloc[0].to_dict()


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp.parquet")
    df.to_parquet(temp_path, index=False)
    temp_path.replace(path)


def _retry_call(func: Any, *args: Any, max_attempts: int = 3, base_delay_seconds: float = 1.0, **kwargs: Any) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(base_delay_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error
