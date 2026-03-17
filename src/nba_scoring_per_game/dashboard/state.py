from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math
from typing import Any
from urllib.parse import parse_qs, urlencode

import pandas as pd

from ..pipeline import query_player_games
from .loader import DashboardDatasets
from .team_logos import resolve_team_logo_asset_src

MAX_COMPARISONS = 4
FILTER_CACHE_SIZE = 128
DEFAULT_ENTITY_MODE = "game"
DEFAULT_ANALYSIS_MODE = "none"
DEFAULT_ANALYSIS_WINDOW = 180
LEADERBOARD_HIGHLIGHT_BACKGROUND = "#f4ebde"
VALID_ENTITY_MODES = {"game", "quarter", "half", "burst"}
VALID_TIME_MODES = {"raw", "normalized"}
VALID_ANALYSIS_MODES = {"none", "rolling_points", "rolling_rate", "projected_pace"}
VALID_LINE_COLOR_MODES = {"player", "margin"}
VALID_WINDOW_SECONDS = {60, 120, 180, 300, 600}
DEFAULT_RANKING_METRIC = {
    "game": "total_points",
    "quarter": "quarter_points",
    "half": "half_points",
    "burst": "points_in_window",
}
RANKING_OPTIONS = {
    "game": [
        ("total_points", "Total Points"),
        ("points_per_minute", "Points / Minute"),
        ("best_60_sec_points", "Best 60 Sec"),
        ("best_2_min_points", "Best 2 Min"),
        ("best_3_min_points", "Best 3 Min"),
        ("best_5_min_points", "Best 5 Min"),
        ("best_10_min_points", "Best 10 Min"),
        ("best_quarter_points", "Best Quarter"),
        ("best_half_points", "Best Half"),
        ("ts_pct", "TS%"),
        ("efg_pct", "eFG%"),
        ("offensive_share", "Offensive Share"),
        ("competitive_points", "Competitive Points"),
        ("competitive_scoring_share", "Competitive Share"),
        ("trailing_points", "Trailing Points"),
        ("trailing_scoring_rate", "Trailing Rate"),
    ],
    "quarter": [
        ("quarter_points", "Quarter Points"),
        ("points_per_minute", "Points / Minute"),
        ("competitive_points", "Competitive Points"),
        ("competitive_scoring_share", "Competitive Share"),
        ("avg_abs_margin_during_scoring_events", "Avg Abs Margin"),
        ("share_points_from_3s", "3PT Share"),
        ("share_points_from_fts", "FT Share"),
    ],
    "half": [
        ("half_points", "Half Points"),
        ("points_per_minute", "Points / Minute"),
        ("competitive_points", "Competitive Points"),
        ("competitive_scoring_share", "Competitive Share"),
        ("avg_abs_margin_during_scoring_events", "Avg Abs Margin"),
        ("share_points_from_3s", "3PT Share"),
        ("share_points_from_fts", "FT Share"),
    ],
    "burst": [
        ("points_in_window", "Window Points"),
        ("points_per_minute", "Points / Minute"),
        ("competitive_points", "Competitive Points"),
        ("competitive_scoring_share", "Competitive Share"),
        ("avg_abs_score_diff_in_window", "Avg Abs Margin"),
        ("trailing_points", "Trailing Points"),
        ("share_points_from_3s", "3PT Share"),
        ("share_points_from_fts", "FT Share"),
    ],
}
PRESET_DEFINITIONS = {
    "top_scoring_games": {
        "entity_mode": "game",
        "ranking_metric": "total_points",
        "min_points": 50,
        "include_ot": True,
    },
    "70_plus_games": {
        "entity_mode": "game",
        "ranking_metric": "total_points",
        "min_points": 70,
        "include_ot": True,
    },
    "best_quarters": {
        "entity_mode": "quarter",
        "ranking_metric": "quarter_points",
        "min_points": 25,
        "include_ot": True,
    },
    "best_halves": {
        "entity_mode": "half",
        "ranking_metric": "half_points",
        "min_points": 35,
        "include_ot": True,
    },
    "best_3_min_bursts": {
        "entity_mode": "burst",
        "ranking_metric": "points_in_window",
        "burst_window": 180,
        "min_points": 10,
        "include_ot": True,
    },
    "competitive_60_plus_games": {
        "entity_mode": "game",
        "ranking_metric": "total_points",
        "min_points": 60,
        "min_competitive_share": 0.75,
        "include_ot": False,
    },
}
PRESET_OPTIONS = [
    ("top_scoring_games", "Top Scoring Games"),
    ("70_plus_games", "70+ Games"),
    ("best_quarters", "Best Quarters"),
    ("best_halves", "Best Halves"),
    ("best_3_min_bursts", "Best 3-Min Bursts"),
    ("competitive_60_plus_games", "Competitive 60+ Games"),
]
QUERY_PARAM_KEYS = {
    "entity_mode": "mode",
    "ranking_metric": "rank",
    "time_mode": "time",
    "burst_window": "burst",
    "analysis_mode": "analysis",
    "analysis_window": "analysis_window",
    "line_color_mode": "line_color",
    "show_shot_markers": "markers",
    "include_ot": "include_ot",
    "competitive_only": "competitive_only",
    "min_points": "min_points",
    "min_competitive_share": "min_comp_share",
    "min_ts_pct": "min_ts",
    "min_efg_pct": "min_efg",
    "min_offensive_share": "min_off_share",
    "player": "player",
    "team": "team",
    "opponent": "opponent",
    "season": "season",
    "season_type": "season_type",
    "era": "era",
    "preset": "preset",
    "selected_ids": "selected",
}
LEADERBOARD_BASE_SPECS = {
    "game": [
        ("rank", "#", "text"),
        ("final_points", "Pts", "int"),
        ("player_name", "Player", "text"),
        ("team_logo", "Team", "markdown"),
        ("opponent_team_logo", "Opp", "markdown"),
        ("game_date", "Year", "text"),
        ("minutes_played", "Mins", "decimal"),
        ("points_per_minute", "Pts / Min", "decimal"),
        ("ts_pct", "TS%", "pct1"),
        ("efg_pct", "eFG%", "pct1"),
        ("offensive_share", "Off Share", "pct1"),
        ("competitive_scoring_share", "Comp Share", "pct1"),
    ],
    "quarter": [
        ("rank", "#", "text"),
        ("quarter_points", "Pts", "int"),
        ("player_name", "Player", "text"),
        ("team_logo", "Team", "markdown"),
        ("opponent_team_logo", "Opp", "markdown"),
        ("game_date", "Year", "text"),
        ("entity_label", "Segment", "text"),
        ("quarter_duration_minutes", "Mins", "decimal"),
        ("points_per_minute", "Pts / Min", "decimal"),
        ("competitive_scoring_share", "Comp Share", "pct1"),
        ("avg_abs_margin_during_scoring_events", "Avg Abs Margin", "decimal"),
        ("share_points_from_3s", "3PT Share", "pct1"),
        ("share_points_from_fts", "FT Share", "pct1"),
    ],
    "half": [
        ("rank", "#", "text"),
        ("half_points", "Pts", "int"),
        ("player_name", "Player", "text"),
        ("team_logo", "Team", "markdown"),
        ("opponent_team_logo", "Opp", "markdown"),
        ("game_date", "Year", "text"),
        ("entity_label", "Segment", "text"),
        ("half_duration_minutes", "Mins", "decimal"),
        ("points_per_minute", "Pts / Min", "decimal"),
        ("competitive_scoring_share", "Comp Share", "pct1"),
        ("avg_abs_margin_during_scoring_events", "Avg Abs Margin", "decimal"),
        ("share_points_from_3s", "3PT Share", "pct1"),
        ("share_points_from_fts", "FT Share", "pct1"),
    ],
    "burst": [
        ("rank", "#", "text"),
        ("points_in_window", "Pts", "int"),
        ("player_name", "Player", "text"),
        ("team_logo", "Team", "markdown"),
        ("opponent_team_logo", "Opp", "markdown"),
        ("game_date", "Year", "text"),
        ("entity_label", "Burst", "text"),
        ("burst_window_seconds", "Mins", "minutes_from_seconds"),
        ("window_points_per_minute", "Pts / Min", "decimal"),
        ("competitive_scoring_share", "Comp Share", "pct1"),
        ("avg_abs_score_diff_in_window", "Avg Abs Margin", "decimal"),
        ("share_points_from_3s", "3PT Share", "pct1"),
        ("share_points_from_fts", "FT Share", "pct1"),
    ],
}
ESTIMATED_LEADERBOARD_COLUMNS = {
    "game": {
        "competitive_points",
        "competitive_scoring_share",
        "trailing_points",
        "trailing_scoring_rate",
        "best_60_sec_points",
        "best_2_min_points",
        "best_3_min_points",
        "best_5_min_points",
        "best_10_min_points",
    },
    "quarter": {
        "competitive_points",
        "competitive_scoring_share",
        "avg_abs_margin_during_scoring_events",
    },
    "half": {
        "competitive_points",
        "competitive_scoring_share",
        "avg_abs_margin_during_scoring_events",
    },
    "burst": {
        "points_in_window",
        "window_points_per_minute",
        "competitive_points",
        "competitive_scoring_share",
        "avg_abs_score_diff_in_window",
        "trailing_points",
    },
}

