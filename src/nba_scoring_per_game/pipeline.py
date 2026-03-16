from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

import pandas as pd

from .source import fetch_boxscore_player_totals, fetch_playbyplay
from .transforms import (
    BURST_SUMMARY_COLUMNS,
    BURST_TIMELINE_COLUMNS,
    BURST_WINDOW_SECONDS,
    COMPETITIVE_MARGIN_THRESHOLD,
    HALF_SUMMARY_COLUMNS,
    MATCHUP_CONTEXT_COLUMNS,
    QUARTER_SUMMARY_COLUMNS,
    RAW_SCORING_COLUMNS,
    SUMMARY_COLUMNS,
    TIMELINE_COLUMNS,
    build_player_scoring_timeline,
    extract_scoring_events,
    summarize_player_bursts,
    summarize_player_games,
    summarize_player_halves,
    summarize_player_quarters,
)
from .validation import validate_game

WRITE_MODES = {"skip_existing", "overwrite", "error_if_exists"}
DATASET_SCHEMA_VERSION = "2.4.0"
DATASET_METADATA_FILENAME = "dataset_metadata.json"
CURATED_DATASET_NAMES = (
    "raw_scoring_events",
    "player_scoring_timelines",
    "player_game_summaries",
    "player_quarter_summaries",
    "player_half_summaries",
    "player_burst_summaries",
)


@dataclass
class GameArtifacts:
    manifest_row: dict[str, Any]
    raw_playbyplay: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_scoring_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_scoring_timelines: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_game_summaries: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_quarter_summaries: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_half_summaries: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_burst_summaries: pd.DataFrame = field(default_factory=pd.DataFrame)
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
    _write_dataset_metadata(out_path)

    if write_mode == "skip_existing" and _should_skip_existing(row["game_id"], out_path, output_paths):
        artifact.skipped_existing = True
        artifact.status = "success"
        artifact.raw_scoring_events = _read_parquet_if_exists(output_paths["raw_scoring_events"])
        artifact.player_scoring_timelines = _read_parquet_if_exists(output_paths["player_scoring_timelines"])
        artifact.player_game_summaries = _read_parquet_if_exists(output_paths["player_game_summaries"])
        artifact.player_quarter_summaries = _read_parquet_if_exists(output_paths["player_quarter_summaries"])
        artifact.player_half_summaries = _read_parquet_if_exists(output_paths["player_half_summaries"])
        artifact.player_burst_summaries = _read_parquet_if_exists(output_paths["player_burst_summaries"])
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

    row = _resolve_matchup_context_from_playbyplay(row, raw_playbyplay)
    artifact.manifest_row = row
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
        raw_scoring_events = _add_matchup_context(raw_scoring_events, row)
        player_scoring_timelines = build_player_scoring_timeline(raw_scoring_events)
        player_game_summaries = summarize_player_games(raw_scoring_events, boxscore_df=boxscore_df)
        player_quarter_summaries = summarize_player_quarters(raw_scoring_events)
        player_half_summaries = summarize_player_halves(raw_scoring_events)
        player_burst_summaries = summarize_player_bursts(raw_scoring_events)
    except Exception as exc:
        artifact.status = "transform_error"
        artifact.error_type = type(exc).__name__
        artifact.error_message = str(exc)
        return artifact

    artifact.raw_scoring_events = raw_scoring_events
    artifact.player_scoring_timelines = player_scoring_timelines
    artifact.player_game_summaries = player_game_summaries
    artifact.player_quarter_summaries = player_quarter_summaries
    artifact.player_half_summaries = player_half_summaries
    artifact.player_burst_summaries = player_burst_summaries

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
        _write_parquet(player_quarter_summaries[QUARTER_SUMMARY_COLUMNS], output_paths["player_quarter_summaries"])
        _write_parquet(player_half_summaries[HALF_SUMMARY_COLUMNS], output_paths["player_half_summaries"])
        _write_parquet(player_burst_summaries[BURST_SUMMARY_COLUMNS], output_paths["player_burst_summaries"])
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
    entity_mode: str = "game",
    min_points: int | None = None,
    max_points: int | None = None,
    max_avg_abs_margin: float | None = None,
    max_median_abs_margin: float | None = None,
    min_pct_within_3: float | None = None,
    min_pct_within_5: float | None = None,
    min_pct_within_10: float | None = None,
    competitive_only: bool = False,
    min_competitive_share: float | None = None,
    include_ot: bool = True,
    burst_window: int | None = None,
    ranking_metric: str | None = None,
    sort_by: str = "final_points",
    ascending: bool = False,
) -> pd.DataFrame:
    """Filter and rank summary tables across game, quarter, half, or burst modes."""
    df = summary_df.copy()
    entity_mode_normalized = str(entity_mode).strip().lower()
    point_column = _entity_point_column(entity_mode_normalized, df)
    effective_sort_by = ranking_metric or sort_by

    if burst_window is not None and "burst_window_seconds" in df.columns:
        df = df.loc[df["burst_window_seconds"] == int(burst_window)]
    if min_points is not None and point_column in df.columns:
        df = df.loc[df[point_column] >= min_points]
    if max_points is not None and point_column in df.columns:
        df = df.loc[df[point_column] <= max_points]
    avg_abs_margin_column = _resolve_metric_column(
        ["avg_abs_margin_during_scoring_events", "avg_abs_score_diff_in_window"],
        df,
    )
    median_abs_margin_column = _resolve_metric_column(
        ["median_abs_margin_during_scoring_events", "median_abs_score_diff_in_window"],
        df,
    )
    if max_avg_abs_margin is not None and avg_abs_margin_column is not None:
        df = df.loc[df[avg_abs_margin_column] <= max_avg_abs_margin]
    if max_median_abs_margin is not None and median_abs_margin_column is not None:
        df = df.loc[df[median_abs_margin_column] <= max_median_abs_margin]
    if min_pct_within_3 is not None and "pct_scoring_events_within_3" in df.columns:
        df = df.loc[df["pct_scoring_events_within_3"] >= min_pct_within_3]
    if min_pct_within_5 is not None and "pct_scoring_events_within_5" in df.columns:
        df = df.loc[df["pct_scoring_events_within_5"] >= min_pct_within_5]
    if min_pct_within_10 is not None and "pct_scoring_events_within_10" in df.columns:
        df = df.loc[df["pct_scoring_events_within_10"] >= min_pct_within_10]
    if competitive_only and "competitive_scoring_share" in df.columns:
        df = df.loc[df["competitive_scoring_share"].astype(float) >= 1.0]
    if min_competitive_share is not None and "competitive_scoring_share" in df.columns:
        df = df.loc[df["competitive_scoring_share"].astype(float) >= float(min_competitive_share)]
    if not include_ot:
        if "went_to_overtime" in df.columns:
            df = df.loc[~df["went_to_overtime"].astype(bool)]
        elif "is_overtime_quarter" in df.columns:
            df = df.loc[~df["is_overtime_quarter"].astype(bool)]
        elif "includes_overtime" in df.columns:
            df = df.loc[~df["includes_overtime"].astype(bool)]

    effective_sort_by = _normalize_ranking_metric(effective_sort_by, entity_mode_normalized, point_column)
    if effective_sort_by not in df.columns:
        raise ValueError(f"ranking metric {effective_sort_by!r} is not available for entity_mode={entity_mode_normalized}")
    sort_columns = [effective_sort_by]
    for column in ["game_id", "player_id", "quarter_number", "half_index", "burst_window_seconds"]:
        if column in df.columns:
            sort_columns.append(column)
    ascending_flags = [ascending] + [True] * (len(sort_columns) - 1)
    return df.sort_values(sort_columns, ascending=ascending_flags).reset_index(drop=True)


