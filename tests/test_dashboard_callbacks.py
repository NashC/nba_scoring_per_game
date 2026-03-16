from __future__ import annotations

import unittest

from dash import no_update
import pandas as pd

from nba_scoring_per_game.dashboard.app import (
    _effective_selected_ids,
    _metric_visibility,
    _prepare_leaderboard_export_frame,
    _preset_filter_values,
    _quick_view_preset,
    _saved_bundle_action,
    _saved_bundle_options,
    _saved_bundle_search,
    _selection_ids_from_tray,
    _updated_url_search,
)
from nba_scoring_per_game.dashboard.state import DashboardFilters, apply_dashboard_preset, encode_dashboard_state, serialize_saved_bundle


def _bundle_payload(name: str, filters: DashboardFilters, selected_ids: list[str] | None) -> dict[str, str]:
    bundle = serialize_saved_bundle(name, filters, selected_ids)
    return {"id": bundle.id, "name": bundle.name, "search": bundle.search, "saved_at": bundle.saved_at}


class DashboardCallbackTests(unittest.TestCase):
    def test_quick_view_preset_uses_triggered_button_payload(self) -> None:
        self.assertEqual(_quick_view_preset({"type": "quick-view-button", "preset": "best_3_min_bursts"}), "best_3_min_bursts")
        self.assertIs(_quick_view_preset("preset-filter"), no_update)

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

    def test_saved_bundle_options_preserve_valid_selection(self) -> None:
        filters = DashboardFilters(entity_mode="game", ranking_metric="ts_pct")
        bundle = _bundle_payload("TS Leaders", filters, ["game:g1:1"])

        options, value = _saved_bundle_options([bundle], bundle["id"])

        self.assertEqual(options, [{"label": "TS Leaders", "value": bundle["id"]}])
        self.assertEqual(value, bundle["id"])

    def test_saved_bundle_action_save_requires_selection_and_name(self) -> None:
        filters = DashboardFilters()
        payload, message, name_value = _saved_bundle_action(
            triggered_id="save-bundle",
            saved_bundles=[],
            bundle_name="Core Set",
            selected_bundle_id=None,
            filters=filters,
            selected_row_ids=[],
        )
        self.assertIs(payload, no_update)
        self.assertEqual(message, "Select at least one comparison before saving a bundle.")
        self.assertIs(name_value, no_update)

        payload, message, name_value = _saved_bundle_action(
            triggered_id="save-bundle",
            saved_bundles=[],
            bundle_name="   ",
            selected_bundle_id=None,
            filters=filters,
            selected_row_ids=["game:g1:1"],
        )
        self.assertIs(payload, no_update)
        self.assertEqual(message, "Enter a bundle name before saving.")
        self.assertIs(name_value, no_update)

    def test_saved_bundle_action_save_replaces_same_name(self) -> None:
        existing = _bundle_payload("Core Set", DashboardFilters(entity_mode="game"), ["game:g1:1"])

        payload, message, name_value = _saved_bundle_action(
            triggered_id="save-bundle",
            saved_bundles=[existing],
            bundle_name="Core Set",
            selected_bundle_id=None,
            filters=DashboardFilters(entity_mode="burst", ranking_metric="points_in_window", burst_window=180),
            selected_row_ids=["burst:g2:2"],
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Core Set")
        self.assertIn("selected=burst%3Ag2%3A2", payload[0]["search"])
        self.assertEqual(message, 'Saved bundle "Core Set".')
        self.assertEqual(name_value, "")

    def test_saved_bundle_action_delete_handles_missing_and_success(self) -> None:
        existing = _bundle_payload("Core Set", DashboardFilters(entity_mode="game"), ["game:g1:1"])

        payload, message, name_value = _saved_bundle_action(
            triggered_id="delete-bundle",
            saved_bundles=[existing],
            bundle_name=None,
            selected_bundle_id=None,
            filters=None,
            selected_row_ids=None,
        )
        self.assertIs(payload, no_update)
        self.assertEqual(message, "Choose a saved bundle to delete.")
        self.assertIs(name_value, no_update)

        payload, message, name_value = _saved_bundle_action(
            triggered_id="delete-bundle",
            saved_bundles=[existing],
            bundle_name=None,
            selected_bundle_id=existing["id"],
            filters=None,
            selected_row_ids=None,
        )
        self.assertEqual(payload, [])
        self.assertEqual(message, "Deleted saved bundle.")
        self.assertIs(name_value, no_update)

    def test_saved_bundle_action_noops_for_unhandled_trigger(self) -> None:
        result = _saved_bundle_action(
            triggered_id="bundle-status",
            saved_bundles=[],
            bundle_name=None,
            selected_bundle_id=None,
            filters=None,
            selected_row_ids=None,
        )

        self.assertEqual(result, (no_update, no_update, no_update))

    def test_saved_bundle_search_handles_missing_and_found_bundles(self) -> None:
        bundle = _bundle_payload("Core Set", DashboardFilters(entity_mode="game"), ["game:g1:1"])

        self.assertIs(_saved_bundle_search(0, bundle["id"], [bundle]), no_update)
        self.assertIs(_saved_bundle_search(1, None, [bundle]), no_update)
        self.assertEqual(_saved_bundle_search(1, bundle["id"], [bundle]), bundle["search"])

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
            _effective_selected_ids("url-selected-ids", ["game:g1:1"], ["game:g2:2"]),
            ["game:g1:1"],
        )
        self.assertEqual(_effective_selected_ids("leaderboard-table", ["game:g1:1"], ["game:g2:2"]), ["game:g2:2"])

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
