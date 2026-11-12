"""Furniture Fulfillment Labor Demand Forecasting and Staffing Scenario Tool.

Run with:  streamlit run app.py
"""
import pandas as pd
import streamlit as st

from src import data, logic, ui
from src.config import APP_TITLE, DEFAULT_BALANCED_TOLERANCE_HRS

st.set_page_config(page_title="Workforce Planning Tool", page_icon=":material/warehouse:", layout="wide")
ui.inject_css()

# ---- Data check -------------------------------------------------------------
try:
    runs = data.forecast_runs()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

# ---- Sidebar: planning context ----------------------------------------------
if "tol" not in st.session_state:
    st.session_state["tol"] = DEFAULT_BALANCED_TOLERANCE_HRS
if "as_of_pick" not in st.session_state:
    st.session_state["as_of_pick"] = runs[-1].date()

with st.sidebar:
    st.markdown(
        '<div class="sb-brand">'
        '<span class="sb-mark" style="background:#D94F4F"></span>'
        '<span class="sb-mark" style="background:#1F9D7A"></span>'
        '<span class="sb-mark" style="background:#D99A1E"></span><br>Workforce Planning Tool</div>'
        '<div class="sb-sub">One furniture fulfillment warehouse · synthetic data 2023–2025</div>',
        unsafe_allow_html=True,
    )
    picked = st.date_input(
        "Planning date",
        key="as_of_pick",
        min_value=runs[0].date(),
        max_value=runs[-1].date(),
        help="The tool shows the forecast run made on this date (or the latest run before it, "
        "since forecasts are only produced on operating days).",
        format="MM/DD/YYYY",
    )
    st.session_state["as_of"] = logic.snap_to_run(picked)
    if st.session_state["as_of"].date() != picked:
        st.caption(f"No run on that date. Showing the run from {st.session_state['as_of']:%a %b %d, %Y}.")

    st.slider(
        "Balanced band (± hours)",
        min_value=0.0,
        max_value=24.0,
        step=1.0,
        key="tol",
        help="A day is Balanced when the capacity gap is within this band. "
        "Default is one 8-hour shift. This is an MVP rule, not an industry threshold.",
    )

    # Shared staffing policy and optional labor budget, used by every page.
    from src import config as _c
    for _k, _v in {"pol_shift": _c.SHIFT_HOURS, "pol_week": _c.FULL_TIME_WEEK_HOURS, "pol_roster": _c.WORKER_ROSTER,
                   "pol_min": _c.MIN_SCHEDULED_WORKERS, "pol_ot": _c.MAX_DAILY_OVERTIME_PER_WORKER,
                   "pol_cap": _c.WEEKLY_HOUR_CAP, "budget_on": False, "budget_amt": _c.DEFAULT_DAILY_LABOR_BUDGET}.items():
        st.session_state.setdefault(_k, _v)
    with st.expander("Staffing policy & labor budget"):
        st.number_input("Worker roster (max per day)", 1, 200, step=1, key="pol_roster",
                        help="30 warehouse workers in dim_employee.")
        st.number_input("Minimum scheduled workers", 0, 200, step=1, key="pol_min",
                        help="Project assumption, not from the source data. Default 20.")
        st.number_input("Max overtime per worker-day (h)", 0.0, 6.0, step=0.5, key="pol_ot",
                        help="(50 − 40) weekly hours ÷ 5 shifts = 2 h by default.")
        st.number_input("Standard shift (h)", 4.0, 12.0, step=0.5, key="pol_shift")
        st.number_input("Full-time week (h)", 20.0, 60.0, step=1.0, key="pol_week")
        st.number_input("Weekly hour cap per worker (h)", 20.0, 80.0, step=1.0, key="pol_cap",
                        help="50 h in dim_employee.")
        st.toggle("Use a daily labor budget", key="budget_on")
        st.number_input("Daily labor budget (USD)", 0.0, 100000.0, step=100.0, key="budget_amt",
                        disabled=not st.session_state["budget_on"],
                        help="Optional. Options above it are flagged, never hidden or changed.")
        st.caption("Minimum staffing (default 20 workers) is a **project assumption**, not source data.")
    if st.session_state.pop("policy_error", None):
        st.error("Policy settings are inconsistent (e.g. minimum above roster); defaults are used.")

# ---- Navigation -------------------------------------------------------------
pages = {
    "Quick decision": [
        st.Page("views/board.py", title="Decision board", icon=":material/bolt:", default=True),
    ],
    "Detailed analysis": [
        st.Page("views/overview.py", title="14-day overview", icon=":material/calendar_view_week:"),
        st.Page("views/workforce_planning.py", title="Workforce planning (FTE)", icon=":material/groups:"),
        st.Page("views/day_detail.py", title="Selected day detail", icon=":material/today:"),
        st.Page("views/scenarios.py", title="Staffing scenarios", icon=":material/compare_arrows:"),
        st.Page("views/decision.py", title="Decision & outcome", icon=":material/task_alt:"),
    ],
    "Predictive Modeling": [
        st.Page("views/predictive_modeling.py", title="Model insights & scenarios", icon=":material/model_training:"),
        st.Page("views/model_validation.py", title="Model validation", icon=":material/fact_check:"),
    ],
    "Performance": [
        st.Page("views/forecast_accuracy.py", title="Forecast accuracy", icon=":material/query_stats:"),
        st.Page("views/operations.py", title="Operations history", icon=":material/insights:"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.divider()
    st.caption(
        "Decision support only. The manager makes the final staffing decision. "
        "Data is synthetic and not calibrated to a real warehouse."
    )

nav.run()
