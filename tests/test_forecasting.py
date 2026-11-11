"""Week 12 forecasting framework: leakage, chronology, metrics and saved-result integrity."""
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import forecasting as fc  # noqa: E402

OUT = ROOT / "models" / "forecast_comparison"
DAILY = fc.load_daily(ROOT / "data")
B = fc.split_boundaries(DAILY)


class FrameworkTests(unittest.TestCase):
    def test_split_matches_week11(self):
        w = pd.read_csv(ROOT / "models" / "week11_evaluation.csv").iloc[0]
        self.assertEqual(str(B["val_end"].date()), w["Validation_end"])
        self.assertEqual(str(B["test_start"].date()), w["Final_test_start"])
        self.assertTrue(B["dev_end"] < B["val_start"] <= B["val_end"] < B["test_start"] <= B["test_end"])

    def test_no_future_information_in_features(self):
        """Changing every outcome after origin t0 must not change any feature of origins <= t0."""
        t0 = 600
        for kpi in fc.KPIS:
            a = fc.build_panel(DAILY, kpi)
            d2 = DAILY.copy()
            rng = np.random.default_rng(0)
            later = d2.index > t0
            for c in ["new_workload_units", "actual_productivity_wlu_per_hour", "ending_backlog_wlu"]:
                d2.loc[later, c] = d2.loc[later, c] * rng.uniform(0.5, 1.5, later.sum())
            # Beginning backlog of day t0+1 equals ending backlog of t0 (known at the origin); perturb later days only.
            d2.loc[d2.index > t0 + 1, "beginning_backlog_wlu"] *= 1.37
            b = fc.build_panel(d2, kpi)
            cols = sorted(set(fc.ENHANCED_FEATURES[kpi]) | set(fc.EXISTING_FEATURES[kpi]))
            ma, mb = a[a["origin_idx"] <= t0], b[b["origin_idx"] <= t0]
            pd.testing.assert_frame_equal(ma[cols].reset_index(drop=True), mb[cols].reset_index(drop=True))
            # ...while the targets after t0 really did change (the test is not vacuous).
            self.assertFalse(np.allclose(ma.loc[ma["target_idx"] > t0, "actual"], mb.loc[mb["target_idx"] > t0, "actual"]))

    def test_weekday_average_uses_only_history_to_origin(self):
        p = fc.build_panel(DAILY, "workload")
        y = DAILY["new_workload_units"]
        for _, r in p.sample(200, random_state=1).iterrows():
            hist = DAILY.iloc[: int(r["origin_idx"]) + 1]
            same = y.iloc[: int(r["origin_idx"]) + 1][hist["day_of_week_number"] == r["dow"]]
            if len(same):
                self.assertAlmostEqual(r["wd_expanding"], same.mean(), places=9)
            self.assertLess(r["origin_date"], r["target_date"])

    def test_existing_features_only_at_horizon_one(self):
        p = fc.build_panel(DAILY, "workload")
        self.assertTrue(p.loc[p["h"] > 1, "workload_lag1"].isna().all())
        h1 = p[(p["h"] == 1) & p["workload_lag1"].notna()]
        np.testing.assert_allclose(h1["workload_lag1"], h1["last"])
        with self.assertRaises(ValueError):
            fc.predict_method("random_forest", "existing_revised", DAILY, p, "workload", "fourteen_day", B["dev_end"], p.head(5), None)

    def test_training_rows_respect_cutoff(self):
        p = fc.build_panel(DAILY, "productivity")
        for horizon in fc.HORIZONS:
            tr = fc.training_rows(p, B["dev_end"], fc.ENHANCED_FEATURES["productivity"], horizon)
            self.assertLessEqual(tr["target_date"].max(), B["dev_end"])
            if horizon == "next_day":
                self.assertEqual(set(tr["h"]), {1})

    def test_metrics_hand_calculated(self):
        m = fc.metrics([10, 20, 30], [12, 18, 33])
        self.assertAlmostEqual(m["mae"], 7 / 3)
        self.assertAlmostEqual(m["rmse"], math.sqrt(17 / 3))
        self.assertAlmostEqual(m["wape"], 7 / 60 * 100)
        self.assertAlmostEqual(m["bias"], -1.0)  # (-2 + 2 - 3) / 3: actual - forecast, over-forecast on average
        self.assertAlmostEqual(fc.improvement_pct(8, 10), 20.0)

    def test_dm_test(self):
        rng = np.random.default_rng(2)
        base = rng.uniform(1, 2, 300)
        better = fc.dm_test(base - 0.5 + rng.normal(0, 0.2, 300), base, lag=0)
        self.assertLess(better["dm_stat"], 0)
        self.assertLess(better["p_value"], 0.001)
        # A constant loss difference has zero variance: the statistic is undefined rather than infinite.
        self.assertTrue(np.isnan(fc.dm_test(base - 0.5, base)["p_value"]))
        same = fc.dm_test(base + rng.normal(0, 0.01, 300), base, lag=13)
        self.assertGreater(same["p_value"], 0.01)


