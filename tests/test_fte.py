"""FTE and staffing-response formulas checked against independently hand-calculated values."""
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import fte  # noqa: E402
from src.fte import StaffingPolicy, fte_summary, horizon_plan, round_half_up, staffing_response  # noqa: E402
from src.planning import plan_day  # noqa: E402


class FteFormulaTests(unittest.TestCase):
    def test_specified_example(self):
        s = fte_summary(215.8, 194)
        self.assertAlmostEqual(s["required_fte"], 26.975)
        self.assertAlmostEqual(s["available_fte"], 24.25)
        self.assertAlmostEqual(s["fte_gap"], 2.725)
        self.assertEqual(round_half_up(s["required_fte"]), 26.98)
        self.assertEqual(round_half_up(s["available_fte"]), 24.25)
        self.assertEqual(round_half_up(s["fte_gap"]), 2.73)
        self.assertEqual(s["additional_shifts"], 3)
        self.assertEqual(s["fte_status"], "Shortage")

    def test_surplus_and_exact_multiples(self):
        s = fte_summary(150, 194)
        self.assertAlmostEqual(s["fte_gap"], -5.5)
        self.assertEqual(s["additional_shifts"], 0)
        self.assertAlmostEqual(s["fte_surplus"], 5.5)
        self.assertEqual(s["fte_status"], "Surplus")
        # 16 hours short is exactly two shifts, not three (no floating-point ceil artefact).
        self.assertEqual(fte_summary(210.0, 194.0)["additional_shifts"], 2)
        self.assertEqual(fte.whole_shifts(0.1 + 0.2 + 1.7), 2)
        self.assertEqual(fte.whole_shifts(-3), 0)

    def test_weekly_fte_and_configurable_shift(self):
        self.assertAlmostEqual(fte.weekly_fte(200), 5.0)
        self.assertAlmostEqual(fte.weekly_fte(200, week_hours=50), 4.0)
        self.assertAlmostEqual(fte.to_fte(100, shift_hours=10), 10.0)
        with self.assertRaises(ValueError):
            fte.to_fte(10, shift_hours=0)

    def test_availability_applied_once_and_managers_excluded(self):
        r = plan_day(300, 0, 1.5, 200, 10, 0.97, 18, 400)
        self.assertAlmostEqual(r["expected_total_available_hours"], 200 * 0.97 + 10)
        self.assertAlmostEqual(fte_summary(r["required_hours"], r["expected_total_available_hours"])["available_fte"], 204 / 8)
        r0 = plan_day(300, 0, 1.5, 200, 10, 0.97, 18, 0)
        self.assertEqual(r["expected_total_available_hours"], r0["expected_total_available_hours"])
        self.assertAlmostEqual(r["labor_cost"] - r0["labor_cost"], 400)  # manager hours add cost only
        # Overtime counted once: 194 regular + 10 overtime x 1.5 pay.
        self.assertAlmostEqual(r0["labor_cost"], 194 * 18 + 10 * 18 * 1.5)

    def test_matches_saved_pipeline_hours(self):
        s = pd.read_csv(ROOT / "data" / "fact_staffing_scenario.csv", nrows=60)
        for _, r in s.iterrows():
            f = fte_summary(r["projected_required_labor_hours"], r["expected_total_available_hours"])
            self.assertAlmostEqual(f["required_fte"], r["projected_required_labor_hours"] / 8)
            self.assertAlmostEqual(f["fte_gap"] * 8, r["projected_labor_gap_hours"], places=1)


