from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .pipeline import build_dataset, load_dataset, process_game, query_player_games
from .source import fetch_game_manifest, fetch_playbyplay
from .transforms import inspect_playbyplay


def main() -> None:
    parser = argparse.ArgumentParser(description="NBA player scoring progression pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-game", help="Inspect raw play-by-play for one game")
    inspect_parser.add_argument("--game-id", required=True)

    process_parser = subparsers.add_parser("process-game", help="Process one game and write outputs")
    process_parser.add_argument("--game-id", required=True)
    process_parser.add_argument("--season", required=True)
    process_parser.add_argument("--season-type", default="Regular Season")
    process_parser.add_argument("--out-dir", default="data")
    process_parser.add_argument("--write-mode", default="skip_existing")
    process_parser.add_argument("--raw-cache", default="true")

    backfill_parser = subparsers.add_parser("backfill-season", help="Backfill one season")
    backfill_parser.add_argument("--season", required=True)
    backfill_parser.add_argument("--season-type", default="Regular Season")
    backfill_parser.add_argument("--out-dir", default="data")
    backfill_parser.add_argument("--write-mode", default="skip_existing")
    backfill_parser.add_argument("--fail-fast", default="false")
    backfill_parser.add_argument("--raw-cache", default="true")

    query_parser = subparsers.add_parser("query-summaries", help="Filter and rank player-game summaries")
    query_parser.add_argument("--out-dir", default="data")
    query_parser.add_argument("--entity-mode", default="game", choices=["game", "quarter", "half", "burst"])
    query_parser.add_argument("--min-points", type=int)
    query_parser.add_argument("--max-points", type=int)
    query_parser.add_argument("--max-avg-abs-margin", type=float)
    query_parser.add_argument("--max-median-abs-margin", type=float)
    query_parser.add_argument("--min-pct-within-3", type=float)
    query_parser.add_argument("--min-pct-within-5", type=float)
    query_parser.add_argument("--min-pct-within-10", type=float)
    query_parser.add_argument("--min-competitive-share", type=float)
    query_parser.add_argument("--ranking-metric", default="total_points")
    query_parser.add_argument("--sort-by", default="final_points")
    query_parser.add_argument("--burst-window", type=int)
    query_parser.add_argument("--competitive-only", default="false")
    query_parser.add_argument("--include-ot", default="true")
    query_parser.add_argument("--descending", default="true")

    args = parser.parse_args()

    if args.command == "inspect-game":
        raw_df = fetch_playbyplay(args.game_id)
        inspection = inspect_playbyplay(raw_df, sample_rows=12, sample_scoring_rows=12)
        print("Columns:")
        print(inspection["columns"])
        print()
        print("Sample raw rows:")
        print(inspection["sample_rows"].to_string(index=False))
        print()
        print("Sample apparent scoring rows:")
        print(inspection["sample_scoring_rows"].to_string(index=False))
        return

    if args.command == "process-game":
        manifest = fetch_game_manifest(args.season, args.season_type)
        selected = manifest.loc[manifest["game_id"].astype(str).eq(str(args.game_id))]
        if selected.empty:
            raise ValueError(
                f"Game {args.game_id} was not found in manifest for season={args.season} season_type={args.season_type}"
            )
        artifact = process_game(
            selected.iloc[0],
            out_dir=Path(args.out_dir),
            write_mode=args.write_mode,
            raw_cache=_parse_bool(args.raw_cache),
        )
        print(pd.DataFrame([_artifact_to_row(artifact)]).to_string(index=False))
        return

    if args.command == "backfill-season":
        manifest = fetch_game_manifest(args.season, args.season_type)
        processing_manifest = build_dataset(
            manifest,
            out_dir=Path(args.out_dir),
            write_mode=args.write_mode,
            fail_fast=_parse_bool(args.fail_fast),
            raw_cache=_parse_bool(args.raw_cache),
        )
        print(processing_manifest.to_string(index=False))
        return

    if args.command == "query-summaries":
        dataset_dir = _dataset_dir_for_entity_mode(args.entity_mode)
        summary_path = Path(args.out_dir) / dataset_dir
        summary_df = load_dataset(summary_path)
        if summary_df.empty:
            print("No summary data found.")
            return
        result = query_player_games(
            summary_df,
            entity_mode=args.entity_mode,
            min_points=args.min_points,
            max_points=args.max_points,
            max_avg_abs_margin=args.max_avg_abs_margin,
            max_median_abs_margin=args.max_median_abs_margin,
            min_pct_within_3=args.min_pct_within_3,
            min_pct_within_5=args.min_pct_within_5,
            min_pct_within_10=args.min_pct_within_10,
            competitive_only=_parse_bool(args.competitive_only),
            min_competitive_share=args.min_competitive_share,
            include_ot=_parse_bool(args.include_ot),
            burst_window=args.burst_window,
            ranking_metric=args.ranking_metric,
            sort_by=args.sort_by,
            ascending=not _parse_bool(args.descending),
        )
        print(result.to_string(index=False))


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"Could not parse boolean value: {value}")


def _artifact_to_row(artifact: object) -> dict[str, object]:
    return {
        "game_id": artifact.manifest_row.get("game_id"),
        "status": artifact.status,
        "skipped_existing": artifact.skipped_existing,
        "validation_passed": artifact.validation_report.get("validation_passed"),
        "num_scoring_events": len(artifact.raw_scoring_events),
        "num_quarter_rows": len(artifact.player_quarter_summaries),
        "num_half_rows": len(artifact.player_half_summaries),
        "num_burst_rows": len(artifact.player_burst_summaries),
        "error_type": artifact.error_type,
        "error_message": artifact.error_message,
    }


def _dataset_dir_for_entity_mode(entity_mode: str) -> str:
    mapping = {
        "game": "player_game_summaries",
        "quarter": "player_quarter_summaries",
        "half": "player_half_summaries",
        "burst": "player_burst_summaries",
    }
    return mapping[entity_mode]


if __name__ == "__main__":
    main()
