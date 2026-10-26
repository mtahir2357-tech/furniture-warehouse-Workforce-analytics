"""Visual system: navy/gray palette, Public Sans, quiet bordered panels."""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---- Palette ---------------------------------------------------------------
# Frame: deep navy + white cards on a soft gray canvas. Status: traffic-light hues
# chosen to stay distinguishable for red-green color blindness (coral vs teal),
# and always paired with an icon + label so color is never the only signal.
INK = "#0E1A2B"          # headings, sidebar
NAVY = "#1D3A6E"         # main chart series
BLUE = "#2F5BEA"         # actions, selection, links
BLUE_TINT = "#EEF3FE"
NAVY_MID = "#5B7BD5"     # secondary chart series
SLATE = "#8A97AB"
SLATE_LIGHT = "#C9D2E0"
LINE = "#E2E7EF"
PANEL = "#F6F8FB"        # page canvas
CARD = "#FFFFFF"
MUTED = "#5E6B7E"
FONT = "Public Sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

STATUS = {
    "Shortage": {"color": "#D94F4F", "tint": "#FDEDED", "icon": "▼", "dark": "#A83232"},
    "Balanced": {"color": "#1F9D7A", "tint": "#E6F6F1", "icon": "●", "dark": "#14715A"},
    "Surplus":  {"color": "#D99A1E", "tint": "#FDF4E1", "icon": "▲", "dark": "#9A6A0B"},
}
RISK = {"Low": STATUS["Balanced"], "Moderate": STATUS["Surplus"], "High": STATUS["Shortage"]}
STATUS_CHART = {k: v["color"] for k, v in STATUS.items()}
# (fill, text, border) kept for older callers
STATUS_STYLE = {k: (v["tint"], v["dark"], v["color"]) for k, v in STATUS.items()}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select,
[data-testid="stSidebar"] {{ font-family: {FONT}; }}
.block-container {{ padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1340px; }}
h1, h2, h3 {{ color: {INK}; letter-spacing: -0.015em; }}
[data-testid="stSidebar"] .sb-brand {{ font-weight: 800; color: #FFFFFF; font-size: 1.05rem; line-height: 1.25; }}
[data-testid="stSidebar"] .sb-sub {{ color: #9FB0C8; font-size: 0.8rem; margin: 0.2rem 0 0.8rem; }}
[data-testid="stSidebar"] .sb-mark {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:3px; }}

/* Page header */
.ph {{ margin-bottom: 1.2rem; }}
.ph-top {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; }}
.ph-app {{ color: {MUTED}; font-size: 0.82rem; font-weight: 600; }}
.ph-asof {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 999px; padding: 0.25rem 0.75rem;
           color: {INK}; font-size: 0.8rem; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.ph-asof b {{ color: {BLUE}; }}
.ph h1 {{ font-size: 2rem; font-weight: 800; margin: 0.4rem 0 0.2rem 0; padding: 0; }}
.ph-purpose {{ color: {MUTED}; font-size: 0.98rem; max-width: 72ch; }}
.ph-flow {{ margin-top: 0.8rem; display: flex; flex-wrap: wrap; gap: 0.3rem; font-size: 0.78rem; color: {MUTED}; }}
.ph-flow span {{ padding: 0.2rem 0.65rem; border: 1px solid {LINE}; border-radius: 999px; background: {CARD}; }}
.ph-flow span.on {{ background: {BLUE}; border-color: {BLUE}; color: #fff; font-weight: 600; }}

.sec {{ font-size: 1.1rem; font-weight: 700; color: {INK}; margin: 1.6rem 0 0.15rem 0; }}
.sec-cap {{ color: {MUTED}; font-size: 0.87rem; margin-bottom: 0.7rem; max-width: 82ch; }}

/* KPI cards */
.kpi-row {{ display: grid; gap: 0.75rem; margin-bottom: 0.5rem; }}
.kpi {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 10px; padding: 0.85rem 1rem 0.9rem;
        min-width: 0; border-left: 4px solid {LINE}; }}
.kpi.em {{ border-left-color: {BLUE}; background: {BLUE_TINT}; border-color: #D6E1FB; border-left-color: {BLUE}; }}
.kpi-l {{ color: {MUTED}; font-size: 0.78rem; font-weight: 600; }}
.kpi-v {{ color: {INK}; font-size: 1.6rem; font-weight: 750; font-variant-numeric: tabular-nums; margin-top: 0.15rem;
          line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.kpi-v small {{ font-size: 0.82rem; font-weight: 500; color: {MUTED}; margin-left: 0.2rem; }}
.kpi-s {{ color: {MUTED}; font-size: 0.77rem; margin-top: 0.2rem; }}

.badge {{ display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.14rem 0.6rem; border-radius: 999px;
          font-size: 0.76rem; font-weight: 700; border: 1px solid; white-space: nowrap; }}

/* 14-day strip */
.strip {{ display: grid; grid-template-columns: repeat(14, minmax(0, 1fr)); gap: 6px; padding: 3px 3px 4px; }}
@media (max-width: 1100px) {{ .strip {{ grid-template-columns: repeat(7, minmax(0, 1fr)); }} }}
.tile {{ border-radius: 8px; padding: 0.45rem 0.45rem 0.5rem; min-width: 0; overflow: hidden; background: {CARD};
         border: 1px solid {LINE}; border-top: 4px solid; font-variant-numeric: tabular-nums; }}
.tile.sel {{ box-shadow: 0 0 0 2.5px {BLUE}; }}
.tile-d {{ font-size: 0.68rem; color: {MUTED}; white-space: nowrap; }}
.tile-g {{ font-size: 1.12rem; font-weight: 800; margin-top: 0.2rem; }}
.tile-s {{ font-size: 0.64rem; margin-top: 0.1rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.legend {{ display: flex; gap: 1rem; font-size: 0.78rem; color: {MUTED}; margin-top: 0.55rem; align-items: center; flex-wrap: wrap; }}
.legend b {{ font-weight: 700; }}

.formula {{ display: grid; grid-template-columns: 1fr auto 1fr auto 1.15fr; gap: 0.75rem; align-items: center; }}
.formula .op {{ font-size: 1.4rem; color: {MUTED}; text-align: center; }}
.range {{ position: relative; height: 34px; margin: 0.6rem 0 0.2rem; }}
.range .bar {{ position: absolute; top: 13px; height: 8px; background: linear-gradient(90deg, #DCE5F7, #B9C9EE, #DCE5F7); border-radius: 4px; }}
.range .pt {{ position: absolute; top: 7px; width: 4px; height: 20px; background: {NAVY}; border-radius: 2px; }}
.range .cap {{ position: absolute; top: 1px; width: 0; height: 32px; border-left: 2px dashed {STATUS["Shortage"]["color"]}; }}
.range-l {{ display: flex; justify-content: space-between; font-size: 0.78rem; color: {MUTED}; font-variant-numeric: tabular-nums; }}

.callout {{ border-left: 4px solid {BLUE}; background: {CARD}; border-top: 1px solid {LINE}; border-right: 1px solid {LINE};
            border-bottom: 1px solid {LINE}; padding: 0.75rem 1rem; border-radius: 0 10px 10px 0; margin: 0.6rem 0;
            font-size: 0.92rem; color: {INK}; }}
.callout ul {{ margin: 0.25rem 0 0 1.1rem; padding: 0; }}
.callout li {{ margin: 0.18rem 0; }}
.note {{ color: {MUTED}; font-size: 0.8rem; margin-top: 0.4rem; }}
.steps {{ display: flex; gap: 0; margin: 0.4rem 0 1rem; flex-wrap: wrap; }}
.step {{ flex: 1; min-width: 120px; font-size: 0.8rem; color: {MUTED}; padding: 0.45rem 0.6rem; border-top: 3px solid {LINE}; }}
.step.done {{ border-top-color: {BLUE}; color: {INK}; font-weight: 600; }}
.step b {{ display: block; font-size: 0.72rem; color: {MUTED}; font-weight: 500; }}

/* Verdict hero */
.hero {{ border-radius: 12px; padding: 1.1rem 1.3rem; color: #fff; margin: 0.2rem 0 0.9rem;
         background: linear-gradient(120deg, {INK} 0%, #1D3A6E 100%); display: grid;
         grid-template-columns: 1.6fr repeat(3, 1fr); gap: 1rem; align-items: center; }}
.hero-t {{ font-size: 1.25rem; font-weight: 800; line-height: 1.3; }}
.hero-t span {{ color: #9FB0C8; font-weight: 500; font-size: 0.9rem; display: block; margin-top: 0.25rem; }}
.hero-k {{ border-left: 1px solid rgba(255,255,255,0.18); padding-left: 1rem; }}
.hero-k .v {{ font-size: 1.55rem; font-weight: 800; font-variant-numeric: tabular-nums; }}
.hero-k .l {{ font-size: 0.75rem; color: #B8C6DA; font-weight: 600; }}
@media (max-width: 900px) {{ .hero {{ grid-template-columns: 1fr 1fr; }} }}

/* Action cards (decision board) */
.ac {{ display: grid; grid-template-columns: 1.05fr 1.25fr 1.7fr; gap: 1rem; align-items: center; }}
.ac-date {{ font-weight: 800; color: {INK}; font-size: 1.02rem; }}
.ac-date small {{ display:block; color: {MUTED}; font-weight: 500; font-size: 0.75rem; margin-top: 0.15rem; }}
.ac-gap {{ display: flex; align-items: center; gap: 0.45rem; font-variant-numeric: tabular-nums; font-weight: 800; font-size: 1.05rem; }}
.ac-gap .arr {{ color: {SLATE}; font-weight: 500; }}
.ac-gap small {{ display:block; font-size: 0.7rem; font-weight: 600; color: {MUTED}; }}
.ac-rec {{ font-size: 0.9rem; color: {INK}; }}
.ac-rec b {{ font-weight: 700; }}
.ac-rec .cost {{ color: {MUTED}; font-size: 0.8rem; display:block; margin-top: 0.15rem; }}
.approved {{ display:inline-flex; gap:0.35rem; align-items:center; color: {STATUS["Balanced"]["dark"]}; background: {STATUS["Balanced"]["tint"]};
             border: 1px solid {STATUS["Balanced"]["color"]}; border-radius: 8px; padding: 0.42rem 0.7rem; font-weight: 700; font-size: 0.85rem; }}

[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARD}; border-radius: 10px; }}
div.stButton > button, div.stDownloadButton > button {{ border-radius: 8px; font-weight: 600; }}
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 10px; overflow: hidden; background: {CARD}; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


FLOW = ["14-day overview", "Day detail", "Scenarios", "Decision & outcome"]


def page_header(title: str, purpose: str, as_of=None, step: int | None = None):
    asof = f'<div class="ph-asof">Forecast run <b>{as_of:%b %d, %Y}</b></div>' if as_of is not None else ""
    flow = ""
    if step is not None:
        flow = '<div class="ph-flow">' + "".join(
            f'<span class="{"on" if i == step else ""}">{i + 1}. {esc(s)}</span>' for i, s in enumerate(FLOW)
        ) + "</div>"
    st.markdown(
        f"""<div class="ph"><div class="ph-top"><div class="ph-app">Furniture Fulfillment Workforce Planning Tool</div>{asof}</div>
        <h1>{esc(title)}</h1><div class="ph-purpose">{esc(purpose)}</div>{flow}</div>""",
        unsafe_allow_html=True,
    )


def section(title: str, caption: str | None = None):
    cap = f'<div class="sec-cap">{esc(caption)}</div>' if caption else ""
    st.markdown(f'<div class="sec">{esc(title)}</div>{cap}', unsafe_allow_html=True)


def kpi_html(label, value, unit=None, sub=None, emphasis=False, status=None) -> str:
    u = f"<small>{esc(unit)}</small>" if unit else ""
    s = f'<div class="kpi-s">{esc(sub)}</div>' if sub else ""
    style = ""
    c = STATUS.get(status) or RISK.get(status)
    if c is not None:
        style = f' style="border-left-color:{c["color"]};"'
        value_html = f'<span style="color:{c["dark"]}">{esc(value)}</span>'
    else:
        value_html = esc(value)
    return (f'<div class="kpi{" em" if emphasis else ""}"{style}><div class="kpi-l">{esc(label)}</div>'
            f'<div class="kpi-v">{value_html}{u}</div>{s}</div>')


def kpi_row(items: list[dict]):
    cards = "".join(kpi_html(**i) for i in items)
    st.markdown(
        f'<div class="kpi-row" style="grid-template-columns: repeat({len(items)}, minmax(0, 1fr));">{cards}</div>',
        unsafe_allow_html=True,
    )


def badge(status: str, text: str | None = None) -> str:
    c = STATUS.get(status) or RISK.get(status)
    if c is None:
        return f'<span class="badge" style="background:{CARD};color:{INK};border-color:{LINE};">{esc(text or status)}</span>'
    icon = c["icon"] if status in STATUS else "●"
    return (f'<span class="badge" style="background:{c["tint"]};color:{c["dark"]};border-color:{c["color"]};">'
            f'{icon} {esc(text or status)}</span>')


def status_banner(status: str, text: str):
    c = STATUS.get(status, STATUS["Balanced"])
    st.markdown(
        f'<div style="background:{c["tint"]};border:1px solid {c["color"]};border-left:6px solid {c["color"]};border-radius:10px;'
        f'padding:0.8rem 1rem;margin:0.5rem 0;color:{INK};"><b style="color:{c["dark"]}">{c["icon"]} Projected {esc(status.lower())}</b>'
        f' &nbsp;{esc(text)}</div>',
        unsafe_allow_html=True,
    )


def callout(lines: list[str], title: str | None = None):
    t = f"<b>{esc(title)}</b>" if title else ""
    items = "".join(f"<li>{esc(l)}</li>" for l in lines)
    st.markdown(f'<div class="callout">{t}<ul>{items}</ul></div>', unsafe_allow_html=True)


def note(text: str):
    st.markdown(f'<div class="note">{esc(text)}</div>', unsafe_allow_html=True)


def day_strip(o: pd.DataFrame, selected=None):
    tiles = []
    for _, r in o.iterrows():
        c = STATUS[r["status"]]
        sel = " sel" if selected is not None and r["target_date"] == selected else ""
        flag = "Holiday" if r.get("known_holiday_flag", 0) == 1 else ("Promo" if r.get("known_promotion_flag", 0) == 1 else "")
        tiles.append(
            f'<div class="tile{sel}" style="border-top-color:{c["color"]};background:{c["tint"]};" '
            f'title="{esc(r["target_date"].strftime("%A %b %d"))} · {esc(r["status"])}: required {r["projected_required_labor_hours"]:.0f} h, available {r["expected_available_regular_hours"]:.0f} h">'
            f'<div class="tile-d">{r["target_date"]:%a %b %d}</div>'
            f'<div class="tile-g" style="color:{c["dark"]}">{r["capacity_gap_hours"]:+.0f} h</div>'
            f'<div class="tile-s" style="color:{c["dark"]}">{c["icon"]} {esc(flag or r["status"])}</div></div>'
        )
    legend = "".join(
        f'<span><b style="color:{STATUS[s]["color"]}">{STATUS[s]["icon"]}</b> {s}</span>' for s in ["Shortage", "Balanced", "Surplus"]
    )
    st.markdown(
        f'<div class="strip">{"".join(tiles)}</div><div class="legend">{legend}'
        f'<span>Capacity gap = available − required labor hours. Blue outline = day under review.</span></div>',
        unsafe_allow_html=True,
    )


def range_bar(lower, point, upper, capacity=None, unit="WLU"):
    lo = min(lower, capacity) if capacity is not None else lower
    hi = max(upper, capacity) if capacity is not None else upper
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    pos = lambda v: (v - lo) / (hi - lo) * 100
    cap = f'<div class="cap" style="left:{pos(capacity):.2f}%" title="Baseline capacity"></div>' if capacity is not None else ""
    st.markdown(
        f"""<div class="range"><div class="bar" style="left:{pos(lower):.2f}%;width:{pos(upper)-pos(lower):.2f}%"></div>
        <div class="pt" style="left:calc({pos(point):.2f}% - 2px)"></div>{cap}</div>
        <div class="range-l"><span>Low (10th pct) {lower:,.0f} {unit}</span><span>Forecast {point:,.0f} {unit}</span>
        <span>High (90th pct) {upper:,.0f} {unit}</span></div>""",
        unsafe_allow_html=True,
    )


def style_fig(fig: go.Figure, height: int = 340, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=30 if legend else 10, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=INK),
        hoverlabel=dict(font=dict(family=FONT), bgcolor="white", bordercolor=LINE),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11, color=MUTED)),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor="#E6EBF2", zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED))
    return fig


PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def chart(fig: go.Figure):
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def fmt_hours(x, signed=False) -> str:
    return f"{x:+,.1f}" if signed else f"{x:,.1f}"


def fmt_money(x) -> str:
    return f"${x:,.0f}"


def fmt_money_delta(x) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.0f}"


def status_legend(fig: go.Figure, kind: str = "bar"):
    """Legend-only entries, one per status, so swatches match their meaning."""
    for name, c in STATUS.items():
        if kind == "bar":
            fig.add_bar(x=[None], y=[None], name=name, marker_color=c["color"], showlegend=True, hoverinfo="skip")
        else:
            fig.add_scatter(x=[None], y=[None], mode="markers", name=name, marker=dict(size=11, color=c["color"]),
                            showlegend=True, hoverinfo="skip")
