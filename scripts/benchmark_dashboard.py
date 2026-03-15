from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median
import time

from nba_scoring_per_game.dashboard import load_dashboard_datasets
from nba_scoring_per_game.dashboard.state import DashboardFilters, filter_summary_frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dashboard dataset loading and summary filtering.")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    load_start = time.perf_counter()
    datasets = load_dashboard_datasets(out_dir)
    load_duration = time.perf_counter() - load_start

    if not datasets.available:
        print("Dashboard datasets are not available.")
        print(datasets.message or "No message available.")
        return

    scenarios = [
        ("top_scoring_games", DashboardFilters(entity_mode="game", ranking_metric="total_points", min_points=50)),
        (
            "competitive_60_plus_games",
            DashboardFilters(entity_mode="game", ranking_metric="total_points", min_points=60, min_competitive_share=0.75, include_ot=False),
        ),
        ("best_quarters", DashboardFilters(entity_mode="quarter", ranking_metric="quarter_points", min_points=25)),
        ("best_3_min_bursts", DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180, min_points=10)),
    ]

    scenario_timings: list[tuple[str, float, int]] = []
    for name, filters in scenarios:
        timings: list[float] = []
        row_count = 0
        for _ in range(max(1, args.repeats)):
            start = time.perf_counter()
            frame = filter_summary_frame(datasets, filters)
            timings.append(time.perf_counter() - start)
            row_count = len(frame)
        scenario_timings.append((name, median(timings), row_count))

    total_summary_rows = sum(
        len(frame)
        for frame in [
            datasets.game_summaries,
            datasets.quarter_summaries,
            datasets.half_summaries,
            datasets.burst_summaries,
        ]
    )

    print(f"load_dashboard_datasets: {load_duration:.3f}s")
    print(f"total_summary_rows: {total_summary_rows}")
    print("")
    for name, timing, row_count in scenario_timings:
        print(f"{name}: median filter time {timing * 1000:.1f} ms over {args.repeats} runs ({row_count} rows)")

    print("")
    print("Threshold rule:")
    print("- If summary loading exceeds 2.5s on at least 100k summary rows, add a summary index next phase.")
    print("- If median filter time exceeds 250ms over 20 runs, add `.dashboard_cache/summary_index.parquet` next phase.")


if __name__ == "__main__":
    main()