class AllMethodsRunTests(unittest.TestCase):
    """Every method produces finite forecasts for both KPIs and both horizons."""

    def test_four_methods_two_kpis_two_horizons(self):
        hol = fc.load_holidays(ROOT / "data")
        for kpi in fc.KPIS:
            p = fc.build_panel(DAILY, kpi)
            origins = fc.origins_for_period(DAILY, B["val_start"], B["val_end"])[:2]
            for horizon in fc.HORIZONS:
                rows = p[p["origin_idx"].isin(origins)]
                rows = rows[rows["h"] == 1] if horizon == "next_day" else rows
                for method in fc.MODELS:
                    cfg = fc.candidates(method, horizon)[0]
                    pred = fc.predict_method(method, cfg, DAILY, p, kpi, horizon, B["dev_end"], rows, hol, workers=1)[0]
                    self.assertEqual(len(pred), len(rows), (kpi, horizon, method))
                    self.assertTrue(np.isfinite(pred).all(), (kpi, horizon, method))
                    self.assertTrue((pred >= 0).all())

    def test_prophet_refits_on_history_up_to_origin_only(self):
        seen = []
        original = fc.prophet_origin_forecast

        def spy(args):
            hist, _, targets, _ = args
            seen.append((hist["ds"].max(), min(targets)))
            return [0.0] * len(targets)

        fc.prophet_origin_forecast = spy
        try:
            p = fc.build_panel(DAILY, "workload")
            rows = p[p["origin_idx"].isin([700, 701, 702])]
            fc.prophet_predictions(DAILY, "workload", None, rows, {}, workers=1)
        finally:
            fc.prophet_origin_forecast = original
        self.assertEqual(len(seen), 3)
        for hist_end, first_target in seen:
            self.assertLess(hist_end, first_target)
        self.assertEqual([s[0] for s in seen], list(DAILY.loc[[700, 701, 702], "date"]))


@unittest.skipUnless((OUT / "metrics.csv").exists(), "run python evaluate_forecasting.py first")
class SavedResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = pd.read_csv(OUT / "metrics.csv")
        cls.p = pd.read_csv(OUT / "predictions.csv.gz", parse_dates=["origin_date", "target_date"])
        cls.sel = json.loads((OUT / "selection.json").read_text())

    def test_complete_grid(self):
        self.assertEqual(len(self.m), 2 * 2 * 2 * 4)
        for keys, g in self.m.groupby(["period", "kpi", "horizon"]):
            self.assertEqual(sorted(g["model"]), sorted(fc.MODELS), keys)

    def test_metrics_recomputed_from_saved_forecasts(self):
        sc = self.p[self.p["scored"] == 1]
        for _, r in self.m.iterrows():
            x = sc[(sc["period"] == r["period"]) & (sc["kpi"] == r["kpi"]) & (sc["horizon"] == r["horizon"]) & (sc["model"] == r["model"])]
            m = fc.metrics(x["actual"], x["forecast"])
            self.assertAlmostEqual(m["mae"], r["mae"], places=6)
            self.assertAlmostEqual(m["rmse"], r["rmse"], places=6)
            self.assertAlmostEqual(m["wape"], r["wape_pct"], places=6)
            self.assertAlmostEqual(m["bias"], r["bias"], places=6)
            self.assertEqual(m["n"], r["n_forecasts"])
            base = self.m[(self.m["period"] == r["period"]) & (self.m["kpi"] == r["kpi"]) & (self.m["horizon"] == r["horizon"])
                          & (self.m["model"] == "weekday_average")]["mae"].iloc[0]
            if r["model"] != "weekday_average":
                self.assertAlmostEqual(r["improvement_vs_baseline_pct"], (base - r["mae"]) / base * 100, places=6)

    def test_identical_dates_and_chronology(self):
        sc = self.p[self.p["scored"] == 1]
        for keys, g in sc.groupby(["period", "kpi", "horizon"]):
            sets = [set(zip(x["origin_date"], x["target_date"])) for _, x in g.groupby("model")]
            self.assertTrue(all(s == sets[0] for s in sets), keys)
        self.assertTrue((self.p["origin_date"] < self.p["target_date"]).all())
        v, f = sc[sc["period"] == "validation"], sc[sc["period"] == "final"]
        self.assertTrue(v["target_date"].between(B["val_start"], B["val_end"]).all())
        self.assertTrue(f["target_date"].between(B["test_start"], B["test_end"]).all())
        nd = sc[sc["horizon"] == "next_day"]
        self.assertEqual(set(nd["h"]), {1})
        fd = sc[sc["horizon"] == "fourteen_day"]
        self.assertTrue((fd.groupby(["period", "kpi", "model", "origin_date"]).size() == 14).all())

    def test_selection_is_lowest_validation_mae(self):
        v = self.m[self.m["period"] == "validation"]
        for kpi, hs in self.sel.items():
            for horizon, s in hs.items():
                g = v[(v["kpi"] == kpi) & (v["horizon"] == horizon)]
                self.assertEqual(s["model"], g.sort_values("mae").iloc[0]["model"])
        # Ranks are by MAE within each table.
        for _, g in self.m.groupby(["period", "kpi", "horizon"]):
            self.assertEqual(g.sort_values("mae")["rank"].tolist()[0], 1)

    def test_existing_random_forest_reproduced(self):
        rep = json.loads((OUT / "reproduction.json").read_text())
        for kpi in fc.KPIS:
            for cfg in ("existing_original", "existing_revised"):
                self.assertTrue(rep[kpi][cfg]["matches_week11"], (kpi, cfg))


if __name__ == "__main__":
    unittest.main()
