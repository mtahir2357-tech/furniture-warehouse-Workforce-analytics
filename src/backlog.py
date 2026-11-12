"""One shared treatment of carry-in backlog for every page (Week 12 review fix F2).

Two views of the same day are shown everywhere:

* **New work only** – the original pipeline figures (forecast workload ÷ productivity). Unchanged.
* **Including carry-in backlog** – new work + backlog projected to be open at the start of the day.

The carry-in comes from ONE projection, ``pipeline_plan`` (the Workforce planning (FTE) 14-day
planner on the original forecast), starting from the backlog actually observed at the end of
the planning date:

* ``response`` path – earlier days follow the planner's recommended feasible responses
  (used for recommendations on Day detail, Staffing scenarios and the Decision board);
* ``no_action`` path – nothing changes on earlier days (shows how backlog would build up).
"""
from __future__ import annotations

import pandas as pd

from src.fte import StaffingPolicy, check_feasibility, horizon_plan
from src.logic import backlog_risk, classify_gap


def pipeline_days(outlook: pd.DataFrame) -> pd.DataFrame:
    """Planner inputs from the original 14-day forecast run (one row per target day)."""
    return pd.DataFrame({
        "target_date": outlook["target_date"].to_numpy(),
        "h": outlook["horizon_operating_days"].to_numpy(),
        "workload": outlook["forecast_workload_units"].to_numpy(),
        "productivity": outlook["expected_productivity_wlu_per_hour"].to_numpy(),
        "planned_regular_hours": outlook["planned_regular_hours"].to_numpy(),
        "availability_ratio": outlook["availability_ratio"].to_numpy(),
        "hourly_rate": outlook["avg_worker_hourly_rate"].to_numpy(),
        "manager_cost": outlook["projected_manager_labor_cost"].to_numpy(),
    })


def opening_backlog(daily: pd.DataFrame, as_of: pd.Timestamp) -> float:
    """Backlog observed at the end of the planning date (the run is made after that day closes)."""
    known = daily.loc[daily["date"] <= as_of]
    if known.empty:
        raise ValueError("No backlog history is available by this forecast date.")
    return float(known.iloc[-1]["ending_backlog_wlu"])


def pipeline_plan(outlook: pd.DataFrame, daily: pd.DataFrame, as_of: pd.Timestamp,
                  policy: StaffingPolicy = StaffingPolicy()) -> pd.DataFrame:
    """The single 14-day projection all pages use for carry-in backlog (original forecast source)."""
    return horizon_plan(pipeline_days(outlook), opening_backlog(daily, as_of), policy)


def carry_in(plan: pd.DataFrame, target_date) -> dict:
    row = plan.loc[pd.to_datetime(plan["target_date"]) == pd.Timestamp(target_date)]
    if row.empty:
        raise KeyError(f"{target_date} is not in this 14-day plan.")
    r = row.iloc[0]
    return {"response": float(r["rec_beginning_backlog_wlu"]), "no_action": float(r["beginning_backlog_wlu"]), "row": r}


def with_carry_in(table: pd.DataFrame, carry_wlu: float, tol: float,
                  policy: StaffingPolicy | None = None) -> pd.DataFrame:
    """Scenario table re-evaluated with carry-in backlog; new-work-only values kept alongside.

    ``capacity_gap_hours`` / ``status`` become backlog-inclusive (what recommendations use);
    ``new_work_gap_hours`` / ``new_work_status`` keep the original pipeline values.
    Carry-in hours use each scenario's own productivity (lower in the low-productivity stress test).
    """
    t = table.copy()
    t["new_work_gap_hours"] = t["capacity_gap_hours"]
    t["new_work_status"] = t["status"]
    t["new_work_required_hours"] = t["projected_required_labor_hours"]
    t["carry_in_wlu"] = float(carry_wlu)
    t["carry_in_hours"] = float(carry_wlu) / t["assumed_productivity_wlu_per_hour"]
    t["projected_required_labor_hours"] = t["new_work_required_hours"] + t["carry_in_hours"]
    t["capacity_gap_hours"] = t["new_work_gap_hours"] - t["carry_in_hours"]
    t["status"] = t["capacity_gap_hours"].map(lambda g: classify_gap(g, tol))
    t["projected_ending_backlog_wlu"] = (t["carry_in_wlu"] + t["assumed_workload_units"]
                                         - t["projected_capacity_wlu"]).clip(lower=0)
    t["new_work_utilization"] = t["projected_capacity_utilization"]
    t["projected_capacity_utilization"] = t["projected_required_labor_hours"] / t["expected_total_available_hours"]
    t["backlog_risk"] = t["projected_capacity_utilization"].map(backlog_risk)
    if policy is not None:
        chk = [check_feasibility(a, b, policy) for a, b in zip(t["planned_regular_hours"], t["planned_overtime_hours"])]
        t["feasible"] = [c["feasible"] for c in chk]
        t["feasibility_issues"] = [" ".join(c["issues"]) for c in chk]
    return t


def adjust_custom(res: dict, carry_wlu: float, productivity: float, workload: float, tol: float) -> dict:
    """Add carry-in backlog to a custom scenario computed by logic.compute_scenario (new work only)."""
    out = dict(res)
    carry_h = float(carry_wlu) / max(float(productivity), 1e-6)
    out["new_work_gap_hours"] = res["capacity_gap_hours"]
    out["carry_in_wlu"] = float(carry_wlu)
    out["carry_in_hours"] = carry_h
    out["projected_required_labor_hours"] = res["projected_required_labor_hours"] + carry_h
    out["capacity_gap_hours"] = res["capacity_gap_hours"] - carry_h
    out["status"] = classify_gap(out["capacity_gap_hours"], tol)
    capacity = res["expected_total_available_hours"] * max(float(productivity), 1e-6)
    out["projected_ending_backlog_wlu"] = max(0.0, float(carry_wlu) + float(workload) - capacity)
    avail = res["expected_total_available_hours"]
    out["projected_capacity_utilization"] = out["projected_required_labor_hours"] / avail if avail > 0 else float("inf")
    return out
