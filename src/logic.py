"""Decision logic. Formulas reproduce the pipeline's fact_staffing_scenario exactly.

Required Labor Hours = Workload / Productivity
Capacity Gap         = Available Labor Hours - Required Labor Hours  (negative = shortage)
"""
import numpy as np
import pandas as pd

from src.config import (
    EXCEEDANCE_RISK_BANDS,
    OVERTIME_MULTIPLIER,
    UTILIZATION_RISK_BANDS,
)
from src import data


def classify_gap(gap: float, tol: float) -> str:
    if gap < -tol:
        return "Shortage"
    if gap > tol:
        return "Surplus"
    return "Balanced"


def exceedance_risk(p: float) -> str:
    lo, hi = EXCEEDANCE_RISK_BANDS
    return "Low" if p < lo else ("Moderate" if p < hi else "High")


def backlog_risk(utilization: float) -> str:
    lo, hi = UTILIZATION_RISK_BANDS
    return "Low" if utilization < lo else ("Moderate" if utilization <= hi else "High")


def compute_scenario(
    workload: float,
    productivity: float,
    planned_regular_hours: float,
    overtime_hours: float,
    availability_ratio: float,
    hourly_rate: float,
    manager_cost: float,
    revenue_per_wlu: float,
) -> dict:
    """Recalculate one staffing scenario with the same rules as the data pipeline."""
    productivity = max(productivity, 1e-6)
    avail_regular = planned_regular_hours * availability_ratio
    total_available = avail_regular + overtime_hours
    required = workload / productivity
    capacity_wlu = total_available * productivity
    unprocessed = max(0.0, workload - capacity_wlu)
    shipped_wlu = workload - unprocessed
    utilization = required / total_available if total_available > 0 else np.inf
    regular_cost = avail_regular * hourly_rate
    overtime_cost = overtime_hours * hourly_rate * OVERTIME_MULTIPLIER
    total_cost = regular_cost + overtime_cost + manager_cost
    revenue = shipped_wlu * revenue_per_wlu
    return {
        "planned_regular_hours": planned_regular_hours,
        "expected_available_regular_hours": avail_regular,
        "planned_overtime_hours": overtime_hours,
        "expected_total_available_hours": total_available,
        "projected_required_labor_hours": required,
        "capacity_gap_hours": total_available - required,
        "projected_capacity_utilization": utilization,
        "projected_unprocessed_wlu": unprocessed,
        "projected_total_labor_cost": total_cost,
        "projected_same_day_shipped_revenue": revenue,
        "projected_labor_cost_pct_revenue": total_cost / revenue * 100 if revenue > 0 else np.nan,
    }


def snap_to_run(chosen) -> pd.Timestamp:
    """Latest forecast run on or before the chosen date."""
    runs = data.forecast_runs()
    chosen = pd.Timestamp(chosen)
    eligible = [r for r in runs if r <= chosen]
    return pd.Timestamp(eligible[-1] if eligible else runs[0])


def outlook(as_of: pd.Timestamp, tol: float) -> pd.DataFrame:
    """The 14 target days of one forecast run, with status and risk."""
    f = data.forecasts()
    o = f[f["forecast_date"] == as_of].sort_values("horizon_operating_days").copy()
    o["status"] = o["capacity_gap_hours"].apply(lambda g: classify_gap(g, tol))
    o["exceedance_risk"] = o["probability_capacity_exceeded"].apply(exceedance_risk)
    o["backlog_risk"] = o["projected_capacity_utilization"].apply(backlog_risk)
    o["required_at_upper"] = o["upper_80_workload_units"] / o["expected_productivity_wlu_per_hour"]
    o["gap_at_upper"] = o["expected_available_regular_hours"] - o["required_at_upper"]
    return o.reset_index(drop=True)


def scenario_table(forecast_id: int, tol: float) -> pd.DataFrame:
    s = data.scenarios()
    t = s[s["forecast_id"] == forecast_id].sort_values("scenario_id").copy()
    t["status"] = t["capacity_gap_hours"].apply(lambda g: classify_gap(g, tol))
    t["backlog_risk"] = t["projected_capacity_utilization"].apply(backlog_risk)
    return t.reset_index(drop=True)


def recent_average_workload(as_of: pd.Timestamp, days: int = 28) -> float:
    d = data.daily()
    hist = d[d["date"] < as_of].tail(days)
    return float(hist["new_workload_units"].mean()) if len(hist) else np.nan


def accuracy_metrics(f: pd.DataFrame) -> dict:
    if f.empty:
        return {k: np.nan for k in ["mae", "rmse", "wape", "bias", "coverage", "n"]}
    err = f["actual_workload_units"] - f["forecast_workload_units"]
    covered = (f["actual_workload_units"] >= f["lower_80_workload_units"]) & (
        f["actual_workload_units"] <= f["upper_80_workload_units"]
    )
    return {
        "mae": err.abs().mean(),
        "rmse": float(np.sqrt((err**2).mean())),
        "wape": err.abs().sum() / f["actual_workload_units"].sum(),
        "bias": err.mean(),
        "coverage": covered.mean(),
        "n": len(f),
    }


def recommend(day: pd.Series, table: pd.DataFrame, tol: float) -> dict:
    """Suggest one predefined action for a day. The manager still decides.

    Shortage -> cheapest action scenario that is no longer a shortage (else the one that closes most).
    Surplus  -> reduce regular hours if that does not create a shortage, else keep.
    Balanced -> keep; flag overtime on standby when the high-demand stress test turns it into a shortage.
    """
    t = table.set_index("scenario_id")
    base = t.loc["S01"]
    keep = {"scenario_id": "S01", "full": True, "standby": False}
    if day["status"] == "Shortage":
        opts = t.loc[["S02", "S03"]]
        fixes = opts[opts["status"] != "Shortage"].sort_values("projected_total_labor_cost")
        if len(fixes):
            pick = {"scenario_id": fixes.index[0], "full": True, "standby": False}
        else:
            pick = {"scenario_id": opts["capacity_gap_hours"].idxmax(), "full": False, "standby": False}
    elif day["status"] == "Surplus":
        red = t.loc["S06"]
        pick = {"scenario_id": "S06", "full": True, "standby": False} if red["status"] != "Shortage" else keep
    else:
        pick = {**keep, "standby": t.loc["S04", "status"] == "Shortage" and day["exceedance_risk"] == "High"}
    row = t.loc[pick["scenario_id"]]
    return {
        **pick,
        "row": row,
        "gap_before": base["capacity_gap_hours"],
        "gap_after": row["capacity_gap_hours"],
        "status_after": row["status"],
        "cost_delta": row["projected_total_labor_cost"] - base["projected_total_labor_cost"],
        "hours_delta": row["expected_total_available_hours"] - base["expected_total_available_hours"],
    }
