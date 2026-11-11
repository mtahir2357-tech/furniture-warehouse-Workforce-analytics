"""Common chronological evaluation framework for the two predictive KPIs (Week 12).

Four forecasting methods are compared on identical forecast origins and target days:

1. Weekday-average baseline  (expanding mean of the same weekday, history <= origin)
2. Random Forest regression  (existing Week 10/11 one-step features + origin-anchored direct features)
3. XGBoost regression        (origin-anchored direct features)
4. Prophet                   (refitted at every forecast origin on history <= origin)

Forecast-origin rule (applies to every method)
----------------------------------------------
A forecast made at origin ``t`` (end of operating day t) may only use outcomes recorded
on operating days <= t. Targets are the next 1..14 *operating* days. Target-day calendar
attributes (weekday, month, peak-season flag, published holiday) are treated as known
in advance. Target-day promotions, staffing outcomes, productivity and backlog are never
used as inputs beyond the origin.

This module has no Streamlit dependency so it can be tested and run from scripts.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

KPIS = {
    "workload": {"target": "new_workload_units", "label": "Daily Workload", "unit": "WLU"},
    "productivity": {"target": "actual_productivity_wlu_per_hour", "label": "Labor Productivity", "unit": "WLU/hour"},
}
MODELS = ["weekday_average", "random_forest", "xgboost", "prophet"]
MODEL_LABELS = {
    "weekday_average": "Weekday Average",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "prophet": "Prophet",
}
HORIZONS = {"next_day": "Next operating day", "fourteen_day": "Next 14 operating days"}
MAX_H = 14

# Existing (Week 10/11) one-step-ahead feature sets. Only valid at horizon 1, because their
# "lag1" / "beginning backlog" values are the origin-day outcome only when the target is t+1.
EXISTING_FEATURES = {
    "workload": ["day_of_week_number", "month_number", "is_peak_season", "is_holiday",
                 "workload_lag1", "workload_lag7", "workload_rolling7"],
    "productivity": ["day_of_week_number", "month_number", "is_peak_season", "beginning_backlog_wlu",
                     "scheduled_worker_count", "scheduled_worker_hours",
                     "productivity_lag1", "productivity_lag7", "productivity_rolling7"],
}

# Origin-anchored ("direct") features: valid for every horizon 1..14.
CALENDAR_FEATURES = ["h", "dow", "month", "is_peak_season", "is_holiday"]
HISTORY_FEATURES = ["last", "mean7", "mean28", "std28", "ewm14", "wd_last", "wd_mean4", "wd_expanding"]
ENHANCED_FEATURES = {
    "workload": CALENDAR_FEATURES + HISTORY_FEATURES,
    "productivity": CALENDAR_FEATURES + HISTORY_FEATURES + ["origin_ending_backlog_wlu"],
}

RF_CANDIDATES = {
    # name: (feature set, parameters). "existing_*" are the Week 10 / Week 11 configurations.
    "existing_original": ("existing", dict(n_estimators=140, min_samples_leaf=4, max_features=0.85)),
    "existing_revised": ("existing", dict(n_estimators=240, min_samples_leaf=8, max_features=0.85)),
    "enhanced_revised": ("enhanced", dict(n_estimators=240, min_samples_leaf=8, max_features=0.85)),
    "enhanced_leaf16": ("enhanced", dict(n_estimators=240, min_samples_leaf=16, max_features=0.6)),
}
XGB_CANDIDATES = {
    "d2_lr05": dict(max_depth=2, learning_rate=0.05, n_estimators=400),
    "d3_lr05": dict(max_depth=3, learning_rate=0.05, n_estimators=400),
    "d4_lr05": dict(max_depth=4, learning_rate=0.05, n_estimators=400),
    "d3_lr03": dict(max_depth=3, learning_rate=0.03, n_estimators=800),
    "d2_lr03_l10": dict(max_depth=2, learning_rate=0.03, n_estimators=600, reg_lambda=10.0),
    "d3_lr05_mae": dict(max_depth=3, learning_rate=0.05, n_estimators=400, objective="reg:absoluteerror"),
}
XGB_COMMON = dict(subsample=0.8, colsample_bytree=0.8, min_child_weight=5, random_state=42,
                  n_jobs=4, tree_method="hist")
PROPHET_CANDIDATES = {
    "additive_cps005": dict(seasonality_mode="additive", changepoint_prior_scale=0.05),
    "additive_cps05": dict(seasonality_mode="additive", changepoint_prior_scale=0.5),
    "multiplicative_cps005": dict(seasonality_mode="multiplicative", changepoint_prior_scale=0.05),
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_daily(data_dir: Path) -> pd.DataFrame:
    """One row per operating day, sorted chronologically, with calendar attributes."""
    data_dir = Path(data_dir)
    d = pd.read_csv(data_dir / "fact_daily_outcome.csv")
    cal = pd.read_csv(data_dir / "dim_date.csv")[
        ["date_key", "date", "day_of_week_number", "month_number", "is_peak_season", "is_holiday", "holiday_name"]
    ]
    d = d.merge(cal, on="date_key", how="left", validate="one_to_one")
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").reset_index(drop=True)
    if d["date"].duplicated().any():
        raise ValueError("Duplicate operating dates.")
    return d


def load_holidays(data_dir: Path) -> pd.DataFrame:
    """Published holiday calendar (known in advance) in Prophet's format."""
    cal = pd.read_csv(Path(data_dir) / "dim_date.csv")
    h = cal.loc[cal["is_holiday"] == 1, ["holiday_name", "date"]].rename(columns={"holiday_name": "holiday", "date": "ds"})
    h["ds"] = pd.to_datetime(h["ds"])
    return h.reset_index(drop=True)


