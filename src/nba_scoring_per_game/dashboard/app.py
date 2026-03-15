from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, no_update

from .charts import build_empty_figure, build_secondary_analysis_figure, build_trajectory_figure
from .layout import build_comparison_tray, build_dashboard_layout, build_enriched_detail_cards
from .loader import DashboardDatasets, load_dashboard_datasets, load_selected_timelines
from .state import (
    DashboardFilters,
    apply_dashboard_preset,
    build_leaderboard_table,
    decode_dashboard_state,
    default_ranking_metric,
    encode_dashboard_state,
    filter_summary_frame,
    filter_values_from_filters,
    get_ranking_options,
    normalize_filters,
    select_records,
)


def create_dashboard_app(out_dir: str | Path = "data") -> Dash:
    """Create the Dash app for exploring scoring trajectories and scoring context."""
    out_path = Path(out_dir)
    datasets = load_dashboard_datasets(out_path)
    assets_dir = Path(__file__).with_name("assets")
    app = Dash(
        __name__,
        title="NBA Scoring Explorer",
        assets_folder=str(assets_dir),
        suppress_callback_exceptions=True,
        prevent_initial_callbacks="initial_duplicate",
    )
    app.layout = build_dashboard_layout(datasets)
    if datasets.available:
        _register_callbacks(app, datasets, out_path)
    return app


def render_dashboard_view(
    datasets: DashboardDatasets,
    out_dir: str | Path,
    filters: DashboardFilters,
    selected_row_ids: list[str] | None,
) -> dict[str, Any]:
    summary_df = filter_summary_frame(datasets, filters)
    records, columns = build_leaderboard_table(summary_df, filters)

    if not records:
        return {
            "records": [],
            "columns": columns,
            "selected_ids": [],
            "figure": build_empty_figure("No performances matched the current filters."),
            "primary_figure": build_empty_figure("No performances matched the current filters."),
            "secondary_figure": build_empty_figure("No secondary analysis is available for the current filters.", height=320),
            "details": build_enriched_detail_cards([], filters.entity_mode, pd.DataFrame()),
            "status": "No performances matched the current filters.",
            "comparison_tray": build_comparison_tray([]),
            "secondary_title": _secondary_title(filters),
            "secondary_note": _secondary_note(filters),
        }

    selected_records = select_records(records, selected_row_ids)
    selected_ids = [record["selection_id"] for record in selected_records]
    if len(selected_row_ids or []) > len(selected_records):
        status = f"Showing the first {len(selected_records)} selected comparisons."
    elif not selected_row_ids:
        status = "Previewing the top-ranked performance. Select rows in the leaderboard to compare up to 4 lines."
    else:
        status = f"Comparing {len(selected_records)} performance(s)."

    timelines = load_selected_timelines(out_dir, selected_records)
    primary_figure = build_trajectory_figure(
        selected_records,
        timelines,
        filters,
        burst_summaries=datasets.burst_summaries,
    )
    secondary_figure = build_secondary_analysis_figure(selected_records, timelines, filters)
    details = build_enriched_detail_cards(selected_records, filters.entity_mode, timelines)
    return {
        "records": records,
        "columns": columns,
        "selected_ids": selected_ids,
        "figure": primary_figure,
        "primary_figure": primary_figure,
        "secondary_figure": secondary_figure,
        "details": details,
        "status": status,
        "comparison_tray": build_comparison_tray(selected_records),
        "secondary_title": _secondary_title(filters),
        "secondary_note": _secondary_note(filters),
    }


