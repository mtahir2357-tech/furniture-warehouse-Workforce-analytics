"""Acceptance tests for the Week 12 review fixes (F1–F7), covering the three decision-support tasks:
daily workload forecasting, workforce staffing and allocation, and staffing scenario comparison.
Expected values are calculated independently from the source CSVs, not read back from the app code.
"""
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import backlog, logic  # noqa: E402
from src.fte import StaffingPolicy, budget_check, check_feasibility, fte_summary, horizon_plan  # noqa: E402
from src import reliability  # noqa: E402

DATA = ROOT / "data"
AS_OF = pd.Timestamp("2025-12-15")


def raw_outlook(as_of=AS_OF):
    """Independent re-creation of the 14 forecast rows (no Streamlit caching)."""
    f = pd.read_csv(DATA / "fact_workload_forecast.csv")
    s = pd.read_csv(DATA / "fact_staffing_scenario.csv")
    f = f[f["forecast_date_key"] == int(as_of.strftime("%Y%m%d"))].sort_values("horizon_operating_days")
    base = s[(s["scenario_id"] == "S01") & s["forecast_id"].isin(f["forecast_id"])][
        ["forecast_id", "avg_worker_hourly_rate", "projected_manager_labor_cost"]]
    f = f.merge(base, on="forecast_id")
    f["target_date"] = pd.to_datetime(f["target_date_key"].astype(str))
    f["availability_ratio"] = f["expected_available_regular_hours"] / f["planned_regular_hours"]
    return f.reset_index(drop=True), s


def daily():
    d = pd.read_csv(DATA / "fact_daily_outcome.csv")
    d["date"] = pd.to_datetime(d["date_key"].astype(str))
    return d.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------- F1 scenario feasibility
class FeasibilityTests(unittest.TestCase):
    P = StaffingPolicy()  # roster 30, minimum 20, 2 h overtime per worker-day, 8 h shift

    def test_rules(self):
        c = check_feasibility(600, 0, self.P)  # 75 workers
        self.assertFalse(c["feasible"]); self.assertIn("exceed the roster", " ".join(c["issues"]))
        c = check_feasibility(168, 60, self.P)  # 21 workers -> cap 42 h
        self.assertFalse(c["feasible"]); self.assertAlmostEqual(c["overtime_cap"], 42)
        self.assertIn("overtime", " ".join(c["issues"]))
        c = check_feasibility(144, 0, self.P)  # 18 workers
        self.assertFalse(c["feasible"]); self.assertIn("project assumption", " ".join(c["issues"]))
        c = check_feasibility(0, 4, self.P)
        self.assertFalse(c["feasible"]); self.assertEqual(len(c["issues"]), 2)
        self.assertFalse(check_feasibility(-8, 0, self.P)["feasible"])
        c = check_feasibility(200, 20, self.P)
        self.assertTrue(c["feasible"]); self.assertEqual(c["warnings"], [])
        c = check_feasibility(204, 0, self.P)
        self.assertTrue(c["feasible"]); self.assertIn("whole number", c["warnings"][0])
        c = check_feasibility(216, 0, self.P)  # 27 workers: allowed today, above 25/day weekly average
        self.assertTrue(c["feasible"]); self.assertIn("sustain", c["warnings"][0])
        self.assertTrue(check_feasibility(240, 60, self.P)["feasible"])   # roster and cap exactly
        self.assertFalse(check_feasibility(248, 0, self.P)["feasible"])   # 31 workers

    def test_predefined_scenarios_feasible_under_default_policy(self):
        s = pd.read_csv(DATA / "fact_staffing_scenario.csv", usecols=["scenario_id", "planned_regular_hours", "planned_overtime_hours"])
        for (reg, ot), _ in s.groupby(["planned_regular_hours", "planned_overtime_hours"]):
            self.assertTrue(check_feasibility(reg, ot, self.P)["feasible"], (reg, ot))

    def test_recommendation_skips_infeasible_options(self):
        f, s = raw_outlook()
        fid = int(f.iloc[1]["forecast_id"])
        t = s[s["forecast_id"] == fid].copy().sort_values("scenario_id").reset_index(drop=True)
        t["capacity_gap_hours"] = -t["projected_labor_gap_hours"]
        t["status"] = t["capacity_gap_hours"].map(lambda g: logic.classify_gap(g, 8))
        t["backlog_risk"] = "Low"
        tight = StaffingPolicy(roster_workers=26, min_workers=20)  # S02 (27 workers) breaks the roster
        tt = backlog.with_carry_in(t, 0.0, 8, tight)
        self.assertFalse(tt.set_index("scenario_id").loc["S02", "feasible"])
        day = pd.Series({"status": "Shortage", "exceedance_risk": "High"})
        self.assertNotEqual(logic.recommend(day, tt, 8)["scenario_id"], "S02")


