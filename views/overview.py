import plotly.graph_objects as go
import streamlit as st

from src import fte, state, ui
from src.config import SHIFT_HOURS

as_of = state.as_of()
o = state.current_outlook()
sel = state.target_row(o)
# FTE = 8-hour worker-shift equivalents of the same required / available hours shown on this page.
_f = o.apply(lambda r: fte.fte_summary(r["projected_required_labor_hours"], r["expected_available_regular_hours"]), axis=1)
o["required_fte"] = [x["required_fte"] for x in _f]
o["available_fte"] = [x["available_fte"] for x in _f]
o["fte_gap"] = [x["fte_gap"] for x in _f]
o["additional_shifts"] = [x["additional_shifts"] for x in _f]

ui.page_header(
    "14-day planning overview",
    "Find the upcoming operating days where planned labor will not match forecast workload.",
    as_of,
    step=0,
)

xlab = o["target_date"].dt.strftime("%a<br>%b %d")
tick = o["target_date"].dt.strftime("%a<br>%d")
n_short = int((o["status"] == "Shortage").sum())
n_surplus = int((o["status"] == "Surplus").sum())
worst = o.loc[o["capacity_gap_hours"].idxmin()]
ui.kpi_row(
    [
        {"label": "Avg. forecast workload", "value": f"{o['forecast_workload_units'].mean():,.0f}", "unit": "WLU/day"},
        {"label": "Avg. required labor", "value": f"{o['projected_required_labor_hours'].mean():,.0f}", "unit": "hrs/day",
         "sub": f"vs {o['expected_available_regular_hours'].mean():,.0f} hrs expected available"},
        {"label": "Shortage days", "value": n_short, "unit": "of 14", "status": "Shortage",
         "sub": f"Largest: {worst['capacity_gap_hours']:+.0f} h on {worst['target_date']:%b %d}" if n_short else "None projected"},
        {"label": "Surplus days", "value": n_surplus, "unit": "of 14", "status": "Surplus"},
        {"label": "High capacity-exceedance risk", "value": int((o["exceedance_risk"] == "High").sum()), "unit": "days",
         "sub": "P(workload > baseline capacity) ≥ 50%"},
        {"label": "Avg. required FTE", "value": f"{o['required_fte'].mean():,.2f}", "unit": "shifts/day",
         "sub": f"vs {o['available_fte'].mean():,.2f} available · peak extra {int(o['additional_shifts'].max())} shift(s)"},
    ]
)

ui.section("Capacity outlook", f"Next 14 operating days after {as_of:%b %d}. Balanced band: ±{state.tol():.0f} hours.")
ui.day_strip(o, selected=sel["target_date"])

c1, c2 = st.columns(2, gap="large")
with c1:
    ui.section("Required vs. available labor hours")
    fig = go.Figure()
    fig.add_bar(
        x=xlab, y=o["projected_required_labor_hours"], name="Required labor", showlegend=False,
        marker_color=[ui.STATUS_CHART[s] for s in o["status"]],
        customdata=o[["capacity_gap_hours", "status"]],
        hovertemplate="%{x}<br>Required %{y:,.1f} h<br>Gap %{customdata[0]:+.1f} h · %{customdata[1]}<extra></extra>",
    )
    fig.add_scatter(
        x=xlab, y=o["expected_available_regular_hours"], name="Expected available",
        mode="lines+markers", line=dict(color=ui.INK, width=2, dash="dash"), marker=dict(size=5, color=ui.INK),
        hovertemplate="Available %{y:,.1f} h<extra></extra>",
    )
    ui.status_legend(fig, "bar")
    fig.update_yaxes(title_text="Labor hours", rangemode="tozero")
    fig.update_xaxes(type="category", tickangle=0, tickfont=dict(size=10), tickmode="array", tickvals=list(xlab), ticktext=list(tick))
    ui.chart(ui.style_fig(fig, 330))
with c2:
    ui.section("Forecast workload with 80% range")
    fig = go.Figure()
    fig.add_scatter(x=xlab, y=o["upper_80_workload_units"], mode="lines", line=dict(width=0),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=xlab, y=o["lower_80_workload_units"], mode="lines", line=dict(width=0),
                    fill="tonexty", fillcolor="rgba(47,91,234,0.13)", name="80% range", hoverinfo="skip")
    fig.add_scatter(x=xlab, y=o["forecast_workload_units"], mode="lines+markers", name="Forecast",
                    line=dict(color=ui.NAVY, width=2.4), marker=dict(size=6),
                    customdata=o[["lower_80_workload_units", "upper_80_workload_units"]],
                    hovertemplate="%{x}<br>Forecast %{y:,.0f} WLU<br>Range %{customdata[0]:,.0f}–%{customdata[1]:,.0f}<extra></extra>")
    fig.add_scatter(x=xlab, y=o["baseline_capacity_wlu"], mode="lines", name="Baseline capacity",
                    line=dict(color=ui.STATUS["Shortage"]["color"], width=1.5, dash="dot"), hovertemplate="Capacity %{y:,.0f} WLU<extra></extra>")
    fig.update_yaxes(title_text="Weighted workload units", rangemode="tozero")
    fig.update_xaxes(type="category", tickangle=0, tickfont=dict(size=10), tickmode="array", tickvals=list(xlab), ticktext=list(tick))
    ui.chart(ui.style_fig(fig, 330))