def split_boundaries(daily: pd.DataFrame) -> dict:
    """Chronological 64% / 16% / 20% split identical to Week 11 (`evaluate_week11.py`).

    Week 11 dropped the first 7 operating days (lag warm-up) and split the remaining rows.
    Reusing the same dates keeps the final period aligned with earlier reported results.
    """
    n_eff = len(daily) - 7
    dev_last = 7 + int(n_eff * 0.64) - 1
    test_first = 7 + int(n_eff * 0.8)
    return {
        "dev_end": daily.loc[dev_last, "date"],
        "val_start": daily.loc[dev_last + 1, "date"],
        "val_end": daily.loc[test_first - 1, "date"],
        "test_start": daily.loc[test_first, "date"],
        "test_end": daily["date"].iloc[-1],
    }


# ---------------------------------------------------------------------------
# Features (all computed from history <= origin)
# ---------------------------------------------------------------------------
def origin_stats(daily: pd.DataFrame, kpi: str) -> tuple[pd.DataFrame, dict]:
    """Per-origin history statistics. Row i uses only operating days 0..i."""
    y = daily[KPIS[kpi]["target"]].astype(float)
    o = pd.DataFrame(index=daily.index)
    o["last"] = y
    o["mean7"] = y.rolling(7).mean()
    o["mean28"] = y.rolling(28).mean()
    o["std28"] = y.rolling(28).std()
    o["ewm14"] = y.ewm(span=14, adjust=False).mean()
    o["origin_ending_backlog_wlu"] = daily["ending_backlog_wlu"].astype(float)
    dow = daily["day_of_week_number"].astype(int)
    wd = {}
    for w in range(1, 8):
        mask = dow == w
        sub = y[mask]
        wd[("last", w)] = y.where(mask).ffill().to_numpy()
        wd[("mean4", w)] = sub.rolling(4).mean().reindex(daily.index).ffill().to_numpy()
        wd[("expanding", w)] = sub.expanding().mean().reindex(daily.index).ffill().to_numpy()
    return o, wd


