from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from diskcache import Cache
import pandas as pd

from ..pipeline import DATASET_METADATA_FILENAME, DATASET_SCHEMA_VERSION, get_dataset_metadata, load_dataset


@dataclass(slots=True)
class DashboardDatasets:
    out_dir: Path
    metadata: dict[str, Any]
    game_summaries: pd.DataFrame
    quarter_summaries: pd.DataFrame
    half_summaries: pd.DataFrame
    burst_summaries: pd.DataFrame
    available: bool
    message: str | None = None


def load_dashboard_datasets(out_dir: str | Path = "data") -> DashboardDatasets:
    """Load app-facing summary datasets and validate the published schema contract."""
    out_path = Path(out_dir)
    metadata_path = out_path / DATASET_METADATA_FILENAME
    if not metadata_path.exists():
        return DashboardDatasets(
            out_dir=out_path,
            metadata={},
            game_summaries=pd.DataFrame(),
            quarter_summaries=pd.DataFrame(),
            half_summaries=pd.DataFrame(),
            burst_summaries=pd.DataFrame(),
            available=False,
            message=(
                "No curated parquet outputs were found. "
                "Run `nba-scoring-per-game backfill-season --season 2023-24 --out-dir data` first."
            ),
        )

    metadata = get_dataset_metadata(out_path)
    schema_version = metadata.get("dataset_schema_version")
    if schema_version != DATASET_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported dataset schema version for the dashboard. "
            f"Expected {DATASET_SCHEMA_VERSION}, found {schema_version}."
        )

    cache_key = ("dashboard-datasets", str(out_path.resolve()), _summary_signature(out_path), schema_version)
    with _cache_for_out_dir(out_path) as cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        datasets = DashboardDatasets(
            out_dir=out_path,
            metadata=metadata,
            game_summaries=_prepare_summary_frame(load_dataset(out_path / "player_game_summaries")),
            quarter_summaries=_prepare_summary_frame(load_dataset(out_path / "player_quarter_summaries")),
            half_summaries=_prepare_summary_frame(load_dataset(out_path / "player_half_summaries")),
            burst_summaries=_prepare_summary_frame(load_dataset(out_path / "player_burst_summaries")),
            available=True,
            message=None,
        )
        if all(
            frame.empty
            for frame in [
                datasets.game_summaries,
                datasets.quarter_summaries,
                datasets.half_summaries,
                datasets.burst_summaries,
            ]
        ):
            datasets.available = False
            datasets.message = (
                "Curated datasets were found, but they are empty. "
                "Run `nba-scoring-per-game process-game` or `backfill-season` to populate them."
            )

        cache.set(cache_key, datasets)
    return datasets


def load_selected_timelines(
    out_dir: str | Path,
    selections: Iterable[dict[str, Any]],
) -> pd.DataFrame:
    """Load only the player timeline parquet files needed for the current selections."""
    selections_list = [dict(selection) for selection in selections]
    if not selections_list:
        return pd.DataFrame()

    out_path = Path(out_dir)
    signature = tuple(
        sorted(
            {
                (
                    str(selection.get("season")),
                    str(selection.get("season_type")),
                    str(selection.get("game_id")),
                )
                for selection in selections_list
            }
        )
    )
    cache_key = ("selected-timelines", str(out_path.resolve()), signature)
    with _cache_for_out_dir(out_path) as cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        frames: list[pd.DataFrame] = []
        for season, season_type, game_id in signature:
            path = (
                out_path
                / "player_scoring_timelines"
                / f"season={season}"
                / f"season_type={season_type}"
                / f"part-{game_id}.parquet"
            )
            if path.exists():
                frames.append(pd.read_parquet(path))

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        cache.set(cache_key, combined)
    return combined


def _summary_signature(out_dir: Path) -> tuple[tuple[str, int], ...]:
    targets = [
        out_dir / DATASET_METADATA_FILENAME,
        out_dir / "player_game_summaries",
        out_dir / "player_quarter_summaries",
        out_dir / "player_half_summaries",
        out_dir / "player_burst_summaries",
    ]
    signature: list[tuple[str, int]] = []
    for target in targets:
        if target.exists():
            if target.is_file():
                signature.append((str(target), target.stat().st_mtime_ns))
            else:
                newest = max((path.stat().st_mtime_ns for path in target.rglob("*.parquet")), default=0)
                signature.append((str(target), newest))
        else:
            signature.append((str(target), 0))
    return tuple(signature)


def _cache_for_out_dir(out_dir: Path) -> Cache:
    cache_dir = out_dir / ".dashboard_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Cache(str(cache_dir))


def _prepare_summary_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    if "era" not in prepared.columns and "season" in prepared.columns:
        prepared["era"] = prepared["season"].astype(str).map(_season_to_era)
    return prepared


def _season_to_era(season: str) -> str | None:
    text = str(season).strip()
    if not text:
        return None
    try:
        year = int(text[:4])
    except ValueError:
        return None
    decade = year - (year % 10)
    return f"{decade}s"
