from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, no_update

from .charts import build_empty_figure, build_secondary_analysis_figure, build_trajectory_figure
from .layout import (
    build_chart_summary_strip,
    build_chart_visual_key,
    build_comparison_tray,
    build_dashboard_layout,
    build_enriched_detail_cards,
    build_quick_view_bar,
)
from .loader import DashboardDatasets, load_dashboard_datasets, load_selected_timelines
from .state import (
    DashboardFilters,
    _prepare_leaderboard_dataframe,
    apply_dashboard_preset,
    build_leaderboard_table,
    decode_dashboard_state,
    default_ranking_metric,
    encode_dashboard_state,
    filter_summary_frame,
    filter_values_from_filters,
    get_preset_label,
    get_ranking_options,
    normalize_filters,
    normalize_saved_bundles,
    saved_bundles_payload,
    select_records,
    serialize_saved_bundle,
)

_PRESET_FILTER_OUTPUT_COUNT = 19


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
    sort_by: list[dict[str, str]] | None = None,
    page_current: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    summary_df = filter_summary_frame(datasets, filters)
    working, _ = _prepare_leaderboard_dataframe(summary_df, filters, sort_by)
    records, columns, styles = build_leaderboard_table(
        summary_df,
        filters,
        sort_by=sort_by,
        page_current=page_current,
        page_size=page_size,
    )

    if working.empty:
        empty_message = _empty_filter_message(filters)
        return {
            "records": [],
            "columns": columns,
            "leaderboard_styles": styles,
            "selected_ids": [],
            "figure": build_empty_figure(empty_message),
            "primary_figure": build_empty_figure(empty_message),
            "secondary_figure": build_empty_figure(
                "Adjust the filters or open a quick view to restore secondary analysis.",
                height=320,
            ),
            "details": build_enriched_detail_cards([], filters.entity_mode, pd.DataFrame()),
            "status": empty_message,
            "comparison_tray": build_comparison_tray([]),
            "chart_summary": build_chart_summary_strip([], filters.entity_mode),
            "chart_visual_key": build_chart_visual_key(filters),
            "secondary_title": _secondary_title(filters),
            "secondary_note": _secondary_note(filters),
        }

    all_records = working.to_dict(orient="records")
    selected_records = select_records(all_records, selected_row_ids)
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
        "leaderboard_styles": styles,
        "selected_ids": selected_ids,
        "figure": primary_figure,
        "primary_figure": primary_figure,
        "secondary_figure": secondary_figure,
        "details": details,
        "status": status,
        "comparison_tray": build_comparison_tray(selected_records),
        "chart_summary": build_chart_summary_strip(selected_records, filters.entity_mode),
        "chart_visual_key": build_chart_visual_key(filters),
        "secondary_title": _secondary_title(filters),
        "secondary_note": _secondary_note(filters),
    }


def _quick_view_preset(triggered_id: Any) -> str | Any:
    if isinstance(triggered_id, dict) and triggered_id.get("type") == "quick-view-button":
        return triggered_id.get("preset")
    return no_update


def _preset_filter_values(preset: str | None, current_search: str | None) -> tuple[Any, ...]:
    if not preset:
        return (no_update,) * _PRESET_FILTER_OUTPUT_COUNT
    current_state = decode_dashboard_state(current_search)
    if current_state["filters"].preset == preset:
        return (no_update,) * _PRESET_FILTER_OUTPUT_COUNT
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


def _saved_bundle_options(saved_bundles: Any, current_value: str | None) -> tuple[list[dict[str, str]], str | None]:
    bundles = normalize_saved_bundles(saved_bundles)
    options = [{"label": bundle.name, "value": bundle.id} for bundle in bundles]
    valid_ids = {bundle.id for bundle in bundles}
    if current_value in valid_ids:
        value = current_value
    else:
        value = bundles[0].id if bundles else None
    return options, value