# ---------------------------------------------------------------- F2 backlog consistency
class BacklogConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.f, self.s = raw_outlook()
        self.plan = backlog.pipeline_plan(self.f, daily(), AS_OF)

    def test_opening_backlog_is_observed_value(self):
        d = daily()
        self.assertAlmostEqual(backlog.opening_backlog(d, AS_OF), float(d.loc[d["date"] == AS_OF, "ending_backlog_wlu"].iloc[0]))

    def test_first_day_requirement_independent(self):
        d = daily()
        carry = float(d.loc[d["date"] == AS_OF, "ending_backlog_wlu"].iloc[0])
        r = self.f.iloc[0]
        expected_fte = (carry + r["forecast_workload_units"]) / r["expected_productivity_wlu_per_hour"] / 8
        row = self.plan.iloc[0]
        self.assertAlmostEqual(row["required_fte"], expected_fte, places=9)
        self.assertAlmostEqual(row["rec_required_fte"], expected_fte, places=9)

    def test_carry_chain_matches_planner(self):
        p = self.plan
        for k in range(1, len(p)):
            self.assertAlmostEqual(p.loc[k, "rec_beginning_backlog_wlu"], p.loc[k - 1, "rec_ending_backlog_wlu"])
            self.assertAlmostEqual(p.loc[k, "beginning_backlog_wlu"], p.loc[k - 1, "ending_backlog_wlu"])
            c = backlog.carry_in(p, p.loc[k, "target_date"])
            self.assertEqual(c["response"], p.loc[k, "rec_beginning_backlog_wlu"])

    def test_with_carry_in_arithmetic_and_pipeline_untouched(self):
        fid = int(self.f.iloc[1]["forecast_id"])
        raw = self.s[self.s["forecast_id"] == fid].sort_values("scenario_id").reset_index(drop=True)
        t = raw.copy()
        t["capacity_gap_hours"] = -t["projected_labor_gap_hours"]
        t["status"] = t["capacity_gap_hours"].map(lambda g: logic.classify_gap(g, 8))
        zero = backlog.with_carry_in(t, 0.0, 8)
        np.testing.assert_allclose(zero["capacity_gap_hours"], t["capacity_gap_hours"])
        self.assertEqual(list(zero["status"]), list(t["status"]))
        hundred = backlog.with_carry_in(t, 100.0, 8)
        np.testing.assert_allclose(hundred["new_work_gap_hours"], -raw["projected_labor_gap_hours"])  # original kept
        np.testing.assert_allclose(t["capacity_gap_hours"] - hundred["capacity_gap_hours"],
                                   100.0 / raw["assumed_productivity_wlu_per_hour"])
        s5 = hundred.set_index("scenario_id")
        self.assertGreater(s5.loc["S05", "carry_in_hours"], s5.loc["S01", "carry_in_hours"])  # lower productivity

    def test_custom_adjustment(self):
        res = logic.compute_scenario(300, 1.5, 200, 0, 0.97, 18, 400, 600)
        a = backlog.adjust_custom(res, 30, 1.5, 300, 8)
        self.assertAlmostEqual(a["capacity_gap_hours"], res["capacity_gap_hours"] - 20)
        self.assertAlmostEqual(a["projected_ending_backlog_wlu"], max(0, 330 - 194 * 1.5))


# ---------------------------------------------------------------- F4 budget
class BudgetTests(unittest.TestCase):
    def test_budget(self):
        self.assertIsNone(budget_check(3000, None))
        self.assertTrue(budget_check(4000, 4000)["within"])
        b = budget_check(4391.4, 4000)
        self.assertFalse(b["within"]); self.assertAlmostEqual(b["over_by"], 391.4); self.assertEqual(b["label"], "Over budget by $391")

    def test_default_budget_close_to_typical_cost(self):
        s = pd.read_csv(DATA / "fact_staffing_scenario.csv", usecols=["scenario_id", "projected_total_labor_cost"])
        typical = s.loc[s["scenario_id"] == "S01", "projected_total_labor_cost"].median()
        self.assertTrue(3500 < typical < 4000, typical)


# ---------------------------------------------------------------- F6 forecast reliability
class ReliabilityTests(unittest.TestCase):
    def test_summary_recomputes_from_source(self):
        f = pd.read_csv(DATA / "fact_workload_forecast.csv")
        s = reliability.summary(f)
        a, p = f["actual_workload_units"], f["forecast_workload_units"]
        self.assertAlmostEqual(s["mae_wlu"], (a - p).abs().mean())
        cov = ((a >= f["lower_80_workload_units"]) & (a <= f["upper_80_workload_units"])).mean()
        self.assertAlmostEqual(s["coverage_80"], cov)
        self.assertAlmostEqual(round(cov, 3), 0.795)
        hi = f["probability_capacity_exceeded"] >= 0.5
        self.assertAlmostEqual(s["high_risk_observed"], (a[hi] > f.loc[hi, "baseline_capacity_wlu"]).mean())
        lines = reliability.manager_lines(s)
        self.assertTrue(any("80% range" in l for l in lines))
        self.assertTrue(any("shifts" in l for l in lines))
        h1 = reliability.summary(f, horizon=1)
        self.assertEqual(h1["n"], int((f["horizon_operating_days"] == 1).sum()))


