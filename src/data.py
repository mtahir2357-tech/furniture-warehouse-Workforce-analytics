"""Cached loaders for the 12-table relational dataset."""
import pandas as pd
import streamlit as st

from src.config import DATA_DIR, SCENARIO_LABELS


def key_to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(int).astype(str), format="%Y%m%d")


@st.cache_data(show_spinner=False)
def load_table(name: str, usecols=None) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing data file: {path}. Put all 12 CSV files in the 'data' folder next to app.py."
        )
    return pd.read_csv(path, usecols=usecols)


@st.cache_data(show_spinner=False)
def dim_date() -> pd.DataFrame:
    d = load_table("dim_date").copy()
    d["date"] = pd.to_datetime(d["date"])
    return d


@st.cache_data(show_spinner=False)
def daily() -> pd.DataFrame:
    """One row per operating day, with calendar attributes."""
    d = load_table("fact_daily_outcome").copy()
    d["date_key"] = d["date_key"].astype(int)
    d = d.merge(dim_date(), on="date_key", how="left")
    d["capacity_gap_hours"] = -d["labor_gap_hours"]  # Week 6 sign: available - required
    return d.sort_values("date").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def forecasts() -> pd.DataFrame:
    """Forecast rows joined to their baseline (current plan) scenario result."""
    f = load_table("fact_workload_forecast").copy()
    s = load_table("fact_staffing_scenario")
    base = s[s["scenario_id"] == "S01"][
        [
            "forecast_id",
            "projected_required_labor_hours",
            "expected_total_available_hours",
            "projected_labor_gap_hours",
            "projected_capacity_utilization",
            "projected_unprocessed_wlu",
            "projected_total_labor_cost",
            "projected_manager_labor_cost",
            "avg_worker_hourly_rate",
        ]
    ]
    f = f.merge(base, on="forecast_id", how="left")
    f["forecast_date"] = key_to_date(f["forecast_date_key"])
    f["target_date"] = key_to_date(f["target_date_key"])
    f["capacity_gap_hours"] = -f["projected_labor_gap_hours"]
    f["availability_ratio"] = f["expected_available_regular_hours"] / f["planned_regular_hours"]
    d = dim_date()[["date", "day_name", "holiday_name", "is_holiday", "is_peak_season"]]
    f = f.merge(d.rename(columns={"date": "target_date"}), on="target_date", how="left")
    return f


@st.cache_data(show_spinner=False)
def scenarios() -> pd.DataFrame:
    s = load_table("fact_staffing_scenario").copy()
    s["target_date"] = key_to_date(s["target_date_key"])
    s["forecast_date"] = key_to_date(s["forecast_date_key"])
    s["scenario_label"] = s["scenario_id"].map(SCENARIO_LABELS)
    s["capacity_gap_hours"] = -s["projected_labor_gap_hours"]
    return s


@st.cache_data(show_spinner=False)
def forecast_runs() -> list:
    return sorted(forecasts()["forecast_date"].unique())


@st.cache_data(show_spinner=False)
def scenario_definitions() -> pd.DataFrame:
    return load_table("dim_scenario")


@st.cache_data(show_spinner="Loading order lines…")
def product_mix() -> pd.DataFrame:
    """Order-line WLU and revenue with product category and release date."""
    lines = load_table("fact_order_line", usecols=["order_id", "product_id", "quantity_pieces", "line_revenue", "line_workload_units"])
    orders = load_table("fact_order", usecols=["order_id", "release_date_key"])
    prod = load_table("dim_product")[["product_id", "product_category", "handling_class", "workload_weight"]]
    m = lines.merge(orders, on="order_id").merge(prod, on="product_id")
    m["release_date"] = key_to_date(m["release_date_key"])
    return m


@st.cache_data(show_spinner="Loading workflow events…")
def workflow_durations() -> pd.DataFrame:
    """Average minutes per workflow activity, by order release month."""
    ev = load_table("fact_workflow_event", usecols=["order_id", "activity_sequence", "duration_minutes"])
    orders = load_table("fact_order", usecols=["order_id", "release_date_key"])
    act = load_table("dim_workflow_activity")
    ev = ev.merge(orders, on="order_id", how="left")
    ev["release_date"] = key_to_date(ev["release_date_key"])
    ev = ev.merge(act, on="activity_sequence", how="left")
    ev = ev[ev["is_processing_activity"] == 1]
    return ev[["release_date", "activity_sequence", "activity_name", "duration_minutes"]]