def load_dataset(dataset_dir: str | Path) -> pd.DataFrame:
    """Load all parquet files recursively from a dataset directory."""
    root = Path(dataset_dir)
    parquet_paths = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not parquet_paths:
        return pd.DataFrame()
    return pd.concat((pd.read_parquet(path) for path in parquet_paths), ignore_index=True)


def get_dataset_metadata(out_dir: str | Path | None = None) -> dict[str, Any]:
    """Return the current dataset schema metadata, preferring an on-disk metadata file when present."""
    if out_dir is not None:
        metadata_path = Path(out_dir) / DATASET_METADATA_FILENAME
        if metadata_path.exists():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
    return _build_dataset_metadata()


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
        "player_quarter_summaries": partition_dir("player_quarter_summaries") / f"part-{game_id}.parquet",
        "player_half_summaries": partition_dir("player_half_summaries") / f"part-{game_id}.parquet",
        "player_burst_summaries": partition_dir("player_burst_summaries") / f"part-{game_id}.parquet",
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


def _write_dataset_metadata(out_dir: Path) -> None:
    payload = _build_dataset_metadata()
    path = out_dir / DATASET_METADATA_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _entity_point_column(entity_mode: str, df: pd.DataFrame) -> str:
    defaults = {
        "game": "final_points",
        "quarter": "quarter_points",
        "half": "half_points",
        "burst": "points_in_window",
    }
    preferred = defaults.get(entity_mode, "final_points")
    if preferred in df.columns:
        return preferred
    if "final_points" in df.columns:
        return "final_points"
    for candidate in ["quarter_points", "half_points", "points_in_window"]:
        if candidate in df.columns:
            return candidate
    raise ValueError("Could not determine the primary point column for the supplied summary dataset.")