# ---------------------------------------------------------------- App-level acceptance (three decision tasks)
class AppAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(ROOT)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def page(self, path, **state):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        at.run()
        for k, v in state.items():
            at.session_state[k] = v
        at.switch_page(path)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def text(at):
        return " ".join([m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning]
                        + [s.value for s in at.success])

    # Task 1: workload forecasting
    def test_forecast_reliability_explained(self):
        for path in ("views/forecast_accuracy.py", "views/overview.py", "views/day_detail.py"):
            at = self.page(path)
            self.assertIn("Typical miss", self.text(at), path)

    # Task 2: staffing and allocation — day detail and the 14-day planner agree
    def test_day_detail_matches_planner(self):
        at = self.page("views/day_detail.py")
        f, _ = raw_outlook(at.session_state["as_of"])
        plan = backlog.pipeline_plan(f, daily(), at.session_state["as_of"])
        row = plan[plan["target_date"] == at.session_state["target_date"]].iloc[0]
        t = self.text(at)
        self.assertIn(f"{row['rec_required_fte']:,.2f}", t)
        self.assertIn(f"{int(row['rec_shift_change']):+d} regular shift(s)", t)
        self.assertIn(f"{row['rec_beginning_backlog_wlu']:,.0f} WLU open at the start of the day", t)
        wp = self.page("views/workforce_planning.py")
        self.assertFalse(wp.error, [e.value for e in wp.error])

    # Task 3: scenario comparison — infeasible custom plans are flagged and blocked
    def test_infeasible_custom_scenario_blocked(self):
        at = self.page("views/scenarios.py")
        at.number_input(key="c_reg").set_value(600.0)
        at.run()
        at.radio[0].set_value("CUSTOM")
        at.run()
        self.assertIn("Infeasible custom scenario", self.text(at))
        self.assertTrue(at.button(key="go_decision").disabled)
        at.switch_page("views/decision.py")
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key="save_decision").disabled)

    def test_feasible_custom_scenario_allowed(self):
        at = self.page("views/scenarios.py")
        at.number_input(key="c_reg").set_value(216.0)
        at.number_input(key="c_ot").set_value(10.0)
        at.run()
        at.radio[0].set_value("CUSTOM")
        at.run()
        self.assertNotIn("Infeasible custom scenario", self.text(at))
        self.assertFalse(at.button(key="go_decision").disabled)

    def test_overtime_cap_flagged(self):
        at = self.page("views/scenarios.py")
        at.number_input(key="c_reg").set_value(168.0)
        at.number_input(key="c_ot").set_value(60.0)
        at.run()
        self.assertIn("overtime hours exceed the cap of 42", self.text(at))

    def test_budget_flags(self):
        at = self.page("views/scenarios.py", budget_on=True, budget_amt=3000.0)
        t = self.text(at)
        self.assertIn("Daily labor budget $3,000", t)
        self.assertIn("exceeded by", t)
        expected = {"views/board.py": "over budget by $", "views/day_detail.py": "over budget by $",
                    "views/workforce_planning.py": "daily labor budget $3,000",
                    "views/decision.py": "over the daily labor budget"}
        for path, phrase in expected.items():
            self.assertIn(phrase, self.text(self.page(path, budget_on=True, budget_amt=3000.0)).lower(), path)
        # Without a budget nothing is flagged.
        self.assertNotIn("over budget by", self.text(self.page("views/board.py")).lower())

    def test_minimum_staffing_labelled_as_assumption(self):
        for path in ("views/scenarios.py", "views/board.py", "views/day_detail.py", "views/workforce_planning.py"):
            at = self.page(path)
            self.assertIn("project assumption", self.text(at), path)

    def test_policy_change_propagates(self):
        default = self.text(self.page("views/board.py"))
        self.assertGreater(default.count("Add 16 regular hours</b>"), 0)  # S02 is recommended under the default roster
        tight = self.text(self.page("views/board.py", pol_roster=26))
        self.assertEqual(tight.count("Add 16 regular hours</b>"), 0)  # S02 needs 27 workers: never recommended
        self.assertGreater(tight.count("Add 20 overtime hours</b>"), 0)
        sc = self.page("views/scenarios.py", pol_roster=26)
        self.assertIn("not feasible under the current policy", self.text(sc))


if __name__ == "__main__":
    unittest.main()
