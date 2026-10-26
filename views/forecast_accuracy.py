import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import data, logic, ui

ui.page_header(
    "Forecast accuracy",
    "How close rolling 14-day workload forecasts came to actual workload, and how well the 80% range held.",
)

f = data.forecasts()
fmin, fmax = f["forecast_date"].min().date(), f["forecast_date"].max().date()
c1, c2 = st.columns([1.6, 1])
with c1:
    rng = st.date_input("Forecast origin dates", value=(fmin, fmax), min_value=fmin, max_value=fmax, format="MM/DD/YYYY")
with c2:
    horizons = st.slider("Horizon (operating days ahead)", 1, 14, (1, 14))
if isinstance(rng, (list, tuple)) and len(rng) == 2:
    start, end = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
else:
    start, end = pd.Timestamp(fmin), pd.Timestamp(fmax)
sub = f[(f["forecast_date"].between(start, end)) & (f["horizon_operating_days"].between(*horizons))]

m = logic.accuracy_metrics(sub)
if sub.empty:
    st.warning("No forecasts match these filters. Widen the date range or horizon.")
    st.stop()
ui.kpi_row([
    {"label": "MAE", "value": f"{m['mae']:,.1f}", "unit": "WLU", "sub": "Mean absolute error"},
    {"label": "RMSE", "value": f"{m['rmse']:,.1f}", "unit": "WLU", "sub": "Penalizes large misses"},
    {"label": "WAPE", "value": f"{m['wape']:.1%}", "sub": "Absolute error ÷ actual workload"},
    {"label": "Bias", "value": f"{m['bias']:+,.2f}", "unit": "WLU", "sub": "Actual − forecast; + means under-forecast"},
    {"label": "80% range coverage", "value": f"{m['coverage']:.1%}", "sub": "Target 80%", "emphasis": True},
])
ui.note(f"{m['n']:,} forecast rows · {sub['forecast_run_id'].nunique():,} forecast runs")

# ---- By horizon -------------------------------------------------------------
sub = sub.assign(covered=(sub["actual_workload_units"] >= sub["lower_80_workload_units"])
                 & (sub["actual_workload_units"] <= sub["upper_80_workload_units"]),
                 err=sub["actual_workload_units"] - sub["forecast_workload_units"])
by_h = sub.groupby("horizon_operating_days").apply(
    lambda g: pd.Series(logic.accuracy_metrics(g)), include_groups=False).reset_index()

g1, g2 = st.columns(2, gap="large")
with g1:
    ui.section("Error by horizon")
    fig = go.Figure()
    fig.add_bar(x=by_h["horizon_operating_days"], y=by_h["mae"], name="MAE", marker_color=ui.NAVY,
                hovertemplate="Day %{x}<br>MAE %{y:,.1f} WLU<extra></extra>")
    fig.add_bar(x=by_h["horizon_operating_days"], y=by_h["rmse"], name="RMSE", marker_color=ui.SLATE_LIGHT,
                hovertemplate="Day %{x}<br>RMSE %{y:,.1f} WLU<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Operating days ahead", dtick=1)
    fig.update_yaxes(title_text="WLU")
    ui.chart(ui.style_fig(fig, 320))
with g2:
    ui.section("80% range coverage by horizon")
    fig = go.Figure()
    fig.add_scatter(x=by_h["horizon_operating_days"], y=by_h["coverage"] * 100, mode="lines+markers", name="Coverage",
                    line=dict(color=ui.NAVY, width=2.4), hovertemplate="Day %{x}<br>%{y:.1f}%<extra></extra>")
    fig.add_hline(y=80, line_dash="dash", line_color=ui.MUTED, annotation_text="80% target",
                  annotation_position="bottom right", annotation_font_color=ui.MUTED)
    lo = min(50, (by_h["coverage"].min() * 100) - 5)
    fig.update_yaxes(title_text="% of actuals inside range", range=[lo, 100])
    fig.update_xaxes(title_text="Operating days ahead", dtick=1)
    ui.chart(ui.style_fig(fig, 320, legend=False))