def _saved_bundle_action(
    *,
    triggered_id: Any,
    saved_bundles: Any,
    bundle_name: str | None,
    selected_bundle_id: str | None,
    filters: DashboardFilters | None,
    selected_row_ids: list[str] | None,
) -> tuple[Any, Any, Any]:
    bundles = normalize_saved_bundles(saved_bundles)
    if triggered_id == "save-bundle":
        clean_name = str(bundle_name or "").strip()
        if not selected_row_ids:
            return no_update, "Select at least one comparison before saving a bundle.", no_update
        if not clean_name:
            return no_update, "Enter a bundle name before saving.", no_update
        if filters is None:
            raise ValueError("filters are required when saving a bundle")
        new_bundle = serialize_saved_bundle(clean_name, filters, list(selected_row_ids or []))
        bundles = [bundle for bundle in bundles if bundle.name.lower() != clean_name.lower()]
        bundles.insert(0, new_bundle)
        bundles = bundles[:12]
        return saved_bundles_payload(bundles), f'Saved bundle "{clean_name}".', ""
    if triggered_id == "delete-bundle":
        if not selected_bundle_id:
            return no_update, "Choose a saved bundle to delete.", no_update
        remaining = [bundle for bundle in bundles if bundle.id != selected_bundle_id]
        if len(remaining) == len(bundles):
            return no_update, "Saved bundle was not found.", no_update
        return saved_bundles_payload(remaining), "Deleted saved bundle.", no_update
    return no_update, no_update, no_update


def _saved_bundle_search(load_clicks: int, selected_bundle_id: str | None, saved_bundles: Any) -> str | Any:
    if not load_clicks or not selected_bundle_id:
        return no_update
    bundles = normalize_saved_bundles(saved_bundles)
    for bundle in bundles:
        if bundle.id == selected_bundle_id:
            return bundle.search
    return no_update


def _metric_visibility(
    entity_mode: str,
    current_metric: str | None,
    analysis_mode: str | None,
    line_color_mode: str | None,
) -> tuple[Any, ...]:
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


def _selection_ids_from_tray(triggered_id: Any, selected_row_ids: list[str] | None) -> list[str] | Any:
    current_ids = list(selected_row_ids or [])
    if triggered_id == "clear-comparisons":
        return []
    if triggered_id == "remove-last-comparison":
        return current_ids[:-1]
    if isinstance(triggered_id, dict) and triggered_id.get("type") == "comparison-remove":
        target_id = triggered_id.get("selection_id")
        return [selection_id for selection_id in current_ids if selection_id != target_id]
    return no_update


def _effective_selected_ids(
    triggered_id: Any,
    url_selected_ids: list[str] | None,
    selected_row_ids: list[str] | None,
) -> list[str] | None:
    if triggered_id == "url-selected-ids" and url_selected_ids:
        return list(url_selected_ids or [])
    return selected_row_ids


def _updated_url_search(
    filters: DashboardFilters,
    current_search: str | None,
) -> str | Any:
    next_search = encode_dashboard_state(filters)
    current_filters = decode_dashboard_state(current_search)["filters"]
    current_filter_search = encode_dashboard_state(current_filters)
    if current_filter_search == next_search:
        return no_update
    return next_search