def _normalize_ranking_metric(metric: str, entity_mode: str, point_column: str) -> str:
    if metric in {"avg_abs_margin_during_scoring_events", "avg_abs_score_diff_in_window"}:
        return "avg_abs_score_diff_in_window" if entity_mode == "burst" else "avg_abs_margin_during_scoring_events"
    if metric in {"median_abs_margin_during_scoring_events", "median_abs_score_diff_in_window"}:
        return "median_abs_score_diff_in_window" if entity_mode == "burst" else "median_abs_margin_during_scoring_events"
    aliases = {
        "total_points": point_column,
        "best_60_sec_points": "best_60_sec_points",
        "best_2_min_points": "best_2_min_points",
        "best_3_min_points": "best_3_min_points",
        "best_5_min_points": "best_5_min_points",
        "best_10_min_points": "best_10_min_points",
        "best_quarter_points": "best_quarter_points",
        "best_half_points": "best_half_points",
        "peak_projected_48": "peak_projected_48",
        "points_per_minute": "window_points_per_minute" if entity_mode == "burst" else "points_per_minute",
        "offensive_share": "offensive_share",
        "competitive_points": "competitive_points_in_window" if entity_mode == "burst" else "competitive_points",
        "competitive_scoring_share": "competitive_scoring_share",
        "trailing_points": "trailing_points_in_window" if entity_mode == "burst" else "trailing_points",
        "trailing_scoring_rate": "trailing_scoring_rate",
        "ts_pct": "ts_pct",
        "efg_pct": "efg_pct",
    }
    if metric == "final_points" and entity_mode != "game":
        return point_column
    return aliases.get(metric, metric)


def _resolve_metric_column(candidates: list[str], df: pd.DataFrame) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _add_matchup_context(df: pd.DataFrame, row: Mapping[str, Any]) -> pd.DataFrame:
    enriched = df.copy()
    for column in MATCHUP_CONTEXT_COLUMNS:
        if column not in enriched.columns:
            enriched[column] = pd.NA

    home_team_id = row.get("home_team_id")
    away_team_id = row.get("away_team_id")
    home_team_tricode = row.get("home_team_tricode")
    away_team_tricode = row.get("away_team_tricode")
    home_team_context_wins = row.get("home_team_context_wins")
    home_team_context_losses = row.get("home_team_context_losses")
    home_team_context_win_pct = row.get("home_team_context_win_pct")
    away_team_context_wins = row.get("away_team_context_wins")
    away_team_context_losses = row.get("away_team_context_losses")
    away_team_context_win_pct = row.get("away_team_context_win_pct")
    record_context_scope = row.get("record_context_scope", "pregame")
    is_playoff_game = _coerce_manifest_bool(
        row.get("is_playoff_game"),
        default=str(row.get("season_type", "")).strip().lower() == "playoffs",
    )
    enriched["home_team_id"] = home_team_id
    enriched["home_team_tricode"] = home_team_tricode
    enriched["away_team_id"] = away_team_id
    enriched["away_team_tricode"] = away_team_tricode

    if enriched.empty:
        return enriched

    is_home_team = enriched["location"].astype(str).str.lower().eq("h")
    enriched["is_home_team"] = is_home_team
    enriched["opponent_team_id"] = pd.Series(
        [away_team_id if is_home else home_team_id for is_home in is_home_team],
        index=enriched.index,
    )
    enriched["opponent_team_tricode"] = pd.Series(
        [away_team_tricode if is_home else home_team_tricode for is_home in is_home_team],
        index=enriched.index,
    )
    enriched["opponent_wins"] = pd.Series(
        [away_team_context_wins if is_home else home_team_context_wins for is_home in is_home_team],
        index=enriched.index,
    )
    enriched["opponent_losses"] = pd.Series(
        [away_team_context_losses if is_home else home_team_context_losses for is_home in is_home_team],
        index=enriched.index,
    )
    enriched["opponent_win_pct"] = pd.Series(
        [away_team_context_win_pct if is_home else home_team_context_win_pct for is_home in is_home_team],
        index=enriched.index,
    )
    enriched["opponent_record_scope"] = record_context_scope
    enriched["is_playoff_game"] = is_playoff_game
    return enriched


