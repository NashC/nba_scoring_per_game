from __future__ import annotations

from typing import Any

import pandas as pd
from plotly import graph_objects as go

from ..transforms import build_burst_timeline, build_half_timeline, build_quarter_timeline
from .state import DashboardFilters, DashboardSelection, selection_from_record

BACKGROUND = "#f5efe6"
PAPER = "#fffaf2"
CARD = "#fdf7ee"
TEXT = "#1f1b18"
MUTED = "#7b6d5d"
GRID = "#d8c9b8"
COMPARISON_COLORS = ["#0d5c63", "#d98324", "#8e3b46", "#3b6b4b"]
SHOT_COLORS = {
    "2PT": "#d98324",
    "3PT": "#0d7c86",
    "FT": "#b33c36",
}
MARGIN_COLORS = {
    "trailing_10_plus": "#8e3b46",
    "trailing_1_9": "#d1644a",
    "within_3": "#e7b35a",
    "leading_1_9": "#3b8d73",
    "leading_10_plus": "#0d5c63",
}
PACE_BENCHMARKS = [50, 60, 70, 80, 100]


def build_empty_figure(message: str, *, height: int = 560) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=PAPER,
        plot_bgcolor=CARD,
        font={"family": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif", "color": TEXT},
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 16, "color": MUTED},
            }
        ],
        margin={"l": 24, "r": 24, "t": 40, "b": 24},
        height=height,
    )
    return figure


def build_trajectory_figure(
    selected_records: list[dict[str, Any]],
    timeline_df: pd.DataFrame,
    filters: DashboardFilters,
    burst_summaries: pd.DataFrame | None = None,
) -> go.Figure:
    if not selected_records:
        return build_empty_figure("Select a performance from the leaderboard to compare trajectories.")
    if timeline_df.empty:
        return build_empty_figure("No timeline rows are available for the selected performance.")

    figure = go.Figure()
    x_field, y_field, x_title = _axis_fields(filters.entity_mode, filters.time_mode)
    has_multiple = len(selected_records) > 1

    for index, record in enumerate(selected_records):
        selection = selection_from_record(record, filters.entity_mode)
        entity_timeline = _prepare_entity_timeline(timeline_df, selection)
        if entity_timeline.empty:
            continue

        line_color = COMPARISON_COLORS[index % len(COMPARISON_COLORS)]
        emphasis = _emphasis_style(index, has_multiple)
        if filters.line_color_mode == "margin":
            _add_margin_segment_traces(
                figure,
                entity_timeline,
                selection,
                record,
                x_field,
                y_field,
                index,
                emphasis=emphasis,
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=entity_timeline[x_field],
                    y=entity_timeline[y_field],
                    mode="lines",
                    line={"color": line_color, "width": emphasis["line_width"], "shape": "hv"},
                    opacity=emphasis["line_opacity"],
                    name=_legend_label(selection, record),
                    legendgroup=selection.selection_id,
                    hoverinfo="skip",
                )
            )

        if filters.show_shot_markers:
            figure.add_trace(
                go.Scatter(
                    x=entity_timeline[x_field],
                    y=entity_timeline[y_field],
                    mode="markers",
                    name=f"{_legend_label(selection, record)} events",
                    legendgroup=selection.selection_id,
                    showlegend=False,
                    marker={
                        "size": emphasis["marker_size"],
                        "color": [SHOT_COLORS.get(value, line_color) for value in entity_timeline["scoring_type"]],
                        "line": {"color": PAPER, "width": 1},
                        "opacity": emphasis["marker_opacity"],
                    },
                    customdata=_hover_customdata(entity_timeline, filters),
                    hovertemplate=_hover_template(),
                )
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=entity_timeline[x_field],
                    y=entity_timeline[y_field],
                    mode="markers",
                    name=f"{_legend_label(selection, record)} hover",
                    legendgroup=selection.selection_id,
                    showlegend=False,
                    marker={"size": 14, "color": "rgba(0,0,0,0.001)", "opacity": 1.0},
                    customdata=_hover_customdata(entity_timeline, filters),
                    hovertemplate=_hover_template(),
                )
            )

        _add_burst_annotations(figure, record, filters, burst_summaries, line_color)

    if not figure.data:
        return build_empty_figure("No chartable timeline rows matched the current selection.")

    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=PAPER,
        plot_bgcolor=CARD,
        font={"family": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif", "color": TEXT},
        hoverlabel={
            "bgcolor": "#1f1b18",
            "font": {"family": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif", "color": "#fffaf2"},
        },
        margin={"l": 60, "r": 24, "t": 20, "b": 112},
        height=560,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "left",
            "x": 0.0,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 13, "color": TEXT},
            "entrywidth": 160,
            "entrywidthmode": "pixels",
            "tracegroupgap": 10,
        },
        xaxis={"title": {"text": x_title, "standoff": 54}, "gridcolor": GRID, "zeroline": False},
        yaxis={"title": _y_axis_title(filters.entity_mode), "gridcolor": GRID, "zeroline": False},
    )
    if filters.entity_mode == "game" and filters.time_mode == "raw":
        _apply_game_time_axis_markers(figure, timeline_df)
    if filters.time_mode == "normalized":
        figure.update_xaxes(range=[0, 1], tickformat=".0%")
    return figure


