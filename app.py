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

# ---- Navigation -------------------------------------------------------------
pages = {
    "Quick decision": [
        st.Page("views/board.py", title="Decision board", icon=":material/bolt:", default=True),
    ],
    "Detailed analysis": [
        st.Page("views/overview.py", title="14-day overview", icon=":material/calendar_view_week:"),
        st.Page("views/day_detail.py", title="Selected day detail", icon=":material/today:"),
        st.Page("views/scenarios.py", title="Staffing scenarios", icon=":material/compare_arrows:"),
        st.Page("views/decision.py", title="Decision & outcome", icon=":material/task_alt:"),
    ],
    "Predictive Modeling": [
        st.Page("views/predictive_modeling.py", title="Model insights & scenarios", icon=":material/model_training:"),
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