class StaffingResponseTests(unittest.TestCase):
    P = StaffingPolicy(roster_workers=30, min_workers=20, max_ot_per_worker_day=2.0)

    def test_shortage_covered_with_whole_shifts(self):
        # 400 WLU / 2 WLU/h = 200 h required; 20 workers x 8 h x 100% = 160 h -> 40 h = 5 shifts.
        r = staffing_response(400, 2.0, 0, 160, 1.0, 20, 100, self.P)
        self.assertEqual(r["shift_change"], 5)
        self.assertEqual(r["overtime_hours"], 0)
        self.assertTrue(r["feasible"])
        self.assertAlmostEqual(r["recommended"]["labor_cost"], 200 * 20 + 100)
        self.assertEqual(r["current"]["additional_shifts"], 5)

    def test_small_remainder_uses_overtime(self):
        # 4 h short: overtime costs 4 x 1.5 = 6 rate-hours < one 8-hour shift.
        r = staffing_response(328, 2.0, 0, 160, 1.0, 20, 100, self.P)
        self.assertEqual(r["shift_change"], 0)
        self.assertAlmostEqual(r["overtime_hours"], 4)
        self.assertAlmostEqual(r["recommended"]["labor_cost"], 160 * 20 + 4 * 20 * 1.5 + 100)
        # 6 h short: 6 x 1.5 = 9 > 8, so a whole regular shift is cheaper.
        r = staffing_response(332, 2.0, 0, 160, 1.0, 20, 100, self.P)
        self.assertEqual((r["shift_change"], r["overtime_hours"]), (1, 0))

    def test_availability_on_added_shifts(self):
        # 200 planned x 0.97 = 194 available; need 215.8 -> 21.8 h; each added shift yields 7.76 h.
        r = staffing_response(215.8 * 1.6, 1.6, 0, 200, 0.97, 18, 400, self.P)
        self.assertAlmostEqual(r["current"]["required_fte"], 26.975)
        self.assertAlmostEqual(r["current"]["available_fte"], 24.25)
        self.assertEqual(r["current"]["additional_shifts"], 3)
        self.assertTrue(r["feasible"])
        self.assertGreaterEqual(r["recommended"]["expected_total_available_hours"], 215.8 - 1e-9)

    def test_roster_and_overtime_limits_make_day_infeasible(self):
        p = StaffingPolicy(roster_workers=22, min_workers=20, max_ot_per_worker_day=0.5)
        # 40 h short; 2 spare workers -> 16 h; overtime cap 22 x 0.5 = 11 h; 13 h uncovered -> 26 WLU backlog.
        r = staffing_response(400, 2.0, 0, 160, 1.0, 20, 100, p)
        self.assertEqual(r["shift_change"], 2)
        self.assertAlmostEqual(r["overtime_hours"], 11)
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["recommended"]["ending_backlog_wlu"], 26)
        self.assertTrue(any("Infeasible" in n for n in r["notes"]))
        p2 = StaffingPolicy(roster_workers=22, min_workers=20, max_ot_per_worker_day=2.0)
        r2 = staffing_response(400, 2.0, 0, 160, 1.0, 20, 100, p2)
        self.assertTrue(r2["feasible"])
        self.assertAlmostEqual(r2["overtime_hours"], 24)

    def test_surplus_respects_minimum_staffing(self):
        # 80 h required vs 200 h available: 15 shifts removable, but only 25 - 20 = 5 allowed.
        r = staffing_response(160, 2.0, 0, 200, 1.0, 20, 100, self.P)
        self.assertEqual(r["shift_change"], -5)
        self.assertEqual(r["recommended"]["scheduled_workers"], 20)
        self.assertTrue(any("Minimum staffing" in n for n in r["notes"]))
        # A modest surplus only removes shifts that keep the day covered.
        r = staffing_response(370, 2.0, 0, 200, 1.0, 20, 100, self.P)  # 185 h required, 15 h spare -> 1 shift
        self.assertEqual(r["shift_change"], -1)
        self.assertTrue(r["feasible"])

    def test_backlog_carry_and_weekly_checks(self):
        days = pd.DataFrame({
            "target_date": pd.to_datetime(["2025-06-02", "2025-06-03", "2025-06-04"]),
            "workload": [500.0, 300.0, 300.0], "productivity": [2.0, 2.0, 2.0],
            "planned_regular_hours": [200.0] * 3, "availability_ratio": [1.0] * 3,
            "hourly_rate": [20.0] * 3, "manager_cost": [100.0] * 3,
        })
        plan = horizon_plan(days, 0, self.P)
        # Day 1: 250 h required vs 200 h -> 100 WLU carried into day 2 under the current plan.
        self.assertAlmostEqual(plan.loc[0, "ending_backlog_wlu"], 100)
        self.assertAlmostEqual(plan.loc[1, "beginning_backlog_wlu"], 100)
        self.assertAlmostEqual(plan.loc[1, "required_fte"], (400 / 2) / 8)
        self.assertAlmostEqual(plan.loc[0, "rec_ending_backlog_wlu"], 0)  # response covers day 1
        self.assertAlmostEqual(plan.loc[0, "weekly_required_fte"], plan["required_hours"].sum() / 40)
        self.assertFalse(plan["week_shift_cap_exceeded"].any())

    def test_policy_validation(self):
        with self.assertRaises(ValueError):
            StaffingPolicy(roster_workers=10, min_workers=20)
        with self.assertRaises(ValueError):
            StaffingPolicy(shift_hours=0)


if __name__ == "__main__":
    unittest.main()
