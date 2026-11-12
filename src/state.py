"""Session state shared across pages: forecast run, tolerance, selected day, selected scenario."""
import pandas as pd
import streamlit as st

from src import logic


def as_of() -> pd.Timestamp:
    return st.session_state["as_of"]


def tol() -> float:
    return st.session_state["tol"]


def current_outlook() -> pd.DataFrame:
    return logic.outlook(as_of(), tol())


def target_row(o: pd.DataFrame) -> pd.Series:
    """Selected target day; falls back to the first shortage day, else the first day."""
    tgt = st.session_state.get("target_date")
    if tgt is None or tgt not in set(o["target_date"]):
        short = o[o["status"] == "Shortage"]
        tgt = (short if len(short) else o).iloc[0]["target_date"]
        st.session_state["target_date"] = tgt
    return o[o["target_date"] == tgt].iloc[0]


def policy():
    """Shared staffing policy from the sidebar (defaults from src/config.py)."""
    from src.config import (FULL_TIME_WEEK_HOURS, MAX_DAILY_OVERTIME_PER_WORKER, MIN_SCHEDULED_WORKERS,
                            SHIFT_HOURS, WEEKLY_HOUR_CAP, WORKER_ROSTER)
    from src.fte import StaffingPolicy

    ss = st.session_state
    try:
        return StaffingPolicy(shift_hours=float(ss.get("pol_shift", SHIFT_HOURS)),
                              week_hours=float(ss.get("pol_week", FULL_TIME_WEEK_HOURS)),
                              roster_workers=int(ss.get("pol_roster", WORKER_ROSTER)),
                              min_workers=int(ss.get("pol_min", MIN_SCHEDULED_WORKERS)),
                              max_ot_per_worker_day=float(ss.get("pol_ot", MAX_DAILY_OVERTIME_PER_WORKER)),
                              weekly_hour_cap=float(ss.get("pol_cap", WEEKLY_HOUR_CAP)))
    except ValueError as exc:
        ss["policy_error"] = str(exc)
        return StaffingPolicy()


def budget():
    """Optional daily labor budget (USD), or None when not set."""
    ss = st.session_state
    return float(ss["budget_amt"]) if ss.get("budget_on") and ss.get("budget_amt") is not None else None


def carry_plan():
    """The shared 14-day carry-in backlog projection for the current run (see src/backlog.py)."""
    from src import backlog, data

    return backlog.pipeline_plan(current_outlook(), data.daily(), as_of(), policy())


def set_target(date):
    st.session_state["target_date"] = pd.Timestamp(date)
    st.session_state.pop("scenario_choice", None)
    st.session_state.pop("custom", None)
