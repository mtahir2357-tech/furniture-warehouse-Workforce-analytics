"""Week 12: four-method forecasting comparison for Daily Workload and Labor Productivity.

Run from the repository root (needs requirements-forecasting.txt):

    python evaluate_forecasting.py

Design (see src/forecasting.py for the forecast-origin rule):
* Chronological split identical to Week 11: development (64%) / validation (16%) / final period (20%).
* Every configuration is tuned ONLY on validation forecast origins, with models trained on
  targets observed by the end of the development period.
* The configuration with the lowest validation MAE is refitted on development + validation
  targets and scored once on the final period. The final period was already viewed in
  Week 11, so final-period numbers are labelled *retrospective*, not untouched.
* Both horizons (next operating day; next 14 operating days) are scored on identical
  forecast origins and target days for all four methods.

Outputs are written to models/forecast_comparison/ and are read by the Streamlit app
(the app never retrains models).
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src import forecasting as fc

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "models" / "forecast_comparison"


def _period_rows(panel, daily, start, end, horizon):
    origins = fc.origins_for_period(daily, start, end)
    rows = panel[panel["origin_idx"].isin(origins)]
    return rows[rows["h"] == 1].copy() if horizon == "next_day" else rows.copy()


def run(data_dir=ROOT / "data", out_dir=OUT, kpis=tuple(fc.KPIS), workers=None, verbose=True):
    t0 = time.time()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    daily = fc.load_daily(data_dir)
    holidays = fc.load_holidays(data_dir)
    b = fc.split_boundaries(daily)
    dev_mask = daily["date"] <= b["dev_end"]
    peak_threshold = float(daily.loc[dev_mask, "new_workload_units"].quantile(0.9))
    periods = {"validation": (b["val_start"], b["val_end"], b["dev_end"]),
               "final": (b["test_start"], b["test_end"], b["val_end"])}

    tuning, preds, repro = [], [], {}
    for kpi in kpis:
        panel = fc.build_panel(daily, kpi)
        prophet_cache = {}

        def predict(method, cfg, horizon, period):
            start, end, cutoff = periods[period]
            if method == "prophet":
                key = (cfg, period)
                if key not in prophet_cache:
                    rows14 = _period_rows(panel, daily, start, end, "fourteen_day")
                    t = time.time()
                    prophet_cache[key] = pd.Series(
                        fc.predict_method(method, cfg, daily, panel, kpi, "fourteen_day", cutoff, rows14, holidays, workers)[0],
                        index=rows14.index)
                    if verbose:
                        print(f"  prophet {kpi} {cfg} {period}: {len(rows14)} rows in {time.time() - t:.0f}s", flush=True)
                rows = _period_rows(panel, daily, start, end, horizon)
                return rows, prophet_cache[key].loc[rows.index].to_numpy()
            rows = _period_rows(panel, daily, start, end, horizon)
            return rows, fc.predict_method(method, cfg, daily, panel, kpi, horizon, cutoff, rows, holidays, workers)[0]

        for horizon in fc.HORIZONS:
            for method in fc.MODELS:
                scores = {}
                for cfg in fc.candidates(method, horizon):
                    rows, p = predict(method, cfg, horizon, "validation")
                    scored = fc.scope_rows(rows.assign(forecast=p), horizon, b["val_end"])
                    scores[cfg] = fc.metrics(scored["actual"], scored["forecast"])["mae"]
                chosen = min(scores, key=scores.get)
                for cfg, mae in scores.items():
                    tuning.append({"kpi": kpi, "horizon": horizon, "model": method, "config": cfg,
                                   "validation_mae": mae, "chosen": cfg == chosen})
                if verbose:
                    print(f"{kpi} {horizon} {method}: chose {chosen} {scores}", flush=True)
                for period in periods:
                    rows, p = predict(method, chosen, horizon, period)
                    end = periods[period][1]
                    scored_idx = fc.scope_rows(rows.assign(forecast=p), horizon, end).index
                    preds.append(pd.DataFrame({
                        "period": period, "kpi": kpi, "horizon": horizon, "model": method, "config": chosen,
                        "origin_date": rows["origin_date"].dt.strftime("%Y-%m-%d"),
                        "target_date": rows["target_date"].dt.strftime("%Y-%m-%d"),
                        "h": rows["h"], "forecast": np.round(p, 6), "actual": rows["actual"],
                        "actual_workload": rows["actual_workload"],
                        "is_peak_day": (rows["actual_workload"] >= peak_threshold).astype(int),
                        "is_peak_season": rows["is_peak_season"], "dow": rows["dow"],
                        "scored": rows.index.isin(scored_idx).astype(int),
                    }))

        # Reproduce the existing Week 11 Random Forest results inside the new framework.
        rows = _period_rows(panel, daily, b["test_start"], b["test_end"], "next_day")
        repro[kpi] = {}
        for cfg in ("existing_original", "existing_revised"):
            p = fc.predict_method("random_forest", cfg, daily, panel, kpi, "next_day", b["val_end"], rows, holidays)[0]
            repro[kpi][cfg] = fc.metrics(rows["actual"], p)

    tuning = pd.DataFrame(tuning)
    preds = pd.concat(preds, ignore_index=True)
    summary = summarise(preds, b)
    segments = segment_errors(preds)
    consistency = consistency_table(segments)
    uncertainty = uncertainty_table(preds, summary)
    selection = select_models(summary)

    tuning.to_csv(out_dir / "tuning.csv", index=False)
    preds.to_csv(out_dir / "predictions.csv.gz", index=False, compression="gzip")
    summary.to_csv(out_dir / "metrics.csv", index=False)
    segments.to_csv(out_dir / "segments.csv", index=False)
    consistency.to_csv(out_dir / "consistency.csv", index=False)
    uncertainty.to_csv(out_dir / "uncertainty.csv", index=False)

    week11 = ROOT / "models" / "week11_evaluation.csv"
    if week11.exists():
        w = pd.read_csv(week11)
        for kpi in repro:
            for cfg in list(repro[kpi]):
                ver = cfg.replace("existing_", "")
                ref = w[(w["KPI"] == kpi) & (w["Configuration"] == ver)]
                if len(ref):
                    repro[kpi][cfg]["week11_final_test_mae"] = float(ref["Final_test_MAE"].iloc[0])
                    repro[kpi][cfg]["matches_week11"] = bool(np.isclose(repro[kpi][cfg]["mae"], ref["Final_test_MAE"].iloc[0], rtol=1e-9, atol=1e-9))
    (out_dir / "reproduction.json").write_text(json.dumps(repro, indent=2))
    (out_dir / "selection.json").write_text(json.dumps(selection, indent=2))
    (out_dir / "protocol.json").write_text(json.dumps(protocol(b, peak_threshold, daily, time.time() - t0), indent=2, default=str))
    if verbose:
        print(summary.to_string())
        print(json.dumps(selection, indent=2))
        print(json.dumps(repro, indent=2))
    return summary, selection


def summarise(preds: pd.DataFrame, b: dict) -> pd.DataFrame:
    rows = []
    sc = preds[preds["scored"] == 1]
    for (period, kpi, horizon), g in sc.groupby(["period", "kpi", "horizon"], sort=False):
        keysets = {m: set(zip(x["origin_date"], x["target_date"])) for m, x in g.groupby("model")}
        ref = next(iter(keysets.values()))
        if any(k != ref for k in keysets.values()):
            raise AssertionError(f"Models scored on different dates for {period}/{kpi}/{horizon}")
        base = fc.metrics(g.loc[g["model"] == "weekday_average", "actual"], g.loc[g["model"] == "weekday_average", "forecast"])
        # Per-origin mean absolute error (one value per origin) for the Diebold-Mariano test.
        g = g.assign(abs_err=(g["actual"] - g["forecast"]).abs())
        origin_loss = g.groupby(["model", "origin_date"])["abs_err"].mean()
        base_loss = origin_loss.loc["weekday_average"]
        lag = fc.MAX_H - 1 if horizon == "fourteen_day" else 0
        for model, x in g.groupby("model"):
            m = fc.metrics(x["actual"], x["forecast"])
            dm = fc.dm_test(origin_loss.loc[model].loc[base_loss.index], base_loss, lag) if model != "weekday_average" else {"dm_stat": np.nan, "p_value": np.nan}
            pk = x[x["is_peak_day"] == 1]
            pm = fc.metrics(pk["actual"], pk["forecast"])
            rows.append({
                "period": period, "kpi": kpi, "horizon": horizon, "model": model, "config": x["config"].iloc[0],
                "mae": m["mae"], "rmse": m["rmse"], "wape_pct": m["wape"], "bias": m["bias"],
                "improvement_vs_baseline_pct": np.nan if model == "weekday_average" else fc.improvement_pct(m["mae"], base["mae"]),
                "dm_stat_vs_baseline": dm["dm_stat"], "dm_p_vs_baseline": dm["p_value"],
                "peak_mae": pm["mae"], "peak_bias": pm["bias"], "peak_n": pm["n"],
                "n_forecasts": m["n"], "n_origins": x["origin_date"].nunique(),
                "first_target": x["target_date"].min(), "last_target": x["target_date"].max(),
            })
    s = pd.DataFrame(rows)
    s["rank"] = s.groupby(["period", "kpi", "horizon"])["mae"].rank(method="min").astype(int)
    order = {m: i for i, m in enumerate(fc.MODELS)}
    return s.sort_values(["period", "kpi", "horizon", "model"], key=lambda c: c.map(order) if c.name == "model" else c).reset_index(drop=True)


def segment_errors(preds: pd.DataFrame) -> pd.DataFrame:
    sc = preds[preds["scored"] == 1].copy()
    sc["month"] = sc["target_date"].str[:7]
    sc["err"] = sc["actual"] - sc["forecast"]
    out = []
    for field in ["month", "dow", "is_peak_season", "is_peak_day", "h"]:
        g = sc.groupby(["period", "kpi", "horizon", "model", field])
        t = g.agg(n=("err", "size"), mae=("err", lambda e: float(np.mean(np.abs(e)))), bias=("err", "mean")).reset_index()
        t = t.rename(columns={field: "segment"})
        t["segment"] = t["segment"].astype(str)
        t.insert(4, "group", field)
        out.append(t)
    return pd.concat(out, ignore_index=True)


def consistency_table(segments: pd.DataFrame) -> pd.DataFrame:
    m = segments[segments["group"] == "month"].copy()
    m["rank"] = m.groupby(["period", "kpi", "horizon", "segment"])["mae"].rank(method="min")
    base = m[m["model"] == "weekday_average"].set_index(["period", "kpi", "horizon", "segment"])["mae"]
    m["beats_baseline"] = m.apply(lambda r: r["mae"] < base.loc[(r["period"], r["kpi"], r["horizon"], r["segment"])], axis=1)
    return (m.groupby(["period", "kpi", "horizon", "model"])
            .agg(months=("segment", "nunique"), months_ranked_first=("rank", lambda r: int((r == 1).sum())),
                 months_beating_baseline=("beats_baseline", "sum"), worst_month_mae=("mae", "max"),
                 best_month_mae=("mae", "min"))
            .reset_index())


def select_models(summary: pd.DataFrame) -> dict:
    sel = {}
    v = summary[summary["period"] == "validation"]
    f = summary[summary["period"] == "final"].set_index(["kpi", "horizon", "model"])
    for (kpi, horizon), g in v.groupby(["kpi", "horizon"]):
        best = g.sort_values("mae").iloc[0]
        fin = f.loc[(kpi, horizon, best["model"])]
        fin_rank = int(fin["rank"])
        sel.setdefault(kpi, {})[horizon] = {
            "model": best["model"], "config": best["config"],
            "validation_mae": float(best["mae"]), "validation_rmse": float(best["rmse"]),
            "validation_wape_pct": float(best["wape_pct"]), "validation_bias": float(best["bias"]),
            "validation_improvement_vs_baseline_pct": None if best["model"] == "weekday_average" else float(best["improvement_vs_baseline_pct"]),
            "validation_runner_up": g.sort_values("mae").iloc[1]["model"],
            "validation_margin_vs_runner_up_pct": float((g.sort_values("mae").iloc[1]["mae"] - best["mae"]) / g.sort_values("mae").iloc[1]["mae"] * 100),
            "validation_dm_p_vs_baseline": None if best["model"] == "weekday_average" else float(best["dm_p_vs_baseline"]),
            "final_mae": float(fin["mae"]), "final_rank": fin_rank,
            "final_improvement_vs_baseline_pct": None if best["model"] == "weekday_average" else float(fin["improvement_vs_baseline_pct"]),
            "final_dm_p_vs_baseline": None if best["model"] == "weekday_average" else float(fin["dm_p_vs_baseline"]),
            "final_best_model": f.loc[(kpi, horizon)].sort_values("mae").index[0],
            "rule": "Lowest validation MAE; RMSE, WAPE, bias and peak-day error reported as supporting evidence.",
        }
        s = sel[kpi][horizon]
        s["significantly_better_than_baseline"] = bool(
            s["model"] != "weekday_average" and s["validation_dm_p_vs_baseline"] < 0.05
            and s["validation_improvement_vs_baseline_pct"] > 0)
    return sel


def uncertainty_table(preds: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Empirical 80th/90th percentile absolute error by horizon, from VALIDATION rows only."""
    v = preds[(preds["period"] == "validation") & (preds["scored"] == 1)].copy()
    v["abs_err"] = (v["actual"] - v["forecast"]).abs()
    v["under"] = (v["actual"] - v["forecast"]).clip(lower=0)
    return (v.groupby(["kpi", "horizon", "model", "h"])
            .agg(n=("abs_err", "size"), q80_abs_error=("abs_err", lambda e: float(np.quantile(e, 0.8))),
                 q80_under_forecast=("under", lambda e: float(np.quantile(e, 0.8))))
            .reset_index())


