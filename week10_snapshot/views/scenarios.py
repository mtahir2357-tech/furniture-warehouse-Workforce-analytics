import plotly.graph_objects as go
import streamlit as st

from src import logic, state, ui
from src.config import ACTION_SCENARIOS, SCENARIO_LABELS

as_of = state.as_of()
o = state.current_outlook()
r = state.target_row(o)
tol = state.tol()
tbl = logic.scenario_table(int(r["forecast_id"]), tol)
base = tbl[tbl["scenario_id"] == "S01"].iloc[0]

ui.page_header(
    "Staffing scenario comparison",
    "Compare practical staffing responses for the selected day before committing to one.",
    as_of,
    step=2,
)

c1, c2, c3 = st.columns([1, 1.3, 1])
with c1:
    if st.button("Back to day detail", width="stretch"):
        st.switch_page("views/day_detail.py")
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
    st.markdown(f"<div style='padding-top:0.45rem'>Current plan &nbsp;{ui.badge(base['status'])}</div>", unsafe_allow_html=True)

ui.section("Current day summary")
ui.kpi_row([
    {"label": "Forecast workload", "value": f"{r['forecast_workload_units']:,.0f}", "unit": "WLU",
     "sub": f"80% range {r['lower_80_workload_units']:,.0f}–{r['upper_80_workload_units']:,.0f}"},
    {"label": "Required labor hours", "value": f"{base['projected_required_labor_hours']:,.1f}", "unit": "hrs"},
    {"label": "Available labor hours", "value": f"{base['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "Current capacity gap", "value": f"{base['capacity_gap_hours']:+,.1f}", "unit": "hrs", "status": base["status"]},
])

# ---- Alternatives table -----------------------------------------------------
ui.section("Staffing alternatives",
           "Stress tests show how the current plan holds up under harder conditions; they are not staffing actions.")
disp = tbl.assign(
    Scenario=tbl["scenario_label"],
    Util=(tbl["projected_capacity_utilization"] * 100),
)[["Scenario", "planned_overtime_hours", "expected_total_available_hours",
   "capacity_gap_hours", "Util", "projected_unprocessed_wlu", "backlog_risk",
   "projected_total_labor_cost", "status"]]
disp["status"] = disp["status"].map(lambda v: f"{ui.STATUS[v]['icon']} {v}")
st.dataframe(
    disp, hide_index=True, width="stretch",
    column_config={
        "expected_available_regular_hours": st.column_config.NumberColumn("Regular hrs", format="%.1f",
                                                                           help="Expected available regular hours (planned × availability)"),
        "planned_overtime_hours": st.column_config.NumberColumn("Overtime hrs", format="%.0f"),
        "expected_total_available_hours": st.column_config.NumberColumn("Total available", format="%.1f"),
        "projected_required_labor_hours": st.column_config.NumberColumn("Required hrs", format="%.1f"),
        "capacity_gap_hours": st.column_config.NumberColumn("Capacity gap", format="%+.1f"),
        "Util": st.column_config.NumberColumn("Utilization", format="%.0f%%"),
        "projected_unprocessed_wlu": st.column_config.NumberColumn("Unprocessed", format="%.1f"),
        "backlog_risk": st.column_config.TextColumn("Backlog risk"),
        "projected_total_labor_cost": st.column_config.NumberColumn("Labor cost", format="$%.0f"),
        "projected_labor_cost_pct_revenue": st.column_config.NumberColumn("Cost % rev.", format="%.2f%%"),
        "status": st.column_config.TextColumn("Status"),
    },
)

g1, g2 = st.columns(2, gap="large")
order = tbl.iloc[::-1]
with g1:
    ui.section("Capacity gap by scenario")
    fig = go.Figure(go.Bar(
        y=order["scenario_label"], x=order["capacity_gap_hours"], orientation="h",
        marker_color=[ui.STATUS_CHART[s] for s in order["status"]],
        text=[f"{v:+.1f} h" for v in order["capacity_gap_hours"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Gap %{x:+.1f} h<extra></extra>",
    ))
    fig.add_vrect(x0=-tol, x1=tol, fillcolor=ui.STATUS["Balanced"]["tint"], line_width=0, layer="below")
    fig.add_vline(x=0, line_color=ui.MUTED, line_width=1)
    lo_x, hi_x = min(order["capacity_gap_hours"].min(), -tol), max(order["capacity_gap_hours"].max(), tol)
    span = hi_x - lo_x
    fig.update_xaxes(title_text="Hours (negative = shortage)", range=[lo_x - 0.22 * span, hi_x + 0.22 * span])
    ui.chart(ui.style_fig(fig, 300, legend=False))
with g2:
    ui.section("Projected labor cost by scenario")
    fig = go.Figure(go.Bar(
        y=order["scenario_label"], x=order["projected_total_labor_cost"], orientation="h",
        marker_color=[ui.BLUE if sid in ACTION_SCENARIOS else ui.SLATE_LIGHT for sid in order["scenario_id"]],
        text=[f"${v:,.0f}" for v in order["projected_total_labor_cost"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>$%{x:,.0f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="USD per day", range=[0, order["projected_total_labor_cost"].max() * 1.18])
    ui.chart(ui.style_fig(fig, 300, legend=False))

# ---- Trade-offs -------------------------------------------------------------
ui.section("Trade-offs")
acts = tbl[tbl["scenario_id"].isin(ACTION_SCENARIOS)].set_index("scenario_id")
lines = []
b_cost = base["projected_total_labor_cost"]
if base["status"] == "Shortage":
    fixes = acts[acts["status"] != "Shortage"].sort_values("projected_total_labor_cost")
    if len(fixes):
        f = fixes.iloc[0]
        lines.append(f"Lowest-cost option that removes the shortage: {SCENARIO_LABELS[fixes.index[0]].lower()} "
                     f"(gap {f['capacity_gap_hours']:+.1f} h, {f['projected_total_labor_cost'] - b_cost:+,.0f} USD vs current plan).")
    else:
        best = acts.sort_values("capacity_gap_hours").iloc[-1]
        lines.append(f"No predefined option fully closes the gap. The closest leaves {best['capacity_gap_hours']:+.1f} h; "
                     "use the custom scenario below to test a larger response.")
elif base["status"] == "Surplus":
    red = acts.loc["S06"]
    lines.append(f"Reducing regular hours moves the gap to {red['capacity_gap_hours']:+.1f} h ({red['status'].lower()}) "
                 f"and saves {b_cost - red['projected_total_labor_cost']:,.0f} USD.")
else:
    lines.append("The current plan is within the balanced band; changes mainly trade cost against buffer.")
for sid in ["S02", "S03", "S06"]:
    a = acts.loc[sid]
    lines.append(f"{SCENARIO_LABELS[sid]}: gap {a['capacity_gap_hours']:+.1f} h, labor cost "
                 f"{a['projected_total_labor_cost'] - b_cost:+,.0f} USD vs current plan.")
s4, s5 = tbl.set_index("scenario_id").loc["S04"], tbl.set_index("scenario_id").loc["S05"]
lines.append(f"Stress tests: high demand gives {s4['capacity_gap_hours']:+.1f} h, low productivity {s5['capacity_gap_hours']:+.1f} h.")
lines.append("The final staffing choice remains with the manager.")
ui.callout(lines)

# ---- Custom scenario --------------------------------------------------------
ui.section("Adjust scenario", "Change the inputs to test a response that is not in the predefined list. Results update immediately.")
fid = int(r["forecast_id"])
custom = st.session_state.get("custom")
if not custom or custom.get("forecast_id") != fid:
    custom = {"forecast_id": fid, "reg": float(base["planned_regular_hours"]), "ot": 0.0,
              "prod": float(base["assumed_productivity_wlu_per_hour"]), "wl": float(base["assumed_workload_units"])}
for k in ["reg", "ot", "prod", "wl"]:
    if f"c_{k}" not in st.session_state or st.session_state.get("c_fid") != fid:
        st.session_state[f"c_{k}"] = custom[k]
st.session_state["c_fid"] = fid
i1, i2, i3, i4 = st.columns(4)
custom["reg"] = i1.number_input("Planned regular hours", 0.0, 600.0, step=8.0, key="c_reg")
custom["ot"] = i2.number_input("Overtime hours", 0.0, 200.0, step=2.0, key="c_ot")
custom["prod"] = i3.number_input("Expected productivity (WLU/hr)", 0.5, 4.0, step=0.05, format="%.3f", key="c_prod")
custom["wl"] = i4.number_input("Workload (WLU)", 0.0, 2000.0, step=10.0, format="%.1f", key="c_wl")
st.session_state["custom"] = custom
res = logic.compute_scenario(custom["wl"], custom["prod"], custom["reg"], custom["ot"], float(r["availability_ratio"]),
                             float(base["avg_worker_hourly_rate"]), float(base["projected_manager_labor_cost"]),
                             float(r["historical_revenue_per_wlu"]))
c_status = logic.classify_gap(res["capacity_gap_hours"], tol)
ui.kpi_row([
    {"label": "Total available labor", "value": f"{res['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "Capacity gap", "value": f"{res['capacity_gap_hours']:+,.1f}", "unit": "hrs", "sub": c_status, "status": c_status},
    {"label": "Backlog risk", "value": logic.backlog_risk(res["projected_capacity_utilization"]),
     "status": logic.backlog_risk(res["projected_capacity_utilization"]),
     "sub": f"Utilization {res['projected_capacity_utilization']:.0%}"},
    {"label": "Labor cost", "value": ui.fmt_money(res["projected_total_labor_cost"]),
     "sub": f"{res['projected_total_labor_cost'] - b_cost:+,.0f} vs current plan"},
])
ui.note("Uses the pipeline's rules: available regular hours = planned × expected availability; overtime paid at 1.5× the "
        "average worker rate; manager cost unchanged.")

# ---- Selection --------------------------------------------------------------
ui.section("Select a staffing option")
options = ACTION_SCENARIOS + ["CUSTOM"]
labels = {**SCENARIO_LABELS, "CUSTOM": "Custom (inputs above)"}
rec = logic.recommend(r, tbl, tol)
current = st.session_state.get("scenario_choice", rec["scenario_id"])
choice = st.radio("Staffing option", options, index=options.index(current) if current in options else 0,
                  format_func=lambda k: labels[k] + ("  (recommended)" if k == rec["scenario_id"] else ""),
                  horizontal=True, label_visibility="collapsed")
st.session_state["scenario_choice"] = choice

if choice == "CUSTOM":
    chosen = {**res, "scenario_label": "Custom", "status": c_status}
else:
    row = tbl[tbl["scenario_id"] == choice].iloc[0]
    chosen = {**row.to_dict(), "status": row["status"]}
st.session_state["chosen_scenario"] = {
    "forecast_id": fid, "scenario_id": choice, "label": labels[choice],
    "planned_regular_hours": float(chosen["planned_regular_hours"]),
    "planned_overtime_hours": float(chosen["planned_overtime_hours"]),
    "expected_total_available_hours": float(chosen["expected_total_available_hours"]),
    "projected_required_labor_hours": float(chosen["projected_required_labor_hours"]),
    "capacity_gap_hours": float(chosen["capacity_gap_hours"]),
    "projected_unprocessed_wlu": float(chosen["projected_unprocessed_wlu"]),
    "backlog_risk": logic.backlog_risk(float(chosen["projected_capacity_utilization"])),
    "projected_total_labor_cost": float(chosen["projected_total_labor_cost"]),
    "projected_same_day_shipped_revenue": float(chosen["projected_same_day_shipped_revenue"]),
    "status": chosen["status"],
    "workload": float(custom["wl"]) if choice == "CUSTOM" else float(r["forecast_workload_units"]),
}
cs = st.session_state["chosen_scenario"]
st.markdown(f"<div style='font-size:1.05rem;font-weight:700;margin:0.4rem 0 0.5rem'>Selected: {ui.esc(cs['label'])} &nbsp;"
            f"{ui.badge(cs['status'])}</div>", unsafe_allow_html=True)
ui.kpi_row([
    {"label": "Total available labor", "value": f"{cs['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "Projected capacity gap", "value": f"{cs['capacity_gap_hours']:+,.1f}", "unit": "hrs", "sub": cs["status"], "status": cs["status"]},
    {"label": "Projected backlog risk", "value": cs["backlog_risk"], "status": cs["backlog_risk"]},
    {"label": "Estimated labor cost", "value": ui.fmt_money(cs["projected_total_labor_cost"])},
])

b1, b2, _ = st.columns([1.2, 1, 3])
with b1:
    if st.button("Continue to decision", type="primary", width="stretch"):
        st.switch_page("views/decision.py")
with b2:
    if st.button("Return to day detail", width="stretch"):
        st.switch_page("views/day_detail.py")
ui.note("Decision supported: which staffing response gives an acceptable balance of capacity, risk, and cost?")
