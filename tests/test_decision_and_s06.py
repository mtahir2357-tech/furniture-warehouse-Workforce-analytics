"""Acceptance tests: decision recording accuracy (Issue 1) and infeasible 'Reduce regular hours' (Issue 2).

All decision saves go to a temporary log; the repository's data folder is never written.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src.config  # noqa: E402
import src.decisions as decisions  # noqa: E402

BASE = {"scenario_id": "S01", "label": "Current plan", "planned_regular_hours": 200.0, "planned_overtime_hours": 0.0,
        "expected_total_available_hours": 194.0, "capacity_gap_hours": -21.8, "projected_total_labor_cost": 3662.23,
        "feasible": True, "over_budget": False}
OT = {"scenario_id": "S03", "label": "Add overtime", "planned_regular_hours": 200.0, "planned_overtime_hours": 20.0,
      "expected_total_available_hours": 214.0, "capacity_gap_hours": -1.8, "projected_total_labor_cost": 4166.87,
      "feasible": True, "over_budget": True}
BAD = {**OT, "scenario_id": "CUSTOM", "label": "Custom", "planned_regular_hours": 600.0, "feasible": False}


class DecisionRecordTests(unittest.TestCase):
    """Issue 1, unit level: the saved hours/cost always describe the plan actually implemented."""

    def rec(self, action, sel=OT, notes=""):
        return decisions.decision_record(action, sel, BASE, "2025-12-15", "2025-12-17", notes)

    def test_implement_records_selected(self):
        r = self.rec("Implement selected scenario")
        self.assertEqual((r["scenario"], r["planned_overtime_hours"], r["projected_labor_cost"]), ("Add overtime", 20.0, 4166.87))
        self.assertEqual(r["proposed_not_implemented"], "")
        self.assertIn("over daily labor budget", r["notes"])

    def test_keep_current_plan_records_baseline(self):
        r = self.rec("Keep current plan", notes="Too costly")
        self.assertEqual(r["scenario"], "Current plan")
        self.assertEqual((r["planned_regular_hours"], r["planned_overtime_hours"]), (200.0, 0.0))
        self.assertEqual(r["expected_available_hours"], 194.0)
        self.assertEqual(r["projected_capacity_gap"], -21.8)
        self.assertEqual(r["projected_labor_cost"], 3662.23)
        self.assertEqual(r["proposed_not_implemented"], "Add overtime")
        self.assertEqual(r["proposed_labor_cost"], 4166.87)
        self.assertNotIn("over daily labor budget", r["notes"])  # the baseline is not over budget
        self.assertTrue(r["notes"].startswith("Too costly"))

    def test_monitor_keeps_baseline_and_flags_proposal(self):
        r = self.rec("Monitor and revisit tomorrow")
        self.assertEqual((r["scenario"], r["planned_overtime_hours"], r["projected_labor_cost"]), ("Current plan", 0.0, 3662.23))
        self.assertEqual(r["proposed_not_implemented"], "Add overtime")
        self.assertIn("Add overtime proposed, not implemented", r["notes"])

    def test_no_proposal_when_baseline_selected(self):
        for action in decisions.ACTIONS:
            r = self.rec(action, sel=BASE)
            self.assertEqual(r["scenario"], "Current plan")
            self.assertEqual(r["proposed_not_implemented"], "")

    def test_infeasible_cannot_be_implemented_but_can_be_declined(self):
        with self.assertRaises(ValueError):
            self.rec("Implement selected scenario", sel=BAD)
        r = self.rec("Keep current plan", sel=BAD)
        self.assertEqual((r["planned_regular_hours"], r["proposed_not_implemented"]), (200.0, "Custom"))
        with self.assertRaises(ValueError):
            self.rec("Do something else")

    def test_old_log_is_migrated_not_corrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "decision_log.csv"
            old_cols = decisions.COLUMNS[:11]
            pd.DataFrame([{c: "x" for c in old_cols}]).to_csv(log, index=False)
            orig = decisions.DECISION_LOG
            decisions.DECISION_LOG = log
            try:
                decisions.save([self.rec("Keep current plan")])
                decisions.save([self.rec("Implement selected scenario")])
                d = pd.read_csv(log)
            finally:
                decisions.DECISION_LOG = orig
            self.assertEqual(list(d.columns), decisions.COLUMNS)
            self.assertEqual(len(d), 3)
            self.assertEqual(list(d["scenario"]), ["x", "Current plan", "Add overtime"])


class AppTests(unittest.TestCase):
    """End-to-end through the Streamlit pages (Issue 1 and Issue 2)."""

    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(ROOT)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = Path(cls.tmp.name) / "decision_log.csv"
        cls.orig = (src.config.DECISION_LOG, decisions.DECISION_LOG)
        src.config.DECISION_LOG = decisions.DECISION_LOG = cls.log

    @classmethod
    def tearDownClass(cls):
        src.config.DECISION_LOG, decisions.DECISION_LOG = cls.orig
        cls.tmp.cleanup()
        os.chdir(cls.cwd)

    def setUp(self):
        if self.log.exists():
            self.log.unlink()

    def app(self, page, **state):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        at.run()
        for k, v in state.items():
            at.session_state[k] = v
        at.switch_page(page)
        at.run()
        self.assertFalse(at.exception, [str(e.value)[:300] for e in at.exception])
        return at

    def decide(self, choice, action, **state):
        at = self.app("views/scenarios.py", **state)
        if choice == "CUSTOM":
            at.number_input(key="c_reg").set_value(600.0)
            at.run()
        at.radio[0].set_value(choice)
        at.run()
        at.switch_page("views/decision.py")
        at.run()
        at.selectbox[0].set_value(action)
        at.run()
        self.assertFalse(at.exception, [str(e.value)[:300] for e in at.exception])
        return at

    def save(self, at):
        at.button(key="save_decision").click()
        at.run()
        self.assertFalse(at.exception)
        return pd.read_csv(self.log).iloc[-1]

    def baseline_row(self):
        at = self.decide("S01", "Implement selected scenario")
        return self.save(at)

    def test_keep_current_plan_after_selecting_overtime(self):
        base = self.baseline_row()
        at = self.decide("S03", "Keep current plan")
        info = " ".join(i.value for i in at.info)
        self.assertIn("Will be recorded as implemented: **Current plan**", info)
        row = self.save(at)
        self.assertEqual(row["scenario"], "Current plan")
        self.assertEqual(row["planned_overtime_hours"], 0.0)  # not the 20 h of "Add overtime"
        self.assertAlmostEqual(row["projected_labor_cost"], base["projected_labor_cost"])
        self.assertAlmostEqual(row["projected_capacity_gap"], base["projected_capacity_gap"])
        self.assertEqual(row["proposed_not_implemented"], "Add overtime")
        self.assertGreater(row["proposed_labor_cost"], row["projected_labor_cost"])

    def test_monitor_after_selecting_overtime(self):
        base = self.baseline_row()
        row = self.save(self.decide("S03", "Monitor and revisit tomorrow"))
        self.assertEqual((row["scenario"], row["final_action"]), ("Current plan", "Monitor and revisit tomorrow"))
        self.assertAlmostEqual(row["projected_labor_cost"], base["projected_labor_cost"])
        self.assertEqual(row["planned_overtime_hours"], 0.0)
        self.assertIn("proposed, not implemented", row["notes"])

    def test_implement_selected_records_scenario(self):
        row = self.save(self.decide("S03", "Implement selected scenario"))
        self.assertEqual((row["scenario"], row["planned_overtime_hours"]), ("Add overtime", 20.0))
        self.assertTrue(pd.isna(row["proposed_not_implemented"]))

    def test_infeasible_custom_blocked_but_can_be_declined(self):
        at = self.decide("CUSTOM", "Implement selected scenario")
        self.assertTrue(at.button(key="save_decision").disabled)
        at.selectbox[0].set_value("Keep current plan")
        at.run()
        self.assertFalse(at.button(key="save_decision").disabled)
        row = self.save(at)
        self.assertEqual((row["scenario"], row["planned_regular_hours"]), ("Current plan", 200.0))
        self.assertEqual(row["proposed_not_implemented"], "Custom (600 h regular + 0 h OT)")

    # ---------------- Issue 2: Reduce regular hours (S06) infeasible on a surplus day
    def test_surplus_day_with_s06_infeasible(self):
        at = self.app("views/scenarios.py", pol_min=24, target_date=pd.Timestamp("2025-12-20"))
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("Surplus", text)
        self.assertIn("Reducing regular hours is not permitted under the selected staffing policy", text)
        options = at.radio[0].options
        self.assertTrue(any("Reduce regular hours" in o and "not feasible" in o for o in options), options)
        self.assertFalse(any("Reduce regular hours" in o and "recommended" in o for o in options), options)
        at.radio[0].set_value("S06")
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key="go_decision").disabled)
        at.switch_page("views/decision.py")
        at.run()
        self.assertTrue(at.button(key="save_decision").disabled)  # cannot be implemented
        board = self.app("views/board.py", pol_min=24)
        self.assertNotIn("Cut 16 regular hours</b>", " ".join(m.value for m in board.markdown))

    def test_surplus_day_with_s06_feasible_unchanged(self):
        at = self.app("views/scenarios.py", target_date=pd.Timestamp("2025-12-20"))
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("Reducing regular hours moves the gap to", text)
        self.assertTrue(any("Reduce regular hours" in o and "recommended" in o for o in at.radio[0].options))


if __name__ == "__main__":
    unittest.main()
