import plotly.graph_objects as go
import streamlit as st

from src import backlog, fte, logic, state, ui
from src.config import ACTION_SCENARIOS, SCENARIO_LABELS, SHIFT_HOURS

as_of = state.as_of()
o = state.current_outlook()
r = state.target_row(o)
tol = state.tol()
pol = state.policy()
budget = state.budget()
# Carry-in backlog from the shared 14-day projection (same numbers as Workforce planning (FTE)).
carry = backlog.carry_in(state.carry_plan(), r["target_date"])
carry_wlu = carry["response"]
tbl = backlog.with_carry_in(logic.scenario_table(int(r["forecast_id"]), tol), carry_wlu, tol, pol)
base = tbl[tbl["scenario_id"] == "S01"].iloc[0]
day = r.copy()
day["status"] = base["status"]  # recommendations use the backlog-inclusive status

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

ui.section("Current day summary", "Gaps and statuses on this page include carry-in backlog; the original "
           "new-work-only figures are shown alongside.")
ui.kpi_row([
    {"label": "Forecast workload", "value": f"{r['forecast_workload_units']:,.0f}", "unit": "WLU",
     "sub": f"80% range {r['lower_80_workload_units']:,.0f}–{r['upper_80_workload_units']:,.0f}"},
    {"label": "Carry-in backlog", "value": f"{carry_wlu:,.0f}", "unit": "WLU",
     "sub": f"≈ {base['carry_in_hours']:,.1f} labor hrs · from the 14-day plan"},
    {"label": "Required labor hours", "value": f"{base['projected_required_labor_hours']:,.1f}", "unit": "hrs",
     "sub": f"new work {base['new_work_required_hours']:,.1f} + carry-in {base['carry_in_hours']:,.1f}"},
    {"label": "Available labor hours", "value": f"{base['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "Current capacity gap", "value": f"{base['capacity_gap_hours']:+,.1f}", "unit": "hrs", "status": base["status"],
     "sub": f"new work only {base['new_work_gap_hours']:+,.1f} h ({base['new_work_status'].lower()})"},
])
ui.note(f"Carry-in backlog = work projected to be open at the start of {r['target_date']:%b %d}: the backlog observed when "
        f"the run was made ({as_of:%b %d}), carried through earlier days assuming their recommended feasible responses "
        "(Workforce planning (FTE) page). "
        + (f"If no earlier day changes staffing it would be {carry['no_action']:,.0f} WLU." if abs(carry['no_action'] - carry_wlu) > 0.5 else ""))

# ---- Alternatives table -----------------------------------------------------
ui.section("Staffing alternatives",
           "Stress tests show how the current plan holds up under harder conditions; they are not staffing actions.")
_tf = [fte.fte_summary(a, b, pol.shift_hours) for a, b in zip(tbl["projected_required_labor_hours"], tbl["expected_total_available_hours"])]
_bud = [fte.budget_check(c, budget) for c in tbl["projected_total_labor_cost"]]
disp = tbl.assign(
    Scenario=tbl["scenario_label"],
    Util=(tbl["projected_capacity_utilization"] * 100),
    req_fte=[x["required_fte"] for x in _tf],
    av_fte=[x["available_fte"] for x in _tf],
    fte_gap=[x["fte_gap"] for x in _tf],
    extra=[x["additional_shifts"] for x in _tf],
    Feasible=["✓ Yes" if f else "✕ No" for f in tbl["feasible"]],
    Budget=["—" if b is None else ("✓ Within" if b["within"] else f"⚠ {b['label']}") for b in _bud],
)[["Scenario", "Feasible", "status", "planned_overtime_hours", "expected_total_available_hours", "new_work_gap_hours",
   "capacity_gap_hours", "req_fte", "av_fte", "fte_gap", "extra", "Util", "projected_ending_backlog_wlu", "backlog_risk",
   "projected_total_labor_cost", "Budget"]]