def _resolve_matchup_context_from_playbyplay(
    row: Mapping[str, Any],
    raw_playbyplay: pd.DataFrame,
) -> dict[str, Any]:
    resolved = dict(row)
    if raw_playbyplay.empty:
        return resolved

    required = {"teamId", "teamTricode", "location"}
    if not required.issubset(raw_playbyplay.columns):
        return resolved

    candidates = raw_playbyplay.loc[
        raw_playbyplay["teamId"].notna()
        & raw_playbyplay["teamTricode"].notna()
        & raw_playbyplay["location"].astype(str).str.lower().isin({"h", "v"})
    , ["teamId", "teamTricode", "location"]].copy()
    if candidates.empty:
        return resolved

    candidates["teamId"] = pd.to_numeric(candidates["teamId"], errors="coerce")
    candidates = candidates.dropna(subset=["teamId"])
    if candidates.empty:
        return resolved

    candidates["location"] = candidates["location"].astype(str).str.lower()
    grouped = (
        candidates.groupby(["teamId", "teamTricode", "location"], dropna=False)
        .size()
        .reset_index(name="event_count")
    )
    home_rows = grouped.loc[grouped["location"].eq("h")].sort_values("event_count", ascending=False)
    away_rows = grouped.loc[grouped["location"].eq("v")].sort_values("event_count", ascending=False)
    if home_rows.empty or away_rows.empty:
        return resolved

    home_row = home_rows.iloc[0]
    away_row = away_rows.iloc[0]
    if int(home_row["teamId"]) == int(away_row["teamId"]):
        return resolved

    resolved["home_team_id"] = int(home_row["teamId"])
    resolved["home_team_tricode"] = str(home_row["teamTricode"])
    resolved["away_team_id"] = int(away_row["teamId"])
    resolved["away_team_tricode"] = str(away_row["teamTricode"])
    return _realign_team_context_fields(resolved, row)


def _realign_team_context_fields(
    resolved: dict[str, Any],
    original_row: Mapping[str, Any],
) -> dict[str, Any]:
    team_context_by_id: dict[int, dict[str, Any]] = {}
    team_context_by_tricode: dict[str, dict[str, Any]] = {}
    for side in ("home", "away"):
        context = {
            "wins": original_row.get(f"{side}_team_context_wins"),
            "losses": original_row.get(f"{side}_team_context_losses"),
            "win_pct": original_row.get(f"{side}_team_context_win_pct"),
        }
        team_id = original_row.get(f"{side}_team_id")
        team_tricode = original_row.get(f"{side}_team_tricode")
        try:
            numeric_team_id = int(team_id)
        except (TypeError, ValueError):
            numeric_team_id = None
        if numeric_team_id is not None:
            team_context_by_id[numeric_team_id] = context
        normalized_tricode = str(team_tricode).strip().upper()
        if normalized_tricode:
            team_context_by_tricode[normalized_tricode] = context

    for side in ("home", "away"):
        resolved_team_id = resolved.get(f"{side}_team_id")
        resolved_tricode = str(resolved.get(f"{side}_team_tricode", "")).strip().upper()
        try:
            numeric_resolved_team_id = int(resolved_team_id)
        except (TypeError, ValueError):
            numeric_resolved_team_id = None
        context = None
        if numeric_resolved_team_id is not None:
            context = team_context_by_id.get(numeric_resolved_team_id)
        if context is None and resolved_tricode:
            context = team_context_by_tricode.get(resolved_tricode)
        if context is None:
            continue
        resolved[f"{side}_team_context_wins"] = context["wins"]
        resolved[f"{side}_team_context_losses"] = context["losses"]
        resolved[f"{side}_team_context_win_pct"] = context["win_pct"]
    return resolved


def _coerce_manifest_bool(value: Any, *, default: bool) -> bool:
    if value in {None, "", "None"}:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return default


def _build_dataset_metadata() -> dict[str, Any]:
    return {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "metadata_filename": DATASET_METADATA_FILENAME,
        "competitive_margin_threshold": COMPETITIVE_MARGIN_THRESHOLD,
        "burst_window_seconds": list(BURST_WINDOW_SECONDS),
        "selection_helpers": [
            "build_quarter_timeline",
            "build_half_timeline",
            "build_burst_timeline",
        ],
        "datasets": {
            "raw_scoring_events": RAW_SCORING_COLUMNS,
            "player_scoring_timelines": TIMELINE_COLUMNS,
            "player_game_summaries": SUMMARY_COLUMNS,
            "player_quarter_summaries": QUARTER_SUMMARY_COLUMNS,
            "player_half_summaries": HALF_SUMMARY_COLUMNS,
            "player_burst_summaries": BURST_SUMMARY_COLUMNS,
            "player_burst_timelines": BURST_TIMELINE_COLUMNS,
        },
    }