def build_secondary_analysis_figure(
    selected_records: list[dict[str, Any]],
    timeline_df: pd.DataFrame,
    filters: DashboardFilters,
) -> go.Figure:
    if filters.entity_mode == "burst":
        return build_empty_figure("Burst mode already isolates the scoring stretch.", height=320)
    if filters.analysis_mode == "none":
        return build_empty_figure("Choose a secondary analysis mode to inspect pace or burst intensity.", height=320)
    if not selected_records:
        return build_empty_figure("Select a performance to open the secondary analysis panel.", height=320)
    if timeline_df.empty:
        return build_empty_figure("No timeline rows are available for secondary analysis.", height=320)

    figure = go.Figure()
    x_field, _, x_title = _axis_fields(filters.entity_mode, filters.time_mode)
    y_title = {
        "rolling_points": f"Trailing {filters.analysis_window // 60 if filters.analysis_window >= 60 else filters.analysis_window}s Points",
        "rolling_rate": f"Trailing {filters.analysis_window // 60 if filters.analysis_window >= 60 else filters.analysis_window}s Points / Minute",
        "projected_pace": "Projected Final Points (48-Min Pace)",
    }[filters.analysis_mode]

    for index, record in enumerate(selected_records):
        selection = selection_from_record(record, filters.entity_mode)
        entity_timeline = _prepare_entity_timeline(timeline_df, selection)
        if entity_timeline.empty:
            continue
        line_color = COMPARISON_COLORS[index % len(COMPARISON_COLORS)]
        if filters.analysis_mode == "projected_pace":
            series_df = entity_timeline.copy()
            y_values = pd.to_numeric(series_df["projected_48"], errors="coerce")
        else:
            series_df = build_rolling_analysis_series(
                entity_timeline,
                window_seconds=filters.analysis_window,
                mode=filters.analysis_mode,
            )
            y_values = pd.to_numeric(series_df["analysis_value"], errors="coerce")
        figure.add_trace(
            go.Scatter(
                x=series_df[x_field],
                y=y_values,
                mode="lines+markers",
                line={"color": line_color, "width": 2.5, "shape": "hv"},
                marker={"size": 7, "color": line_color},
                name=_legend_label(selection),
                legendgroup=selection.selection_id,
                customdata=_analysis_hover_customdata(series_df, filters),
                hovertemplate=_analysis_hover_template(filters.analysis_mode),
            )
        )

    if not figure.data:
        return build_empty_figure("No secondary analysis rows matched the current selection.", height=320)

    if filters.analysis_mode == "projected_pace":
        for benchmark in PACE_BENCHMARKS:
            figure.add_hline(
                y=benchmark,
                line={"color": GRID, "dash": "dot", "width": 1},
                annotation_text=str(benchmark),
                annotation_position="right",
                annotation_font={"color": MUTED, "size": 11},
            )

    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=PAPER,
        plot_bgcolor=CARD,
        font={"family": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif", "color": TEXT},
        hoverlabel={
            "bgcolor": "#1f1b18",
            "font": {"family": "Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif", "color": "#fffaf2"},
        },
        margin={"l": 60, "r": 24, "t": 48, "b": 96},
        height=320,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
            "entrywidth": 150,
            "entrywidthmode": "pixels",
            "tracegroupgap": 8,
        },
        xaxis={"title": {"text": x_title, "standoff": 50}, "gridcolor": GRID, "zeroline": False},
        yaxis={"title": y_title, "gridcolor": GRID, "zeroline": False},
    )
    if filters.entity_mode == "game" and filters.time_mode == "raw":
        _apply_game_time_axis_markers(figure, timeline_df, secondary=True)
    if filters.time_mode == "normalized":
        figure.update_xaxes(range=[0, 1], tickformat=".0%")
    return figure