# ---- Forecast vs actual over time --------------------------------------------
ui.section("Forecast vs. actual workload", "One horizon at a time, so each target day appears once. Drag the slider below the chart to move through time.")
h1, h2 = st.columns([1, 3])
with h1:
    h = st.selectbox("Horizon", list(range(horizons[0], horizons[1] + 1)), format_func=lambda x: f"{x} day{'s' if x > 1 else ''} ahead")
ts = sub[sub["horizon_operating_days"] == h].sort_values("target_date")
fig = go.Figure()
fig.add_scatter(x=ts["target_date"], y=ts["upper_80_workload_units"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
fig.add_scatter(x=ts["target_date"], y=ts["lower_80_workload_units"], mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(47,91,234,0.13)", name="80% range", hoverinfo="skip")
fig.add_scatter(x=ts["target_date"], y=ts["forecast_workload_units"], mode="lines+markers", marker=dict(size=3), name="Forecast",
                line=dict(color=ui.NAVY, width=1.6), hovertemplate="%{x|%b %d, %Y}<br>Forecast %{y:,.0f}<extra></extra>")
fig.add_scatter(x=ts["target_date"], y=ts["actual_workload_units"], mode="markers", name="Actual",
                marker=dict(color=ui.INK, size=4, opacity=0.7), hovertemplate="Actual %{y:,.0f}<extra></extra>")
fig.update_yaxes(title_text="WLU")
if len(ts):
    x_end = ts["target_date"].max()
    fig.update_xaxes(range=[max(ts["target_date"].min(), x_end - pd.Timedelta(days=120)), x_end + pd.Timedelta(days=2)])
fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06))
ui.chart(ui.style_fig(fig, 400))

g3, g4 = st.columns(2, gap="large")
with g3:
    ui.section("Distribution of errors", "Actual − forecast. Values right of zero are under-forecasts.")
    fig = go.Figure(go.Histogram(x=sub["err"], nbinsx=60, marker_color=ui.NAVY_MID, marker_line=dict(color="white", width=0.5),
                                 hovertemplate="%{x}<br>%{y} forecasts<extra></extra>"))
    fig.add_vline(x=0, line_color=ui.MUTED, line_dash="dot")
    fig.update_xaxes(title_text="Error (WLU)")
    fig.update_yaxes(title_text="Forecasts")
    ui.chart(ui.style_fig(fig, 300, legend=False))
with g4:
    ui.section("Accuracy by target weekday")
    by_d = sub.groupby("day_name").apply(lambda g: pd.Series(logic.accuracy_metrics(g)), include_groups=False)
    days = [d for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] if d in by_d.index]
    by_d = by_d.loc[days]
    fig = go.Figure(go.Bar(x=[d[:3] for d in days], y=by_d["wape"] * 100, marker_color=ui.NAVY,
                           text=[f"{v:.1%}" for v in by_d["wape"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}<br>WAPE %{y:.1f}%<extra></extra>"))
    fig.update_yaxes(title_text="WAPE (%)", range=[0, by_d["wape"].max() * 118])
    ui.chart(ui.style_fig(fig, 300, legend=False))

ui.section("Accuracy table by horizon")
st.dataframe(by_h.rename(columns={"horizon_operating_days": "Horizon"}), hide_index=True, width="stretch",
             height=35 * (len(by_h) + 1) + 3,
             column_config={
                 "n": st.column_config.NumberColumn("N", format="%d"),
                 "mae": st.column_config.NumberColumn("MAE", format="%.2f"),
                 "rmse": st.column_config.NumberColumn("RMSE", format="%.2f"),
                 "wape": st.column_config.NumberColumn("WAPE", format="percent"),
                 "bias": st.column_config.NumberColumn("Bias", format="%+.2f"),
                 "coverage": st.column_config.NumberColumn("80% coverage", format="percent"),
             }, column_order=["Horizon", "n", "mae", "rmse", "wape", "bias", "coverage"])
ui.note("Coverage is recomputed from the stored lower/upper bounds and actual workload. The forecast model uses only information "
        "available before each forecast date; demand surges are not known in advance.")