def _register_callbacks(app: Dash, datasets: DashboardDatasets, out_dir: Path) -> None:
    @app.callback(
        Output("entity-mode", "value", allow_duplicate=True),
        Output("ranking-metric", "value", allow_duplicate=True),
        Output("time-mode", "value", allow_duplicate=True),
        Output("burst-window", "value", allow_duplicate=True),
        Output("analysis-mode", "value", allow_duplicate=True),
        Output("analysis-window", "value", allow_duplicate=True),
        Output("line-color-mode", "value", allow_duplicate=True),
        Output("shot-markers", "value", allow_duplicate=True),
        Output("include-ot", "value", allow_duplicate=True),
        Output("competitive-only", "value", allow_duplicate=True),
        Output("min-points", "value", allow_duplicate=True),
        Output("min-competitive-share", "value", allow_duplicate=True),
        Output("min-ts-pct", "value", allow_duplicate=True),
        Output("min-efg-pct", "value", allow_duplicate=True),
        Output("min-offensive-share", "value", allow_duplicate=True),
        Output("player-filter", "value", allow_duplicate=True),
        Output("team-filter", "value", allow_duplicate=True),
        Output("opponent-filter", "value", allow_duplicate=True),
        Output("season-filter", "value", allow_duplicate=True),
        Output("season-type-filter", "value", allow_duplicate=True),
        Output("era-filter", "value", allow_duplicate=True),
        Output("preset-filter", "value", allow_duplicate=True),
        Output("url-selected-ids", "data"),
        Input("dashboard-location", "search"),
        prevent_initial_call=False,
    )
    def _hydrate_from_url(search: str | None):
        state = decode_dashboard_state(search)
        filters: DashboardFilters = state["filters"]
        values = filter_values_from_filters(filters)
        return (
            values["entity_mode"],
            values["ranking_metric"],
            values["time_mode"],
            values["burst_window"],
            values["analysis_mode"],
            values["analysis_window"],
            values["line_color_mode"],
            values["shot_markers"],
            values["include_ot"],
            values["competitive_only"],
            values["min_points"],
            values["min_competitive_share"],
            values["min_ts_pct"],
            values["min_efg_pct"],
            values["min_offensive_share"],
            values["player"],
            values["team"],
            values["opponent"],
            values["season"],
            values["season_type"],
            values["era"],
            values["preset"],
            state["selected_row_ids"],
        )

    @app.callback(
        Output("entity-mode", "value", allow_duplicate=True),
        Output("ranking-metric", "value", allow_duplicate=True),
        Output("time-mode", "value", allow_duplicate=True),
        Output("burst-window", "value", allow_duplicate=True),
        Output("analysis-mode", "value", allow_duplicate=True),
        Output("analysis-window", "value", allow_duplicate=True),
        Output("include-ot", "value", allow_duplicate=True),
        Output("competitive-only", "value", allow_duplicate=True),
        Output("min-points", "value", allow_duplicate=True),
        Output("min-competitive-share", "value", allow_duplicate=True),
        Output("min-ts-pct", "value", allow_duplicate=True),
        Output("min-efg-pct", "value", allow_duplicate=True),
        Output("min-offensive-share", "value", allow_duplicate=True),
        Output("player-filter", "value", allow_duplicate=True),
        Output("team-filter", "value", allow_duplicate=True),
        Output("opponent-filter", "value", allow_duplicate=True),
        Output("season-filter", "value", allow_duplicate=True),
        Output("season-type-filter", "value", allow_duplicate=True),
        Output("era-filter", "value", allow_duplicate=True),
        Input("preset-filter", "value"),
        prevent_initial_call=True,
    )
    def _apply_preset_value(preset: str | None):
        if not preset:
            return (no_update,) * 19
        filters = apply_dashboard_preset(preset)
        return (
            filters.entity_mode,
            filters.ranking_metric,
            filters.time_mode,
            filters.burst_window,
            filters.analysis_mode,
            filters.analysis_window,
            ["include"] if filters.include_ot else [],
            ["competitive"] if filters.competitive_only else [],
            filters.min_points,
            filters.min_competitive_share,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    @app.callback(
        Output("ranking-metric", "options"),
        Output("ranking-metric", "value"),
        Output("burst-window-wrap", "style"),
        Output("analysis-window-wrap", "style"),
        Output("min-ts-pct-wrap", "style"),
        Output("min-efg-pct-wrap", "style"),
        Output("min-offensive-share-wrap", "style"),
        Output("margin-legend-wrap", "style"),
        Output("secondary-analysis-chart", "style"),
        Output("secondary-analysis-note", "style"),
        Input("entity-mode", "value"),
        Input("ranking-metric", "value"),
        Input("analysis-mode", "value"),
        Input("line-color-mode", "value"),
    )
    def _update_metric_options_and_visibility(
        entity_mode: str,
        current_metric: str | None,
        analysis_mode: str | None,
        line_color_mode: str | None,
    ):
        options = get_ranking_options(entity_mode)
        valid_values = {option["value"] for option in options}
        value = current_metric if current_metric in valid_values else default_ranking_metric(entity_mode)
        show_game_only = {} if entity_mode == "game" else {"display": "none"}
        show_burst = {} if entity_mode == "burst" else {"display": "none"}
        show_analysis_window = {} if analysis_mode in {"rolling_points", "rolling_rate"} else {"display": "none"}
        show_margin = {"display": "flex"} if line_color_mode == "margin" else {"display": "none"}
        if entity_mode == "burst":
            secondary_chart_style = {"display": "none"}
            secondary_note_style = {"display": "block"}
        else:
            secondary_chart_style = {}
            secondary_note_style = {"display": "none"}
        return (
            options,
            value,
            show_burst,
            show_analysis_window,
            show_game_only,
            show_game_only,
            show_game_only,
            show_margin,
            secondary_chart_style,
            secondary_note_style,
        )

    @app.callback(
        Output("leaderboard-table", "selected_row_ids", allow_duplicate=True),
        Input("clear-comparisons", "n_clicks"),
        Input({"type": "comparison-remove", "selection_id": ALL}, "n_clicks"),
        State("leaderboard-table", "selected_row_ids"),
        prevent_initial_call=True,
    )
    def _update_selection_from_tray(
        clear_clicks: int,
        remove_clicks: list[int] | None,
        selected_row_ids: list[str] | None,
    ):
        current_ids = list(selected_row_ids or [])
        triggered = ctx.triggered_id
        if triggered == "clear-comparisons":
            return []
        if isinstance(triggered, dict) and triggered.get("type") == "comparison-remove":
            target_id = triggered.get("selection_id")
            return [selection_id for selection_id in current_ids if selection_id != target_id]
        return no_update

    @app.callback(
        Output("leaderboard-table", "data"),
        Output("leaderboard-table", "columns"),
        Output("leaderboard-table", "selected_row_ids"),
        Output("comparison-chart", "figure"),
        Output("secondary-analysis-chart", "figure"),
        Output("detail-panel-content", "children"),
        Output("status-banner", "children"),
        Output("comparison-tray", "children"),
        Output("secondary-analysis-title", "children"),
        Output("secondary-analysis-note", "children"),
        Input("entity-mode", "value"),
        Input("ranking-metric", "value"),
        Input("time-mode", "value"),
        Input("burst-window", "value"),
        Input("analysis-mode", "value"),
        Input("analysis-window", "value"),
        Input("line-color-mode", "value"),
        Input("shot-markers", "value"),
        Input("include-ot", "value"),
        Input("competitive-only", "value"),
        Input("min-points", "value"),
        Input("min-competitive-share", "value"),
        Input("min-ts-pct", "value"),
        Input("min-efg-pct", "value"),
        Input("min-offensive-share", "value"),
        Input("player-filter", "value"),
        Input("team-filter", "value"),
        Input("opponent-filter", "value"),
        Input("season-filter", "value"),
        Input("season-type-filter", "value"),
        Input("era-filter", "value"),
        Input("preset-filter", "value"),
        Input("url-selected-ids", "data"),
        Input("leaderboard-table", "selected_row_ids"),
    )
    def _update_dashboard(
        entity_mode: str,
        ranking_metric: str,
        time_mode: str,
        burst_window: int,
        analysis_mode: str,
        analysis_window: int,
        line_color_mode: str,
        shot_markers: list[str] | None,
        include_ot: list[str] | None,
        competitive_only: list[str] | None,
        min_points: Any,
        min_competitive_share: Any,
        min_ts_pct: Any,
        min_efg_pct: Any,
        min_offensive_share: Any,
        player: str | None,
        team: str | None,
        opponent: str | None,
        season: str | None,
        season_type: str | None,
        era: str | None,
        preset: str | None,
        url_selected_ids: list[str] | None,
        selected_row_ids: list[str] | None,
    ):
        filters = normalize_filters(
            entity_mode=entity_mode,
            ranking_metric=ranking_metric,
            time_mode=time_mode,
            burst_window=burst_window,
            analysis_mode=analysis_mode,
            analysis_window=analysis_window,
            line_color_mode=line_color_mode,
            show_shot_markers="markers" in (shot_markers or []),
            include_ot="include" in (include_ot or []),
            competitive_only="competitive" in (competitive_only or []),
            min_points=min_points,
            min_competitive_share=min_competitive_share,
            min_ts_pct=min_ts_pct,
            min_efg_pct=min_efg_pct,
            min_offensive_share=min_offensive_share,
            player=player,
            team=team,
            opponent=opponent,
            season=season,
            season_type=season_type,
            era=era,
            preset=preset,
        )
        effective_selected_ids = (
            list(url_selected_ids or [])
            if ctx.triggered_id == "url-selected-ids" and url_selected_ids
            else selected_row_ids
        )
        view = render_dashboard_view(datasets, out_dir, filters, effective_selected_ids)
        return (
            view["records"],
            view["columns"],
            view["selected_ids"],
            view["primary_figure"],
            view["secondary_figure"],
            view["details"],
            view["status"],
            view["comparison_tray"],
            view["secondary_title"],
            view["secondary_note"],
        )

    @app.callback(
        Output("dashboard-location", "search"),
        Input("entity-mode", "value"),
        Input("ranking-metric", "value"),
        Input("time-mode", "value"),
        Input("burst-window", "value"),
        Input("analysis-mode", "value"),
        Input("analysis-window", "value"),
        Input("line-color-mode", "value"),
        Input("shot-markers", "value"),
        Input("include-ot", "value"),
        Input("competitive-only", "value"),
        Input("min-points", "value"),
        Input("min-competitive-share", "value"),
        Input("min-ts-pct", "value"),
        Input("min-efg-pct", "value"),
        Input("min-offensive-share", "value"),
        Input("player-filter", "value"),
        Input("team-filter", "value"),
        Input("opponent-filter", "value"),
        Input("season-filter", "value"),
        Input("season-type-filter", "value"),
        Input("era-filter", "value"),
        Input("preset-filter", "value"),
        Input("leaderboard-table", "selected_row_ids"),
        State("dashboard-location", "search"),
    )
    def _update_url_state(
        entity_mode: str,
        ranking_metric: str,
        time_mode: str,
        burst_window: int,
        analysis_mode: str,
        analysis_window: int,
        line_color_mode: str,
        shot_markers: list[str] | None,
        include_ot: list[str] | None,
        competitive_only: list[str] | None,
        min_points: Any,
        min_competitive_share: Any,
        min_ts_pct: Any,
        min_efg_pct: Any,
        min_offensive_share: Any,
        player: str | None,
        team: str | None,
        opponent: str | None,
        season: str | None,
        season_type: str | None,
        era: str | None,
        preset: str | None,
        selected_row_ids: list[str] | None,
        current_search: str | None,
    ):
        filters = normalize_filters(
            entity_mode=entity_mode,
            ranking_metric=ranking_metric,
            time_mode=time_mode,
            burst_window=burst_window,
            analysis_mode=analysis_mode,
            analysis_window=analysis_window,
            line_color_mode=line_color_mode,
            show_shot_markers="markers" in (shot_markers or []),
            include_ot="include" in (include_ot or []),
            competitive_only="competitive" in (competitive_only or []),
            min_points=min_points,
            min_competitive_share=min_competitive_share,
            min_ts_pct=min_ts_pct,
            min_efg_pct=min_efg_pct,
            min_offensive_share=min_offensive_share,
            player=player,
            team=team,
            opponent=opponent,
            season=season,
            season_type=season_type,
            era=era,
            preset=preset,
        )
        next_search = encode_dashboard_state(filters, list(selected_row_ids or []))
        if (current_search or "") == next_search:
            return no_update
        return next_search

    @app.callback(
        Output("leaderboard-download", "data"),
        Input("export-leaderboard", "n_clicks"),
        State("leaderboard-table", "data"),
        prevent_initial_call=True,
    )
    def _download_leaderboard_csv(n_clicks: int, rows: list[dict[str, Any]] | None):
        if not n_clicks or not rows:
            return no_update
        frame = pd.DataFrame(rows)
        if frame.empty:
            return no_update
        export_columns = [
            column
            for column in [
                "rank",
                "player_name",
                "team_tricode",
                "opponent_team_tricode",
                "date_label",
                "era_label",
                "entity_label",
                "primary_points",
                "rate_value",
                "competitive_share_value",
            ]
            if column in frame.columns
        ]
        return dcc.send_data_frame(frame[export_columns].to_csv, "nba_scoring_leaderboard.csv", index=False)


def _secondary_title(filters: DashboardFilters) -> str:
    mapping = {
        "none": "Secondary Analysis",
        "rolling_points": "Trailing Window Points",
        "rolling_rate": "Trailing Window Rate",
        "projected_pace": "Projected Pace",
    }
    return mapping.get(filters.analysis_mode, "Secondary Analysis")


def _secondary_note(filters: DashboardFilters) -> str:
    if filters.entity_mode == "burst":
        return "Burst mode already isolates one scoring stretch, so the secondary analysis panel is hidden."
    if filters.analysis_mode == "none":
        return ""
    if filters.analysis_mode == "projected_pace":
        return "Projected pace uses the published `projected_48` values and benchmark guide lines."
    return f"Rolling analysis uses the trailing {filters.analysis_window}-second window at each scoring event."