def protocol(b, peak_threshold, daily, seconds) -> dict:
    import sklearn
    versions = {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                "scikit-learn": sklearn.__version__}
    for mod in ("xgboost", "prophet"):
        try:
            versions[mod] = __import__(mod).__version__
        except Exception:  # pragma: no cover
            versions[mod] = "not installed"
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "runtime_seconds": round(seconds, 1),
        "versions": versions,
        "operating_days": len(daily),
        "boundaries": {k: str(v.date()) for k, v in b.items()},
        "forecast_origin_rule": "A forecast issued at the end of operating day t uses outcomes from operating days <= t only. "
                                "Targets are the next 1..14 operating days. Target-day calendar (weekday, month, peak-season "
                                "flag, published holidays) is treated as known in advance. Promotions, staffing outcomes, "
                                "productivity and backlog after the origin are never used.",
        "tuning": "Each configuration was trained on targets observed by the development cut-off and scored on validation "
                  "origins only. The lowest-validation-MAE configuration was refitted on development + validation targets "
                  "and scored once on the final period.",
        "prophet": "Refitted at every forecast origin on all history <= origin; weekly + yearly seasonality and the published "
                   "holiday calendar from dim_date.",
        "tabular_models": "Random Forest and XGBoost are trained once per period (on targets <= cut-off) and predict from "
                          "origin-anchored features. Next-day uses horizon-1 rows; 14-day uses one direct model pooled over "
                          "horizons 1..14 with horizon as a feature (no recursive use of predictions).",
        "weekday_average": "Expanding mean of all observations on the target's weekday up to and including the origin day.",
        "scoring": "Next day: every origin whose next operating day is in the period. 14 days: origins whose complete "
                   "14-day window lies inside the period; all 14 horizons pooled. Identical origins/targets for all methods.",
        "peak_demand_definition": f"Target days whose actual workload >= {peak_threshold:.1f} WLU (90th percentile of the "
                                  "development period). Classification is post hoc and is used only for diagnostics.",
        "bias_sign": "Bias = mean(actual - forecast). Positive = under-forecast.",
        "final_period_status": "Retrospective: the final period (same dates as the Week 11 final test) was already viewed in "
                               "Week 11. It was not used for any tuning or selection here, but it is not an untouched test.",
        "limitations": [
            "Fully synthetic data; results describe internal simulated performance only.",
            "Validation MAE of tuned methods is slightly optimistic because configurations were selected on the same window.",
            "Overlapping 14-day windows reuse target days; forecasts are not independent observations.",
            "Scheduled staffing is constant (25 workers / 200 hours), so no model learns staffing effects on productivity.",
            "Promotion flags are excluded because a timestamped promotion calendar is not available.",
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=None, help="Processes for Prophet refits (default: all cores)")
    args = ap.parse_args()
    run(workers=args.workers)