_FILTER_CACHE: OrderedDict[tuple[Any, ...], pd.DataFrame] = OrderedDict()


@dataclass(slots=True)
class DashboardFilters:
    entity_mode: str = DEFAULT_ENTITY_MODE
    ranking_metric: str = DEFAULT_RANKING_METRIC[DEFAULT_ENTITY_MODE]
    time_mode: str = "raw"
    burst_window: int = 180
    analysis_mode: str = DEFAULT_ANALYSIS_MODE
    analysis_window: int = DEFAULT_ANALYSIS_WINDOW
    line_color_mode: str = "player"
    show_shot_markers: bool = True
    include_ot: bool = True
    competitive_only: bool = False
    min_points: int | None = None
    min_competitive_share: float | None = None
    min_ts_pct: float | None = None
    min_efg_pct: float | None = None
    min_offensive_share: float | None = None
    player: str | None = None
    team: str | None = None
    opponent: str | None = None
    season: str | None = None
    season_type: str | None = None
    era: str | None = None
    preset: str | None = None


@dataclass(slots=True)
class DashboardSelection:
    entity_mode: str
    selection_id: str
    label: str
    season: str
    season_type: str
    game_id: str
    player_id: int
    player_name: str
    team_tricode: str
    opponent_team_tricode: str
    payload: dict[str, Any]


def normalize_filters(**kwargs: Any) -> DashboardFilters:
    entity_mode = str(kwargs.get("entity_mode") or DEFAULT_ENTITY_MODE).strip().lower()
    if entity_mode not in VALID_ENTITY_MODES:
        entity_mode = DEFAULT_ENTITY_MODE
    ranking_metric = _normalize_ranking_metric_for_mode(entity_mode, kwargs.get("ranking_metric"))
    analysis_mode = str(kwargs.get("analysis_mode") or DEFAULT_ANALYSIS_MODE).strip().lower()
    if analysis_mode not in VALID_ANALYSIS_MODES:
        analysis_mode = DEFAULT_ANALYSIS_MODE
    time_mode = str(kwargs.get("time_mode") or "raw").strip().lower()
    if time_mode not in VALID_TIME_MODES:
        time_mode = "raw"
    line_color_mode = str(kwargs.get("line_color_mode") or "player").strip().lower()
    if line_color_mode not in VALID_LINE_COLOR_MODES:
        line_color_mode = "player"
    burst_window = _normalize_window(kwargs.get("burst_window"), default=180)
    analysis_window = _normalize_window(kwargs.get("analysis_window"), default=DEFAULT_ANALYSIS_WINDOW)
    return DashboardFilters(
        entity_mode=entity_mode,
        ranking_metric=ranking_metric,
        time_mode=time_mode,
        burst_window=burst_window,
        analysis_mode=analysis_mode,
        analysis_window=analysis_window,
        line_color_mode=line_color_mode,
        show_shot_markers=bool(kwargs.get("show_shot_markers", True)),
        include_ot=bool(kwargs.get("include_ot", True)),
        competitive_only=bool(kwargs.get("competitive_only", False)),
        min_points=_coerce_int(kwargs.get("min_points")),
        min_competitive_share=_coerce_float(kwargs.get("min_competitive_share")),
        min_ts_pct=_coerce_float(kwargs.get("min_ts_pct")),
        min_efg_pct=_coerce_float(kwargs.get("min_efg_pct")),
        min_offensive_share=_coerce_float(kwargs.get("min_offensive_share")),
        player=_clean_text(kwargs.get("player")),
        team=_clean_text(kwargs.get("team")),
        opponent=_clean_text(kwargs.get("opponent")),
        season=_clean_text(kwargs.get("season")),
        season_type=_clean_text(kwargs.get("season_type")),
        era=_clean_text(kwargs.get("era")),
        preset=_clean_text(kwargs.get("preset")),
    )