def build_rolling_analysis_series(
    entity_timeline: pd.DataFrame,
    *,
    window_seconds: int,
    mode: str,
) -> pd.DataFrame:
    if entity_timeline.empty:
        empty = entity_timeline.copy()
        empty["analysis_window_seconds"] = pd.Series(dtype="Int64")
        empty["analysis_window_points"] = pd.Series(dtype="float64")
        empty["analysis_window_span_seconds"] = pd.Series(dtype="float64")
        empty["analysis_value"] = pd.Series(dtype="float64")
        return empty

    if mode not in {"rolling_points", "rolling_rate"}:
        raise ValueError(f"Unsupported rolling analysis mode: {mode}")

    timeline = entity_timeline.sort_values(["elapsed_seconds_in_game", "action_id"]).reset_index(drop=True).copy()
    event_times = pd.to_numeric(timeline["elapsed_seconds_in_game"], errors="coerce")
    point_values = pd.to_numeric(timeline["point_value"], errors="coerce").fillna(0.0)
    interval_start = float(event_times.min())

    points_in_window: list[float] = []
    spans_in_window: list[float] = []
    values: list[float] = []
    for position, event_time in enumerate(event_times.tolist()):
        lower_bound = max(interval_start, float(event_time) - float(window_seconds))
        mask = event_times.ge(lower_bound) & (
            (event_times < float(event_time))
            | ((event_times == float(event_time)) & (timeline.index <= position))
        )
        window_points = float(point_values.loc[mask].sum())
        span_seconds = float(event_time) - lower_bound
        points_in_window.append(window_points)
        spans_in_window.append(span_seconds)
        if mode == "rolling_points":
            values.append(window_points)
        elif span_seconds <= 0:
            values.append(pd.NA)
        else:
            values.append(window_points / (span_seconds / 60.0))

    timeline["analysis_window_seconds"] = int(window_seconds)
    timeline["analysis_window_points"] = points_in_window
    timeline["analysis_window_span_seconds"] = spans_in_window
    timeline["analysis_value"] = pd.Series(values, dtype="Float64")
    return timeline


def _prepare_entity_timeline(timeline_df: pd.DataFrame, selection: DashboardSelection) -> pd.DataFrame:
    if selection.entity_mode == "game":
        entity_timeline = timeline_df.loc[
            timeline_df["game_id"].eq(selection.game_id) & timeline_df["player_id"].eq(selection.player_id)
        ].sort_values(["game_id", "action_id"]).reset_index(drop=True)
    elif selection.entity_mode == "quarter":
        entity_timeline = build_quarter_timeline(
            timeline_df,
            game_id=selection.game_id,
            player_id=selection.player_id,
            quarter_number=int(selection.payload["quarter_number"]),
        )
    elif selection.entity_mode == "half":
        entity_timeline = build_half_timeline(
            timeline_df,
            game_id=selection.game_id,
            player_id=selection.player_id,
            half_index=int(selection.payload["half_index"]),
        )
    else:
        entity_timeline = build_burst_timeline(timeline_df, selection.payload)
    if entity_timeline.empty:
        return entity_timeline
    prepared = entity_timeline.copy()
    if selection.entity_mode == "burst":
        window_seconds = float(prepared["burst_window_seconds"].iloc[0] or 0)
        prepared["burst_time_normalized"] = prepared["burst_elapsed_seconds"] / window_seconds if window_seconds > 0 else 0.0
    return prepared


