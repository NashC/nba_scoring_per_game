from __future__ import annotations

import math
from tempfile import TemporaryDirectory
import unittest

from nba_scoring_per_game.dashboard import LiveLogo3D, create_dashboard_app, load_dashboard_datasets
from nba_scoring_per_game.dashboard.state import DashboardFilters, filter_values_from_filters
from tests.fixtures import build_test_outputs, find_component_by_id


class LiveLogoTests(unittest.TestCase):
    def test_live_logo_uses_expected_dom_contract(self) -> None:
        logo = LiveLogo3D(id="test-live-logo", variant="hero", size=320, animated=False, interactive=False, glow=False)
        props = logo.to_plotly_json()["props"]

        self.assertEqual(props["id"], "test-live-logo")
        self.assertEqual(props["data-live-logo"], "true")
        self.assertEqual(props["data-variant"], "hero")
        self.assertEqual(props["data-size"], "320px")
        self.assertEqual(props["data-animated"], "false")
        self.assertEqual(props["data-interactive"], "false")
        self.assertEqual(props["data-glow"], "false")
        self.assertEqual(props["data-reduced-motion"], "system")
        self.assertEqual(props["style"]["--live-logo-size"], "320px")
        self.assertEqual(props["aria-hidden"], "true")
        self.assertIn("live-logo--hero", props["className"])
        self.assertEqual(len(props["children"]), 2)
        self.assertEqual(props["children"][0].className, "live-logo-canvas")
        self.assertEqual(props["children"][1].className, "live-logo-fallback")

    def test_live_logo_supports_accessible_labeled_usage(self) -> None:
        logo = LiveLogo3D(
            variant="nav",
            decorative=False,
            aria_label="Scoring Explorer logo",
            reduced_motion_override=True,
        )
        props = logo.to_plotly_json()["props"]

        self.assertEqual(props["role"], "img")
        self.assertEqual(props["aria-label"], "Scoring Explorer logo")
        self.assertEqual(props["data-reduced-motion"], "true")
        self.assertNotIn("aria-hidden", props)

    def test_live_logo_preserves_fractional_size_and_rejects_non_positive_sizes(self) -> None:
        logo = LiveLogo3D(size=48.5)
        props = logo.to_plotly_json()["props"]

        self.assertEqual(props["data-size"], "48.5px")
        self.assertEqual(props["style"]["--live-logo-size"], "48.5px")
        with self.assertRaisesRegex(ValueError, "size must be positive"):
            LiveLogo3D(size=0)

    def test_filter_values_drop_non_finite_numeric_values(self) -> None:
        filters = DashboardFilters(
            min_competitive_share=math.nan,
            min_ts_pct=math.inf,
            min_efg_pct=-math.inf,
            min_offensive_share=0.4,
        )
        values = filter_values_from_filters(filters)

        self.assertIsNone(values["min_competitive_share"])
        self.assertIsNone(values["min_ts_pct"])
        self.assertIsNone(values["min_efg_pct"])
        self.assertEqual(values["min_offensive_share"], 0.4)

    def test_dashboard_layout_includes_logo_mounts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            build_test_outputs(tmpdir)
            app = create_dashboard_app(tmpdir)
            self.assertIsNotNone(find_component_by_id(app.layout, "hero-brand-lockup"))
            self.assertIsNotNone(find_component_by_id(app.layout, "hero-live-logo"))
            self.assertIsNotNone(find_component_by_id(app.layout, "hero-brand-stage"))

        with TemporaryDirectory() as tmpdir:
            app = create_dashboard_app(tmpdir)
            self.assertEqual(app.layout.className, "app-shell")
            self.assertFalse(load_dashboard_datasets(tmpdir).available)
            self.assertIsNotNone(find_component_by_id(app.layout, "empty-brand-lockup"))


if __name__ == "__main__":
    unittest.main()