def build_panel(daily: pd.DataFrame, kpi: str, max_h: int = MAX_H) -> pd.DataFrame:
    """One row per (forecast origin, horizon h) with the target h operating days later."""
    n = len(daily)
    target = KPIS[kpi]["target"]
    o, wd = origin_stats(daily, kpi)
    origin = np.repeat(np.arange(n), max_h)
    h = np.tile(np.arange(1, max_h + 1), n)
    j = origin + h
    keep = j < n
    origin, h, j = origin[keep], h[keep], j[keep]
    p = pd.DataFrame({"origin_idx": origin, "target_idx": j, "h": h})
    p["origin_date"] = daily["date"].to_numpy()[origin]
    p["target_date"] = daily["date"].to_numpy()[j]
    tdow = daily["day_of_week_number"].astype(int).to_numpy()[j]
    p["dow"] = tdow
    p["month"] = daily["month_number"].to_numpy()[j]
    p["is_peak_season"] = daily["is_peak_season"].to_numpy()[j]
    p["is_holiday"] = daily["is_holiday"].to_numpy()[j]
    for c in ["last", "mean7", "mean28", "std28", "ewm14", "origin_ending_backlog_wlu"]:
        p[c] = o[c].to_numpy()[origin]
    for name, col in [("last", "wd_last"), ("mean4", "wd_mean4"), ("expanding", "wd_expanding")]:
        mat = np.column_stack([wd[(name, w)] for w in range(1, 8)])
        p[col] = mat[origin, tdow - 1]
    p["actual"] = daily[target].astype(float).to_numpy()[j]
    p["actual_workload"] = daily["new_workload_units"].astype(float).to_numpy()[j]

    # Existing one-step features, reproduced exactly as in train_models.make_frame, defined only at h == 1.
    ex = pd.DataFrame(index=daily.index)
    ex["day_of_week_number"] = daily["day_of_week_number"]
    ex["month_number"] = daily["month_number"]
    ex["beginning_backlog_wlu"] = daily["beginning_backlog_wlu"]
    ex["scheduled_worker_count"] = daily["scheduled_worker_count"]
    ex["scheduled_worker_hours"] = daily["scheduled_worker_hours"]
    for source, prefix in [("new_workload_units", "workload"), ("actual_productivity_wlu_per_hour", "productivity")]:
        ex[f"{prefix}_lag1"] = daily[source].shift(1)
        ex[f"{prefix}_lag7"] = daily[source].shift(7)
        ex[f"{prefix}_rolling7"] = daily[source].shift(1).rolling(7).mean()
    one = p["h"].to_numpy() == 1
    for c in sorted(set(EXISTING_FEATURES["workload"] + EXISTING_FEATURES["productivity"]) - {"is_peak_season", "is_holiday"}):
        vals = ex[c].to_numpy(dtype=float)[j]
        p[c] = np.where(one, vals, np.nan)
    return p


def feature_list(kpi: str, feature_set: str) -> list:
    return EXISTING_FEATURES[kpi] if feature_set == "existing" else ENHANCED_FEATURES[kpi]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def metrics(actual, forecast) -> dict:
    """MAE, RMSE, WAPE (%), mean bias (actual - forecast; positive = under-forecast)."""
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if len(a) == 0:
        return {"mae": np.nan, "rmse": np.nan, "wape": np.nan, "bias": np.nan, "n": 0}
    e = a - f
    return {
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "wape": float(np.sum(np.abs(e)) / np.sum(np.abs(a)) * 100) if np.sum(np.abs(a)) else np.nan,
        "bias": float(np.mean(e)),
        "n": int(len(a)),
    }


def improvement_pct(model_mae: float, baseline_mae: float) -> float:
    return float((baseline_mae - model_mae) / baseline_mae * 100) if baseline_mae else np.nan


def dm_test(loss_model, loss_base, lag: int = 0) -> dict:
    """Diebold-Mariano test of equal mean absolute error (two-sided, normal approximation).

    Loss differential d = |e_model| - |e_base| per forecast origin. ``lag`` sets the Newey-West
    (Bartlett) autocovariance window; use h-1 = 13 for overlapping 14-day windows.
    Negative statistic = the model has lower error than the baseline.
    """
    import math

    d = np.asarray(loss_model, dtype=float) - np.asarray(loss_base, dtype=float)
    n = len(d)
    if n < 10:
        return {"dm_stat": np.nan, "p_value": np.nan, "n": n}
    dc = d - d.mean()
    var = float(np.dot(dc, dc) / n)
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * float(np.dot(dc[k:], dc[:-k]) / n)
    if var <= 0:
        return {"dm_stat": np.nan, "p_value": np.nan, "n": n}
    stat = float(d.mean() / math.sqrt(var / n))
    return {"dm_stat": stat, "p_value": float(math.erfc(abs(stat) / math.sqrt(2))), "n": n}


# ---------------------------------------------------------------------------
# Evaluation design
# ---------------------------------------------------------------------------
def origins_for_period(daily: pd.DataFrame, start, end) -> np.ndarray:
    """Origin indices whose next operating day falls inside [start, end]."""
    dates = daily["date"]
    tgt = np.where((dates >= start) & (dates <= end))[0]
    return tgt - 1


def training_rows(panel: pd.DataFrame, cutoff, features: list, horizon: str) -> pd.DataFrame:
    """Rows whose *target* outcome is observed by the cutoff date (no peeking past the cutoff)."""
    rows = panel[panel["target_date"] <= cutoff]
    if horizon == "next_day":
        rows = rows[rows["h"] == 1]
    return rows.dropna(subset=features + ["actual"])


