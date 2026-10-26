import streamlit as st

from src import logic, state, ui

as_of = state.as_of()
o = state.current_outlook()
r = state.target_row(o)

ui.page_header(
    "Selected day detail",
    "Understand why one operating day is projected to be short or over-staffed before comparing responses.",
    as_of,
    step=1,
)

c1, c2, c3 = st.columns([1, 1.3, 1])
with c1:
    if st.button("Back to 14-day overview", width="stretch"):
        st.switch_page("views/overview.py")
with c2:
    dates = list(o["target_date"])
    picked = st.selectbox(
        "Selected date", dates, index=dates.index(r["target_date"]),
        format_func=lambda d: f"{d:%a %b %d, %Y}  ·  {o.loc[o['target_date'] == d, 'status'].iloc[0]}",
        label_visibility="collapsed",
    )
    if picked != r["target_date"]:
        state.set_target(picked)
        st.rerun()
with c3:
    st.markdown(f"<div style='padding-top:0.45rem'>Status &nbsp;{ui.badge(r['status'])} &nbsp;"
                f"<span style='color:{ui.MUTED};font-size:0.85rem'>Horizon: day {int(r['horizon_operating_days'])} of 14</span></div>",
                unsafe_allow_html=True)

W, lo, hi = r["forecast_workload_units"], r["lower_80_workload_units"], r["upper_80_workload_units"]
prod = r["expected_productivity_wlu_per_hour"]
req, avail, gap = r["projected_required_labor_hours"], r["expected_available_regular_hours"], r["capacity_gap_hours"]

# 1. Workload forecast
ui.section("1. Workload forecast", "The forecast is a range, not a single certain value.")
ui.kpi_row([
    {"label": "Forecast workload", "value": f"{W:,.0f}", "unit": "WLU", "emphasis": True},
    {"label": "Lower 80% bound", "value": f"{lo:,.0f}", "unit": "WLU"},
    {"label": "Upper 80% bound", "value": f"{hi:,.0f}", "unit": "WLU"},
    {"label": "Baseline capacity", "value": f"{r['baseline_capacity_wlu']:,.0f}", "unit": "WLU",
     "sub": "Available hours × expected productivity"},
])
ui.range_bar(lo, W, hi, capacity=r["baseline_capacity_wlu"])
ui.note("Dashed marker: baseline capacity. If it sits inside the range, the day could be short even when the point forecast fits.")

# 2. Operating inputs
ui.section("2. Expected operating inputs")
ui.kpi_row([
    {"label": "Expected productivity", "value": f"{prod:.3f}", "unit": "WLU / labor hr",
     "sub": "Based on recent operating history"},
    {"label": "Planned regular hours", "value": f"{r['planned_regular_hours']:,.0f}", "unit": "hrs"},
    {"label": "Expected availability", "value": f"{r['availability_ratio']:.0%}", "sub": "Share of scheduled hours expected to show"},
    {"label": "Expected available hours", "value": f"{avail:,.1f}", "unit": "hrs"},
])

# 3. Labor requirement
ui.section("3. Labor requirement", "Required labor hours = forecast workload ÷ expected productivity")
st.markdown(
    f'<div class="formula">{ui.kpi_html("Forecast workload", f"{W:,.1f}", "WLU")}<div class="op">÷</div>'
    f'{ui.kpi_html("Expected productivity", f"{prod:.4f}", "WLU/hr")}<div class="op">=</div>'
    f'{ui.kpi_html("Required labor hours", f"{req:,.1f}", "hrs", emphasis=True)}</div>',
    unsafe_allow_html=True,
)

