"""Headless smoke test: every navigation page renders without an exception."""
import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["views/board.py", "views/overview.py", "views/workforce_planning.py", "views/day_detail.py",
         "views/scenarios.py", "views/decision.py", "views/predictive_modeling.py", "views/model_validation.py",
         "views/forecast_accuracy.py", "views/operations.py"]


class AppPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(ROOT)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def run_page(self, page, setup=None):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        at.switch_page(page)
        if setup:
            setup(at)
        at.run()
        self.assertFalse(at.exception, f"{page}: {[e.value for e in at.exception]}")
        return at

    def test_all_pages_render(self):
        for page in PAGES:
            with self.subTest(page=page):
                self.run_page(page)

    def test_navigation_preserved(self):
        src = (ROOT / "app.py").read_text()
        for page in PAGES:
            self.assertIn(page, src)

    def test_workforce_planning_with_model_forecasts(self):
        at = self.run_page("views/workforce_planning.py")
        at.radio(key="wp_source").set_value("model")
        at.toggle(key="wp_buffer").set_value(True)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertFalse(at.error, [e.value for e in at.error])

    def test_day_detail_fte(self):
        at = self.run_page("views/day_detail.py")
        html = " ".join(m.value for m in at.markdown)
        self.assertIn("5. FTE requirement", html)
        self.assertIn("Feasible staffing response for this day", html)
        # Values shown equal hours / 8 for the selected day (recomputed independently from the outlook).
        import sys
        sys.path.insert(0, str(ROOT))
        from src import logic
        o = logic.outlook(at.session_state["as_of"], at.session_state["tol"])
        r = o[o["target_date"] == at.session_state["target_date"]].iloc[0]
        self.assertIn(f"{r['projected_required_labor_hours'] / 8:,.2f}"[:-1], html)
        self.assertIn(f"{r['expected_available_regular_hours'] / 8:,.2f}", html)

    def test_comparison_controls(self):
        at = self.run_page("views/model_validation.py")
        for kpi in ("workload", "productivity"):
            for h in ("next_day", "fourteen_day"):
                for period in ("validation", "final"):
                    at.selectbox(key="mv_cmp_kpi").set_value(kpi)
                    at.selectbox(key="mv_cmp_h").set_value(h)
                    at.selectbox(key="mv_cmp_p").set_value(period)
                    at.run()
                    self.assertFalse(at.exception, (kpi, h, period, [e.value for e in at.exception]))


if __name__ == "__main__":
    unittest.main()