def _add_margin_segment_traces(
    figure: go.Figure,
    timeline_df: pd.DataFrame,
    selection: DashboardSelection,
    record: dict[str, Any],
    x_field: str,
    y_field: str,
    comparison_index: int,
    *,
    emphasis: dict[str, float],
) -> None:
    if len(timeline_df) == 1:
        figure.add_trace(
            go.Scatter(
                x=timeline_df[x_field],
                y=timeline_df[y_field],
                mode="lines",
                line={
                    "color": MARGIN_COLORS.get(timeline_df.iloc[0]["margin_bucket"], COMPARISON_COLORS[comparison_index]),
                    "width": emphasis["line_width"],
                },
                opacity=emphasis["line_opacity"],
                name=_legend_label(selection, record),
                legendgroup=selection.selection_id,
                hoverinfo="skip",
            )
        )
        return

    first_trace = True
    for position in range(1, len(timeline_df)):
        segment = timeline_df.iloc[position - 1 : position + 1]
        color = MARGIN_COLORS.get(
            segment.iloc[-1]["margin_bucket"],
            COMPARISON_COLORS[comparison_index % len(COMPARISON_COLORS)],
        )
        figure.add_trace(
            go.Scatter(
                x=segment[x_field],
                y=segment[y_field],
                mode="lines",
                line={"color": color, "width": emphasis["line_width"], "shape": "hv"},
                opacity=emphasis["line_opacity"],
                name=_legend_label(selection, record),
                legendgroup=selection.selection_id,
                showlegend=first_trace,
                hoverinfo="skip",
            )
        )
        first_trace = False


def _add_burst_annotations(
    figure: go.Figure,
    record: dict[str, Any],
    filters: DashboardFilters,
    burst_summaries: pd.DataFrame | None,
    color: str,
) -> None:
    if filters.entity_mode != "game":
        return
    if filters.analysis_mode not in {"rolling_points", "rolling_rate"}:
        return
    if burst_summaries is None or burst_summaries.empty:
        return
    burst_window = int(filters.analysis_window)
    matches = burst_summaries.loc[
        burst_summaries["game_id"].astype(str).eq(str(record["game_id"]))
        & burst_summaries["player_id"].astype(int).eq(int(record["player_id"]))
        & burst_summaries["burst_window_seconds"].astype(int).eq(burst_window)
    ]
    if matches.empty:
        return
    row = matches.iloc[0]
    start_min = float(row["window_start_seconds_in_game"]) / 60.0
    end_min = float(row["window_end_seconds_in_game"]) / 60.0
    figure.add_vrect(
        x0=start_min,
        x1=end_min,
        fillcolor=color,
        opacity=0.07,
        line_width=0,
        layer="below",
    )


def _axis_fields(entity_mode: str, time_mode: str) -> tuple[str, str, str]:
    if entity_mode == "game":
        return (
            ("elapsed_minutes_in_game", "player_game_cumulative_points", "Game Minute")
            if time_mode == "raw"
            else ("game_time_normalized", "player_game_cumulative_points", "Normalized Game Progress")
        )
    if entity_mode == "quarter":
        return (
            ("quarter_time_elapsed", "player_quarter_cumulative_points", "Quarter Minute")
            if time_mode == "raw"
            else ("quarter_time_normalized", "player_quarter_cumulative_points", "Normalized Quarter Progress")
        )
    if entity_mode == "half":
        return (
            ("half_time_elapsed", "player_half_cumulative_points", "Half Minute")
            if time_mode == "raw"
            else ("half_time_normalized", "player_half_cumulative_points", "Normalized Half Progress")
        )
    return (
        ("burst_elapsed_seconds", "burst_cumulative_points", "Burst Seconds")
        if time_mode == "raw"
        else ("burst_time_normalized", "burst_cumulative_points", "Normalized Burst Progress")
    )


def _apply_game_time_axis_markers(figure: go.Figure, timeline_df: pd.DataFrame, *, secondary: bool = False) -> None:
    total_minutes = _total_game_minutes(timeline_df)
    tickvals, ticktext = _game_time_ticks(total_minutes)
    figure.update_xaxes(
        range=[0, total_minutes],
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )

    for boundary, label in _period_end_markers(total_minutes):
        line_color = "rgba(123,109,93,0.42)" if label not in {"HT", "REG"} else "rgba(123,109,93,0.62)"
        line_width = 1.0 if label not in {"HT", "REG"} else 1.35
        figure.add_vline(
            x=boundary,
            line={"color": line_color, "dash": "dot", "width": line_width},
        )
        figure.add_annotation(
            x=boundary,
            y=-0.038 if not secondary else -0.07,
            xref="x",
            yref="paper",
            text=label,
            showarrow=False,
            font={
                "size": 12 if not secondary else 11,
                "color": TEXT,
                "family": "Avenir Next Demi Bold, Avenir Next, Trebuchet MS, Helvetica Neue, sans-serif",
            },
            xanchor="center",
            yanchor="top",
        )