# 4. Capacity comparison
ui.section("4. Capacity comparison", "Capacity gap = available labor hours − required labor hours")
ui.kpi_row([
    {"label": "Required labor hours", "value": f"{req:,.1f}", "unit": "hrs"},
    {"label": "Available labor hours", "value": f"{avail:,.1f}", "unit": "hrs"},
    {"label": "Capacity gap", "value": f"{gap:+,.1f}", "unit": "hrs", "status": r["status"],
     "sub": f"{avail:,.1f} − {req:,.1f}"},
])
explain = {
    "Shortage": f"available labor is {abs(gap):.1f} hours below the estimated requirement.",
    "Surplus": f"available labor exceeds the estimated requirement by {gap:.1f} hours.",
    "Balanced": f"the gap is within the ±{state.tol():.0f}-hour balanced band.",
}
ui.status_banner(r["status"], explain[r["status"]])

# 5. Risk
ui.section("5. Backlog and capacity risk")
util = r["projected_capacity_utilization"]
ui.kpi_row([
    {"label": "Projected capacity utilization", "value": f"{util:.0%}", "sub": "Required ÷ available hours"},
    {"label": "Capacity exceedance risk", "value": r["exceedance_risk"], "status": r["exceedance_risk"],
     "sub": f"{r['probability_capacity_exceeded']:.0%} chance workload exceeds baseline capacity"},
    {"label": "Projected backlog risk", "value": r["backlog_risk"], "status": r["backlog_risk"],
     "sub": f"{r['projected_unprocessed_wlu']:,.1f} WLU projected unprocessed"},
    {"label": "Gap at upper forecast bound", "value": f"{r['gap_at_upper']:+,.1f}", "unit": "hrs",
     "sub": f"If workload reaches {hi:,.0f} WLU"},
])

# Stress check
st_tbl = logic.scenario_table(int(r["forecast_id"]), state.tol()).set_index("scenario_id")
hd, lp = st_tbl.loc["S04"], st_tbl.loc["S05"]
ui.note(f"Stress tests: with 20% higher workload the gap would be {hd['capacity_gap_hours']:+.1f} h; "
        f"with 15% lower productivity it would be {lp['capacity_gap_hours']:+.1f} h.")

# Why
ui.section("Why this day needs attention" if r["status"] != "Balanced" else "Why this day looks manageable")
recent = logic.recent_average_workload(as_of)
reasons = []
if r["status"] == "Shortage":
    reasons.append(f"Forecast workload requires {req:,.1f} labor hours, but only {avail:,.1f} are expected to be available.")
elif r["status"] == "Surplus":
    reasons.append(f"Expected available labor ({avail:,.1f} h) exceeds the {req:,.1f} hours the forecast requires.")
else:
    reasons.append(f"Required ({req:,.1f} h) and available ({avail:,.1f} h) labor are within ±{state.tol():.0f} hours.")
if recent == recent:
    diff = W / recent - 1
    reasons.append(f"Forecast workload is {abs(diff):.0%} {'above' if diff >= 0 else 'below'} the recent 28-day average of {recent:,.0f} WLU "
                   f"({r['day_name']} pattern{' and peak season' if r['is_peak_season'] == 1 else ''}).")
if r["known_holiday_flag"] == 1:
    reasons.append(f"Known holiday ({r['holiday_name']}) lowers expected demand.")
if r["known_promotion_flag"] == 1:
    reasons.append("A known promotion raises expected demand.")
if r["gap_at_upper"] < -state.tol():
    reasons.append(f"At the upper end of the forecast range the shortage would reach {abs(r['gap_at_upper']):.1f} hours.")
if r["exceedance_risk"] != "Low":
    reasons.append(f"Capacity-exceedance risk is {r['exceedance_risk'].lower()} ({r['probability_capacity_exceeded']:.0%}).")
if hd["status"] == "Shortage" and r["status"] != "Shortage":
    reasons.append("The high-demand stress test turns this day into a shortage, so a conservative plan may be worth comparing.")
ui.callout(reasons)

b1, b2, _ = st.columns([1.2, 1, 3])
with b1:
    if st.button("Compare staffing scenarios", type="primary", width="stretch"):
        st.switch_page("views/scenarios.py")
with b2:
    if st.button("Return to overview", width="stretch"):
        st.switch_page("views/overview.py")
ui.note("Decision supported: why is this day projected to be short or over-staffed, and does it need action?")