disp["status"] = disp["status"].map(lambda v: f"{ui.STATUS[v]['icon']} {v}")
st.dataframe(
    disp, hide_index=True, width="stretch",
    column_config={
        "expected_available_regular_hours": st.column_config.NumberColumn("Regular hrs", format="%.1f",
                                                                           help="Expected available regular hours (planned × availability)"),
        "planned_overtime_hours": st.column_config.NumberColumn("Overtime hrs", format="%.0f"),
        "expected_total_available_hours": st.column_config.NumberColumn("Total available", format="%.1f"),
        "projected_required_labor_hours": st.column_config.NumberColumn("Required hrs", format="%.1f"),
        "new_work_gap_hours": st.column_config.NumberColumn("Gap · new work only", format="%+.1f",
                                                            help="Original pipeline figure: forecast workload only."),
        "capacity_gap_hours": st.column_config.NumberColumn("Gap · incl. carry-in", format="%+.1f",
                                                            help="Available − (new work + carry-in backlog) hours. Used for status."),
        "projected_ending_backlog_wlu": st.column_config.NumberColumn("Ending backlog", format="%.1f",
                                                                      help="WLU left open at day end, incl. carry-in"),
        "Feasible": st.column_config.TextColumn(help="Within roster, minimum staffing and overtime limits (sidebar policy)"),
        "Budget": st.column_config.TextColumn(help="Compared with the optional daily labor budget in the sidebar"),
        "req_fte": st.column_config.NumberColumn("Required FTE", format="%.2f", help=f"Required hours ÷ {pol.shift_hours:g}"),
        "av_fte": st.column_config.NumberColumn("Available FTE", format="%.2f",
                                                help=f"Available worker hours (incl. overtime, excl. managers) ÷ {pol.shift_hours:g}"),
        "fte_gap": st.column_config.NumberColumn("FTE gap", format="%+.2f", help="Required − available (positive = shortage)"),
        "extra": st.column_config.NumberColumn("Extra shifts", format="%d", help="Whole 8-hour shift equivalents still needed"),
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
    ui.section("Capacity gap by scenario (incl. carry-in backlog)")
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
    if budget is not None:
        fig.add_vline(x=budget, line_color=ui.STATUS["Shortage"]["color"], line_dash="dash",
                      annotation_text=f"Budget ${budget:,.0f}", annotation_position="top")
    fig.update_xaxes(title_text="USD per day", range=[0, max(order["projected_total_labor_cost"].max(), budget or 0) * 1.18])
    ui.chart(ui.style_fig(fig, 300, legend=False))

# ---- Trade-offs -------------------------------------------------------------
ui.section("Trade-offs")
acts = tbl[tbl["scenario_id"].isin(ACTION_SCENARIOS)].set_index("scenario_id")
acts = acts[acts["feasible"] | (acts.index == "S01")]
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
for sid in [s for s in ["S02", "S03", "S06"] if s in acts.index]:
    a = acts.loc[sid]
    lines.append(f"{SCENARIO_LABELS[sid]}: gap {a['capacity_gap_hours']:+.1f} h, labor cost "
                 f"{a['projected_total_labor_cost'] - b_cost:+,.0f} USD vs current plan.")
s4, s5 = tbl.set_index("scenario_id").loc["S04"], tbl.set_index("scenario_id").loc["S05"]
lines.append(f"Stress tests: high demand gives {s4['capacity_gap_hours']:+.1f} h, low productivity {s5['capacity_gap_hours']:+.1f} h.")
bad = tbl[~tbl["feasible"] & tbl["scenario_id"].isin(ACTION_SCENARIOS)]
for _, b in bad.iterrows():
    lines.append(f"{b['scenario_label']} is not feasible under the current policy: {b['feasibility_issues']}")
if budget is not None:
    over = [f"{SCENARIO_LABELS[s]} (${c - budget:,.0f} over)" for s, c in zip(tbl["scenario_id"], tbl["projected_total_labor_cost"])
            if s in ACTION_SCENARIOS and c > budget + 1e-9]
    lines.append(f"Daily labor budget ${budget:,.0f}: " + (f"exceeded by {', '.join(over)}." if over else "every action option is within it."))
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
res = backlog.adjust_custom(res, carry_wlu, custom["prod"], custom["wl"], tol)
c_status = res["status"]
c_feas = fte.check_feasibility(custom["reg"], custom["ot"], pol)
c_bud = fte.budget_check(res["projected_total_labor_cost"], budget)
c_fte = fte.fte_summary(res["projected_required_labor_hours"], res["expected_total_available_hours"], pol.shift_hours)
ui.kpi_row([
    {"label": "Total available labor", "value": f"{res['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "Required vs available FTE", "value": f"{c_fte['required_fte']:,.2f} / {c_fte['available_fte']:,.2f}",
     "sub": f"FTE gap {c_fte['fte_gap']:+.2f} · extra shifts {c_fte['additional_shifts']}"},
    {"label": "Capacity gap (incl. carry-in)", "value": f"{res['capacity_gap_hours']:+,.1f}", "unit": "hrs",
     "sub": f"{c_status} · new work only {res['new_work_gap_hours']:+,.1f}", "status": c_status},
    {"label": "Backlog risk", "value": logic.backlog_risk(res["projected_capacity_utilization"]),
     "status": logic.backlog_risk(res["projected_capacity_utilization"]),
     "sub": f"Utilization {res['projected_capacity_utilization']:.0%}"},
    {"label": "Labor cost", "value": ui.fmt_money(res["projected_total_labor_cost"]),
     "sub": f"{res['projected_total_labor_cost'] - b_cost:+,.0f} vs current plan" + (f" · {c_bud['label']}" if c_bud else ""),
     "status": None if c_bud is None or c_bud["within"] else "Shortage"},
])
if not c_feas["feasible"]:
    ui.status_banner("Shortage", "Infeasible custom scenario: " + " ".join(c_feas["issues"])
                     + " It can be explored here but cannot be taken forward to the decision.")
elif c_feas["warnings"]:
    st.warning(" ".join(c_feas["warnings"]))
else:
    st.success(f"Feasible: {c_feas['scheduled_workers']:.0f} scheduled workers within the roster of {pol.roster_workers}, "
               f"minimum of {pol.min_workers} (project assumption) and overtime cap of {c_feas['overtime_cap']:g} h.")
ui.note("Uses the pipeline's rules: available regular hours = planned × expected availability; overtime paid at 1.5× the "
        f"average worker rate; manager cost unchanged. Feasibility uses the sidebar policy: roster {pol.roster_workers}, "
        f"minimum {pol.min_workers} workers (project assumption), overtime ≤ {pol.max_ot_per_worker_day:g} h per scheduled worker.")

# ---- Selection --------------------------------------------------------------
ui.section("Select a staffing option")
options = ACTION_SCENARIOS + ["CUSTOM"]
labels = {**SCENARIO_LABELS, "CUSTOM": "Custom (inputs above)"}
rec = logic.recommend(day, tbl, tol)
current = st.session_state.get("scenario_choice", rec["scenario_id"])
choice = st.radio("Staffing option", options, index=options.index(current) if current in options else 0,
                  format_func=lambda k: labels[k] + ("  (recommended)" if k == rec["scenario_id"] else ""),
                  horizontal=True, label_visibility="collapsed")
st.session_state["scenario_choice"] = choice

if choice == "CUSTOM":
    chosen = {**res, "scenario_label": "Custom", "status": c_status,
              "feasible": c_feas["feasible"], "feasibility_issues": " ".join(c_feas["issues"])}
else:
    row = tbl[tbl["scenario_id"] == choice].iloc[0]
    chosen = {**row.to_dict(), "status": row["status"]}
ch_bud = fte.budget_check(float(chosen["projected_total_labor_cost"]), budget)
st.session_state["chosen_scenario"] = {
    "forecast_id": fid, "scenario_id": choice, "label": labels[choice],
    "planned_regular_hours": float(chosen["planned_regular_hours"]),
    "planned_overtime_hours": float(chosen["planned_overtime_hours"]),
    "expected_total_available_hours": float(chosen["expected_total_available_hours"]),
    "projected_required_labor_hours": float(chosen["projected_required_labor_hours"]),
    "capacity_gap_hours": float(chosen["capacity_gap_hours"]),
    "projected_unprocessed_wlu": float(chosen["projected_ending_backlog_wlu"]),
    "carry_in_wlu": float(carry_wlu),
    "new_work_gap_hours": float(chosen["new_work_gap_hours"]),
    "feasible": bool(chosen["feasible"]),
    "feasibility_issues": chosen["feasibility_issues"],
    "budget": budget,
    "over_budget": bool(ch_bud and not ch_bud["within"]),
    "backlog_risk": logic.backlog_risk(float(chosen["projected_capacity_utilization"])),
    "projected_total_labor_cost": float(chosen["projected_total_labor_cost"]),
    "projected_same_day_shipped_revenue": float(chosen["projected_same_day_shipped_revenue"]),
    "status": chosen["status"],
    "workload": float(custom["wl"]) if choice == "CUSTOM" else float(r["forecast_workload_units"]),
}
cs = st.session_state["chosen_scenario"]
st.markdown(f"<div style='font-size:1.05rem;font-weight:700;margin:0.4rem 0 0.5rem'>Selected: {ui.esc(cs['label'])} &nbsp;"
            f"{ui.badge(cs['status'])}</div>", unsafe_allow_html=True)
s_fte = fte.fte_summary(cs["projected_required_labor_hours"], cs["expected_total_available_hours"], pol.shift_hours)
ui.kpi_row([
    {"label": "Total available labor", "value": f"{cs['expected_total_available_hours']:,.1f}", "unit": "hrs"},
    {"label": "FTE gap", "value": f"{s_fte['fte_gap']:+,.2f}", "unit": "shifts",
     "sub": f"Required {s_fte['required_fte']:,.2f} · available {s_fte['available_fte']:,.2f}"},
    {"label": "Projected capacity gap", "value": f"{cs['capacity_gap_hours']:+,.1f}", "unit": "hrs", "sub": cs["status"], "status": cs["status"]},
    {"label": "Projected backlog risk", "value": cs["backlog_risk"], "status": cs["backlog_risk"]},
    {"label": "Estimated labor cost", "value": ui.fmt_money(cs["projected_total_labor_cost"]),
     "sub": ch_bud["label"] if ch_bud else None, "status": "Shortage" if cs["over_budget"] else None},
])
if not cs["feasible"]:
    st.error(f"This option is infeasible: {cs['feasibility_issues']} Choose a feasible option to continue.")
elif cs["over_budget"]:
    st.warning(f"This option is over the daily labor budget ({ch_bud['label']}). You can continue; the flag is recorded.")

b1, b2, _ = st.columns([1.2, 1, 3])
with b1:
    if st.button("Continue to decision", type="primary", width="stretch", disabled=not cs["feasible"], key="go_decision"):
        st.switch_page("views/decision.py")
with b2:
    if st.button("Return to day detail", width="stretch"):
        st.switch_page("views/day_detail.py")
ui.note("Decision supported: which staffing response gives an acceptable balance of capacity, risk, and cost?")
