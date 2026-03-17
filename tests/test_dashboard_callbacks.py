from __future__ import annotations

import unittest

from dash import no_update
import pandas as pd

from nba_scoring_per_game.dashboard.app import (
    _effective_selected_ids,
    _hydrated_selection_values,
    _metric_visibility,
    _prepare_leaderboard_export_frame,
    _preset_filter_values,
    _quick_view_preset,
    _search_has_selected_param,
    _selected_ids_for_current_page,
    _selected_rows_for_page,
    _selection_ids_from_tray,
    _share_link_search,
    _updated_url_search,
)
from nba_scoring_per_game.dashboard.state import DashboardFilters, apply_dashboard_preset, encode_dashboard_state


class DashboardCallbackTests(unittest.TestCase):
    def test_quick_view_preset_uses_triggered_button_payload(self) -> None:
        self.assertEqual(
            _quick_view_preset({"type": "quick-view-button", "preset": "best_3_min_bursts"}, [0, 1, 0]),
            "best_3_min_bursts",
        )
        self.assertIs(_quick_view_preset("preset-filter"), no_update)
        self.assertIs(_quick_view_preset({"type": "quick-view-button", "preset": "top_scoring_games"}, [0, 0, 0]), no_update)

    def test_preset_filter_values_noops_for_empty_or_matching_preset(self) -> None:
        noop_values = _preset_filter_values(None, None)
        self.assertEqual(len(noop_values), 19)
        self.assertTrue(all(value is no_update for value in noop_values))

        same_preset_search = encode_dashboard_state(apply_dashboard_preset("best_3_min_bursts"), [])
        same_values = _preset_filter_values("best_3_min_bursts", same_preset_search)
        self.assertTrue(all(value is no_update for value in same_values))

    def test_preset_filter_values_returns_expected_outputs_for_new_preset(self) -> None:
        values = _preset_filter_values("competitive_60_plus_games", encode_dashboard_state(DashboardFilters(), []))

        self.assertEqual(values[0], "game")
        self.assertEqual(values[1], "total_points")
        self.assertEqual(values[6], [])
        self.assertEqual(values[7], [])
        self.assertEqual(values[8], 60)
        self.assertEqual(values[9], 0.75)

    def test_share_link_search_includes_filters_and_selected_rows(self) -> None:
        filters = DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180)
        search = _share_link_search(filters, ["burst:g2:2"])

        self.assertEqual(search, encode_dashboard_state(filters, ["burst:g2:2"]))

    def test_selected_rows_for_page_maps_selected_ids_to_current_page_indices(self) -> None:
        rows = [
            {"selection_id": "game:g1:1"},
            {"selection_id": "game:g2:2"},
            {"selection_id": "game:g3:3"},
        ]

        self.assertEqual(_selected_rows_for_page(rows, ["game:g1:1", "game:g3:3"]), [0, 2])
        self.assertEqual(_selected_rows_for_page(rows, ["game:missing"]), [])
        self.assertEqual(_selected_rows_for_page([], ["game:g1:1"]), [])

    def test_search_has_selected_param_only_when_query_contains_selected_key(self) -> None:
        self.assertFalse(_search_has_selected_param(None))
        self.assertFalse(_search_has_selected_param("?mode=game&rank=total_points"))
        self.assertTrue(_search_has_selected_param("?mode=game&selected=game:g1:1"))

    def test_hydrated_selection_values_only_updates_table_state_for_explicit_selected_query(self) -> None:
        rows = [
            {"selection_id": "game:g1:1"},
            {"selection_id": "game:g2:2"},
            {"selection_id": "game:g3:3"},
        ]

        self.assertEqual(
            _hydrated_selection_values("?mode=game&selected=game:g1:1,game:g3:3", rows),
            (["game:g1:1", "game:g3:3"], ["game:g1:1", "game:g3:3"], [0, 2]),
        )
        self.assertEqual(
            _hydrated_selection_values("?mode=game&rank=total_points", rows),
            (no_update, no_update, no_update),
        )

    def test_selected_ids_for_current_page_merges_current_page_rows_with_existing_cross_page_selection(self) -> None:
        rows = [
            {"selection_id": "game:g1:1"},
            {"selection_id": "game:g2:2"},
            {"selection_id": "game:g3:3"},
        ]

        self.assertEqual(
            _selected_ids_for_current_page(rows, [0, 2], ["game:other:9", "game:g1:1"]),
            ["game:other:9", "game:g1:1", "game:g3:3"],
        )
        self.assertEqual(_selected_ids_for_current_page(rows, [], ["game:g1:1"]), [])
        self.assertEqual(_selected_ids_for_current_page([], [0], ["game:g1:1"]), [])

    def test_metric_visibility_applies_mode_specific_toggles(self) -> None:
        burst_values = _metric_visibility("burst", "bad_metric", "none", "margin")
        self.assertEqual(burst_values[1], "points_in_window")
        self.assertEqual(burst_values[2], {})
        self.assertEqual(burst_values[7], {"display": "flex"})
        self.assertEqual(burst_values[8], {"display": "none"})
        self.assertEqual(burst_values[9], {"display": "block"})

        game_values = _metric_visibility("game", "ts_pct", "rolling_points", "player")
        self.assertEqual(game_values[1], "ts_pct")
        self.assertEqual(game_values[3], {})
        self.assertEqual(game_values[4], {})
        self.assertEqual(game_values[8], {})
        self.assertEqual(game_values[9], {"display": "none"})

    def test_selection_ids_from_tray_covers_all_trigger_branches(self) -> None:
        current_ids = ["game:g1:1", "game:g2:2", "game:g3:3"]

        self.assertEqual(_selection_ids_from_tray("clear-comparisons", current_ids), [])
        self.assertEqual(_selection_ids_from_tray("remove-last-comparison", current_ids), current_ids[:-1])
        self.assertEqual(
            _selection_ids_from_tray({"type": "comparison-remove", "selection_id": "game:g2:2"}, current_ids),
            ["game:g1:1", "game:g3:3"],
        )
        self.assertIs(_selection_ids_from_tray("leaderboard-table", current_ids), no_update)

    def test_effective_selected_ids_prioritizes_url_trigger(self) -> None:
        self.assertEqual(
            _effective_selected_ids("url-selected-ids", None, ["game:g1:1"], ["game:g2:2"]),
            ["game:g1:1"],
        )
        self.assertEqual(_effective_selected_ids("leaderboard-table", None, ["game:g1:1"], ["game:g2:2"]), ["game:g2:2"])

    def test_effective_selected_ids_honors_url_selection_when_url_store_is_among_triggered_inputs(self) -> None:
        self.assertEqual(
            _effective_selected_ids(
                "entity-mode",
                {"url-selected-ids.data": "url-selected-ids.data", "entity-mode.value": "entity-mode.value"},
                ["game:g1:1", "game:g2:2"],
                ["game:g3:3"],
            ),
            ["game:g1:1", "game:g2:2"],
        )

    def test_updated_url_search_returns_no_update_when_search_is_unchanged(self) -> None:
        filters = DashboardFilters(entity_mode="game", ranking_metric="ts_pct")
        search = encode_dashboard_state(filters, ["game:g1:1"])

        self.assertIs(_updated_url_search(filters, search), no_update)
        changed = _updated_url_search(DashboardFilters(entity_mode="quarter", ranking_metric="quarter_points"), search)
        self.assertEqual(changed, "?mode=quarter&rank=quarter_points")

    def test_prepare_leaderboard_export_frame_handles_empty_and_renames_columns(self) -> None:
        self.assertIsNone(_prepare_leaderboard_export_frame([], [{"id": "player_name", "name": "Player"}]))

        frame = _prepare_leaderboard_export_frame(
            [{"player_name": "Scorer", "final_points": 70, "ignored": "x"}],
            [
                {"id": "player_name", "name": "Player"},
                {"id": "final_points", "name": "Pts"},
            ],
        )

        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(frame.columns.tolist(), ["Player", "Pts"])
        self.assertEqual(frame.iloc[0].to_dict(), {"Player": "Scorer", "Pts": 70})


if __name__ == "__main__":
    unittest.main()
