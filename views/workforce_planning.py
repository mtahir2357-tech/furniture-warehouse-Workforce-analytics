"""Manager-facing 14-day workload, FTE and forward-backlog planning.

Chain: Forecast workload -> forecast productivity -> required labor hours -> required FTE
       -> available FTE -> staffing gap -> feasible response / scenario comparison.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import backlog, data, fte, logic, reliability, state, ui
from src import model_comparison as mc
from src.fte import horizon_plan, weekly_fte

as_of = st.session_state['as_of']
tol = st.session_state['tol']
ui.page_header('Workforce planning (FTE)',
               'Can planned staffing handle the next 14 operating days, and how many worker-shift equivalents are needed?',
               as_of)
raw = logic.outlook(as_of, tol)
if raw.empty:
    st.warning('No forecast days in this run.')
    st.stop()
# A run made at the end of its operating day can use that day's observed closing backlog (shared helper).
try:
    carry = backlog.opening_backlog(data.daily(), as_of)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

# ---- Forecast source ----------------------------------------------------------------------
SOURCES = {'pipeline': 'Original 14-day planning forecast',
           'model': 'Validated model selection (Week 12)'}
model_ok = mc.available()
lo, hi = mc.origin_range() if model_ok else (None, None)
c1, c2 = st.columns([1.3, 1])
source = c1.radio('Forecast source', list(SOURCES), format_func=SOURCES.get, horizontal=True, key='wp_source')
buffer_on = c2.toggle('Plan for higher workload (80th-percentile under-forecast)', key='wp_buffer',
                      help='Adds the 80th percentile of past under-forecasts to each day\'s workload to show '
                           'the staffing needed if demand comes in high.')

policy = state.policy()
budget = state.budget()
ui.note(f"Staffing policy (sidebar → Staffing policy & labor budget): {policy.shift_hours:g}-hour shift, "
        f"{policy.week_hours:g}-hour week, roster {policy.roster_workers}, minimum {policy.min_workers} workers "
        f"(project assumption, not source data), overtime ≤ {policy.max_ot_per_worker_day:g} h per worker-day"
        + (f", daily labor budget ${budget:,.0f}." if budget is not None else "; no labor budget set."))

base = pd.DataFrame({
    'target_date': raw['target_date'], 'h': raw['horizon_operating_days'],
    'planned_regular_hours': raw['planned_regular_hours'], 'availability_ratio': raw['availability_ratio'],
    'hourly_rate': raw['avg_worker_hourly_rate'], 'manager_cost': raw['projected_manager_labor_cost'],
})
if source == 'pipeline':
    days = base.assign(workload=raw['forecast_workload_units'].to_numpy(),
                       productivity=raw['expected_productivity_wlu_per_hour'].to_numpy())
    if buffer_on:
        days['workload'] = raw['upper_80_workload_units'].to_numpy()
        _rel = reliability.summary(data.forecasts())
    source_note = ('Original rule-based forecast (same-weekday + recent-mean workload; 28-day mean productivity), '
                   'made with data through the day before the forecast run.'
                   + (f' Higher-workload view uses the pipeline\'s upper 80% bound; across all saved runs the actual '
                      f'workload stayed inside the 80% range on {_rel["coverage_80"]:.0%} of days and exceeded the upper '
                      f'bound on {_rel["above_upper"]:.0%}.' if buffer_on else ''))
else:
    if not model_ok:
        st.warning('Model forecasts are missing; run `python evaluate_forecasting.py`. Showing the original forecast.')
        st.stop()
    sel = mc.selection()
    w = mc.selected_path('workload', as_of)
    p = mc.selected_path('productivity', as_of)
    if w.empty or p.empty:
        st.info(f'Validated model forecasts exist only for forecast runs from {lo:%b %d, %Y} to {hi:%b %d, %Y} '
                '(the validation and final evaluation periods, where every forecast is out-of-sample). '
                'Pick a planning date in that range in the sidebar, or use the original forecast.')
        st.stop()
    m = base.merge(w[['target_date', 'forecast']].rename(columns={'forecast': 'workload'}), on='target_date', how='left')
    m = m.merge(p[['target_date', 'forecast']].rename(columns={'forecast': 'productivity'}), on='target_date', how='left')
    if m[['workload', 'productivity']].isna().any().any():
        st.error('Model forecast dates do not line up with this planning run; not mixing incompatible forecasts.')
        st.stop()
    if buffer_on:
        buf = mc.under_forecast_buffer('workload')
        m['workload'] = m['workload'] + m['h'].map(buf).fillna(0).to_numpy()
    days = m
    wsel, psel = sel['workload']['fourteen_day'], sel['productivity']['fourteen_day']
    source_note = (f"Workload: {mc.MODEL_LABELS[wsel['model']]}; productivity: {mc.MODEL_LABELS[psel['model']]} — the "
                   'lowest validation MAE for 14-day forecasts. Same targets (new WLU; WLU per worker-hour) and the '
                   'same 14 operating days as this run, using outcomes through the planning date. Plan inputs '
                   '(planned hours, availability, wage, manager cost) come from the original run. Neither selection is '
                   'statistically better than the weekday-average baseline (see Model validation).'
                   + (' Higher-workload view adds the 80th-percentile under-forecast of the selected workload model, '
                      'measured on validation forecasts only.' if buffer_on else ''))

plan = horizon_plan(days, carry, policy)
plan['status'] = (-plan['fte_gap'] * policy.shift_hours).map(lambda v: logic.classify_gap(v, tol))
ui.note(source_note)

# ---- Headline -------------------------------------------------------------------------------
n_short = int((plan['fte_gap'] > 1e-9).sum())
infeasible = int((~plan['rec_feasible']).sum())
ui.kpi_row([
    {'label': 'Avg. required FTE', 'value': f"{plan['required_fte'].mean():,.2f}", 'unit': 'shifts/day',
     'sub': f"incl. carry-in backlog · {plan['workload_wlu'].mean():,.0f} WLU/day forecast"},
    {'label': 'Avg. available FTE', 'value': f"{plan['available_fte'].mean():,.2f}", 'unit': 'shifts/day',
     'sub': f"{plan['available_hours'].mean():,.1f} worker hrs/day"},
    {'label': 'Days with an FTE shortage', 'value': n_short, 'unit': f'of {len(plan)}',
     'status': 'Shortage' if n_short else 'Balanced',
     'sub': f"max gap {plan['fte_gap'].max():+.2f} FTE"},
    {'label': 'Feasible response (14 days)', 'value': f"+{int(plan['rec_shift_change'].clip(lower=0).sum())}",
     'unit': 'shifts',
     'sub': f"{plan['rec_overtime_hours'].sum():,.0f} OT h · {int(-plan['rec_shift_change'].clip(upper=0).sum())} shifts released · "
            f"cost {ui.fmt_money_delta(plan['rec_labor_cost'].sum() - plan['labor_cost'].sum())}"},
    {'label': 'Backlog after day 14', 'value': f"{plan.iloc[-1]['ending_backlog_wlu']:,.0f}", 'unit': 'WLU',
     'sub': f"beginning {carry:,.0f} WLU"},
])
if infeasible:
    ui.status_banner('Shortage', f'{infeasible} day(s) cannot be fully covered within the roster and overtime limits; '
                                 'the remaining work is carried forward as backlog.')

# ---- Chart ----------------------------------------------------------------------------------
ui.section('Required versus available FTE', 'Bars: required 8-hour worker-shift equivalents (incl. carry-in backlog). '
           'Line: available FTE under the current plan. Dashed: available after the feasible response.')
xlab = plan['target_date'].dt.strftime('%a<br>%b %d')
fig = go.Figure()
fig.add_bar(x=xlab, y=plan['required_fte'], name='Required FTE', showlegend=False,
            marker_color=[ui.STATUS_CHART[s] for s in plan['status']],
            hovertemplate='%{x}<br>Required %{y:.2f} FTE<extra></extra>')
fig.add_scatter(x=xlab, y=plan['available_fte'], name='Available FTE (current plan)', mode='lines+markers',
                line=dict(color=ui.INK, width=2), hovertemplate='Available %{y:.2f} FTE<extra></extra>')
fig.add_scatter(x=xlab, y=plan['rec_available_fte'], name='Available FTE (feasible response)', mode='lines',
                line=dict(color=ui.BLUE, width=2, dash='dash'), hovertemplate='Response %{y:.2f} FTE<extra></extra>')
ui.status_legend(fig, 'bar')
fig.update_yaxes(title_text='Worker-shift equivalents (FTE)', rangemode='tozero')
fig.update_xaxes(type='category', tickangle=0, tickfont=dict(size=10))
ui.chart(ui.style_fig(fig, 340))

# ---- Daily plan -----------------------------------------------------------------------------
ui.section('Daily FTE plan', 'Current plan, then the lowest-cost feasible response (extra whole shifts first, '
           'overtime for a small remainder; reductions never go below the minimum staffing level).')
show = pd.DataFrame({
    'Date': plan['target_date'],
    'Forecast WLU': plan['workload_wlu'],
    'Productivity (WLU/h)': plan['productivity'],
    'Carry-in WLU': plan['beginning_backlog_wlu'],
    'Required hrs': plan['required_hours'],
    'Available hrs': plan['available_hours'],
    'Required FTE': plan['required_fte'],
    'Available FTE': plan['available_fte'],
    'FTE gap': plan['fte_gap'],
    'Extra shifts': plan['additional_shifts'],
    'Capacity WLU': plan['capacity_wlu'],
    'Ending backlog WLU': plan['ending_backlog_wlu'],
    'Labor cost': plan['labor_cost'],
    'Required FTE (with responses)': plan['rec_required_fte'],
    'Response': [(f"{int(s):+d} shift(s)" if s else 'No shift change') + (f", +{o:.1f} OT h" if o > 1e-9 else '')
                 for s, o in zip(plan['rec_shift_change'], plan['rec_overtime_hours'])],
    'Response cost': plan['rec_labor_cost'],
    'Budget': ['—' if b is None else ('Within' if b['within'] else b['label'])
               for b in (fte.budget_check(c, budget) for c in plan['rec_labor_cost'])],
    'Feasible': plan['rec_feasible'].map({True: 'Yes', False: 'No'}),
    'Status': plan['status'].map(lambda v: f"{ui.STATUS[v]['icon']} {v}"),
})
st.dataframe(show, hide_index=True, width='stretch', height=35 * (len(show) + 1) + 3, column_config={
    'Date': st.column_config.DateColumn(format='ddd MMM DD'),
    'Forecast WLU': st.column_config.NumberColumn(format='%.0f'),
    'Productivity (WLU/h)': st.column_config.NumberColumn(format='%.3f'),
    'Required hrs': st.column_config.NumberColumn(format='%.1f'),
    'Available hrs': st.column_config.NumberColumn(format='%.1f'),
    'Available FTE': st.column_config.NumberColumn(format='%.2f'),
    'FTE gap': st.column_config.NumberColumn(format='%+.2f', help='Required − available FTE; positive = shortage'),
    'Extra shifts': st.column_config.NumberColumn(format='%d', help='Whole 8-hour worker-shift equivalents (rounded up)'),
    'Capacity WLU': st.column_config.NumberColumn(format='%.0f'),
    'Ending backlog WLU': st.column_config.NumberColumn(format='%.0f'),
    'Labor cost': st.column_config.NumberColumn('Labor cost (current)', format='$%.0f'),
    'Required FTE (with responses)': st.column_config.NumberColumn(format='%.2f',
        help='Required FTE when earlier days follow their recommended responses (the carry-in used on other pages).'),
    'Carry-in WLU': st.column_config.NumberColumn('Carry-in WLU (no changes)', format='%.0f'),
    'Required FTE': st.column_config.NumberColumn('Required FTE (no changes)', format='%.2f'),
    'Budget': st.column_config.TextColumn('Budget (response)', help='Response cost vs the optional daily labor budget'),
    'Response cost': st.column_config.NumberColumn(format='$%.0f'),
})
notes = plan.loc[plan['rec_notes'] != '', ['target_date', 'rec_notes']]
if len(notes):
    ui.callout([f"{r.target_date:%a %b %d}: {r.rec_notes}" for r in notes.itertuples()], title='Constraints and limitations')

# ---- Weekly FTE -----------------------------------------------------------------------------
ui.section('Weekly FTE', f'Weekly labor hours ÷ {policy.week_hours:g}-hour full-time week. Partial weeks at the edges '
           'of the 14-day window are labelled.')
wk = plan.groupby('week').agg(days=('target_date', 'size'), first=('target_date', 'min'), last=('target_date', 'max'),
                              required_hours=('required_hours', 'sum'), available_hours=('available_hours', 'sum'),
                              rec_shifts=('rec_scheduled_workers', 'sum'), rec_ot=('rec_overtime_hours', 'sum'),
                              shift_cap=('week_shift_cap_exceeded', 'any'), ot_capx=('week_overtime_cap_exceeded', 'any'))
wk['Required weekly FTE'] = wk['required_hours'].map(lambda v: weekly_fte(v, policy.week_hours))
wk['Available weekly FTE'] = wk['available_hours'].map(lambda v: weekly_fte(v, policy.week_hours))
wk['Week'] = [f"{a:%b %d} – {b:%b %d}" + ('' if n == 6 else f' (partial, {n} days)')
              for a, b, n in zip(wk['first'], wk['last'], wk['days'])]
wk['Roster check'] = [('Exceeds weekly shift capacity' if s else 'Within weekly shift capacity')
                      + ('; exceeds weekly overtime cap' if o else '') for s, o in zip(wk['shift_cap'], wk['ot_capx'])]
st.dataframe(wk[['Week', 'required_hours', 'available_hours', 'Required weekly FTE', 'Available weekly FTE',
                 'rec_shifts', 'Roster check']], hide_index=True, width='stretch', column_config={
    'required_hours': st.column_config.NumberColumn('Required hrs', format='%.1f'),
    'available_hours': st.column_config.NumberColumn('Available hrs', format='%.1f'),
    'Required weekly FTE': st.column_config.NumberColumn(format='%.2f'),
    'Available weekly FTE': st.column_config.NumberColumn(format='%.2f'),
    'rec_shifts': st.column_config.NumberColumn('Shifts in response plan', format='%.0f',
                                                help=f'Roster can work {policy.weekly_shift_cap:,.0f} regular shifts per week'),
})

ui.note('Daily FTE = 8-hour worker-shift equivalents (hours ÷ shift length), not contractual headcount. Available hours = '
        'planned regular hours × expected availability (applied once) + planned overtime; manager hours are excluded '
        'from capacity and only their cost is included. Overtime is paid at 1.5× and is not reduced by availability. '
        'Backlog is projected forward: each day starts with the previous day\'s projected ending backlog. This is a '
        'formula-based plan on synthetic data, not a trained backlog model or a scheduling optimiser.')
st.info('Open **Staffing scenarios** to compare predefined responses for one selected day. Those day-level effects do '
        'not automatically re-optimise the rest of the 14-day schedule.')
