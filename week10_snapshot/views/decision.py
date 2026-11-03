from datetime import datetime

import pandas as pd
import streamlit as st

from src import data, logic, state, ui
from src.config import DECISION_LOG

as_of = state.as_of()
o = state.current_outlook()
r = state.target_row(o)
tol = state.tol()

ui.page_header(
    "Decision and outcome review",
    "Record the staffing action, then compare the plan with what actually happened on the day.",
    as_of,
    step=3,
)


def load_log() -> pd.DataFrame:
    if DECISION_LOG.exists():
        return pd.read_csv(DECISION_LOG)
    return pd.DataFrame()


log = load_log()
key_target = r["target_date"].strftime("%Y-%m-%d")
key_run = as_of.strftime("%Y-%m-%d")
saved = log[(log["target_date"] == key_target) & (log["forecast_run"] == key_run)] if not log.empty else pd.DataFrame()
latest = saved.iloc[-1] if len(saved) else None

chosen_ok = st.session_state.get("chosen_scenario", {}).get("forecast_id") == int(r["forecast_id"])
saved_ok = latest is not None
steps = [("Select scenario", chosen_ok or saved_ok), ("Record decision", saved_ok),
         ("Operating day", saved_ok), ("Review outcome", saved_ok)]
st.markdown('<div class="steps">' + "".join(
    f'<div class="step{" done" if done else ""}"><b>Step {i + 1}</b>{ui.esc(n)}</div>' for i, (n, done) in enumerate(steps)
) + "</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1.3, 1])
with c1:
    if st.button("Back to staffing scenarios", width="stretch"):
        st.switch_page("views/scenarios.py")
with c2:
    st.markdown(f"<div style='padding-top:0.45rem'>Selected date: <b>{r['target_date']:%a %b %d, %Y}</b></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div style='padding-top:0.45rem'>Decision status: <b>{'Saved' if latest is not None else 'Pending'}</b></div>",
                unsafe_allow_html=True)

ui.kpi_row([
    {"label": "Forecast workload", "value": f"{r['forecast_workload_units']:,.0f}", "unit": "WLU"},
    {"label": "Required labor hours", "value": f"{r['projected_required_labor_hours']:,.1f}", "unit": "hrs"},
    {"label": "Original capacity gap", "value": f"{r['capacity_gap_hours']:+,.1f}", "unit": "hrs", "sub": r["status"], "status": r["status"]},
])

# ---- Selected scenario ------------------------------------------------------
cs = st.session_state.get("chosen_scenario")
if not cs or cs["forecast_id"] != int(r["forecast_id"]):
    base = logic.scenario_table(int(r["forecast_id"]), tol).iloc[0]
    cs = {
        "forecast_id": int(r["forecast_id"]), "scenario_id": "S01", "label": "Current plan",
        "planned_regular_hours": base["planned_regular_hours"], "planned_overtime_hours": 0.0,
        "expected_total_available_hours": base["expected_total_available_hours"],
        "projected_required_labor_hours": base["projected_required_labor_hours"],
        "capacity_gap_hours": base["capacity_gap_hours"], "projected_unprocessed_wlu": base["projected_unprocessed_wlu"],
        "backlog_risk": base["backlog_risk"], "projected_total_labor_cost": base["projected_total_labor_cost"],
        "projected_same_day_shipped_revenue": base["projected_same_day_shipped_revenue"], "status": base["status"],
        "workload": float(r["forecast_workload_units"]),
    }
    ui.callout(["No scenario has been selected for this day yet, so the current plan is shown. "
                "Choose another option on the Staffing scenarios page."])

left, right = st.columns([1.1, 1], gap="large")
with left:
    ui.section("1. Selected staffing scenario")
    detail = pd.DataFrame({
        "Item": ["Scenario", "Planned regular hours", "Planned overtime hours", "Total expected available hours",
                 "Projected capacity gap", "Projected backlog risk", "Estimated labor cost"],
        "Value": [cs["label"], f"{cs['planned_regular_hours']:,.0f} h", f"{cs['planned_overtime_hours']:,.0f} h",
                  f"{cs['expected_total_available_hours']:,.1f} h", f"{cs['capacity_gap_hours']:+,.1f} h ({cs['status']})",
                  cs["backlog_risk"], ui.fmt_money(cs["projected_total_labor_cost"])],
    })
    st.dataframe(detail, hide_index=True, width="stretch")

with right:
    ui.section("2. Final manager decision")
    action = st.selectbox("Final action", ["Implement selected scenario", "Keep current plan", "Monitor and revisit tomorrow"])
    notes = st.text_area("Manager notes", placeholder="Operational considerations or reasons for the decision", height=96)
    if st.button("Save decision", type="primary"):
        row = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "forecast_run": key_run, "target_date": key_target,
            "scenario": cs["label"] if action == "Implement selected scenario" else "Current plan",
            "final_action": action,
            "planned_regular_hours": round(cs["planned_regular_hours"], 1),
            "planned_overtime_hours": round(cs["planned_overtime_hours"], 1),
            "expected_available_hours": round(cs["expected_total_available_hours"], 1),
            "projected_capacity_gap": round(cs["capacity_gap_hours"], 1),
            "projected_labor_cost": round(cs["projected_total_labor_cost"], 2),
            "notes": notes.strip(),
        }
        DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([row]).to_csv(DECISION_LOG, mode="a", header=not DECISION_LOG.exists(), index=False)
        st.toast(f"Decision saved for {r['target_date']:%b %d, %Y}")
        st.rerun()
    ui.note("The manager remains responsible for the final staffing decision.")

