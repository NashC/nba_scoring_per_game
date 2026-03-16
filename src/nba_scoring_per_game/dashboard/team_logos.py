from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


_TEAM_LOGO_DIR = Path(__file__).with_name("assets") / "team_logos"


@dataclass(frozen=True, slots=True)
class HistoricalTeamLogoRule:
    team_id: int
    asset_filename: str
    start_date: date | None = None
    end_date: date | None = None


_HISTORICAL_TEAM_LOGO_RULES: tuple[HistoricalTeamLogoRule, ...] = (
    HistoricalTeamLogoRule(team_id=990001, asset_filename="990001.svg"),
    HistoricalTeamLogoRule(team_id=990002, asset_filename="990002.svg"),
    HistoricalTeamLogoRule(
        team_id=1610612747,
        asset_filename="1610612747_1960.svg",
        end_date=date(1965, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612752,
        asset_filename="1610612752_1963.svg",
        end_date=date(1963, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612752,
        asset_filename="1610612752_1977.svg",
        start_date=date(1963, 7, 1),
        end_date=date(1992, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612743,
        asset_filename="1610612743_1978.svg",
        start_date=date(1976, 7, 1),
        end_date=date(1981, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612765,
        asset_filename="1610612765_1978.svg",
        start_date=date(1975, 7, 1),
        end_date=date(1978, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612739,
        asset_filename="1610612739_1990.svg",
        start_date=date(1983, 7, 1),
        end_date=date(1994, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612759,
        asset_filename="1610612759_1994.svg",
        start_date=date(1989, 7, 1),
        end_date=date(2002, 6, 30),
    ),
    HistoricalTeamLogoRule(
        team_id=1610612746,
        asset_filename="1610612746_1994.svg",
        start_date=date(1984, 7, 1),
        end_date=date(2010, 6, 30),
    ),
)


def resolve_team_logo_asset_src(team_id: Any, game_date: Any = None) -> str | None:
    asset_filename = resolve_team_logo_asset_filename(team_id, game_date)
    if asset_filename is None:
        return None
    return f"/assets/team_logos/{asset_filename}"


def resolve_team_logo_asset_path(team_id: Any, game_date: Any = None) -> Path | None:
    asset_filename = resolve_team_logo_asset_filename(team_id, game_date)
    if asset_filename is None:
        return None
    return _TEAM_LOGO_DIR / asset_filename


def resolve_team_logo_asset_filename(team_id: Any, game_date: Any = None) -> str | None:
    numeric_team_id = _coerce_team_id(team_id)
    if numeric_team_id is None:
        return None

    normalized_game_date = _coerce_game_date(game_date)
    for rule in _HISTORICAL_TEAM_LOGO_RULES:
        if rule.team_id != numeric_team_id or not _historical_rule_matches(rule, normalized_game_date):
            continue
        if (_TEAM_LOGO_DIR / rule.asset_filename).exists():
            return rule.asset_filename

    default_filename = f"{numeric_team_id}.svg"
    if (_TEAM_LOGO_DIR / default_filename).exists():
        return default_filename
    return None


def _historical_rule_matches(rule: HistoricalTeamLogoRule, game_date: date | None) -> bool:
    if game_date is None:
        return rule.start_date is None and rule.end_date is None
    if rule.start_date is not None and game_date < rule.start_date:
        return False
    if rule.end_date is not None and game_date > rule.end_date:
        return False
    return True


def _coerce_team_id(team_id: Any) -> int | None:
    try:
        return int(team_id)
    except (TypeError, ValueError):
        return None


def _coerce_game_date(game_date: Any) -> date | None:
    if game_date in {None, "", "None"}:
        return None
    if isinstance(game_date, datetime):
        return game_date.date()
    if isinstance(game_date, date):
        return game_date
    if hasattr(game_date, "to_pydatetime"):
        try:
            return game_date.to_pydatetime().date()
        except (AttributeError, TypeError, ValueError):
            return None
    if not isinstance(game_date, str):
        return None
    cleaned = game_date.strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned[:10]).date()
    except ValueError:
        return None
