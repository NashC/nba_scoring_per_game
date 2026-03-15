from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_scoring_per_game import (  # noqa: E402
    add_game_time_columns,
    build_player_scoring_timeline,
    fetch_boxscore_player_totals,
    fetch_game_manifest,
    extract_scoring_events,
    fetch_playbyplay,
    inspect_playbyplay,
    process_game,
    summarize_player_bursts,
    summarize_player_games,
    summarize_player_halves,
    summarize_player_quarters,
    validate_game,
)

INSPECTION_GAME_ID = "0020500594"
KOBE_81_GAME_ID = "0020500591"
KOBE_PLAYER_ID = 977
OT_VALIDATION_GAME_ID = "0022301070"
KOBE_SEASON = "2005-06"
OT_SEASON = "2023-24"


def print_section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def main() -> None:
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.width", 140)

    print_section("A. Source Assessment")
    print(
        "Using official NBA play-by-play via nba_api PlayByPlayV3. "
        "It exposes period, clock, event ordering fields, player/team identity, action metadata, "
        "and running scores needed for event-level scoring plus competitiveness context."
    )
    print(
        "Empirical caveat: PlayByPlayV3 `pointsTotal` is the running game total after the event, "
        "not the event's point value. This pipeline derives `point_value` from score deltas."
    )

    print_section("B. Raw Inspection")
    raw_inspection = fetch_playbyplay(INSPECTION_GAME_ID)
    inspection = inspect_playbyplay(raw_inspection, sample_rows=12, sample_scoring_rows=12)
    print("Columns:")
    print(inspection["columns"])
    print()
    print("Sample raw rows:")
    print(inspection["sample_rows"].head(12).to_string(index=False))
    print()
    print("Sample apparent scoring rows:")
    print(inspection["sample_scoring_rows"].to_string(index=False))

    print_section("C. Scoring-Event Extraction")
    inspection_scoring = extract_scoring_events(
        raw_inspection,
        game_id=INSPECTION_GAME_ID,
        season="2005-06",
        season_type="Regular Season",
        game_date="2006-01-24",
    )
    print(inspection_scoring.head(15).to_string(index=False))

    print_section("D. Timeline Transformation")
    kobe_raw = fetch_playbyplay(KOBE_81_GAME_ID)
    kobe_scoring = extract_scoring_events(
        kobe_raw,
        game_id=KOBE_81_GAME_ID,
        season=KOBE_SEASON,
        season_type="Regular Season",
        game_date="2006-01-22",
    )
    kobe_timeline = build_player_scoring_timeline(
        kobe_scoring,
        player_id=KOBE_PLAYER_ID,
        game_id=KOBE_81_GAME_ID,
    )
    timeline_columns = [
        "player_name",
        "game_id",
        "period",
        "clock",
        "point_value",
        "elapsed_minutes_in_game",
        "game_time_normalized",
        "player_game_cumulative_points",
        "cumulative_2pt_points",
        "cumulative_3pt_points",
        "cumulative_ft_points",
        "player_team_margin_after",
        "margin_bucket",
        "projected_48",
        "scoring_type",
        "competitiveness_bucket",
    ]
    print(kobe_timeline[timeline_columns].head(20).to_string(index=False))

    print_section("E. Summary / Ranking Logic")
    ot_scoring = extract_scoring_events(
        fetch_playbyplay(OT_VALIDATION_GAME_ID),
        game_id=OT_VALIDATION_GAME_ID,
        season=OT_SEASON,
        season_type="Regular Season",
        game_date="2024-03-29",
    )
    combined_scoring = pd.concat([inspection_scoring, kobe_scoring, ot_scoring], ignore_index=True)
    combined_boxscore = pd.concat(
        [
            fetch_boxscore_player_totals(INSPECTION_GAME_ID),
            fetch_boxscore_player_totals(KOBE_81_GAME_ID),
            fetch_boxscore_player_totals(OT_VALIDATION_GAME_ID),
        ],
        ignore_index=True,
    )
    summary = summarize_player_games(combined_scoring, boxscore_df=combined_boxscore)
    quarter_summary = summarize_player_quarters(combined_scoring)
    half_summary = summarize_player_halves(combined_scoring)
    burst_summary = summarize_player_bursts(combined_scoring)
    print("Player-game summary:")
    print(summary.head(10).to_string(index=False))
    print()
    print("Top quarters:")
    print(quarter_summary.sort_values("quarter_points", ascending=False).head(10).to_string(index=False))
    print()
    print("Top halves:")
    print(half_summary.sort_values("half_points", ascending=False).head(10).to_string(index=False))
    print()
    print("Top 3-minute bursts:")
    print(
        burst_summary.loc[burst_summary["burst_window_seconds"].eq(180)]
        .sort_values("points_in_window", ascending=False)
        .head(10)
        .to_string(index=False)
    )

    print_section("F. Validation Notes")
    for game_id in [INSPECTION_GAME_ID, KOBE_81_GAME_ID, OT_VALIDATION_GAME_ID]:
        print(validate_game(game_id))

    print_section("G. Sample Output")
    sample_columns = [
        "player_name",
        "game_id",
        "period",
        "clock",
        "point_value",
        "elapsed_minutes_in_game",
        "player_game_cumulative_points",
        "player_team_margin_after",
    ]
    print(kobe_timeline[sample_columns].head(12).to_string(index=False))

    print_section("OT Time Check")
    ot_timeline = add_game_time_columns(ot_scoring)
    print(
        ot_timeline.loc[ot_timeline["period"] >= 5, ["game_id", "period", "clock", "elapsed_seconds_in_game"]]
        .head(12)
        .to_string(index=False)
    )

    print_section("Batch Example")
    season_manifest = fetch_game_manifest("2023-24").head(1)
    artifact = process_game(season_manifest.iloc[0], out_dir=ROOT / "data", write_mode="overwrite", raw_cache=False)
    print(pd.DataFrame([{
        "game_id": artifact.manifest_row["game_id"],
        "status": artifact.status,
        "validation_passed": artifact.validation_report.get("validation_passed"),
        "num_scoring_events": len(artifact.raw_scoring_events),
        "num_quarter_rows": len(artifact.player_quarter_summaries),
        "num_half_rows": len(artifact.player_half_summaries),
        "num_burst_rows": len(artifact.player_burst_summaries),
    }]).to_string(index=False))


if __name__ == "__main__":
    main()