def _total_game_minutes(timeline_df: pd.DataFrame) -> float:
    if timeline_df.empty:
        return 48.0
    total_series = pd.to_numeric(timeline_df.get("total_game_minutes"), errors="coerce")
    if total_series.notna().any():
        return max(48.0, float(total_series.max()))
    elapsed_series = pd.to_numeric(timeline_df.get("elapsed_minutes_in_game"), errors="coerce")
    if not elapsed_series.notna().any():
        return 48.0
    elapsed_max = float(elapsed_series.max())
    if elapsed_max <= 48.0:
        return 48.0
    ot_count = int((elapsed_max - 48.0 + 4.999999) // 5.0)
    return 48.0 + 5.0 * max(1, ot_count)


def _game_time_ticks(total_minutes: float) -> tuple[list[float], list[str]]:
    tickvals = [0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0, 42.0, 48.0]
    ticktext = ["0", "6", "12", "18", "24", "30", "36", "42", "48"]
    overtime_index = 1
    boundary = 53.0
    while boundary <= total_minutes + 1e-9:
        tickvals.append(boundary)
        ticktext.append(str(int(boundary)))
        overtime_index += 1
        boundary += 5.0
    return tickvals, ticktext


def _period_end_markers(total_minutes: float) -> list[tuple[float, str]]:
    markers: list[tuple[float, str]] = [
        (12.0, "Q1"),
        (24.0, "HT"),
        (36.0, "Q3"),
        (48.0, "REG"),
    ]
    overtime_index = 1
    boundary = 53.0
    while boundary <= total_minutes + 1e-9:
        markers.append((boundary, f"OT{overtime_index}"))
        overtime_index += 1
        boundary += 5.0
    return markers


def _y_axis_title(entity_mode: str) -> str:
    if entity_mode == "quarter":
        return "Quarter Cumulative Points"
    if entity_mode == "half":
        return "Half Cumulative Points"
    if entity_mode == "burst":
        return "Burst Cumulative Points"
    return "Cumulative Points"


def _legend_label(selection: DashboardSelection, record: dict[str, Any] | None = None) -> str:
    short_name = selection.player_name.split()[-1] if selection.player_name.strip() else selection.player_name
    if record is None:
        return short_name
    points_key = {
        "game": "final_points",
        "quarter": "quarter_points",
        "half": "half_points",
        "burst": "points_in_window",
    }[selection.entity_mode]
    points = record.get(points_key)
    points_suffix = ""
    if points not in {None, "", "None"} and not pd.isna(points):
        points_suffix = f" ({int(points)})"
    if selection.entity_mode == "game":
        return f"{short_name}{points_suffix}"
    return f"{short_name} · {selection.label}{points_suffix}"


def _emphasis_style(index: int, has_multiple: bool) -> dict[str, float]:
    if not has_multiple or index == 0:
        return {
            "line_width": 3.4,
            "line_opacity": 1.0,
            "marker_size": 10.0,
            "marker_opacity": 0.98,
        }
    return {
        "line_width": 2.2,
        "line_opacity": 0.48,
        "marker_size": 8.0,
        "marker_opacity": 0.84,
    }


def _hover_customdata(timeline_df: pd.DataFrame, filters: DashboardFilters) -> list[list[Any]]:
    return [
        [
            row["player_name"],
            row["team_tricode"],
            row.get("opponent_team_tricode", ""),
            row["game_date"],
            row["season"],
            _period_label(row),
            _clock_display(row.get("clock")),
            _mode_time_label(filters.entity_mode, filters.time_mode),
            _mode_time_value(row, filters.entity_mode, filters.time_mode),
            _entity_context_label(row, filters.entity_mode),
            _game_minute_label(row.get("game_minute")),
            row["point_value"],
            row["scoring_type"],
            row["player_team_score_after"],
            row["opponent_score_after"],
            row["score_diff"],
            _projected_label(row["projected_48"]),
        ]
        for _, row in timeline_df.iterrows()
    ]


def _hover_template() -> str:
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{customdata[1]} vs %{customdata[2]}<br>"
        "%{customdata[3]} · %{customdata[4]}<br>"
        "%{customdata[5]} · %{customdata[6]} remaining<br>"
        "%{customdata[9]} · %{customdata[7]} %{customdata[8]}<br>"
        "Game minute %{customdata[10]}<br>"
        "Cumulative: %{y}<br>"
        "Event: %{customdata[11]} pts (%{customdata[12]})<br>"
        "Score: %{customdata[13]}-%{customdata[14]}<br>"
        "Diff: %{customdata[15]}<br>"
        "Projected 48: %{customdata[16]}<extra></extra>"
    )


