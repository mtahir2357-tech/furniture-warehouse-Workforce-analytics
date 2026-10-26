import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import data, ui

ui.page_header(
    "Operations history",
    "Actual workload, labor, productivity, backlog, and cost for the warehouse's operating days.",
)

d = data.daily()
dmin, dmax = d["date"].min().date(), d["date"].max().date()
c1, c2 = st.columns([1.6, 1])
with c1:
    rng = st.date_input("Period", value=(pd.Timestamp("2025-01-01").date(), dmax), min_value=dmin, max_value=dmax,
                        format="MM/DD/YYYY")
with c2:
    grain = st.radio("Group by", ["Week", "Month"], horizontal=True)
if isinstance(rng, (list, tuple)) and len(rng) == 2:
    start, end = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
else:
    start, end = pd.Timestamp(dmin), pd.Timestamp(dmax)
p = d[d["date"].between(start, end)].copy()
if p.empty:
    st.warning("No operating days in this period. Choose a wider range.")
    st.stop()
freq = "W-SAT" if grain == "Week" else "MS"

ui.kpi_row([
    {"label": "Operating days", "value": f"{len(p):,}"},
    {"label": "Avg. daily workload", "value": f"{p['new_workload_units'].mean():,.0f}", "unit": "WLU",
     "sub": f"{p['new_orders'].mean():,.1f} orders/day"},
    {"label": "Avg. productivity", "value": f"{p['actual_productivity_wlu_per_hour'].mean():.3f}", "unit": "WLU/hr"},
    {"label": "Avg. capacity utilization", "value": f"{p['capacity_utilization'].mean():.1%}"},
    {"label": "On-time shipment rate", "value": f"{p['on_time_orders'].sum() / max(p['orders_shipped'].sum(), 1):.1%}"},
])
ui.kpi_row([
    {"label": "Days with backlog", "value": f"{(p['ending_backlog_wlu'] > 0).sum():,}", "sub": f"{(p['ending_backlog_wlu'] > 0).mean():.0%} of days"},
    {"label": "Days with overtime", "value": f"{(p['worker_overtime_hours'] > 0).sum():,}", "sub": f"{p['worker_overtime_hours'].sum():,.0f} overtime hours"},
    {"label": "Shipped revenue", "value": f"${p['shipped_revenue'].sum() / 1e6:,.1f}M"},
    {"label": "Total labor cost", "value": f"${p['total_labor_cost'].sum() / 1e3:,.0f}K"},
    {"label": "Labor cost % of revenue", "value": f"{p['total_labor_cost'].sum() / p['shipped_revenue'].sum():.2%}"},
])

agg = p.set_index("date").resample(freq).agg({
    "new_workload_units": "sum", "processed_workload_units": "sum", "ending_backlog_wlu": "mean",
    "base_worker_hours": "sum", "extra_hours_worked": "sum", "worker_overtime_hours": "sum", "manager_hours": "sum",
    "actual_productivity_wlu_per_hour": "mean", "capacity_utilization": "mean",
    "shipped_revenue": "sum", "total_labor_cost": "sum", "on_time_orders": "sum", "orders_shipped": "sum",
}).reset_index()
agg = agg[agg["new_workload_units"] > 0]

ui.section("Workload and backlog", f"{grain}ly totals; backlog is the average end-of-day backlog.")
fig = go.Figure()
fig.add_bar(x=agg["date"], y=agg["new_workload_units"], name="New workload (WLU)", marker_color=ui.SLATE_LIGHT,
            hovertemplate="%{x|%b %d, %Y}<br>New %{y:,.0f} WLU<extra></extra>")
fig.add_scatter(x=agg["date"], y=agg["processed_workload_units"], name="Processed (WLU)", mode="lines",
                line=dict(color=ui.NAVY, width=2), hovertemplate="Processed %{y:,.0f} WLU<extra></extra>")
fig.add_scatter(x=agg["date"], y=agg["ending_backlog_wlu"], name="Avg. ending backlog (WLU, right axis)", mode="lines",
                line=dict(color=ui.MUTED, width=1.6, dash="dot"), yaxis="y2", hovertemplate="Backlog %{y:,.1f} WLU<extra></extra>")
fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, rangemode="tozero", tickfont=dict(color=ui.MUTED)))
fig.update_layout(yaxis=dict(title_text="WLU", rangemode="tozero"))
ui.chart(ui.style_fig(fig, 360))