def apply_dashboard_preset(preset: str | None) -> DashboardFilters:
    defaults = DashboardFilters()
    if preset is None:
        return defaults
    payload = PRESET_DEFINITIONS.get(str(preset).strip())
    if payload is None:
        return defaults
    return normalize_filters(**payload, preset=preset)


def get_ranking_options(entity_mode: str) -> list[dict[str, str]]:
    normalized = str(entity_mode).strip().lower()
    return [{"label": label, "value": value} for value, label in RANKING_OPTIONS[normalized]]


def build_quick_view_options() -> list[dict[str, str]]:
    return [{"label": label, "value": value} for value, label in PRESET_OPTIONS]


def get_preset_options() -> list[dict[str, str]]:
    return build_quick_view_options()


def get_preset_label(preset: str | None) -> str | None:
    if preset is None:
        return None
    lookup = dict(PRESET_OPTIONS)
    return lookup.get(str(preset).strip())


def default_ranking_metric(entity_mode: str) -> str:
    return DEFAULT_RANKING_METRIC[str(entity_mode).strip().lower()]


def _valid_ranking_metrics(entity_mode: str) -> set[str]:
    normalized = str(entity_mode).strip().lower()
    options = RANKING_OPTIONS.get(normalized, RANKING_OPTIONS[DEFAULT_ENTITY_MODE])
    return {value for value, _ in options}


def _normalize_ranking_metric_for_mode(entity_mode: str, ranking_metric: Any) -> str:
    normalized = str(entity_mode).strip().lower()
    default_metric = DEFAULT_RANKING_METRIC.get(normalized, DEFAULT_RANKING_METRIC[DEFAULT_ENTITY_MODE])
    metric = str(ranking_metric or default_metric).strip()
    if metric in _valid_ranking_metrics(normalized):
        return metric
    return default_metric


def filter_summary_frame(datasets: DashboardDatasets, filters: DashboardFilters) -> pd.DataFrame:
    cache_key = _filter_cache_key(datasets, filters)
    cached = _FILTER_CACHE.get(cache_key)
    if cached is not None:
        _FILTER_CACHE.move_to_end(cache_key)
        return cached.copy()

    frame = get_entity_frame(datasets, filters.entity_mode).copy()
    if frame.empty:
        return frame
    ranking_metric = _normalize_ranking_metric_for_mode(filters.entity_mode, filters.ranking_metric)

    if filters.season:
        frame = frame.loc[frame["season"].astype(str).eq(filters.season)]
    if filters.season_type:
        frame = frame.loc[frame["season_type"].astype(str).eq(filters.season_type)]
    if filters.player:
        frame = frame.loc[frame["player_name"].astype(str).eq(filters.player)]
    if filters.team:
        frame = frame.loc[frame["team_tricode"].astype(str).eq(filters.team)]
    if filters.opponent:
        frame = frame.loc[frame["opponent_team_tricode"].astype(str).eq(filters.opponent)]
    if filters.era and "era" in frame.columns:
        frame = frame.loc[frame["era"].astype(str).eq(filters.era)]
    if filters.min_ts_pct is not None and "ts_pct" in frame.columns:
        ts_pct = pd.to_numeric(frame["ts_pct"], errors="coerce")
        frame = frame.loc[ts_pct >= float(filters.min_ts_pct)]
    if filters.min_efg_pct is not None and "efg_pct" in frame.columns:
        efg_pct = pd.to_numeric(frame["efg_pct"], errors="coerce")
        frame = frame.loc[efg_pct >= float(filters.min_efg_pct)]
    if filters.min_offensive_share is not None and "offensive_share" in frame.columns:
        off_share = pd.to_numeric(frame["offensive_share"], errors="coerce")
        frame = frame.loc[off_share >= float(filters.min_offensive_share)]

    filtered = query_player_games(
        frame,
        entity_mode=filters.entity_mode,
        min_points=filters.min_points,
        competitive_only=filters.competitive_only,
        min_competitive_share=filters.min_competitive_share,
        include_ot=filters.include_ot,
        burst_window=filters.burst_window,
        ranking_metric=ranking_metric,
        sort_by=ranking_metric,
        ascending=False,
    ).reset_index(drop=True)
    _remember_filter_cache(cache_key, filtered)
    return filtered.copy()