def scope_rows(pred: pd.DataFrame, horizon: str, period_end) -> pd.DataFrame:
    """Rows used for scoring: next-day = h 1; 14-day = complete 14-day windows inside the period."""
    if horizon == "next_day":
        return pred[pred["h"] == 1]
    last_origin_ok = pred.groupby("origin_date")["target_date"].transform("max")
    full = pred.groupby("origin_date")["h"].transform("max") == MAX_H
    return pred[full & (last_origin_ok <= period_end)]


# ---------------------------------------------------------------------------
# Model fitting / prediction
# ---------------------------------------------------------------------------
def make_rf(params: dict):
    from sklearn.ensemble import RandomForestRegressor
    return RandomForestRegressor(random_state=42, n_jobs=-1, **params)


def make_xgb(params: dict):
    from xgboost import XGBRegressor
    return XGBRegressor(**{**XGB_COMMON, **params})


def fit_predict_tabular(model, panel, cutoff, features, horizon, eval_rows):
    tr = training_rows(panel, cutoff, features, horizon)
    if len(tr) < 50:
        raise ValueError("Insufficient training history before the cutoff.")
    assert tr["target_date"].max() <= cutoff
    model.fit(tr[features].astype(float), tr["actual"].astype(float))
    x = eval_rows[features].astype(float)
    if x.isna().any().any():
        raise ValueError("Missing predictors at a forecast origin.")
    return np.clip(model.predict(x), 0, None), model


def _quiet_prophet():
    for name in ("cmdstanpy", "prophet"):
        logging.getLogger(name).setLevel(logging.ERROR)
        logging.getLogger(name).propagate = False


def prophet_origin_forecast(args) -> list:
    """Fit Prophet on history <= origin and forecast the given target dates (one origin)."""
    history, holidays, targets, params = args
    _quiet_prophet()
    from prophet import Prophet

    m = Prophet(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False,
                holidays=holidays, uncertainty_samples=0, **params)
    m.fit(history)
    fc = m.predict(pd.DataFrame({"ds": targets}))
    return np.clip(fc["yhat"].to_numpy(), 0, None).tolist()


def prophet_predictions(daily, kpi, holidays, eval_rows, params, workers=None) -> np.ndarray:
    """Refit Prophet at every forecast origin in eval_rows."""
    from concurrent.futures import ProcessPoolExecutor

    target = KPIS[kpi]["target"]
    hist_all = daily[["date", target]].rename(columns={"date": "ds", target: "y"})
    jobs, keys = [], []
    for origin_date, grp in eval_rows.groupby("origin_date", sort=True):
        hist = hist_all[hist_all["ds"] <= origin_date]
        assert hist["ds"].max() <= origin_date
        jobs.append((hist, holidays, grp["target_date"].to_numpy(), params))
        keys.append(grp.index.to_numpy())
    out = pd.Series(np.nan, index=eval_rows.index)
    if workers == 1:
        results = map(prophet_origin_forecast, jobs)
    else:
        ex = ProcessPoolExecutor(max_workers=workers)
        results = ex.map(prophet_origin_forecast, jobs, chunksize=4)
    for idx, vals in zip(keys, results):
        out.loc[idx] = vals
    if workers != 1:
        ex.shutdown()
    return out.to_numpy()


def predict_method(method, config, daily, panel, kpi, horizon, cutoff, eval_rows, holidays, workers=None):
    """Forecasts for eval_rows from one method/configuration trained on targets <= cutoff."""
    if method == "weekday_average":
        return eval_rows["wd_expanding"].to_numpy(dtype=float), None
    if method == "random_forest":
        fset, params = RF_CANDIDATES[config]
        if fset == "existing" and horizon != "next_day":
            raise ValueError("Existing one-step features are only valid for the next-day horizon.")
        return fit_predict_tabular(make_rf(params), panel, cutoff, feature_list(kpi, fset), horizon, eval_rows)
    if method == "xgboost":
        return fit_predict_tabular(make_xgb(XGB_CANDIDATES[config]), panel, cutoff,
                                   feature_list(kpi, "enhanced"), horizon, eval_rows)
    if method == "prophet":
        return prophet_predictions(daily, kpi, holidays, eval_rows, PROPHET_CANDIDATES[config], workers), None
    raise ValueError(method)


def candidates(method: str, horizon: str) -> list:
    if method == "weekday_average":
        return ["expanding_same_weekday"]
    if method == "random_forest":
        return [k for k, (fs, _) in RF_CANDIDATES.items() if horizon == "next_day" or fs == "enhanced"]
    if method == "xgboost":
        return list(XGB_CANDIDATES)
    return list(PROPHET_CANDIDATES)
