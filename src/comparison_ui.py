"""Shared "Forecasting Model Comparison" section (Model validation + Predictive modeling pages)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src import model_comparison as mc
from src import ui

MODEL_COLORS = {"weekday_average": ui.SLATE, "random_forest": ui.STATUS["Balanced"]["color"],
                "xgboost": ui.STATUS["Surplus"]["color"], "prophet": ui.BLUE}

METHOD_TEXT = {
    "weekday_average": "Forecasts each day as the historical average of the same weekday (all Mondays, all Tuesdays, …), "
                       "using only days up to the forecast date. No training; the reference every model must beat.",
    "random_forest": "Averages many decision trees trained on recent history (last value, 7- and 28-day averages, recent "
                     "same-weekday values) plus the target day's calendar. The original Week 10/11 feature set was "
                     "re-tested and reproduces its Week 11 results exactly; the configuration shown was chosen on validation.",
    "xgboost": "Gradient-boosted trees built one after another, each correcting the last, on the same leakage-safe "
               "history features as Random Forest. Shallow, regularised trees were tuned on the validation window only.",
    "prophet": "Meta's additive time-series model: trend + weekly + yearly seasonality + published holidays. Refitted "
               "at every forecast date on history up to that date, so it never sees later outcomes.",
}


def _fmt(kpi):
    return "%.2f" if kpi == "workload" else "%.4f"


def render(key: str, compact: bool = False):
    """Interactive comparison. ``key`` keeps widget state separate on each page."""
    ui.section("Forecasting Model Comparison",
               "Four forecasting methods compared on identical forecast dates and target days, chronologically. "
               "All values are read from the saved evaluation (python evaluate_forecasting.py).")
    if not mc.available():
        st.warning("Comparison results are missing. Run `python evaluate_forecasting.py` to create "
                   "models/forecast_comparison/.")
        return
    c1, c2, c3 = st.columns([1, 1, 1.2])
    kpi = c1.selectbox("KPI", list(mc.KPI_LABELS), format_func=mc.KPI_LABELS.get, key=f"{key}_kpi")
    horizon = c2.selectbox("Forecast horizon", list(mc.HORIZON_LABELS), format_func=mc.HORIZON_LABELS.get, key=f"{key}_h")
    period = c3.selectbox("Evaluation period", list(mc.PERIOD_LABELS), format_func=mc.PERIOD_LABELS.get, key=f"{key}_p")
    m = mc.metrics()
    t = mc.comparison_table(m, period, kpi, horizon)
    row = m[(m["period"] == period) & (m["kpi"] == kpi) & (m["horizon"] == horizon)].iloc[0]
    unit = mc.KPI_UNITS[kpi]
    best_model = t.loc[t["Rank"] == 1, "model"].iloc[0]
    sel = mc.selection()[kpi][horizon]

    show = t.drop(columns=["model"])
    styled = show.style.apply(
        lambda r: [f"background-color: {ui.BLUE_TINT}; font-weight: 700" if t.loc[r.name, "model"] == best_model else ""
                   for _ in r], axis=1)
    st.dataframe(styled, hide_index=True, width="stretch", column_config={
        "MAE": st.column_config.NumberColumn(f"MAE ({unit})", format=_fmt(kpi)),
        "RMSE": st.column_config.NumberColumn(f"RMSE ({unit})", format=_fmt(kpi)),
        "WAPE (%)": st.column_config.NumberColumn(format="%.2f"),
        "Bias": st.column_config.NumberColumn(f"Bias ({unit})", format=_fmt(kpi),
                                              help="Mean of actual − forecast. Positive = under-forecast."),
        "Improvement vs Baseline (%)": st.column_config.TextColumn(help="MAE reduction versus the weekday-average baseline."),
        "p-value vs baseline": st.column_config.TextColumn(
            help="Diebold-Mariano test of equal absolute error versus the baseline (Newey-West variance for "
                 "overlapping 14-day windows). p ≥ 0.05 means the difference is not statistically reliable."),
        "Peak-day MAE": st.column_config.NumberColumn(f"Peak-day MAE ({unit})", format=_fmt(kpi)),
    })
    period_note = ("Validation forecasts come from models trained on development data only; this window chose each "
                   "method's settings, so tuned methods are slightly flattered." if period == "validation" else
                   "Final period: settings fixed on validation, models refitted on development + validation data. "
                   "These dates were already viewed in Week 11, so this is a retrospective check, not an untouched test.")
    ui.note(f"Highlighted = lowest MAE in this table. {int(row['n_origins'])} forecast dates, {int(row['n_forecasts'])} "
            f"forecasts, targets {row['first_target']} to {row['last_target']}. {period_note}")

    cur = m[(m["period"] == period) & (m["kpi"] == kpi) & (m["horizon"] == horizon)]
    spread = (cur["mae"].max() - cur["mae"].min()) / cur["mae"].min() * 100
    sig_better = cur[(cur["model"] != "weekday_average") & (cur["dm_p_vs_baseline"] < 0.05) & (cur["improvement_vs_baseline_pct"] > 0)]
    sig_worse = cur[(cur["model"] != "weekday_average") & (cur["dm_p_vs_baseline"] < 0.05) & (cur["improvement_vs_baseline_pct"] < 0)]
    evidence = (f"In this view the best and worst MAE differ by {spread:.1f}%. "
                + (f"Statistically better than the baseline (p < 0.05): {', '.join(sig_better['model'].map(mc.MODEL_LABELS))}. "
                   if len(sig_better) else "No trained model is statistically better than the weekday-average baseline. ")
                + (f"Statistically worse: {', '.join(sig_worse['model'].map(mc.MODEL_LABELS))}." if len(sig_worse) else ""))
    ui.callout([
        mc.describe_selection(kpi, horizon),
        f"Final-period check: the selected method ranks #{sel['final_rank']} of 4; the lowest final-period MAE belongs to "
        f"{mc.MODEL_LABELS[sel['final_best_model']]}.",
        evidence,
        "Limitation: synthetic data, small margins and overlapping 14-day windows; treat the ranking as weak evidence "
        "and keep the simple baseline as a credible fallback.",
    ], title=f"Strongest validated method · {mc.KPI_LABELS[kpi]} · {mc.HORIZON_LABELS[horizon].lower()}")

    p = mc.predictions()
    p = p[(p["period"] == period) & (p["kpi"] == kpi) & (p["horizon"] == horizon) & (p["scored"] == 1)]
    h_pick = 1
    if horizon == "fourteen_day":
        h_pick = st.slider("Show forecasts made this many operating days ahead", 1, 14, 1, key=f"{key}_hpick")
    default = list(dict.fromkeys([best_model, "weekday_average"]))
    shown = st.multiselect("Methods on the chart", mc.MODELS, default=default, format_func=mc.MODEL_LABELS.get,
                           key=f"{key}_show")
    ph = p[p["h"] == h_pick]
    actual = ph.drop_duplicates("target_date").sort_values("target_date")
    fig = go.Figure()
    fig.add_scatter(x=actual["target_date"], y=actual["actual"], name="Actual", mode="lines",
                    line=dict(color=ui.INK, width=1.6))
    for mdl in shown:
        x = ph[ph["model"] == mdl].sort_values("target_date")
        fig.add_scatter(x=x["target_date"], y=x["forecast"], name=mc.MODEL_LABELS[mdl], mode="lines",
                        line=dict(color=MODEL_COLORS[mdl], width=1.8, dash="dot" if mdl == "weekday_average" else "solid"))
    fig.update_yaxes(title_text=f"{mc.KPI_LABELS[kpi]} ({unit})")
    ui.section(f"Actual versus predicted {mc.KPI_LABELS[kpi].lower()}",
               f"Forecasts made {h_pick} operating day{'s' if h_pick > 1 else ''} before each target day.")
    ui.chart(ui.style_fig(fig, 340))
    if compact:
        return

    g1, g2 = st.columns(2, gap="large")
    tt = t.set_index("model")
    with g1:
        ui.section("Forecast error comparison", "Lower is better. MAE and RMSE in KPI units.")
        fig = go.Figure()
        fig.add_bar(x=tt["Model"], y=tt["MAE"], name="MAE", marker_color=[MODEL_COLORS[k] for k in tt.index])
        fig.add_bar(x=tt["Model"], y=tt["RMSE"], name="RMSE", marker_color=ui.SLATE_LIGHT)
        fig.update_layout(barmode="group")
        fig.update_yaxes(title_text=unit)
        ui.chart(ui.style_fig(fig, 300))
    with g2:
        ui.section("Peak-demand performance",
                   "Error on the busiest days (actual workload ≥ the 90th percentile of the development period).")
        fig = go.Figure()
        fig.add_bar(x=tt["Model"], y=m.set_index(["period", "kpi", "horizon", "model"]).loc[(period, kpi, horizon)]
                    .loc[tt.index, "peak_mae"], name="Peak-day MAE", marker_color=[MODEL_COLORS[k] for k in tt.index])
        fig.add_bar(x=tt["Model"], y=m.set_index(["period", "kpi", "horizon", "model"]).loc[(period, kpi, horizon)]
                    .loc[tt.index, "peak_bias"], name="Peak-day bias (actual − forecast)", marker_color=ui.SLATE_LIGHT)
        fig.update_layout(barmode="group")
        fig.update_yaxes(title_text=unit)
        ui.chart(ui.style_fig(fig, 300))
    ui.note(f"Peak days in this view: {int(row['peak_n'])} forecasts. Peak classification uses the realised workload, "
            "so it is a post-hoc diagnostic, not something known before the shift. Positive peak bias = busy days "
            "are under-forecast, which is the main staffing risk.")

    seg = mc.segments()
    group = "h" if horizon == "fourteen_day" else "month"
    s = seg[(seg["period"] == period) & (seg["kpi"] == kpi) & (seg["horizon"] == horizon) & (seg["group"] == group)].copy()
    s["x"] = s["segment"].astype(int) if group == "h" else s["segment"]
    ui.section("Consistency across " + ("forecast horizons" if group == "h" else "months"),
               "MAE by " + ("operating days ahead" if group == "h" else "target month") + ". Crossing lines mean no "
               "method dominates in every condition.")
    fig = go.Figure()
    for mdl in mc.MODELS:
        x = s[s["model"] == mdl].sort_values("x")
        fig.add_scatter(x=x["x"], y=x["mae"], name=mc.MODEL_LABELS[mdl], mode="lines+markers",
                        line=dict(color=MODEL_COLORS[mdl], width=2, dash="dot" if mdl == "weekday_average" else "solid"))
    fig.update_yaxes(title_text=f"MAE ({unit})")
    fig.update_xaxes(title_text="Operating days ahead" if group == "h" else "Month", type="category" if group != "h" else "linear")
    ui.chart(ui.style_fig(fig, 300))
    c = mc.consistency()
    c = c[(c["period"] == period) & (c["kpi"] == kpi) & (c["horizon"] == horizon)].copy()
    c["Model"] = c["model"].map(mc.MODEL_LABELS)
    c["order"] = c["model"].map({k: i for i, k in enumerate(mc.MODELS)})
    st.dataframe(c.sort_values("order")[["Model", "months", "months_ranked_first", "months_beating_baseline",
                                         "best_month_mae", "worst_month_mae"]],
                 hide_index=True, width="stretch", column_config={
                     "months": st.column_config.NumberColumn("Months"),
                     "months_ranked_first": st.column_config.NumberColumn("Months ranked 1st"),
                     "months_beating_baseline": st.column_config.NumberColumn("Months beating baseline"),
                     "best_month_mae": st.column_config.NumberColumn("Best month MAE", format=_fmt(kpi)),
                     "worst_month_mae": st.column_config.NumberColumn("Worst month MAE", format=_fmt(kpi)),
                 })

    with st.expander("How each method works (plain language)"):
        for mdl in mc.MODELS:
            st.markdown(f"**{mc.MODEL_LABELS[mdl]}** — {METHOD_TEXT[mdl]}")
    with st.expander("Evaluation rules and limitations", expanded=False):
        pr = mc.protocol()
        b = pr["boundaries"]
        rep = mc.reproduction()
        rep_line = ""
        if rep:
            w = rep.get("workload", {}).get("existing_revised", {})
            q = rep.get("productivity", {}).get("existing_revised", {})
            if w and q:
                rep_line = (f"- **Existing Random Forest reproduced:** Week 11 selected models give final-period MAE "
                            f"{w['mae']:.2f} WLU and {q['mae']:.4f} WLU/hour in this framework "
                            f"({'identical to' if w.get('matches_week11') and q.get('matches_week11') else 'compare with'} "
                            "models/week11_evaluation.csv).\n")
        st.markdown(
            f"- **Chronological split (same dates as Week 11):** development to {b['dev_end']}; validation "
            f"{b['val_start']} – {b['val_end']}; final period {b['test_start']} – {b['test_end']}. No random shuffling.\n"
            f"- **Forecast-origin rule:** {pr['forecast_origin_rule']}\n"
            f"- **Tuning:** {pr['tuning']}\n"
            f"- **Prophet:** {pr['prophet']}\n"
            f"- **Random Forest / XGBoost:** {pr['tabular_models']}\n"
            f"- **Scoring:** {pr['scoring']}\n"
            f"- **Peak demand:** {pr['peak_demand_definition']}\n"
            f"- **Final period status:** {pr['final_period_status']}\n"
            + rep_line
            + "".join(f"- {lim}\n" for lim in pr["limitations"])
        )