if latest is not None:
    ui.callout([f"{latest['final_action']} · {latest['scenario']}",
                f"Regular {latest['planned_regular_hours']:,.0f} h + overtime {latest['planned_overtime_hours']:,.0f} h · saved {latest['saved_at']}"]
               + ([f"Notes: {latest['notes']}"] if isinstance(latest["notes"], str) and latest["notes"] else []),
               title=f"Decision saved for {r['target_date']:%b %d, %Y}")

# ---- Outcome ----------------------------------------------------------------
d = data.daily()
act = d[d["date"] == r["target_date"]]
ui.section("3. Actual results after the operating day")
if act.empty:
    ui.callout(["No actual outcome is recorded for this date."])
    st.stop()
a = act.iloc[0]
ui.kpi_row([
    {"label": "Actual new workload", "value": f"{a['new_workload_units']:,.0f}", "unit": "WLU"},
    {"label": "Actual worker hours", "value": f"{a['worker_total_hours']:,.1f}", "unit": "hrs"},
    {"label": "Extra hours worked", "value": f"{a['extra_hours_worked']:,.1f}", "unit": "hrs",
     "sub": f"{a['worker_overtime_hours']:,.1f} h paid as overtime"},
    {"label": "Ending backlog", "value": f"{a['ending_backlog_wlu']:,.1f}", "unit": "WLU"},
    {"label": "Shipped revenue", "value": ui.fmt_money(a["shipped_revenue"])},
    {"label": "Actual labor cost", "value": ui.fmt_money(a["total_labor_cost"])},
])

ui.section("4. Forecast and plan vs. actual")
comp = pd.DataFrame([
    ("Workload (WLU)", cs["workload"], a["new_workload_units"]),
    ("Productivity (WLU/hr)", r["expected_productivity_wlu_per_hour"], a["actual_productivity_wlu_per_hour"]),
    ("Worker labor hours", cs["expected_total_available_hours"], a["worker_total_hours"]),
    ("Overtime / extra hours", cs["planned_overtime_hours"], a["extra_hours_worked"]),
    ("Unprocessed / ending backlog (WLU)", cs["projected_unprocessed_wlu"], a["ending_backlog_wlu"]),
    ("Labor cost (USD)", cs["projected_total_labor_cost"], a["total_labor_cost"]),
    ("Shipped revenue (USD)", cs["projected_same_day_shipped_revenue"], a["shipped_revenue"]),
], columns=["Metric", "Forecast / plan", "Actual"])
comp["Difference"] = comp["Actual"] - comp["Forecast / plan"]
comp["Difference %"] = comp["Difference"] / comp["Forecast / plan"].where(comp["Forecast / plan"] != 0) * 100
show = comp.copy()
for c in ["Forecast / plan", "Actual"]:
    show[c] = comp[c].map(lambda v: f"{v:,.2f}")
show["Difference"] = comp["Difference"].map(lambda v: f"{v:+,.2f}")
show["Difference %"] = comp["Difference %"].map(lambda v: "—" if pd.isna(v) else f"{v:+.1f}%")
st.dataframe(show, hide_index=True, width="stretch")

ui.section("What happened")
wl_err = a["new_workload_units"] - cs["workload"]
in_range = r["lower_80_workload_units"] <= a["new_workload_units"] <= r["upper_80_workload_units"]
happened = [
    f"Actual workload was {abs(wl_err):,.0f} WLU ({abs(wl_err) / cs['workload']:.0%}) {'above' if wl_err > 0 else 'below'} forecast, "
    f"{'inside' if in_range else 'outside'} the 80% range.",
    f"Productivity was {a['actual_productivity_wlu_per_hour']:.3f} WLU/hr vs {r['expected_productivity_wlu_per_hour']:.3f} expected.",
    f"The operation worked {a['extra_hours_worked']:,.1f} extra hours vs {cs['planned_overtime_hours']:,.0f} planned.",
    "No backlog remained at day end." if a["ending_backlog_wlu"] == 0 else f"{a['ending_backlog_wlu']:,.1f} WLU carried into the next day as backlog.",
    f"Actual labor cost was {a['total_labor_cost'] - cs['projected_total_labor_cost']:+,.0f} USD vs the plan estimate.",
]
flags = [n for n, c in [("promotion", "promotion_flag"), ("demand surge", "demand_surge_flag"), ("equipment issue", "equipment_issue_flag"),
                        ("congestion", "congestion_flag"), ("transportation delay", "transportation_delay_flag")] if a[c] == 1]
if flags:
    happened.append("Operating events that day: " + ", ".join(flags) + ".")
ui.callout(happened)
ui.note("Actual results are the synthetic outcomes stored in the dataset; the simulated operation did not follow the decision recorded here. "
        "Actual required labor and backlog also include carry-in backlog from earlier days.")
if r["target_date"] == d["date"].max():
    ui.note("This is the last day of the dataset, where residual backlog is force-closed. Treat its backlog result as non-typical.")

# ---- History ----------------------------------------------------------------
ui.section("Decision history")
log = load_log()
if log.empty:
    st.caption("No decisions saved yet. Saved decisions are stored in data/decision_log.csv.")
else:
    st.dataframe(log.iloc[::-1], hide_index=True, width="stretch")
    st.download_button("Download decision log (CSV)", log.to_csv(index=False).encode(), "decision_log.csv", "text/csv")

b1, _ = st.columns([1.2, 4])
with b1:
    if st.button("Return to 14-day overview", width="stretch"):
        st.switch_page("views/overview.py")
ui.note("Decision supported: was the staffing action appropriate, and how did results compare with the plan?")
