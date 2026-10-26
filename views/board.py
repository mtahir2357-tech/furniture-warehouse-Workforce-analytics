import plotly.graph_objects as go
import streamlit as st

from src import decisions, logic, state, ui

as_of = state.as_of()
tol = state.tol()
o = state.current_outlook()
run_key = as_of.strftime("%Y-%m-%d")

ACTION_TEXT = {
    "S01": "Keep current plan",
    "S02": "Add 16 regular hours",
    "S03": "Add 20 overtime hours",
    "S06": "Cut 16 regular hours",
}

# ---- Recommendations for all 14 days ---------------------------------------
recs = []
for _, day in o.iterrows():
    tbl = logic.scenario_table(int(day["forecast_id"]), tol)
    rec = logic.recommend(day, tbl, tol)
    recs.append({"day": day, "rec": rec, "s04": tbl.set_index("scenario_id").loc["S04"]})
approved = decisions.latest_for_run(as_of)


def is_approved(d) -> bool:
    return d.strftime("%Y-%m-%d") in approved.index


def log_row(item) -> dict:
    d, r = item["day"], item["rec"]
    row = r["row"]
    return {
        "forecast_run": run_key,
        "target_date": d["target_date"].strftime("%Y-%m-%d"),
        "scenario": row["scenario_label"],
        "final_action": "Approved recommendation",
        "planned_regular_hours": round(float(row["planned_regular_hours"]), 1),
        "planned_overtime_hours": round(float(row["planned_overtime_hours"]), 1),
        "expected_available_hours": round(float(row["expected_total_available_hours"]), 1),
        "projected_capacity_gap": round(float(row["capacity_gap_hours"]), 1),
        "projected_labor_cost": round(float(row["projected_total_labor_cost"]), 2),
        "notes": "Approved on the decision board",
    }


# ---- Header and verdict -----------------------------------------------------
ui.page_header(
    "Decision board",
    "Every day in the next 14 operating days that needs action, with a recommended response you can approve in one click.",
    as_of,
)

n_short = sum(i["day"]["status"] == "Shortage" for i in recs)
n_surplus = sum(i["day"]["status"] == "Surplus" for i in recs)
residual = sum(i["rec"]["status_after"] == "Shortage" for i in recs)
net_hours = sum(i["rec"]["hours_delta"] for i in recs)
net_cost = sum(i["rec"]["cost_delta"] for i in recs)
n_approved = sum(is_approved(i["day"]["target_date"]) for i in recs)

headline = (f"{n_short} shortage and {n_surplus} surplus day{'s' if n_surplus != 1 else ''} ahead"
            if n_short + n_surplus else "All 14 days are balanced")
sub = ("Approving every recommendation leaves no shortage days." if residual == 0
       else f"Approving every recommendation still leaves {residual} shortage day{'s' if residual > 1 else ''}; review those individually.")
st.markdown(
    f'<div class="hero"><div class="hero-t">{ui.esc(headline)}<span>{ui.esc(sub)}</span></div>'
    f'<div class="hero-k"><div class="l">Net labor hours if approved</div><div class="v">{net_hours:+,.0f} h</div></div>'
    f'<div class="hero-k"><div class="l">Net labor cost if approved</div><div class="v">{ui.fmt_money_delta(net_cost)}</div></div>'
    f'<div class="hero-k"><div class="l">Days approved</div><div class="v">{n_approved} / {len(recs)}</div></div></div>',
    unsafe_allow_html=True,
)

# ---- Before / after chart ---------------------------------------------------
ui.section("Capacity gap now and after the recommended actions",
           f"Each line moves a day from its current gap to the gap after the recommendation. Green band = balanced (±{tol:.0f} h).")
xlab = [i["day"]["target_date"].strftime("%a<br>%b %d") for i in recs]
before = [i["rec"]["gap_before"] for i in recs]
after = [i["rec"]["gap_after"] for i in recs]
fig = go.Figure()
fig.add_hrect(y0=-tol, y1=tol, fillcolor=ui.STATUS["Balanced"]["tint"], line_width=0, layer="below")
fig.add_hline(y=0, line_color=ui.SLATE_LIGHT, line_width=1)
for x, b, a in zip(xlab, before, after):
    if abs(a - b) > 0.05:
        fig.add_scatter(x=[x, x], y=[b, a], mode="lines", line=dict(color=ui.SLATE_LIGHT, width=3), showlegend=False, hoverinfo="skip")
fig.add_scatter(x=xlab, y=before, mode="markers", name="Now (filled)", showlegend=False,
                marker=dict(size=13, color=[ui.STATUS_CHART[i["day"]["status"]] for i in recs], line=dict(color="white", width=1.5)),
                customdata=[i["day"]["status"] for i in recs],
                hovertemplate="%{x}<br>Now %{y:+.1f} h · %{customdata}<extra></extra>")