g1, g2 = st.columns(2, gap="large")
with g1:
    ui.section("Labor hours composition")
    fig = go.Figure()
    fig.add_bar(x=agg["date"], y=agg["base_worker_hours"], name="Base worker hours", marker_color=ui.NAVY)
    fig.add_bar(x=agg["date"], y=agg["extra_hours_worked"], name="Extra hours", marker_color=ui.SLATE)
    fig.add_bar(x=agg["date"], y=agg["manager_hours"], name="Manager hours", marker_color=ui.SLATE_LIGHT)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Hours")
    ui.chart(ui.style_fig(fig, 320))
with g2:
    ui.section("Productivity and utilization")
    fig = go.Figure()
    fig.add_scatter(x=agg["date"], y=agg["actual_productivity_wlu_per_hour"], name="Productivity (WLU/hr)", mode="lines",
                    line=dict(color=ui.NAVY, width=2), hovertemplate="%{y:.3f} WLU/hr<extra></extra>")
    fig.add_scatter(x=agg["date"], y=agg["capacity_utilization"] * 100, name="Utilization (%, right axis)", mode="lines",
                    line=dict(color=ui.MUTED, width=1.6, dash="dot"), yaxis="y2", hovertemplate="%{y:.1f}%<extra></extra>")
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color=ui.MUTED)))
    ui.chart(ui.style_fig(fig, 320))

g3, g4 = st.columns(2, gap="large")
with g3:
    ui.section("Labor cost as % of shipped revenue")
    pct = agg["total_labor_cost"] / agg["shipped_revenue"] * 100
    fig = go.Figure(go.Scatter(x=agg["date"], y=pct, mode="lines+markers", line=dict(color=ui.NAVY, width=2),
                               marker=dict(size=4), hovertemplate="%{x|%b %d, %Y}<br>%{y:.2f}%<extra></extra>"))
    fig.update_yaxes(title_text="%")
    ui.chart(ui.style_fig(fig, 300, legend=False))
with g4:
    ui.section("Operating events")
    ev = pd.Series({
        "Promotion": p["promotion_flag"].sum(), "Demand surge": p["demand_surge_flag"].sum(),
        "Equipment issue": p["equipment_issue_flag"].sum(), "Congestion": p["congestion_flag"].sum(),
        "Transportation delay": p["transportation_delay_flag"].sum(),
    }).sort_values()
    fig = go.Figure(go.Bar(y=ev.index, x=ev.values, orientation="h", marker_color=ui.NAVY_MID,
                           text=ev.values, textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x} days<extra></extra>"))
    fig.update_xaxes(title_text="Days", range=[0, max(ev.max() * 1.2, 1)])
    ui.chart(ui.style_fig(fig, 300, legend=False))

g5, g6 = st.columns(2, gap="large")
with g5:
    ui.section("Workload by furniture category", "Share of weighted workload units released in the period.")
    mix = data.product_mix()
    mix = mix[mix["release_date"].between(start, end)]
    cat = mix.groupby("product_category").agg(wlu=("line_workload_units", "sum"), pieces=("quantity_pieces", "sum"),
                                              weight=("workload_weight", "first")).sort_values("wlu")
    fig = go.Figure(go.Bar(y=cat.index, x=cat["wlu"], orientation="h", marker_color=ui.NAVY,
                           customdata=cat[["pieces", "weight"]],
                           text=[f"{v / cat['wlu'].sum():.0%}" for v in cat["wlu"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}<br>%{x:,.0f} WLU · %{customdata[0]:,} pieces<br>Weight %{customdata[1]} WLU/piece<extra></extra>"))
    fig.update_xaxes(title_text="WLU", range=[0, cat["wlu"].max() * 1.15])
    ui.chart(ui.style_fig(fig, 320, legend=False))
with g6:
    ui.section("Average time per workflow activity", "Minutes per shipped order, processing steps only.")
    wf = data.workflow_durations()
    wf = wf[wf["release_date"].between(start, end)]
    act = wf.groupby(["activity_sequence", "activity_name"])["duration_minutes"].mean().reset_index().sort_values("activity_sequence", ascending=False)
    fig = go.Figure(go.Bar(y=act["activity_name"], x=act["duration_minutes"], orientation="h", marker_color=ui.NAVY_MID,
                           text=[f"{v:.1f} min" for v in act["duration_minutes"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f} min<extra></extra>"))
    fig.update_xaxes(title_text="Minutes", range=[0, act["duration_minutes"].max() * 1.2])
    ui.chart(ui.style_fig(fig, 320, legend=False))

if end >= d["date"].max():
    ui.note("The final dataset day force-closes any residual backlog, so its backlog and shipments are not typical.")
