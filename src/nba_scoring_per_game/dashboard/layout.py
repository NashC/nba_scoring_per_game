from __future__ import annotations

from typing import Any

from dash import dcc, html
from dash import dash_table
import pandas as pd

from ..transforms import build_burst_timeline, build_half_timeline, build_quarter_timeline
from .branding import LiveLogo3D, build_brand_lockup
from .charts import (
    COMPARISON_COLORS,
    SHOT_COLORS,
    build_empty_figure,
    build_secondary_analysis_figure,
    build_trajectory_figure,
)
from .loader import DashboardDatasets, load_selected_timelines
from .state import (
    DashboardFilters,
    build_quick_view_options,
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
                dcc.Store(id="saved-bundles", storage_type="local"),
                html.Div(
                    className="empty-state-card",
                    children=[
                        build_brand_lockup(id="empty-brand-lockup", logo_id="empty-brand-logo"),
                        html.H1("Backfill curated outputs to unlock the explorer.", className="app-title"),
                        html.P(
                            datasets.message or "No local parquet data is available yet.",
                            className="empty-state-text",
                        ),
                        html.Pre(
                            "nba-scoring-per-game backfill-season --season 2023-24 --out-dir data",
                            className="empty-state-command",
                        ),
                        html.Pre(
                            "nba-scoring-per-game serve-app --out-dir data",
                            className="empty-state-command empty-state-command-secondary",
                        ),
                        html.P(
                            "Backfill the curated parquet outputs first, then launch the app locally. "
                            "Once data is available, use quick views, leaderboard selection, and saved bundles "
                            "directly inside the dashboard.",
                            className="empty-state-text",
                        ),
                    ],
                ),
            ],
        )

    default_filters = DashboardFilters()
    initial_frame = filter_summary_frame(datasets, default_filters)
    initial_records, initial_columns, initial_styles = build_leaderboard_table(
        initial_frame,
        default_filters,
        page_current=0,
        page_size=10,
    )
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
    initial_chart_summary = build_chart_summary_strip(initial_selected_records, default_filters.entity_mode)
    initial_chart_key = build_chart_visual_key(default_filters)
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
            dcc.Store(id="saved-bundles", storage_type="local"),
            html.Div(
                className="hero-panel",
                children=[
                    html.Div(
                        className="hero-copy",
                        children=[
                            build_brand_lockup(id="hero-brand-lockup", logo_id="hero-nav-logo"),
                            html.H1("Historic scoring trajectories, bursts, quarters, and context.", className="app-title"),
                            html.P(
                                "Compare volume, pace, burst intensity, shot mix, and competitiveness across the best scoring performances ever.",
                                className="app-subtitle",
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
                        ]
                    ),
                    html.Div(
                        id="hero-brand-stage",
                        className="hero-brand-stage",
                        children=[
                            html.Div(
                                className="hero-brand-stage-inner",
                                children=[
                                    html.Div("Premium brand mark", className="hero-brand-stage-eyebrow"),
                                    LiveLogo3D(
                                        id="hero-live-logo",
                                        variant="hero",
                                        decorative=True,
                                        class_name="hero-live-logo",
                                    ),
                                    html.P(
                                        "A live basketball mark with controlled fire, tuned for a dark shell and small-size clarity.",
                                        className="hero-brand-stage-note",
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            ),
            build_app_guide(),
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
                        className="content-side-stack",
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
                                                    html.P(
                                                        "Use quick views for preset workflows, then select up to 4 rows to compare. "
                                                        "The active ranking metric is highlighted in the table.",
                                                        className="panel-caption",
                                                    ),
                                                ]
                                            ),
                                            html.Button("Export CSV", id="export-leaderboard", className="panel-button", n_clicks=0),
                                        ],
                                    ),
                                    html.Div(id="quick-view-bar", className="quick-view-bar", children=build_quick_view_bar(default_filters.preset)),
                                    dash_table.DataTable(
                                        id="leaderboard-table",
                                        data=initial_records,
                                        columns=initial_columns,
                                        tooltip_header=initial_styles["tooltip_header"],
                                        tooltip_data=initial_styles["tooltip_data"],
                                        tooltip_delay=0,
                                        tooltip_duration=None,
                                        selected_row_ids=initial_selected_ids,
                                        row_selectable="multi",
                                        page_action="custom",
                                        page_current=0,
                                        sort_action="custom",
                                        sort_mode="single",
                                        sort_by=[],
                                        style_as_list_view=True,
                                        page_size=10,
                                        page_count=initial_styles["page_count"],
                                        fixed_columns={"headers": True, "data": 3},
                                        markdown_options={"html": True},
                                        style_table={"overflowX": "auto", "minWidth": "100%"},
                                        style_header={
                                            "backgroundColor": "#efe5d7",
                                            "fontWeight": 700,
                                            "border": "none",
                                            "color": "#1f1b18",
                                        },
                                        style_header_conditional=initial_styles["style_header_conditional"],
                                        style_cell={
                                            "backgroundColor": "#fffaf2",
                                            "border": "none",
                                            "color": "#1f1b18",
                                            "fontFamily": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif",
                                            "padding": "10px 12px",
                                            "textAlign": "left",
                                        },
                                        style_cell_conditional=initial_styles["style_cell_conditional"],
                                        style_data_conditional=initial_styles["style_data_conditional"],
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
                    html.Div(
                        className="chart-panel",
                        children=[
                            html.Div(
                                className="panel-header",
                                children=[
                                    html.H2("Historic Scoring Trajectories", className="panel-title"),
                                    html.P(
                                        "The main chart stays cumulative. Use the summary strip for fast context, "
                                        "keep lines for player comparison, and let marker colors explain shot type.",
                                        className="panel-caption",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="bundle-toolbar",
                                children=[
                                    html.Div(
                                        className="bundle-toolbar-inputs",
                                        children=[
                                            dcc.Input(
                                                id="bundle-name",
                                                type="text",
                                                value="",
                                                placeholder="Save current comparison bundle",
                                                className="bundle-name-input",
                                            ),
                                            html.Button("Save Bundle", id="save-bundle", className="panel-button", n_clicks=0),
                                        ],
                                    ),
                                    html.Div(
                                        className="bundle-toolbar-actions",
                                        children=[
                                            dcc.Dropdown(
                                                id="saved-bundle-select",
                                                options=[],
                                                value=None,
                                                placeholder="Saved bundles",
                                                clearable=True,
                                                className="saved-bundle-select",
                                            ),
                                            html.Button("Load", id="load-bundle", className="panel-button", n_clicks=0),
                                            html.Button("Delete", id="delete-bundle", className="panel-button panel-button-muted", n_clicks=0),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                "Bundles save the current filters and selected comparisons in this browser only.",
                                id="bundle-status",
                                className="bundle-status",
                            ),
                            html.Div(id="comparison-tray", className="comparison-tray", children=build_comparison_tray(initial_selected_records)),
                            html.Div(id="chart-summary-strip", className="chart-summary-strip", children=initial_chart_summary),
                            html.Div(id="chart-visual-key", className="chart-visual-key", children=initial_chart_key),
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
                ],
            ),
        ],
    )


def build_app_guide() -> html.Details:
    return html.Details(
        id="app-guide",
        className="guide-panel",
        children=[
            html.Summary("How to Use This Explorer", className="guide-summary"),
            html.Div(
                className="guide-grid",
                children=[
                    _guide_block(
                        "Quick Views",
                        "Start with presets like top scoring games, best quarters, best halves, or best 3-minute bursts. "
                        "Quick views stay synced with the preset filter and URL state.",
                    ),
                    _guide_block(
                        "Leaderboard",
                        "Change the ranking metric to reorder the table. The highlighted column is the active metric, "
                        "and you can export the filtered leaderboard as CSV.",
                    ),
                    _guide_block(
                        "Compare and Save",
                        "Select up to 4 rows to compare. Save that view as a local bundle to restore the same filters "
                        "and comparison set later in this browser.",
                    ),
                    _guide_block(
                        "Chart and Context",
                        "The main chart remains cumulative. Use raw or normalized time, shot markers, margin-context "
                        "colors, and the secondary panel for rolling burst intensity or projected pace.",
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
    badges = _detail_badges(record, entity_mode, context)
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
                            html.Div(
                                className="detail-card-subtitle detail-matchup-row",
                                children=[
                                    _team_logo_img(record.get("team_id"), record.get("team_tricode"), class_name="team-logo team-logo-medium"),
                                    html.Span(record.get("team_tricode", ""), className="matchup-team-code"),
                                    html.Span("vs", className="matchup-vs"),
                                    _team_logo_img(
                                        record.get("opponent_team_id"),
                                        record.get("opponent_team_tricode"),
                                        class_name="team-logo team-logo-medium",
                                    ),
                                    html.Span(record.get("opponent_team_tricode", ""), className="matchup-team-code"),
                                    html.Span(f"· {record.get('game_date', '')}", className="matchup-date"),
                                ],
                            ),
                            html.Div(badges, className="detail-badge-row") if badges else None,
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
    chips = [
        html.Div(
            className="comparison-chip",
            children=[
                _team_logo_img(record.get("team_id"), record.get("team_tricode"), class_name="team-logo team-logo-small comparison-chip-logo"),
                html.Span(f"{record.get('player_name')} · {record.get('entity_label')}", className="comparison-chip-label"),
                html.Button(
                    "Remove",
                    id={"type": "comparison-remove", "selection_id": record["selection_id"]},
                    className="comparison-chip-remove",
                    n_clicks=0,
                    title=f"Remove {record.get('player_name')} from the comparison set",
                ),
            ],
        )
        for record in selected_records
    ]
    actions = html.Div(
        className="comparison-actions",
        children=[
            html.Span("Use Tab and Enter to remove chips or step back one selection.", className="comparison-help"),
            html.Button("Remove Last", id="remove-last-comparison", className="clear-comparisons-button", n_clicks=0, accessKey="r"),
            html.Button("Clear All", id="clear-comparisons", className="clear-comparisons-button", n_clicks=0, accessKey="c"),
        ],
    )
    return [html.Div(chips, className="comparison-chip-list"), actions]


def build_chart_summary_strip(selected_records: list[dict[str, Any]], entity_mode: str):
    if not selected_records:
        return html.Div("Select one or more leaderboard rows to populate the chart summary.", className="chart-summary-empty")

    cards = []
    for index, record in enumerate(selected_records[:4]):
        color = COMPARISON_COLORS[index % len(COMPARISON_COLORS)]
        cards.append(
            html.Div(
                className="chart-summary-card",
                children=[
                    html.Div(
                        className="chart-summary-card-header",
                        children=[
                            html.Span(className="chart-summary-swatch", style={"backgroundColor": color}),
                            html.Div(
                                children=[
                                    html.Div(record.get("player_name", "Unknown"), className="chart-summary-player"),
                                    html.Div(
                                        className="chart-summary-label chart-summary-matchup",
                                        children=[
                                            html.Span(record.get("entity_label", "Selection")),
                                            html.Span("·", className="chart-summary-divider"),
                                            _team_logo_img(
                                                record.get("team_id"),
                                                record.get("team_tricode"),
                                                class_name="team-logo team-logo-small",
                                            ),
                                            html.Span(record.get("team_tricode", "")),
                                            html.Span("vs", className="matchup-vs"),
                                            _team_logo_img(
                                                record.get("opponent_team_id"),
                                                record.get("opponent_team_tricode"),
                                                class_name="team-logo team-logo-small",
                                            ),
                                            html.Span(record.get("opponent_team_tricode", "")),
                                        ],
                                    ),
                                ],
                            ),
                            html.Span("Focus" if index == 0 else "Context", className="chart-summary-role"),
                        ],
                    ),
                    html.Div(className="chart-summary-metrics", children=_summary_metrics_for_record(record, entity_mode)),
                ],
            )
        )
    return cards


def build_chart_visual_key(filters: DashboardFilters):
    items = [
        html.Div(
            className="chart-key-item",
            children=[
                html.Span(className="chart-key-line chart-key-line-focus"),
                html.Span("Focus line", className="chart-key-label"),
            ],
        ),
        html.Div(
            className="chart-key-item",
            children=[
                html.Span(className="chart-key-line chart-key-line-context"),
                html.Span("Comparison context", className="chart-key-label"),
            ],
        ),
    ]
    if filters.show_shot_markers:
        for label, color in [("2PT", SHOT_COLORS["2PT"]), ("3PT", SHOT_COLORS["3PT"]), ("FT", SHOT_COLORS["FT"])]:
            items.append(
                html.Div(
                    className="chart-key-item",
                    children=[
                        html.Span(className="chart-key-dot", style={"backgroundColor": color}),
                        html.Span(label, className="chart-key-label"),
                    ],
                )
            )
    return items


def build_quick_view_bar(active_preset: str | None):
    return [
        html.Button(
            option["label"],
            id={"type": "quick-view-button", "preset": option["value"]},
            className="quick-view-button quick-view-button-active" if option["value"] == active_preset else "quick-view-button",
            n_clicks=0,
        )
        for option in build_quick_view_options()
    ]


def _guide_block(title: str, body: str) -> html.Div:
    return html.Div(
        className="guide-block",
        children=[
            html.H3(title, className="guide-block-title"),
            html.P(body, className="guide-block-body"),
        ],
    )


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


def _detail_badges(
    record: dict[str, Any],
    entity_mode: str,
    context: dict[str, float | None],
) -> list[html.Span]:
    labels: list[str] = []
    if entity_mode == "game":
        pace_badge = _pace_benchmark_badge(record.get("peak_projected_48"))
        best_burst = _best_burst_badge(record)
        if pace_badge:
            labels.append(pace_badge)
        if best_burst:
            labels.append(best_burst)
        competitive = record.get("competitive_scoring_share")
        if competitive not in {None, "", "None"}:
            labels.append(f"Competitive {_pct(competitive)}")
    elif entity_mode == "burst":
        labels.append(str(record.get("burst_window_label", "Burst Window")))
    if context.get("trailing_share") not in {None, "", "None"}:
        labels.append(f"Trailing {_pct(context['trailing_share'])}")
    return [html.Span(label, className="detail-mini-badge") for label in labels[:4]]


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


def _team_logo_img(team_id: Any, tricode: Any, *, class_name: str = "team-logo") -> html.Span | html.Img:
    tri = "" if tricode in {None, "", "None"} else str(tricode).strip()
    try:
        numeric_team_id = int(team_id)
    except (TypeError, ValueError):
        numeric_team_id = None
    if numeric_team_id is None:
        return html.Span(tri, className=f"{class_name} team-logo-fallback".strip())
    return html.Img(
        src=f"/assets/team_logos/{numeric_team_id}.svg",
        alt=tri or str(numeric_team_id),
        title=tri or str(numeric_team_id),
        className=class_name,
    )


def _summary_metrics_for_record(record: dict[str, Any], entity_mode: str) -> list[html.Div]:
    if entity_mode == "game":
        return [
            _summary_metric("Points", str(int(record.get("final_points", 0) or 0))),
            _summary_metric("Shot Mix", _shot_mix(record)),
            _summary_metric("Comp", _pct(record.get("competitive_scoring_share"))),
            _summary_metric("Peak Pace", _decimal(record.get("peak_projected_48"))),
        ]
    if entity_mode == "quarter":
        return [
            _summary_metric("Points", str(int(record.get("quarter_points", 0) or 0))),
            _summary_metric("Rate", _decimal(record.get("points_per_minute"))),
            _summary_metric("3PT Share", _pct(record.get("share_points_from_3s"))),
            _summary_metric("Comp", _pct(record.get("competitive_scoring_share"))),
        ]
    if entity_mode == "half":
        return [
            _summary_metric("Points", str(int(record.get("half_points", 0) or 0))),
            _summary_metric("Rate", _decimal(record.get("points_per_minute"))),
            _summary_metric("3PT Share", _pct(record.get("share_points_from_3s"))),
            _summary_metric("Comp", _pct(record.get("competitive_scoring_share"))),
        ]
    return [
        _summary_metric("Points", str(int(record.get("points_in_window", 0) or 0))),
        _summary_metric("Rate", _decimal(record.get("window_points_per_minute", record.get("points_per_minute")))),
        _summary_metric("3PT Share", _pct(record.get("share_points_from_3s"))),
        _summary_metric("Comp", _pct(record.get("competitive_scoring_share"))),
    ]


def _summary_metric(label: str, value: str) -> html.Div:
    return html.Div(
        className="chart-summary-metric",
        children=[
            html.Div(label, className="chart-summary-metric-label"),
            html.Div(value, className="chart-summary-metric-value"),
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


def _pace_benchmark_badge(value: Any) -> str | None:
    if value in {None, "", "None"}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    for benchmark in [100, 80, 70, 60, 50]:
        if numeric >= benchmark:
            return f"Pace {benchmark}+"
    return None


def _best_burst_badge(record: dict[str, Any]) -> str | None:
    candidates = [
        ("60s", record.get("best_60_sec_points")),
        ("2m", record.get("best_2_min_points")),
        ("3m", record.get("best_3_min_points")),
        ("5m", record.get("best_5_min_points")),
        ("10m", record.get("best_10_min_points")),
    ]
    resolved: list[tuple[str, int]] = []
    for label, value in candidates:
        if value in {None, "", "None"}:
            continue
        try:
            resolved.append((label, int(value)))
        except (TypeError, ValueError):
            continue
    if not resolved:
        return None
    label, amount = max(resolved, key=lambda item: item[1])
    return f"Best {label}: {amount}"


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