def build_leaderboard_table(
    summary_df: pd.DataFrame,
    filters: DashboardFilters,
    limit: int | None = None,
    sort_by: list[dict[str, str]] | None = None,
    page_current: int = 0,
    page_size: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    ranking_metric = _normalize_ranking_metric_for_mode(filters.entity_mode, filters.ranking_metric)
    working, column_specs = _prepare_leaderboard_dataframe(summary_df, filters, sort_by)
    if working.empty:
        return [], _leaderboard_columns(column_specs), _leaderboard_style_metadata(
            column_specs,
            None,
            filters.entity_mode,
            tooltip_data=[],
            page_count=0,
            total_rows=0,
        )

    if limit is not None:
        working = working.head(limit).copy()
    total_rows = len(working)
    paged = _slice_leaderboard_page(working, page_current=page_current, page_size=page_size)

    records = paged.to_dict(orient="records")
    highlight_column = _highlight_display_id(filters.entity_mode, ranking_metric)
    style_meta = _leaderboard_style_metadata(
        column_specs,
        highlight_column,
        filters.entity_mode,
        tooltip_data=_leaderboard_tooltip_data(paged, column_specs, filters.entity_mode),
        page_count=_page_count(total_rows, page_size),
        total_rows=total_rows,
    )
    return records, _leaderboard_columns(column_specs), style_meta


def select_records(
    records: list[dict[str, Any]],
    selected_row_ids: list[str] | None,
    max_comparisons: int = MAX_COMPARISONS,
) -> list[dict[str, Any]]:
    if not records:
        return []
    selected_ids = list(selected_row_ids or [])
    if not selected_ids:
        return [records[0]]
    selected_set = set(selected_ids[:max_comparisons])
    selected = [record for record in records if record["selection_id"] in selected_set]
    return selected[:max_comparisons] or [records[0]]


def selection_from_record(record: dict[str, Any], entity_mode: str) -> DashboardSelection:
    return DashboardSelection(
        entity_mode=entity_mode,
        selection_id=str(record["selection_id"]),
        label=str(record["entity_label"]),
        season=str(record["season"]),
        season_type=str(record["season_type"]),
        game_id=str(record["game_id"]),
        player_id=int(record["player_id"]),
        player_name=str(record["player_name"]),
        team_tricode=str(record["team_tricode"]),
        opponent_team_tricode=str(record.get("opponent_team_tricode", "")),
        payload=dict(record),
    )


def build_filter_options(datasets: DashboardDatasets) -> dict[str, list[dict[str, str]]]:
    game_df = datasets.game_summaries
    return {
        "player": _options_from_series(game_df.get("player_name", pd.Series(dtype="object"))),
        "team": _options_from_series(game_df.get("team_tricode", pd.Series(dtype="object"))),
        "opponent": _options_from_series(game_df.get("opponent_team_tricode", pd.Series(dtype="object"))),
        "season": _options_from_series(game_df.get("season", pd.Series(dtype="object"))),
        "season_type": _options_from_series(game_df.get("season_type", pd.Series(dtype="object"))),
        "era": _options_from_series(game_df.get("era", pd.Series(dtype="object"))),
        "preset": get_preset_options(),
    }


def get_entity_frame(datasets: DashboardDatasets, entity_mode: str) -> pd.DataFrame:
    normalized = str(entity_mode).strip().lower()
    mapping = {
        "game": datasets.game_summaries,
        "quarter": datasets.quarter_summaries,
        "half": datasets.half_summaries,
        "burst": datasets.burst_summaries,
    }
    return mapping[normalized]


def selection_id_from_row(row: pd.Series | dict[str, Any], entity_mode: str) -> str:
    data = dict(row)
    if entity_mode == "game":
        return f"game:{data['game_id']}:{int(data['player_id'])}"
    if entity_mode == "quarter":
        return f"quarter:{data['game_id']}:{int(data['player_id'])}:q{int(data['quarter_number'])}"
    if entity_mode == "half":
        return f"half:{data['game_id']}:{int(data['player_id'])}:h{int(data['half_index'])}"
    return (
        f"burst:{data['game_id']}:{int(data['player_id'])}:"
        f"{int(data['burst_window_seconds'])}:{float(data['window_start_seconds_in_game']):.1f}"
    )


def entity_label_from_row(row: pd.Series | dict[str, Any], entity_mode: str) -> str:
    data = dict(row)
    if entity_mode == "game":
        return "Full Game"
    if entity_mode == "quarter":
        return str(data["quarter_label"])
    if entity_mode == "half":
        return str(data["half_label"])
    return f"{data['burst_window_label']} burst"


def encode_dashboard_state(filters: DashboardFilters, selected_ids: list[str] | None = None) -> str:
    params: dict[str, str] = {}
    defaults = DashboardFilters()
    for field_name, query_key in QUERY_PARAM_KEYS.items():
        if field_name == "selected_ids":
            continue
        value = _finite_or_none(getattr(filters, field_name))
        default_value = getattr(defaults, field_name)
        if value is None or value == default_value:
            continue
        if isinstance(value, bool):
            params[query_key] = "1" if value else "0"
        else:
            params[query_key] = str(value)
    if selected_ids:
        params[QUERY_PARAM_KEYS["selected_ids"]] = ",".join(selected_ids[:MAX_COMPARISONS])
    if not params:
        return ""
    return "?" + urlencode(params)


def decode_dashboard_state(search: str | None) -> dict[str, Any]:
    if not search:
        return {"filters": DashboardFilters(), "selected_row_ids": []}
    params = parse_qs(search.lstrip("?"), keep_blank_values=False)
    payload = {
        "entity_mode": _first_param(params, "entity_mode"),
        "ranking_metric": _first_param(params, "ranking_metric"),
        "time_mode": _first_param(params, "time_mode"),
        "burst_window": _first_param(params, "burst_window"),
        "analysis_mode": _first_param(params, "analysis_mode"),
        "analysis_window": _first_param(params, "analysis_window"),
        "line_color_mode": _first_param(params, "line_color_mode"),
        "show_shot_markers": _coerce_bool(_first_param(params, "show_shot_markers"), default=True),
        "include_ot": _coerce_bool(_first_param(params, "include_ot"), default=True),
        "competitive_only": _coerce_bool(_first_param(params, "competitive_only"), default=False),
        "min_points": _first_param(params, "min_points"),
        "min_competitive_share": _first_param(params, "min_competitive_share"),
        "min_ts_pct": _first_param(params, "min_ts_pct"),
        "min_efg_pct": _first_param(params, "min_efg_pct"),
        "min_offensive_share": _first_param(params, "min_offensive_share"),
        "player": _first_param(params, "player"),
        "team": _first_param(params, "team"),
        "opponent": _first_param(params, "opponent"),
        "season": _first_param(params, "season"),
        "season_type": _first_param(params, "season_type"),
        "era": _first_param(params, "era"),
        "preset": _first_param(params, "preset"),
    }
    filters = normalize_filters(**payload)
    selected_raw = _first_param(params, "selected_ids")
    selected_ids = [value for value in (selected_raw or "").split(",") if value][:MAX_COMPARISONS]
    return {"filters": filters, "selected_row_ids": selected_ids}


def filter_values_from_filters(filters: DashboardFilters) -> dict[str, Any]:
    return {
        "entity_mode": filters.entity_mode,
        "ranking_metric": filters.ranking_metric,
        "time_mode": filters.time_mode,
        "burst_window": filters.burst_window,
        "analysis_mode": filters.analysis_mode,
        "analysis_window": filters.analysis_window,
        "line_color_mode": filters.line_color_mode,
        "shot_markers": ["markers"] if filters.show_shot_markers else [],
        "include_ot": ["include"] if filters.include_ot else [],
        "competitive_only": ["competitive"] if filters.competitive_only else [],
        "min_points": _finite_or_none(filters.min_points),
        "min_competitive_share": _finite_or_none(filters.min_competitive_share),
        "min_ts_pct": _finite_or_none(filters.min_ts_pct),
        "min_efg_pct": _finite_or_none(filters.min_efg_pct),
        "min_offensive_share": _finite_or_none(filters.min_offensive_share),
        "player": filters.player,
        "team": filters.team,
        "opponent": filters.opponent,
        "season": filters.season,
        "season_type": filters.season_type,
        "era": filters.era,
        "preset": filters.preset,
    }


def _leaderboard_columns(column_specs: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    columns: list[dict[str, str]] = []
    for column_id, label, column_type in column_specs:
        column = {"name": label, "id": _display_id(column_id)}
        if column_type == "markdown":
            column["presentation"] = "markdown"
        columns.append(column)
    return columns


def _leaderboard_column_specs(entity_mode: str, ranking_metric: str) -> list[tuple[str, str, str]]:
    specs = list(LEADERBOARD_BASE_SPECS[entity_mode])
    source_column = _ranking_source_column(entity_mode, ranking_metric)
    if source_column not in {column_id for column_id, _, _ in specs}:
        specs.append(
            (
                source_column,
                _ranking_metric_label(entity_mode, ranking_metric),
                _column_type_for_metric(source_column),
            )
        )
    return specs


def _leaderboard_style_metadata(
    column_specs: list[tuple[str, str, str]],
    highlight_display_id: str | None,
    entity_mode: str,
    *,
    tooltip_data: list[dict[str, dict[str, str]]] | None = None,
    page_count: int | None = None,
    total_rows: int | None = None,
) -> dict[str, Any]:
    numeric_columns = [
        _display_id(column_id)
        for column_id, _, column_type in column_specs
        if column_type != "text" and column_id != "rank"
    ]
    style_cell_conditional = [{"if": {"column_id": column_id}, "textAlign": "right"} for column_id in numeric_columns]
    style_data_conditional: list[dict[str, Any]] = [
        {
            "if": {"state": "selected"},
            "backgroundColor": "#efe5d7",
            "border": "none",
        }
    ]
    for column_id, _, column_type in column_specs:
        if column_type == "markdown":
            style_cell_conditional.append(
                {
                    "if": {"column_id": _display_id(column_id)},
                    "textAlign": "center",
                    "overflow": "visible",
                    "position": "relative",
                }
            )
            style_data_conditional.append(
                {
                    "if": {"column_id": _display_id(column_id)},
                    "paddingTop": "0px",
                    "paddingBottom": "0px",
                    "paddingLeft": "3px",
                    "paddingRight": "3px",
                }
            )
    style_header_conditional: list[dict[str, Any]] = []
    if highlight_display_id:
        style_header_conditional.append(
            {
                "if": {"column_id": highlight_display_id},
                "backgroundColor": "#d8c5a9",
                "color": "#1f1b18",
            }
        )
        style_data_conditional.append(
            {
                "if": {"column_id": highlight_display_id},
                "backgroundColor": LEADERBOARD_HIGHLIGHT_BACKGROUND,
            }
        )
    return {
        "highlight_column_id": highlight_display_id,
        "style_cell_conditional": style_cell_conditional,
        "style_header_conditional": style_header_conditional,
        "style_data_conditional": style_data_conditional,
        "tooltip_header": _leaderboard_tooltip_header(column_specs, entity_mode),
        "tooltip_data": tooltip_data or [],
        "page_count": page_count,
        "total_rows": total_rows,
    }


def _prepare_leaderboard_dataframe(
    summary_df: pd.DataFrame,
    filters: DashboardFilters,
    sort_by: list[dict[str, str]] | None,
) -> tuple[pd.DataFrame, list[tuple[str, str, str]]]:
    ranking_metric = _normalize_ranking_metric_for_mode(filters.entity_mode, filters.ranking_metric)
    column_specs = _leaderboard_column_specs(filters.entity_mode, ranking_metric)
    if summary_df.empty:
        return pd.DataFrame(), column_specs
    working = summary_df.copy()
    working["rank"] = range(1, len(working) + 1)
    working["entity_label"] = working.apply(lambda row: entity_label_from_row(row, filters.entity_mode), axis=1)
    working["selection_id"] = working.apply(lambda row: selection_id_from_row(row, filters.entity_mode), axis=1)
    working["id"] = working["selection_id"]
    working = _sort_leaderboard_rows(working, column_specs, sort_by)
    for column_id, _, column_type in column_specs:
        display_id = _display_id(column_id)
        working[display_id] = _format_display_series(working, column_id, column_type, filters.entity_mode)
    return working, column_specs


def _sort_leaderboard_rows(
    df: pd.DataFrame,
    column_specs: list[tuple[str, str, str]],
    sort_by: list[dict[str, str]] | None,
) -> pd.DataFrame:
    if df.empty or not sort_by:
        return df
    active_sort = sort_by[0]
    display_id = str(active_sort.get("column_id") or "").strip()
    if not display_id:
        return df
    direction = str(active_sort.get("direction") or "asc").strip().lower()
    ascending = direction != "desc"
    source_column = _sortable_source_column(display_id, column_specs)
    if source_column is None or source_column not in df.columns:
        return df
    working = df.copy()
    column_type = _sortable_column_type(display_id, column_specs)
    if source_column == "rank":
        sort_series = pd.to_numeric(working[source_column], errors="coerce")
    elif source_column == "game_date":
        parsed = pd.to_datetime(working[source_column], errors="coerce")
        sort_series = parsed.dt.year
    elif column_type in {"int", "decimal", "minutes_from_seconds", "pct1"}:
        sort_series = pd.to_numeric(working[source_column], errors="coerce")
    else:
        sort_series = working[source_column].fillna("").astype(str)
    working["_sort_value"] = sort_series
    working = working.sort_values(
        by=["_sort_value", "rank"],
        ascending=[ascending, True],
        na_position="last",
        kind="mergesort",
    )
    return working.drop(columns="_sort_value")


def _slice_leaderboard_page(
    df: pd.DataFrame,
    *,
    page_current: int,
    page_size: int | None,
) -> pd.DataFrame:
    if page_size is None or page_size <= 0:
        return df
    current = max(int(page_current), 0)
    start = current * int(page_size)
    end = start + int(page_size)
    if start >= len(df):
        start = max(((len(df) - 1) // int(page_size)) * int(page_size), 0)
        end = start + int(page_size)
    return df.iloc[start:end].copy()


def _page_count(total_rows: int, page_size: int | None) -> int:
    if page_size is None or page_size <= 0 or total_rows <= 0:
        return 1 if total_rows else 0
    return ((int(total_rows) - 1) // int(page_size)) + 1


def _sortable_source_column(
    display_id: str,
    column_specs: list[tuple[str, str, str]],
) -> str | None:
    reverse_map = {_display_id(column_id): column_id for column_id, _, _ in column_specs}
    column_id = reverse_map.get(display_id)
    if column_id is None:
        return None
    if column_id == "team_logo":
        return "team_tricode"
    if column_id == "opponent_team_logo":
        return "opponent_team_tricode"
    return column_id


def _sortable_column_type(
    display_id: str,
    column_specs: list[tuple[str, str, str]],
) -> str:
    for column_id, _, column_type in column_specs:
        if _display_id(column_id) == display_id:
            return column_type
    return "text"


def _format_display_series(df: pd.DataFrame, column_id: str, column_type: str, entity_mode: str) -> pd.Series:
    if column_id == "rank":
        return df["rank"]
    if column_id == "team_logo":
        return _team_logo_markdown_series(df, "team_id", "team_tricode")
    if column_id == "opponent_team_logo":
        return _team_logo_markdown_series(df, "opponent_team_id", "opponent_team_tricode")
    if column_id == "game_date":
        return _format_game_year_series(df.get(column_id, pd.Series(index=df.index, dtype="object")))
    series = df.get(column_id, pd.Series(index=df.index, dtype="object"))
    if column_type == "text":
        formatted = series.fillna("").astype(str)
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    if column_type == "markdown":
        formatted = series.fillna("").astype(str)
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    numeric = pd.to_numeric(series, errors="coerce")
    if column_type == "int":
        formatted = numeric.map(lambda value: "NA" if pd.isna(value) else f"{int(round(float(value)))}")
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    if column_type == "decimal":
        formatted = numeric.map(lambda value: "NA" if pd.isna(value) else f"{float(value):.1f}")
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    if column_type == "minutes_from_seconds":
        formatted = numeric.map(lambda value: "NA" if pd.isna(value) else f"{float(value) / 60.0:.1f}")
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    if column_type == "pct1":
        formatted = numeric.map(lambda value: "NA" if pd.isna(value) else f"{float(value):.1%}")
        return _append_estimation_markers(formatted, df, column_id, entity_mode)
    formatted = series.fillna("").astype(str)
    return _append_estimation_markers(formatted, df, column_id, entity_mode)


def _ranking_source_column(entity_mode: str, ranking_metric: str) -> str:
    point_columns = {
        "game": "final_points",
        "quarter": "quarter_points",
        "half": "half_points",
        "burst": "points_in_window",
    }
    aliases = {
        "total_points": point_columns[entity_mode],
        "points_per_minute": "window_points_per_minute" if entity_mode == "burst" else "points_per_minute",
        "avg_abs_margin_during_scoring_events": "avg_abs_score_diff_in_window"
        if entity_mode == "burst"
        else "avg_abs_margin_during_scoring_events",
    }
    return aliases.get(ranking_metric, ranking_metric)


def _ranking_metric_label(entity_mode: str, ranking_metric: str) -> str:
    options = dict(RANKING_OPTIONS[entity_mode])
    return options.get(ranking_metric, ranking_metric.replace("_", " ").title())


def _column_type_for_metric(column_id: str) -> str:
    if column_id in {
        "player_name",
        "team_tricode",
        "opponent_team_tricode",
        "game_date",
        "entity_label",
    }:
        return "text"
    if column_id in {"team_logo", "opponent_team_logo"}:
        return "markdown"
    if column_id.endswith("_share") or column_id in {"ts_pct", "efg_pct", "competitive_scoring_share"}:
        return "pct1"
    if "points" in column_id or column_id.endswith("_margin") or column_id.endswith("_window"):
        if column_id in {
            "points_per_minute",
            "window_points_per_minute",
            "avg_abs_margin_during_scoring_events",
            "avg_abs_score_diff_in_window",
            "peak_projected_48",
            "trailing_scoring_rate",
        }:
            return "decimal"
        return "int"
    if column_id in {
        "offensive_share",
        "share_points_from_3s",
        "share_points_from_fts",
    }:
        return "pct1"
    return "decimal"


def _display_id(column_id: str) -> str:
    if column_id in {"rank", "player_name", "team_tricode", "opponent_team_tricode", "entity_label"}:
        return column_id
    return f"{column_id}_display"


def _team_logo_markdown_series(
    df: pd.DataFrame,
    team_id_column: str,
    tricode_column: str,
    game_date_column: str = "game_date",
) -> pd.Series:
    game_dates = df.get(game_date_column, pd.Series(index=df.index))
    return pd.Series(
        [
            _team_logo_markdown(team_id, tricode, game_date)
            for team_id, tricode, game_date in zip(
                df.get(team_id_column, pd.Series(index=df.index)),
                df.get(tricode_column, pd.Series(index=df.index)),
                game_dates,
            )
        ],
        index=df.index,
        dtype="object",
    )


def _team_logo_markdown(team_id: Any, tricode: Any, game_date: Any = None) -> str:
    tri = "" if tricode in {None, "", "None"} else str(tricode).strip()
    src = resolve_team_logo_asset_src(team_id, game_date)
    if src is None:
        return tri
    title = tri or str(team_id)
    return (
        f'<div class="table-team-logo-wrap">'
        f'<img src="{src}" alt="{title}" title="{title}" class="table-team-logo" />'
        f"</div>"
    )


def _highlight_display_id(entity_mode: str, ranking_metric: str) -> str:
    return _display_id(_ranking_source_column(entity_mode, ranking_metric))


def _leaderboard_tooltip_header(
    column_specs: list[tuple[str, str, str]],
    entity_mode: str,
) -> dict[str, dict[str, str]]:
    return {
        _display_id(column_id): {
            "type": "markdown",
            "value": _column_tooltip(column_id, entity_mode),
        }
        for column_id, _, _ in column_specs
    }


def _leaderboard_tooltip_data(
    df: pd.DataFrame,
    column_specs: list[tuple[str, str, str]],
    entity_mode: str,
) -> list[dict[str, dict[str, str]]]:
    if df.empty:
        return []
    supported_display_ids = {_display_id(column_id) for column_id, _, _ in column_specs}
    exact_dates = _exact_game_date_series(df.get("game_date", pd.Series(index=df.index, dtype="object")))
    tooltips: list[dict[str, dict[str, str]]] = []
    for index in df.index:
        row_tooltips: dict[str, dict[str, str]] = {}
        if "game_date_display" in supported_display_ids:
            exact_date = exact_dates.loc[index]
            if exact_date:
                row_tooltips["game_date_display"] = {
                    "value": f"Exact date: {exact_date}",
                    "type": "text",
                }
        if bool(df.loc[index].get("is_manual_approximation")):
            estimation_note = _manual_estimation_tooltip(df.loc[index], entity_mode)
            for column_id, _, _ in column_specs:
                display_id = _display_id(column_id)
                if display_id not in supported_display_ids:
                    continue
                if _is_estimated_metric_column(column_id, entity_mode, df.loc[index]):
                    row_tooltips[display_id] = {
                        "value": estimation_note,
                        "type": "text",
                    }
            row_tooltips.setdefault(
                "player_name",
                {
                    "value": _manual_estimation_tooltip(df.loc[index], entity_mode, player_cell=True),
                    "type": "text",
                },
            )
        tooltips.append(row_tooltips)
    return tooltips


def _column_tooltip(column_id: str, entity_mode: str) -> str:
    entity_label = {
        "game": "full game",
        "quarter": "quarter",
        "half": "half",
        "burst": "burst window",
    }.get(entity_mode, "performance")
    definitions = {
        "rank": "**Rank**\n\nCurrent leaderboard position after the active filters and ranking metric are applied.\n\n**Why it matters:** If you temporarily sort another column, rank still preserves the original context from the current filters and ranking metric.",
        "final_points": "**Total Points**\n\n**Formula:** `Σ point_value`\n\n**Why it matters:** Raw scoring volume is still the baseline comparison for full games.",
        "quarter_points": "**Quarter Points**\n\n**Formula:** `Σ point_value` within the quarter\n\n**Why it matters:** This is the core stat for best-quarter comparisons.",
        "half_points": "**Half Points**\n\n**Formula:** `Σ point_value` within the half\n\n**Why it matters:** This identifies dominant first halves and second halves.",
        "points_in_window": "**Burst Points**\n\n**Formula:** `Σ point_value` inside the selected fixed-length burst window\n\n**Why it matters:** This is the core short-heater measure for burst mode.",
        "player_name": "**Player**\n\nThe scorer tied to this row.\n\n**Why it matters:** The same game can contribute multiple player or segment rows.",
        "team_logo": "**Team**\n\nPlayer's team logo.\n\n**Why it matters:** It keeps matchup context visible without spending width on text abbreviations.",
        "opponent_team_logo": "**Opponent**\n\nOpponent team logo.\n\n**Why it matters:** It keeps matchup context visible without spending width on text abbreviations.",
        "game_date": "**Year**\n\nLeaderboard display uses the game year for faster era scanning.\n\n**Exact date:** hover the year cell.\n\n**Why it matters:** It keeps the table compact while preserving exact identification on hover.",
        "minutes_played": "**Minutes**\n\nOfficial minutes played from the box score.\n\n**Why it matters:** Rate stats depend on opportunity, not just raw total points.",
        "quarter_duration_minutes": "**Quarter Minutes**\n\n**Formula:** `quarter_duration_seconds / 60`\n\n**Why it matters:** It anchors pace comparisons inside a quarter.",
        "half_duration_minutes": "**Half Minutes**\n\n**Formula:** `half_duration_seconds / 60`\n\n**Why it matters:** It anchors pace comparisons across halves.",
        "burst_window_seconds": "**Burst Minutes**\n\n**Formula:** `burst_window_seconds / 60`\n\n**Why it matters:** Burst intensity depends on the chosen window length.",
        "entity_label": "**Segment**\n\nLabel for the selected quarter, half, or burst interval.\n\n**Why it matters:** The same player-game can produce multiple ranked segments.",
        "points_per_minute": f"**Points / Minute**\n\n**Formula:** `points / minutes`\n\n**Why it matters:** It pace-adjusts the selected {entity_label} so unequal-length performances can be compared fairly.",
        "window_points_per_minute": "**Window Points / Minute**\n\n**Formula:** `points_in_window / (burst_window_seconds / 60)`\n\n**Why it matters:** It compares burst explosiveness independent of raw window total.",
        "ts_pct": "**True Shooting Percentage**\n\n**Formula:** `PTS / (2 × (FGA + 0.44 × FTA))`\n\n**Why it matters:** This is the strongest all-in scoring-efficiency metric in the table.",
        "efg_pct": "**Effective Field Goal Percentage**\n\n**Formula:** `(FGM + 0.5 × 3PM) / FGA`\n\n**Why it matters:** It isolates shot-making efficiency while giving extra weight to 3s.",
        "offensive_share": "**Offensive Share**\n\n**Formula:** `player_points / team_points`\n\n**Why it matters:** It measures how much of the team offense came from this scorer.",
        "peak_projected_48": "**Peak Projected 48**\n\n**Formula:** `cumulative_points / minutes_elapsed × 48`\n\nComputed after the first minute.\n\n**Why it matters:** It tracks when a game was on record-level pace.",
        "competitive_scoring_share": "**Competitive Share**\n\n**Formula:** `competitive_points / total_points`\n\nCompetitive means the score margin was within 10 points.\n\n**Why it matters:** It separates close-game production from blowout accumulation.",
        "avg_abs_margin_during_scoring_events": "**Average Absolute Margin**\n\n**Formula:** `mean(|score_diff|)` at the player's scoring events\n\n**Why it matters:** Lower values mean the scoring happened in a tighter game.",
        "avg_abs_score_diff_in_window": "**Average Absolute Margin**\n\n**Formula:** `mean(|score_diff|)` inside the burst window\n\n**Why it matters:** Lower values mean the burst happened in a tighter game.",
        "share_points_from_2s": "**2PT Share**\n\n**Formula:** `points_from_2s / total_points`\n\n**Why it matters:** It reveals how much of the scoring came from 2-point makes.",
        "share_points_from_3s": "**3PT Share**\n\n**Formula:** `points_from_3s / total_points`\n\n**Why it matters:** It reveals how much of the scoring came from 3-pointers.",
        "share_points_from_fts": "**FT Share**\n\n**Formula:** `points_from_fts / total_points`\n\n**Why it matters:** It reveals how much of the scoring came from free throws.",
        "best_60_sec_points": "**Best 60 Seconds**\n\nMaximum points in any 60-second stretch.\n\n**Why it matters:** It highlights ultra-short heaters.",
        "best_2_min_points": "**Best 2 Minutes**\n\nMaximum points in any 2-minute stretch.\n\n**Why it matters:** It captures short-burst dominance.",
        "best_3_min_points": "**Best 3 Minutes**\n\nMaximum points in any 3-minute stretch.\n\n**Why it matters:** It is the most useful default burst comparison in the app.",
        "best_5_min_points": "**Best 5 Minutes**\n\nMaximum points in any 5-minute stretch.\n\n**Why it matters:** It measures sustained heaters beyond a quick flurry.",
        "best_10_min_points": "**Best 10 Minutes**\n\nMaximum points in any 10-minute stretch.\n\n**Why it matters:** It captures extended scoring domination.",
        "best_quarter_points": "**Best Quarter**\n\nHighest-scoring quarter in the game.\n\n**Why it matters:** Many historic games are remembered for one overwhelming quarter.",
        "best_half_points": "**Best Half**\n\nHighest-scoring half in the game.\n\n**Why it matters:** It surfaces games built on half-to-half dominance.",
        "competitive_points": "**Competitive Points**\n\nPoints scored while the game was within 10 points.\n\n**Why it matters:** Raw points alone can hide whether the scoring happened in a live game.",
        "trailing_points": "**Trailing Points**\n\nPoints scored while the player's team was behind.\n\n**Why it matters:** Comeback scoring often feels more meaningful than front-running accumulation.",
        "trailing_scoring_rate": "**Trailing Rate**\n\n**Formula:** `trailing_points / minutes_played`\n\n**Why it matters:** It measures pressure scoring rather than overall volume.",
    }
    return definitions.get(column_id, f"{column_id.replace('_', ' ').title()} for the selected performance.")


def _append_estimation_markers(
    formatted: pd.Series,
    df: pd.DataFrame,
    column_id: str,
    entity_mode: str,
) -> pd.Series:
    if "is_manual_approximation" not in df.columns:
        return formatted
    mask = pd.Series(
        [_is_estimated_metric_column(column_id, entity_mode, df.loc[index]) for index in df.index],
        index=df.index,
        dtype=bool,
    )
    return formatted.where(~mask, formatted.astype(str) + "*")


def _is_estimated_metric_column(column_id: str, entity_mode: str, row: pd.Series | dict[str, Any]) -> bool:
    data = row if isinstance(row, dict) else row.to_dict()
    if not bool(data.get("is_manual_approximation")):
        return False
    if column_id in {"share_points_from_3s", "share_points_from_fts", "share_points_from_2s"}:
        return bool(data.get("estimated_period_shot_mix"))
    if column_id == "points_per_minute" and entity_mode == "burst":
        return True
    return column_id in ESTIMATED_LEADERBOARD_COLUMNS.get(entity_mode, set())


def _manual_estimation_tooltip(
    row: pd.Series | dict[str, Any],
    entity_mode: str,
    *,
    player_cell: bool = False,
) -> str:
    data = row if isinstance(row, dict) else row.to_dict()
    source_note = str(data.get("manual_source_note") or "").strip()
    intro = "Legacy manual approximation."
    entity_hint = {
        "game": "Timing, burst, and score-context metrics are estimated from published splits.",
        "quarter": "Score-context metrics are estimated from published splits.",
        "half": "Score-context metrics are estimated from published splits.",
        "burst": "Burst timing, points, and context metrics are estimated from evenly spaced scoring events.",
    }.get(entity_mode, "Some metrics are estimated from published splits.")
    if bool(data.get("estimated_period_shot_mix")):
        entity_hint += " Segment shot-mix fields are also estimated from game totals."
    if source_note:
        return f"{intro} {entity_hint}\n\nSource note: {source_note}"
    return f"{intro} {entity_hint}"


def _format_game_year_series(series: pd.Series) -> pd.Series:
    formatted = series.fillna("").astype(str)
    parsed = pd.to_datetime(series, errors="coerce")
    valid = parsed.notna()
    if valid.any():
        formatted.loc[valid] = parsed.loc[valid].dt.year.astype(str)
    return formatted


def _exact_game_date_series(series: pd.Series) -> pd.Series:
    formatted = series.fillna("").astype(str)
    parsed = pd.to_datetime(series, errors="coerce")
    valid = parsed.notna()
    if valid.any():
        formatted.loc[valid] = parsed.loc[valid].dt.strftime("%Y-%m-%d")
    return formatted


def _options_from_series(series: pd.Series) -> list[dict[str, str]]:
    values = sorted({str(value) for value in series.dropna().tolist() if str(value).strip()})
    return [{"label": value, "value": value} for value in values]


def _filter_cache_key(datasets: DashboardDatasets, filters: DashboardFilters) -> tuple[Any, ...]:
    ranking_metric = _normalize_ranking_metric_for_mode(filters.entity_mode, filters.ranking_metric)
    return (
        getattr(datasets, "summary_signature", ()),
        filters.entity_mode,
        ranking_metric,
        filters.time_mode,
        filters.burst_window,
        filters.analysis_mode,
        filters.analysis_window,
        filters.line_color_mode,
        filters.show_shot_markers,
        filters.include_ot,
        filters.competitive_only,
        filters.min_points,
        filters.min_competitive_share,
        filters.min_ts_pct,
        filters.min_efg_pct,
        filters.min_offensive_share,
        filters.player,
        filters.team,
        filters.opponent,
        filters.season,
        filters.season_type,
        filters.era,
        filters.preset,
    )


def _remember_filter_cache(cache_key: tuple[Any, ...], frame: pd.DataFrame) -> None:
    _FILTER_CACHE[cache_key] = frame.copy()
    _FILTER_CACHE.move_to_end(cache_key)
    while len(_FILTER_CACHE) > FILTER_CACHE_SIZE:
        _FILTER_CACHE.popitem(last=False)


def _first_param(params: dict[str, list[str]], field_name: str) -> str | None:
    values = params.get(QUERY_PARAM_KEYS[field_name], [])
    return values[0] if values else None


def _coerce_int(value: Any) -> int | None:
    if value in {None, "", "None"}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return int(numeric)


def _coerce_float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value in {None, "", "None"}:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return default


def _normalize_window(value: Any, *, default: int) -> int:
    numeric = _coerce_int(value)
    if numeric is None:
        return default
    return numeric if numeric in VALID_WINDOW_SECONDS else default


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