fig.add_scatter(x=xlab, y=after, mode="markers", name="After (diamond)", showlegend=False,
                marker=dict(size=11, symbol="diamond", color="white",
                            line=dict(color=[ui.STATUS_CHART[i["rec"]["status_after"]] for i in recs], width=2.5)),
                customdata=[ACTION_TEXT[i["rec"]["scenario_id"]] for i in recs],
                hovertemplate="After %{y:+.1f} h<br>%{customdata}<extra></extra>")
fig.update_xaxes(type="category", categoryorder="array", categoryarray=xlab, tickangle=0, tickfont=dict(size=10), tickmode="array", tickvals=xlab,
                 ticktext=[i["day"]["target_date"].strftime("%a<br>%d") for i in recs])
fig.add_scatter(x=[None], y=[None], mode="markers", name="Now", marker=dict(size=11, color=ui.SLATE), hoverinfo="skip")
fig.add_scatter(x=[None], y=[None], mode="markers", name="After recommendation",
                marker=dict(size=10, symbol="diamond", color="white", line=dict(color=ui.SLATE, width=2.5)), hoverinfo="skip")
ui.status_legend(fig, "dot")
fig.update_yaxes(title_text="Capacity gap (hours)")
ui.chart(ui.style_fig(fig, 320))

# ---- Action list ------------------------------------------------------------
needs = [i["day"]["status"] != "Balanced" for i in recs]
action_items = [i for i, n in zip(recs, needs) if n]
calm_items = [i for i, n in zip(recs, needs) if not n]

h1, h2 = st.columns([3, 1.1])
with h1:
    ui.section(f"Needs a decision ({len(action_items)})", "Sorted by date. Review opens the full day analysis and scenario comparison.")
with h2:
    pending = [i for i in recs if not is_approved(i["day"]["target_date"])]
    st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    if st.button(f"Approve all {len(pending)} remaining" if pending else "All approved", type="primary", width="stretch", disabled=not pending):
        decisions.save([log_row(i) for i in pending])
        st.toast(f"Approved {len(pending)} recommendations")
        st.rerun()


def action_card(item, idx: int):
    d, r = item["day"], item["rec"]
    c_now, c_after = ui.STATUS[d["status"]], ui.STATUS[r["status_after"]]
    sid = r["scenario_id"]
    if sid == "S01" and r["standby"]:
        rec_html = (f"<b>Keep current plan, overtime on standby</b><span class='cost'>High-demand test gives "
                    f"{item['s04']['capacity_gap_hours']:+.1f} h · exceedance risk {d['probability_capacity_exceeded']:.0%}</span>")
    elif sid == "S01":
        rec_html = ("<b>Keep current plan</b><span class='cost'>Reducing hours would create a shortage</span>"
                    if d["status"] == "Surplus" else "<b>Keep current plan</b>")
    else:
        verb = "saves" if r["cost_delta"] < 0 else "adds"
        partial = "" if r["full"] else " · closes most of the gap; consider a custom option"
        rec_html = (f"<b>{ACTION_TEXT[sid]}</b><span class='cost'>{verb} ${abs(r['cost_delta']):,.0f} labor cost · "
                    f"{r['status_after'].lower()} after{partial}</span>")
    with st.container(border=True):
        left, mid, right = st.columns([4.2, 1.15, 0.95], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div class="ac"><div class="ac-date">{d["target_date"]:%a %b %d} &nbsp;{ui.badge(d["status"])}'
                f'<small>Day {int(d["horizon_operating_days"])} of 14 · forecast {d["forecast_workload_units"]:,.0f} WLU</small></div>'
                f'<div class="ac-gap"><span style="color:{c_now["dark"]}">{r["gap_before"]:+.1f} h</span><span class="arr">→</span>'
                f'<span style="color:{c_after["dark"]}">{r["gap_after"]:+.1f} h</span></div>'
                f'<div class="ac-rec">{rec_html}</div></div>',
                unsafe_allow_html=True,
            )
        with mid:
            if is_approved(d["target_date"]):
                st.markdown('<span class="approved">✓ Approved</span>', unsafe_allow_html=True)
            elif st.button("Approve", key=f"ap_{idx}", type="primary", width="stretch"):
                decisions.save([log_row(item)])
                st.toast(f"Approved: {ACTION_TEXT[sid]} on {d['target_date']:%b %d}")
                st.rerun()
        with right:
            if st.button("Review", key=f"rv_{idx}", width="stretch"):
                state.set_target(d["target_date"])
                st.switch_page("views/day_detail.py")


if not action_items:
    ui.callout(["No day needs a change. Keep the current plan for the whole period."])
for k, item in enumerate(action_items):
    action_card(item, k)

if calm_items:
    n_standby = sum(bool(i["rec"]["standby"]) for i in calm_items)
    extra = f", {n_standby} with overtime on standby" if n_standby else ""
    with st.expander(f"Balanced days ({len(calm_items)}): keep current plan{extra}"):
        for k, item in enumerate(calm_items):
            action_card(item, 100 + k)

ui.note("Recommendation rule: for a shortage, the cheapest predefined option that removes it; for a surplus, cutting hours "
        "unless that creates a shortage; otherwise keep the plan. Approvals are saved to data/decision_log.csv. "
        "The manager makes the final decision.")
