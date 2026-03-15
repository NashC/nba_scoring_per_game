from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode

import pandas as pd

from ..pipeline import query_player_games
from .loader import DashboardDatasets

MAX_COMPARISONS = 4
DEFAULT_ENTITY_MODE = "game"
DEFAULT_ANALYSIS_MODE = "none"
DEFAULT_ANALYSIS_WINDOW = 180
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
        ("peak_projected_48", "Peak Projected 48"),
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
    ranking_metric = str(
        kwargs.get("ranking_metric") or DEFAULT_RANKING_METRIC.get(entity_mode, DEFAULT_RANKING_METRIC["game"])
    ).strip()
    valid_metrics = {value for value, _ in RANKING_OPTIONS.get(entity_mode, RANKING_OPTIONS[DEFAULT_ENTITY_MODE])}
    if ranking_metric not in valid_metrics:
        ranking_metric = DEFAULT_RANKING_METRIC.get(entity_mode, DEFAULT_RANKING_METRIC[DEFAULT_ENTITY_MODE])
    analysis_mode = str(kwargs.get("analysis_mode") or DEFAULT_ANALYSIS_MODE).strip().lower()
    return DashboardFilters(
        entity_mode=entity_mode,
        ranking_metric=ranking_metric,
        time_mode=str(kwargs.get("time_mode") or "raw").strip().lower(),
        burst_window=int(kwargs.get("burst_window") or 180),
        analysis_mode=analysis_mode,
        analysis_window=int(kwargs.get("analysis_window") or DEFAULT_ANALYSIS_WINDOW),
        line_color_mode=str(kwargs.get("line_color_mode") or "player").strip().lower(),
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


def get_preset_options() -> list[dict[str, str]]:
    return [{"label": label, "value": value} for value, label in PRESET_OPTIONS]


def default_ranking_metric(entity_mode: str) -> str:
    return DEFAULT_RANKING_METRIC[str(entity_mode).strip().lower()]


def filter_summary_frame(datasets: DashboardDatasets, filters: DashboardFilters) -> pd.DataFrame:
    frame = get_entity_frame(datasets, filters.entity_mode).copy()
    if frame.empty:
        return frame

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
        ranking_metric=filters.ranking_metric,
        sort_by=filters.ranking_metric,
        ascending=False,
    )
    return filtered.reset_index(drop=True)


def build_leaderboard_table(
    summary_df: pd.DataFrame,
    filters: DashboardFilters,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if summary_df.empty:
        return [], _leaderboard_columns()

    point_column = {
        "game": "final_points",
        "quarter": "quarter_points",
        "half": "half_points",
        "burst": "points_in_window",
    }[filters.entity_mode]
    rate_column = "window_points_per_minute" if filters.entity_mode == "burst" else "points_per_minute"
    working = summary_df.head(limit).copy()
    working["rank"] = range(1, len(working) + 1)
    working["entity_label"] = working.apply(lambda row: entity_label_from_row(row, filters.entity_mode), axis=1)
    working["selection_id"] = working.apply(lambda row: selection_id_from_row(row, filters.entity_mode), axis=1)
    working["id"] = working["selection_id"]
    working["primary_points"] = pd.to_numeric(working[point_column], errors="coerce")
    working["rate_value"] = pd.to_numeric(working.get(rate_column), errors="coerce")
    working["competitive_share_value"] = pd.to_numeric(working.get("competitive_scoring_share"), errors="coerce")
    working["date_label"] = working["game_date"].astype(str)
    working["era_label"] = working.get("era", pd.Series(dtype="object")).astype(str) if "era" in working.columns else ""
    return working.to_dict(orient="records"), _leaderboard_columns()


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
        value = getattr(filters, field_name)
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
        "min_points": filters.min_points,
        "min_competitive_share": filters.min_competitive_share,
        "min_ts_pct": filters.min_ts_pct,
        "min_efg_pct": filters.min_efg_pct,
        "min_offensive_share": filters.min_offensive_share,
        "player": filters.player,
        "team": filters.team,
        "opponent": filters.opponent,
        "season": filters.season,
        "season_type": filters.season_type,
        "era": filters.era,
        "preset": filters.preset,
    }


def _leaderboard_columns() -> list[dict[str, str]]:
    return [
        {"name": "#", "id": "rank"},
        {"name": "Player", "id": "player_name"},
        {"name": "Team", "id": "team_tricode"},
        {"name": "Opp", "id": "opponent_team_tricode"},
        {"name": "Date", "id": "date_label"},
        {"name": "Era", "id": "era_label"},
        {"name": "Segment", "id": "entity_label"},
        {"name": "Points", "id": "primary_points"},
        {"name": "Rate", "id": "rate_value"},
        {"name": "Comp Share", "id": "competitive_share_value"},
    ]


def _options_from_series(series: pd.Series) -> list[dict[str, str]]:
    values = sorted({str(value) for value in series.dropna().tolist() if str(value).strip()})
    return [{"label": value, "value": value} for value in values]


def _first_param(params: dict[str, list[str]], field_name: str) -> str | None:
    values = params.get(QUERY_PARAM_KEYS[field_name], [])
    return values[0] if values else None


def _coerce_int(value: Any) -> int | None:
    if value in {None, "", "None"}:
        return None
    return int(float(value))


def _coerce_float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    return float(value)


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value in {None, "", "None"}:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return default


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