def _prepare_leaderboard_export_frame(
    rows: list[dict[str, Any]] | None,
    columns: list[dict[str, Any]] | None,
) -> pd.DataFrame | None:
    if not rows or not columns:
        return None
    frame = pd.DataFrame(rows)
    if frame.empty:
        return None
    export_ids = [column["id"] for column in columns if column["id"] in frame.columns]
    export_names = {column["id"]: column["name"] for column in columns}
    return frame[export_ids].rename(columns=export_names)


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
        Output("preset-filter", "value", allow_duplicate=True),
        Input({"type": "quick-view-button", "preset": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _apply_quick_view(_clicks: list[int] | None):
        return _quick_view_preset(ctx.triggered_id)

    @app.callback(
        Output("quick-view-bar", "children"),
        Input("preset-filter", "value"),
    )
    def _update_quick_view_bar(preset: str | None):
        return build_quick_view_bar(preset)

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
        State("dashboard-location", "search"),
        prevent_initial_call=True,
    )
    def _apply_preset_value(preset: str | None, current_search: str | None):
        return _preset_filter_values(preset, current_search)

    @app.callback(
        Output("saved-bundle-select", "options"),
        Output("saved-bundle-select", "value"),
        Input("saved-bundles", "data"),
        State("saved-bundle-select", "value"),
    )
    def _sync_saved_bundle_options(saved_bundles: Any, current_value: str | None):
        return _saved_bundle_options(saved_bundles, current_value)

    @app.callback(
        Output("saved-bundles", "data"),
        Output("bundle-status", "children"),
        Output("bundle-name", "value"),
        Input("save-bundle", "n_clicks"),
        Input("delete-bundle", "n_clicks"),
        State("saved-bundles", "data"),
        State("bundle-name", "value"),
        State("saved-bundle-select", "value"),
        State("entity-mode", "value"),
        State("ranking-metric", "value"),
        State("time-mode", "value"),
        State("burst-window", "value"),
        State("analysis-mode", "value"),
        State("analysis-window", "value"),
        State("line-color-mode", "value"),
        State("shot-markers", "value"),
        State("include-ot", "value"),
        State("competitive-only", "value"),
        State("min-points", "value"),
        State("min-competitive-share", "value"),
        State("min-ts-pct", "value"),
        State("min-efg-pct", "value"),
        State("min-offensive-share", "value"),
        State("player-filter", "value"),
        State("team-filter", "value"),
        State("opponent-filter", "value"),
        State("season-filter", "value"),
        State("season-type-filter", "value"),
        State("era-filter", "value"),
        State("preset-filter", "value"),
        State("leaderboard-table", "selected_row_ids"),
        prevent_initial_call=True,
    )
    def _manage_saved_bundles(
        save_clicks: int,
        delete_clicks: int,
        saved_bundles: Any,
        bundle_name: str | None,
        selected_bundle_id: str | None,
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
    ):
        filters: DashboardFilters | None = None
        if ctx.triggered_id == "save-bundle":
            filters = _build_filters_from_inputs(
                entity_mode=entity_mode,
                ranking_metric=ranking_metric,
                time_mode=time_mode,
                burst_window=burst_window,
                analysis_mode=analysis_mode,
                analysis_window=analysis_window,
                line_color_mode=line_color_mode,
                shot_markers=shot_markers,
                include_ot=include_ot,
                competitive_only=competitive_only,
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
        return _saved_bundle_action(
            triggered_id=ctx.triggered_id,
            saved_bundles=saved_bundles,
            bundle_name=bundle_name,
            selected_bundle_id=selected_bundle_id,
            filters=filters,
            selected_row_ids=selected_row_ids,
        )

    @app.callback(
        Output("dashboard-location", "search", allow_duplicate=True),
        Input("load-bundle", "n_clicks"),
        State("saved-bundle-select", "value"),
        State("saved-bundles", "data"),
        prevent_initial_call=True,
    )
    def _load_saved_bundle(
        load_clicks: int,
        selected_bundle_id: str | None,
        saved_bundles: Any,
    ):
        return _saved_bundle_search(load_clicks, selected_bundle_id, saved_bundles)

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
        return _metric_visibility(entity_mode, current_metric, analysis_mode, line_color_mode)

    @app.callback(
        Output("leaderboard-table", "selected_row_ids", allow_duplicate=True),
        Input("clear-comparisons", "n_clicks"),
        Input("remove-last-comparison", "n_clicks"),
        Input({"type": "comparison-remove", "selection_id": ALL}, "n_clicks"),
        State("leaderboard-table", "selected_row_ids"),
        prevent_initial_call=True,
    )
    def _update_selection_from_tray(
        clear_clicks: int,
        remove_last_clicks: int,
        remove_clicks: list[int] | None,
        selected_row_ids: list[str] | None,
    ):
        return _selection_ids_from_tray(ctx.triggered_id, selected_row_ids)

    @app.callback(
        Output("leaderboard-table", "data"),
        Output("leaderboard-table", "columns"),
        Output("leaderboard-table", "tooltip_header"),
        Output("leaderboard-table", "tooltip_data"),
        Output("leaderboard-table", "style_header_conditional"),
        Output("leaderboard-table", "style_data_conditional"),
        Output("leaderboard-table", "style_cell_conditional"),
        Output("leaderboard-table", "page_count"),
        Output("leaderboard-table", "selected_row_ids"),
        Output("comparison-chart", "figure"),
        Output("secondary-analysis-chart", "figure"),
        Output("detail-panel-content", "children"),
        Output("status-banner", "children"),
        Output("comparison-tray", "children"),
        Output("chart-summary-strip", "children"),
        Output("chart-visual-key", "children"),
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
        Input("leaderboard-table", "sort_by"),
        Input("leaderboard-table", "page_current"),
        State("leaderboard-table", "page_size"),
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
        sort_by: list[dict[str, str]] | None,
        page_current: int,
        page_size: int,
    ):
        filters = _build_filters_from_inputs(
            entity_mode=entity_mode,
            ranking_metric=ranking_metric,
            time_mode=time_mode,
            burst_window=burst_window,
            analysis_mode=analysis_mode,
            analysis_window=analysis_window,
            line_color_mode=line_color_mode,
            shot_markers=shot_markers,
            include_ot=include_ot,
            competitive_only=competitive_only,
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
        effective_selected_ids = _effective_selected_ids(ctx.triggered_id, url_selected_ids, selected_row_ids)
        view = render_dashboard_view(
            datasets,
            out_dir,
            filters,
            effective_selected_ids,
            sort_by=sort_by,
            page_current=page_current,
            page_size=page_size,
        )
        return (
            view["records"],
            view["columns"],
            view["leaderboard_styles"]["tooltip_header"],
            view["leaderboard_styles"]["tooltip_data"],
            view["leaderboard_styles"]["style_header_conditional"],
            view["leaderboard_styles"]["style_data_conditional"],
            view["leaderboard_styles"]["style_cell_conditional"],
            view["leaderboard_styles"]["page_count"],
            view["selected_ids"],
            view["primary_figure"],
            view["secondary_figure"],
            view["details"],
            view["status"],
            view["comparison_tray"],
            view["chart_summary"],
            view["chart_visual_key"],
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
        current_search: str | None,
    ):
        filters = _build_filters_from_inputs(
            entity_mode=entity_mode,
            ranking_metric=ranking_metric,
            time_mode=time_mode,
            burst_window=burst_window,
            analysis_mode=analysis_mode,
            analysis_window=analysis_window,
            line_color_mode=line_color_mode,
            shot_markers=shot_markers,
            include_ot=include_ot,
            competitive_only=competitive_only,
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
        return _updated_url_search(filters, current_search)

    @app.callback(
        Output("leaderboard-download", "data"),
        Input("export-leaderboard", "n_clicks"),
        State("leaderboard-table", "data"),
        State("leaderboard-table", "columns"),
        prevent_initial_call=True,
    )
    def _download_leaderboard_csv(
        n_clicks: int,
        rows: list[dict[str, Any]] | None,
        columns: list[dict[str, Any]] | None,
    ):
        if not n_clicks:
            return no_update
        export_frame = _prepare_leaderboard_export_frame(rows, columns)
        if export_frame is None:
            return no_update
        return dcc.send_data_frame(export_frame.to_csv, "nba_scoring_leaderboard.csv", index=False)


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


def _empty_filter_message(filters: DashboardFilters) -> str:
    hints: list[str] = []
    preset_label = get_preset_label(filters.preset)
    if preset_label:
        hints.append(f"quick view is {preset_label}")
    if filters.min_points:
        hints.append(f"min points is {filters.min_points}")
    if filters.competitive_only:
        hints.append("competitive-only is on")
    elif filters.min_competitive_share is not None:
        hints.append(f"competitive share is at least {filters.min_competitive_share:.2f}")
    if not filters.include_ot:
        hints.append("OT is excluded")
    if filters.player:
        hints.append(f"player is {filters.player}")
    if filters.team:
        hints.append(f"team is {filters.team}")
    if filters.opponent:
        hints.append(f"opponent is {filters.opponent}")
    if filters.era:
        hints.append(f"era is {filters.era}")
    if filters.entity_mode == "game":
        if filters.min_ts_pct is not None:
            hints.append(f"TS% is at least {filters.min_ts_pct:.2f}")
        if filters.min_efg_pct is not None:
            hints.append(f"eFG% is at least {filters.min_efg_pct:.2f}")
        if filters.min_offensive_share is not None:
            hints.append(f"offensive share is at least {filters.min_offensive_share:.2f}")
    if not hints:
        return "No performances matched the current filters. Try a quick view or relax the ranking thresholds."
    joined = "; ".join(hints[:4])
    return f"No performances matched the current filters. Current constraints: {joined}. Try a quick view or relax one of those constraints."


def _build_filters_from_inputs(
    *,
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
) -> DashboardFilters:
    return normalize_filters(
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