ui.section("Daily staffing outlook", "Select a row to review that day in detail.")
table = o.assign(
    Date=o["target_date"].dt.strftime("%a %b %d"),
    Range=o.apply(lambda r: f"{r['lower_80_workload_units']:,.0f} – {r['upper_80_workload_units']:,.0f}", axis=1),
    Risk=(o["probability_capacity_exceeded"] * 100).round(0),
    Note=o.apply(lambda r: r["holiday_name"] if r["known_holiday_flag"] == 1 and isinstance(r["holiday_name"], str)
                 else ("Promotion" if r["known_promotion_flag"] == 1 else ""), axis=1),
)[["Date", "forecast_workload_units", "Range", "projected_required_labor_hours", "expected_available_regular_hours",
   "capacity_gap_hours", "required_fte", "available_fte", "fte_gap", "additional_shifts", "Risk", "status", "Note"]]
table["status"] = table["status"].map(lambda v: f"{ui.STATUS[v]['icon']} {v}")
event = st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    key="outlook_table",
    height=35 * (len(table) + 1) + 3,
    column_config={
        "forecast_workload_units": st.column_config.NumberColumn("Forecast WLU", format="%.0f"),
        "Range": st.column_config.TextColumn("80% range (WLU)"),
        "projected_required_labor_hours": st.column_config.NumberColumn("Required hrs", format="%.1f"),
        "expected_available_regular_hours": st.column_config.NumberColumn("Available hrs", format="%.1f"),
        "capacity_gap_hours": st.column_config.NumberColumn("Capacity gap (hrs)", format="%+.1f"),
        "required_fte": st.column_config.NumberColumn("Required FTE", format="%.2f",
                                                      help=f"Required labor hours ÷ {SHIFT_HOURS:g} (worker-shift equivalents)"),
        "available_fte": st.column_config.NumberColumn("Available FTE", format="%.2f",
                                                       help=f"Available worker hours ÷ {SHIFT_HOURS:g}; manager hours excluded"),
        "fte_gap": st.column_config.NumberColumn("FTE gap", format="%+.2f", help="Required − available FTE (positive = shortage)"),
        "additional_shifts": st.column_config.NumberColumn("Extra shifts", format="%d",
                                                           help="Whole 8-hour worker-shift equivalents to cover a shortage (rounded up)"),
        "Risk": st.column_config.ProgressColumn("Exceedance risk", format="%d%%", min_value=0, max_value=100),
        "status": st.column_config.TextColumn("Status"),
        "Note": st.column_config.TextColumn("Calendar"),
    },
)
rows = event.selection.rows if event and event.selection else []
if rows:
    picked = o.iloc[rows[0]]["target_date"]
    if picked != st.session_state.get("target_date"):
        state.set_target(picked)
        st.rerun()

ui.section("Days requiring attention")
attention = o[o["status"] != "Balanced"].sort_values("capacity_gap_hours")
if attention.empty:
    ui.callout(["All 14 days are within the balanced band. No staffing change is indicated by the point forecast."])
else:
    lines = []
    for _, r in attention.iterrows():
        kind = "shortage" if r["status"] == "Shortage" else "surplus"
        lines.append(f"{r['target_date']:%a %b %d}: projected {kind} of {abs(r['capacity_gap_hours']):.1f} labor hours "
                     f"(exceedance risk {r['probability_capacity_exceeded']:.0%})")
    ui.callout(lines)

cA, cB, _ = st.columns([1.4, 1, 2.6])
with cA:
    st.markdown(f"**Day under review:** {sel['target_date']:%a %b %d, %Y} &nbsp;{ui.badge(sel['status'])}", unsafe_allow_html=True)
with cB:
    if st.button("Review selected day", type="primary", width="stretch"):
        st.switch_page("views/day_detail.py")
ui.note(f"FTE = 8-hour worker-shift equivalents (hours ÷ {SHIFT_HOURS:g}), not contractual full-time headcount. "
        "Required FTE uses the forecast workload ÷ expected productivity, as in the required-hours column; carry-in backlog "
        "is added on the Workforce planning (FTE) page.")
ui.note("Decision supported: which future operating days require staffing review?")