def _analysis_hover_customdata(series_df: pd.DataFrame, filters: DashboardFilters) -> list[list[Any]]:
    label = {
        "rolling_points": "Rolling points",
        "rolling_rate": "Rolling rate",
        "projected_pace": "Projected 48",
    }[filters.analysis_mode]
    customdata: list[list[Any]] = []
    for _, row in series_df.iterrows():
        if filters.analysis_mode == "projected_pace":
            value = _projected_label(row["projected_48"])
            window = "48-min pace"
        else:
            value = _analysis_value_label(row["analysis_value"])
            window = _window_label(int(row["analysis_window_seconds"]))
        customdata.append(
            [
                row["player_name"],
                label,
                window,
                _period_label(row),
                _clock_display(row.get("clock")),
                _mode_time_value(row, filters.entity_mode, filters.time_mode),
                value,
            ]
        )
    return customdata


def _analysis_hover_template(mode: str) -> str:
    if mode == "projected_pace":
        return (
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}: %{customdata[6]}<br>"
            "%{customdata[3]} · %{customdata[4]} remaining<br>"
            "At %{customdata[5]}<extra></extra>"
        )
    return (
        "<b>%{customdata[0]}</b><br>"
        "%{customdata[1]} (%{customdata[2]}): %{customdata[6]}<br>"
        "%{customdata[3]} · %{customdata[4]} remaining<br>"
        "At %{customdata[5]}<extra></extra>"
    )


def _mode_time_label(entity_mode: str, time_mode: str) -> str:
    if entity_mode == "game":
        return "Game minute"
    if entity_mode == "quarter":
        return "Quarter progress" if time_mode == "normalized" else "Quarter minute"
    if entity_mode == "half":
        return "Half progress" if time_mode == "normalized" else "Half minute"
    return "Burst progress" if time_mode == "normalized" else "Burst second"


def _mode_time_value(row: pd.Series, entity_mode: str, time_mode: str) -> str:
    if entity_mode == "game":
        value = row["game_time_normalized"] if time_mode == "normalized" else row["elapsed_minutes_in_game"]
    elif entity_mode == "quarter":
        value = row["quarter_time_normalized"] if time_mode == "normalized" else row["quarter_time_elapsed"]
    elif entity_mode == "half":
        value = row["half_time_normalized"] if time_mode == "normalized" else row["half_time_elapsed"]
    else:
        value = row.get("burst_time_normalized") if time_mode == "normalized" else row["burst_elapsed_seconds"]
    if value is None or pd.isna(value):
        return "NA"
    numeric = float(value)
    return f"{numeric:.0%}" if time_mode == "normalized" else f"{numeric:.1f}"


def _entity_context_label(row: pd.Series, entity_mode: str) -> str:
    if entity_mode == "quarter":
        return "Quarter context"
    if entity_mode == "half":
        half_index = row.get("half_index")
        return f"H{int(half_index)} context" if half_index not in {None, "", "None"} and not pd.isna(half_index) else "Half context"
    if entity_mode == "burst":
        return "Burst context"
    return "Game context"


def _game_minute_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.1f}"


def _clock_display(value: Any) -> str:
    if value in {None, "", "None"}:
        return "NA"
    text = str(value).strip()
    if not text.startswith("PT"):
        return text
    body = text[2:]
    minutes_text = "0"
    seconds_text = "00"
    if "M" in body:
        minutes_text, body = body.split("M", 1)
    if body.endswith("S"):
        seconds_text = body[:-1] or "0"
    try:
        minutes = int(float(minutes_text or 0))
        seconds = float(seconds_text or 0)
    except ValueError:
        return text
    return f"{minutes}:{int(seconds):02d}"


def _period_label(row: Any) -> str:
    period = int(row["period"])
    if period <= 4:
        return f"Q{period}"
    return f"OT{period - 4}"


def _projected_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{numeric:.1f}"


def _analysis_value_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "NA"


def _window_label(window_seconds: int) -> str:
    if window_seconds % 60 == 0:
        minutes = window_seconds // 60
        return f"{minutes} min"
    return f"{window_seconds} sec"
