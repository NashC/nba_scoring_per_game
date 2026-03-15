from __future__ import annotations

from typing import Any

from dash import dcc, html
from dash import dash_table
import pandas as pd

from ..transforms import build_burst_timeline, build_half_timeline, build_quarter_timeline
from .charts import build_empty_figure, build_secondary_analysis_figure, build_trajectory_figure
from .loader import DashboardDatasets, load_selected_timelines
from .state import (
    DashboardFilters,
    build_filter_options,
    build_leaderboard_table,
    filter_summary_frame,
    get_preset_options,
    get_ranking_options,
    select_records,
    selection_from_record,
)


def build_dashboard_layout(datasets: DashboardDatasets) -> html.Div:
    if not datasets.available:
        return html.Div(
            className="app-shell",
            children=[
                dcc.Location(id="dashboard-location", refresh=False),
                dcc.Download(id="leaderboard-download"),
                dcc.Store(id="url-selected-ids"),
                html.Div(
                    className="empty-state-card",
                    children=[
                        html.H1("NBA Scoring Explorer", className="app-title"),
                        html.P(
                            datasets.message or "No local parquet data is available yet.",
                            className="empty-state-text",
                        ),
                        html.Pre(
                            "nba-scoring-per-game backfill-season --season 2023-24 --out-dir data",
                            className="empty-state-command",
                        ),
                    ],
                ),
            ],
        )

    default_filters = DashboardFilters()
    initial_frame = filter_summary_frame(datasets, default_filters)
    initial_records, initial_columns = build_leaderboard_table(initial_frame, default_filters)
    initial_selected_ids = [initial_records[0]["id"]] if initial_records else []
    initial_selected_records = select_records(initial_records, initial_selected_ids)
    initial_timelines = load_selected_timelines(datasets.out_dir, initial_selected_records)
    initial_primary_figure = (
        build_trajectory_figure(
            initial_selected_records,
            initial_timelines,
            default_filters,
            burst_summaries=datasets.burst_summaries,
        )
        if initial_selected_records
        else build_empty_figure("No performances matched the current filters.")
    )
    initial_secondary_figure = build_secondary_analysis_figure(initial_selected_records, initial_timelines, default_filters)
    initial_details = build_enriched_detail_cards(initial_selected_records, default_filters.entity_mode, initial_timelines)
    initial_status = (
        "Previewing the top-ranked performance. Select rows in the leaderboard to compare up to 4 lines."
        if initial_records
        else "No performances matched the current filters."
    )
    filter_options = build_filter_options(datasets)

    return html.Div(
        className="app-shell",
        children=[
            dcc.Location(id="dashboard-location", refresh=False),
            dcc.Download(id="leaderboard-download"),
            dcc.Store(id="url-selected-ids"),
            html.Div(
                className="hero-panel",
                children=[
                    html.Div(
                        children=[
                            html.Div("NBA Scoring Explorer", className="eyebrow"),
                            html.H1("Historic scoring trajectories, bursts, quarters, and context.", className="app-title"),
                            html.P(
                                "Compare volume, pace, burst intensity, shot mix, and competitiveness across the best scoring performances ever.",
                                className="app-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        className="hero-metrics",
                        children=[
                            _metric_chip("Games", len(datasets.game_summaries)),
                            _metric_chip("Quarters", len(datasets.quarter_summaries)),
                            _metric_chip("Halves", len(datasets.half_summaries)),
                            _metric_chip("Bursts", len(datasets.burst_summaries)),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="filter-bar",
                children=[
                    _dropdown("Preset", "preset-filter", get_preset_options(), None, clearable=True),
                    _dropdown(
                        "Entity Mode",
                        "entity-mode",
                        [
                            {"label": "Full Game", "value": "game"},
                            {"label": "Quarter", "value": "quarter"},
                            {"label": "Half", "value": "half"},
                            {"label": "Burst", "value": "burst"},
                        ],
                        default_filters.entity_mode,
                        clearable=False,
                    ),
                    _dropdown(
                        "Ranking Metric",
                        "ranking-metric",
                        get_ranking_options(default_filters.entity_mode),
                        default_filters.ranking_metric,
                        clearable=False,
                    ),
                    _dropdown(
                        "Time Mode",
                        "time-mode",
                        [
                            {"label": "Raw Time", "value": "raw"},
                            {"label": "Normalized", "value": "normalized"},
                        ],
                        default_filters.time_mode,
                        clearable=False,
                    ),
                    _dropdown(
                        "Analysis Mode",
                        "analysis-mode",
                        [
                            {"label": "None", "value": "none"},
                            {"label": "Rolling Points", "value": "rolling_points"},
                            {"label": "Rolling Rate", "value": "rolling_rate"},
                            {"label": "Projected Pace", "value": "projected_pace"},
                        ],
                        default_filters.analysis_mode,
                        clearable=False,
                    ),
                    html.Div(
                        id="analysis-window-wrap",
                        className="filter-control",
                        style={"display": "none"},
                        children=[
                            html.Label("Analysis Window", className="filter-label"),
                            dcc.Dropdown(
                                id="analysis-window",
                                options=[
                                    {"label": "60 sec", "value": 60},
                                    {"label": "2 min", "value": 120},
                                    {"label": "3 min", "value": 180},
                                    {"label": "5 min", "value": 300},
                                    {"label": "10 min", "value": 600},
                                ],
                                value=default_filters.analysis_window,
                                clearable=False,
                            ),
                        ],
                    ),
                    html.Div(
                        id="burst-window-wrap",
                        className="filter-control",
                        children=[
                            html.Label("Burst Window", className="filter-label"),
                            dcc.Dropdown(
                                id="burst-window",
                                options=[
                                    {"label": "60 sec", "value": 60},
                                    {"label": "2 min", "value": 120},
                                    {"label": "3 min", "value": 180},
                                    {"label": "5 min", "value": 300},
                                    {"label": "10 min", "value": 600},
                                ],
                                value=default_filters.burst_window,
                                clearable=False,
                            ),
                        ],
                        style={"display": "none"},
                    ),
                    _dropdown(
                        "Line Color",
                        "line-color-mode",
                        [
                            {"label": "Compare Colors", "value": "player"},
                            {"label": "Margin Context", "value": "margin"},
                        ],
                        default_filters.line_color_mode,
                        clearable=False,
                    ),
                    _dropdown("Season", "season-filter", filter_options["season"], None, clearable=True),
                    _dropdown("Season Type", "season-type-filter", filter_options["season_type"], None, clearable=True),
                    _dropdown("Era", "era-filter", filter_options["era"], None, clearable=True),
                    _dropdown("Player", "player-filter", filter_options["player"], None, clearable=True),
                    _dropdown("Team", "team-filter", filter_options["team"], None, clearable=True),
                    _dropdown("Opponent", "opponent-filter", filter_options["opponent"], None, clearable=True),
                    _number_input("Min Points", "min-points", default_filters.min_points, 0),
                    _number_input("Min Competitive Share", "min-competitive-share", "", 0, 0.05),
                    html.Div(
                        id="min-ts-pct-wrap",
                        className="filter-control",
                        children=[
                            html.Label("Min TS%", className="filter-label"),
                            dcc.Input(id="min-ts-pct", type="number", value="", min=0, max=1, step=0.01, className="numeric-input"),
                        ],
                    ),
                    html.Div(
                        id="min-efg-pct-wrap",
                        className="filter-control",
                        children=[
                            html.Label("Min eFG%", className="filter-label"),
                            dcc.Input(id="min-efg-pct", type="number", value="", min=0, max=1, step=0.01, className="numeric-input"),
                        ],
                    ),
                    html.Div(
                        id="min-offensive-share-wrap",
                        className="filter-control",
                        children=[
                            html.Label("Min Offensive Share", className="filter-label"),
                            dcc.Input(
                                id="min-offensive-share",
                                type="number",
                                value="",
                                min=0,
                                max=1,
                                step=0.01,
                                className="numeric-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter-control compact-checks",
                        children=[
                            html.Label("Display", className="filter-label"),
                            dcc.Checklist(
                                id="shot-markers",
                                options=[{"label": "Shot Markers", "value": "markers"}],
                                value=["markers"],
                                className="compact-checklist",
                            ),
                            dcc.Checklist(
                                id="include-ot",
                                options=[{"label": "Include OT", "value": "include"}],
                                value=["include"],
                                className="compact-checklist",
                            ),
                            dcc.Checklist(
                                id="competitive-only",
                                options=[{"label": "Competitive Only", "value": "competitive"}],
                                value=[],
                                className="compact-checklist",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(initial_status, id="status-banner", className="status-banner"),
            html.Div(
                className="content-grid",
                children=[
                    html.Div(
                        className="leaderboard-panel",
                        children=[
                            html.Div(
                                className="panel-header panel-header-row",
                                children=[
                                    html.Div(
                                        children=[
                                            html.H2("Leaderboard", className="panel-title"),
                                            html.P("Select up to 4 rows to compare.", className="panel-caption"),
                                        ]
                                    ),
                                    html.Button("Export CSV", id="export-leaderboard", className="panel-button", n_clicks=0),
                                ],
                            ),
                            dash_table.DataTable(
                                id="leaderboard-table",
                                data=initial_records,
                                columns=initial_columns,
                                selected_row_ids=initial_selected_ids,
                                row_selectable="multi",
                                sort_action="none",
                                style_as_list_view=True,
                                page_size=14,
                                style_table={"overflowX": "auto"},
                                style_header={
                                    "backgroundColor": "#efe5d7",
                                    "fontWeight": 700,
                                    "border": "none",
                                    "color": "#1f1b18",
                                },
                                style_cell={
                                    "backgroundColor": "#fffaf2",
                                    "border": "none",
                                    "color": "#1f1b18",
                                    "fontFamily": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif",
                                    "padding": "10px 12px",
                                    "textAlign": "left",
                                },
                                style_data_conditional=[
                                    {
                                        "if": {"state": "selected"},
                                        "backgroundColor": "#efe5d7",
                                        "border": "none",
                                    }
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="chart-panel",
                        children=[
                            html.Div(
                                className="panel-header",
                                children=[
                                    html.H2("Trajectory View", className="panel-title"),
                                    html.P("The main chart stays cumulative; secondary analysis runs below it.", className="panel-caption"),
                                ],
                            ),
                            html.Div(id="comparison-tray", className="comparison-tray", children=build_comparison_tray(initial_selected_records)),
                            html.Div(id="margin-legend-wrap", className="margin-legend-wrap", style={"display": "none"}, children=build_margin_legend()),
                            dcc.Graph(
                                id="comparison-chart",
                                figure=initial_primary_figure,
                                config={"displayModeBar": "hover", "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                            ),
                            html.Div(
                                id="secondary-analysis-panel",
                                className="secondary-analysis-panel",
                                children=[
                                    html.Div(
                                        className="panel-header",
                                        children=[
                                            html.H2("Secondary Analysis", id="secondary-analysis-title", className="panel-title"),
                                            html.P(
                                                "Rolling burst intensity or projected pace for the selected comparison set.",
                                                className="panel-caption",
                                            ),
                                        ],
                                    ),
                                    html.Div(id="secondary-analysis-note", className="secondary-analysis-note"),
                                    dcc.Graph(
                                        id="secondary-analysis-chart",
                                        figure=initial_secondary_figure,
                                        config={"displayModeBar": "hover", "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="detail-panel",
                        children=[
                            html.Div(
                                className="panel-header",
                                children=[
                                    html.H2("Selection Details", className="panel-title"),
                                    html.P("Summary metrics update with the active comparison set.", className="panel-caption"),
                                ],
                            ),
                            html.Div(initial_details, id="detail-panel-content", className="detail-panel-content"),
                        ],
                    ),
                ],
            ),
        ],
    )


def build_enriched_detail_cards(
    selected_records: list[dict[str, Any]],
    entity_mode: str,
    timeline_df,
):
    if not selected_records:
        return html.Div("Choose a leaderboard row to inspect its details.", className="detail-empty")
    return [build_detail_card(record, entity_mode, _select_detail_timeline(timeline_df, record, entity_mode)) for record in selected_records]


def build_detail_card(record: dict[str, Any], entity_mode: str, timeline_df):
    context = _context_shares(timeline_df)
    if entity_mode == "game":
        metrics = [
            ("Points", record.get("final_points")),
            ("Final Score", _final_score(record)),
            ("Final Margin", _signed(record.get("final_player_team_margin"))),
            ("TS%", _pct(record.get("ts_pct"), digits=1)),
            ("eFG%", _pct(record.get("efg_pct"), digits=1)),
            ("Points / Min", _decimal(record.get("points_per_minute"))),
            ("Offensive Share", _pct(record.get("offensive_share"))),
            ("Shot Mix", _shot_mix(record, with_share=True)),
            ("Competitive", _share_with_points(record.get("competitive_points"), record.get("competitive_scoring_share"))),
            ("Trailing", _share_with_points(record.get("trailing_points"), _ratio(record.get("trailing_points"), record.get("final_points")))),
            ("Trailing Rate", _decimal(record.get("trailing_scoring_rate"))),
            ("Best 60s", record.get("best_60_sec_points")),
            ("Best 2 Min", record.get("best_2_min_points")),
            ("Best 3 Min", record.get("best_3_min_points")),
            ("Best 5 Min", record.get("best_5_min_points")),
            ("Best 10 Min", record.get("best_10_min_points")),
            ("Best Quarter", record.get("best_quarter_points")),
            ("Best Half", record.get("best_half_points")),
            ("Peak Proj 48", _decimal(record.get("peak_projected_48"))),
            ("OT", "Yes" if record.get("went_to_overtime") else "No"),
        ]
    else:
        points_key = {"quarter": "quarter_points", "half": "half_points", "burst": "points_in_window"}[entity_mode]
        rate_key = "window_points_per_minute" if entity_mode == "burst" else "points_per_minute"
        duration = _interval_duration(record, entity_mode)
        metrics = [
            ("Points", record.get(points_key)),
            ("Duration", duration),
            ("Rate", _decimal(record.get(rate_key))),
            ("Shot Mix", _shot_mix(record, with_share=True)),
            ("Avg Diff", _decimal(record.get("avg_margin_during_scoring_events", record.get("avg_score_diff_in_window")))),
            ("Median Diff", _decimal(record.get("median_margin_during_scoring_events", record.get("median_score_diff_in_window")))),
            ("Competitive Share", _pct(record.get("competitive_scoring_share"))),
            ("Trailing Share", _pct(context["trailing_share"])),
            ("Leading Share", _pct(context["leading_share"])),
            ("Tied Share", _pct(context["tied_share"])),
        ]
        if entity_mode == "burst":
            metrics.extend(
                [
                    ("Burst Start", f"{_period_string(record.get('start_period'))} · {record.get('start_clock')}"),
                    ("Burst End", f"{_period_string(record.get('end_period'))} · {record.get('end_clock')}"),
                ]
            )
    return html.Div(
        className="detail-card",
        children=[
            html.Div(
                className="detail-card-header",
                children=[
                    html.Div(
                        children=[
                            html.H3(record.get("player_name", "Unknown"), className="detail-card-title"),
                            html.P(
                                f"{record.get('team_tricode', '')} vs {record.get('opponent_team_tricode', '')} · {record.get('game_date', '')}",
                                className="detail-card-subtitle",
                            ),
                        ]
                    ),
                    html.Div(record.get("entity_label", "Selection"), className="detail-badge"),
                ],
            ),
            html.Div(
                className="detail-grid",
                children=[
                    html.Div(
                        className="detail-stat",
                        children=[
                            html.Div(label, className="detail-stat-label"),
                            html.Div(value, className="detail-stat-value"),
                        ],
                    )
                    for label, value in metrics
                ],
            ),
        ],
    )


def build_comparison_tray(selected_records: list[dict[str, Any]]):
    if not selected_records:
        return html.Div("No active comparisons.", className="comparison-tray-empty")
    return [
        html.Div(
            className="comparison-chip",
            children=[
                html.Span(f"{record.get('player_name')} · {record.get('entity_label')}", className="comparison-chip-label"),
                html.Button(
                    "Remove",
                    id={"type": "comparison-remove", "selection_id": record["selection_id"]},
                    className="comparison-chip-remove",
                    n_clicks=0,
                ),
            ],
        )
        for record in selected_records
    ] + [html.Button("Clear All", id="clear-comparisons", className="clear-comparisons-button", n_clicks=0)]


def build_margin_legend():
    items = [
        ("Trailing 10+", "trailing_10_plus"),
        ("Trailing 1-9", "trailing_1_9"),
        ("Within 3", "within_3"),
        ("Leading 1-9", "leading_1_9"),
        ("Leading 10+", "leading_10_plus"),
    ]
    return [
        html.Div(
            className="margin-legend-item",
            children=[
                html.Span(className=f"margin-legend-swatch margin-{key}"),
                html.Span(label),
            ],
        )
        for label, key in items
    ]


def _select_detail_timeline(timeline_df, record: dict[str, Any], entity_mode: str):
    if timeline_df is None or getattr(timeline_df, "empty", True):
        return timeline_df
    selection = selection_from_record(record, entity_mode)
    if entity_mode == "game":
        return timeline_df.loc[
            timeline_df["game_id"].astype(str).eq(selection.game_id)
            & timeline_df["player_id"].astype(int).eq(selection.player_id)
        ].copy()
    if entity_mode == "quarter":
        return build_quarter_timeline(timeline_df, selection.game_id, selection.player_id, int(record["quarter_number"]))
    if entity_mode == "half":
        return build_half_timeline(timeline_df, selection.game_id, selection.player_id, int(record["half_index"]))
    return build_burst_timeline(timeline_df, record)


def _context_shares(timeline_df) -> dict[str, float | None]:
    if timeline_df is None or getattr(timeline_df, "empty", True):
        return {"trailing_share": None, "leading_share": None, "tied_share": None}
    points = timeline_df["point_value"].astype(float)
    total = float(points.sum())
    if total <= 0:
        return {"trailing_share": None, "leading_share": None, "tied_share": None}
    trailing = float(points.loc[pd.to_numeric(timeline_df["score_diff"], errors="coerce") < 0].sum()) / total
    leading = float(points.loc[pd.to_numeric(timeline_df["score_diff"], errors="coerce") > 0].sum()) / total
    tied = float(points.loc[pd.to_numeric(timeline_df["score_diff"], errors="coerce") == 0].sum()) / total
    return {"trailing_share": trailing, "leading_share": leading, "tied_share": tied}


def _dropdown(label: str, component_id: str, options: list[dict[str, Any]], value: Any, clearable: bool) -> html.Div:
    return html.Div(
        className="filter-control",
        children=[
            html.Label(label, className="filter-label"),
            dcc.Dropdown(id=component_id, options=options, value=value, clearable=clearable),
        ],
    )


def _number_input(label: str, component_id: str, value: Any, minimum: int | float, step: float = 1.0) -> html.Div:
    return html.Div(
        className="filter-control",
        children=[
            html.Label(label, className="filter-label"),
            dcc.Input(id=component_id, type="number", value=value, min=minimum, step=step, className="numeric-input"),
        ],
    )


def _metric_chip(label: str, value: Any) -> html.Div:
    return html.Div(
        className="metric-chip",
        children=[
            html.Div(str(value), className="metric-chip-value"),
            html.Div(label, className="metric-chip-label"),
        ],
    )


def _shot_mix(record: dict[str, Any], *, with_share: bool = False) -> str:
    two = int(record.get("points_from_2s", 0) or 0)
    three = int(record.get("points_from_3s", 0) or 0)
    ft = int(record.get("points_from_fts", 0) or 0)
    if not with_share:
        return f"2s {two} · 3s {three} · FT {ft}"
    return (
        f"2s {two} ({_pct(record.get('share_points_from_2s'))}) · "
        f"3s {three} ({_pct(record.get('share_points_from_3s'))}) · "
        f"FT {ft} ({_pct(record.get('share_points_from_fts'))})"
    )


def _share_with_points(points: Any, share: Any) -> str:
    if points in {None, "", "None"}:
        return "NA"
    return f"{int(points)} · {_pct(share)}"


def _final_score(record: dict[str, Any]) -> str:
    team_score = record.get("final_player_team_score")
    opponent_score = record.get("final_opponent_score")
    if team_score in {None, "", "None"} or opponent_score in {None, "", "None"}:
        return "NA"
    return f"{team_score}-{opponent_score}"


def _interval_duration(record: dict[str, Any], entity_mode: str) -> str:
    if entity_mode == "quarter":
        value = record.get("quarter_duration_minutes")
    elif entity_mode == "half":
        value = record.get("half_duration_minutes")
    else:
        value = (float(record.get("burst_window_seconds", 0) or 0)) / 60.0
    return _decimal(value)


def _period_string(value: Any) -> str:
    if value in {None, "", "None"}:
        return "NA"
    period = int(value)
    return f"Q{period}" if period <= 4 else f"OT{period - 4}"


def _signed(value: Any) -> str:
    if value in {None, "", "None"}:
        return "NA"
    numeric = int(value)
    return f"{numeric:+d}"


def _pct(value: Any, *, digits: int = 0) -> str:
    if value in {None, "", "None"}:
        return "NA"
    try:
        return f"{float(value):.{digits}%}"
    except (TypeError, ValueError):
        return "NA"


def _decimal(value: Any) -> str:
    if value in {None, "", "None"}:
        return "NA"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def _ratio(numerator: Any, denominator: Any) -> float | None:
    if numerator in {None, "", "None"} or denominator in {None, "", "None"}:
        return None
    try:
        denominator_value = float(denominator)
        if denominator_value == 0:
            return None
        return float(numerator) / denominator_value
    except (TypeError, ValueError):
        return None
