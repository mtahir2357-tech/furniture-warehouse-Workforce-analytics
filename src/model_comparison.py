"""Read-only access to the Week 12 forecasting comparison artifacts (models/forecast_comparison/).

The Streamlit app never retrains: it loads results produced by `python evaluate_forecasting.py`.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st

from src.config import BASE_DIR

COMPARISON_DIR = BASE_DIR / "models" / "forecast_comparison"
MODELS = ["weekday_average", "random_forest", "xgboost", "prophet"]
MODEL_LABELS = {"weekday_average": "Weekday Average", "random_forest": "Random Forest",
                "xgboost": "XGBoost", "prophet": "Prophet"}
KPI_LABELS = {"workload": "Daily Workload", "productivity": "Labor Productivity"}
KPI_UNITS = {"workload": "WLU", "productivity": "WLU/hour"}
HORIZON_LABELS = {"next_day": "Next operating day", "fourteen_day": "Next 14 operating days"}
PERIOD_LABELS = {"validation": "Validation (used for selection)", "final": "Final period (retrospective)"}


def available() -> bool:
    return all((COMPARISON_DIR / f).exists() for f in ("metrics.csv", "predictions.csv.gz", "selection.json"))


@st.cache_data(show_spinner=False)
def metrics() -> pd.DataFrame:
    return pd.read_csv(COMPARISON_DIR / "metrics.csv")


@st.cache_data(show_spinner="Loading saved model forecasts…")
def predictions() -> pd.DataFrame:
    p = pd.read_csv(COMPARISON_DIR / "predictions.csv.gz", parse_dates=["origin_date", "target_date"])
    return p


@st.cache_data(show_spinner=False)
def selection() -> dict:
    return json.loads((COMPARISON_DIR / "selection.json").read_text())


@st.cache_data(show_spinner=False)
def protocol() -> dict:
    return json.loads((COMPARISON_DIR / "protocol.json").read_text())


@st.cache_data(show_spinner=False)
def reproduction() -> dict:
    path = COMPARISON_DIR / "reproduction.json"
    return json.loads(path.read_text()) if path.exists() else {}


@st.cache_data(show_spinner=False)
def segments() -> pd.DataFrame:
    return pd.read_csv(COMPARISON_DIR / "segments.csv")


@st.cache_data(show_spinner=False)
def consistency() -> pd.DataFrame:
    return pd.read_csv(COMPARISON_DIR / "consistency.csv")


@st.cache_data(show_spinner=False)
def uncertainty() -> pd.DataFrame:
    return pd.read_csv(COMPARISON_DIR / "uncertainty.csv")


def comparison_table(m: pd.DataFrame, period: str, kpi: str, horizon: str) -> pd.DataFrame:
    """The four-method table, in a fixed model order, straight from the saved evaluation."""
    t = m[(m["period"] == period) & (m["kpi"] == kpi) & (m["horizon"] == horizon)].copy()
    t["order"] = t["model"].map({k: i for i, k in enumerate(MODELS)})
    t = t.sort_values("order")
    return pd.DataFrame({
        "model": t["model"].to_numpy(),
        "Model": t["model"].map(MODEL_LABELS).to_numpy(),
        "MAE": t["mae"].to_numpy(),
        "RMSE": t["rmse"].to_numpy(),
        "WAPE (%)": t["wape_pct"].to_numpy(),
        "Bias": t["bias"].to_numpy(),
        "Improvement vs Baseline (%)": [("Reference" if mdl == "weekday_average" else f"{v:+.2f}")
                                        for mdl, v in zip(t["model"], t["improvement_vs_baseline_pct"])],
        "p-value vs baseline": [("—" if mdl == "weekday_average" else f"{v:.2f}")
                                for mdl, v in zip(t["model"], t["dm_p_vs_baseline"])],
        "Peak-day MAE": t["peak_mae"].to_numpy(),
        "Rank": t["rank"].astype(int).to_numpy(),
    })


def selected_path(kpi: str, origin: pd.Timestamp, horizon: str = "fourteen_day") -> pd.DataFrame:
    """Out-of-sample forecasts of the validation-selected method for one forecast origin.

    Validation-period origins come from models trained on development data; final-period
    origins from models trained on development + validation data. Empty if not available.
    """
    sel = selection()[kpi][horizon]
    p = predictions()
    rows = p[(p["kpi"] == kpi) & (p["horizon"] == horizon) & (p["model"] == sel["model"])
             & (p["origin_date"] == pd.Timestamp(origin))]
    if rows["period"].nunique() > 1:  # an origin belongs to exactly one period
        rows = rows[rows["period"] == rows["period"].iloc[0]]
    return rows.sort_values("h").reset_index(drop=True)


def origin_range(horizon: str = "fourteen_day"):
    p = predictions()
    p = p[p["horizon"] == horizon]
    return p["origin_date"].min(), p["origin_date"].max()


def under_forecast_buffer(kpi: str, horizon: str = "fourteen_day") -> pd.Series:
    """80th percentile of validation under-forecast by horizon for the selected method."""
    u = uncertainty()
    sel = selection()[kpi][horizon]["model"]
    x = u[(u["kpi"] == kpi) & (u["horizon"] == horizon) & (u["model"] == sel)]
    return x.set_index("h")["q80_under_forecast"].astype(float) if len(x) else pd.Series(dtype=float)


def describe_selection(kpi: str, horizon: str) -> str:
    s = selection()[kpi][horizon]
    name = MODEL_LABELS[s["model"]]
    unit = KPI_UNITS[kpi]
    fmt = (lambda v: f"{v:,.2f}") if kpi == "workload" else (lambda v: f"{v:.4f}")
    if s["model"] == "weekday_average":
        return (f"{name} has the lowest validation MAE ({fmt(s['validation_mae'])} {unit}); none of the trained "
                f"models beat the baseline on validation.")
    sig = ("statistically significant" if s["significantly_better_than_baseline"]
           else f"not statistically significant (Diebold-Mariano p = {s['validation_dm_p_vs_baseline']:.2f})")
    return (f"{name} has the lowest validation MAE ({fmt(s['validation_mae'])} {unit}), "
            f"{s['validation_improvement_vs_baseline_pct']:+.2f}% versus the weekday-average baseline; the difference is {sig}.")


def safe_ratio(a, b):
    return a / b if b else np.nan
