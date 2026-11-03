"""Manager-facing 14-day workload and forward-backlog planning."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src import data,logic
from src.planning import forward_plan

st.title('Workforce Planning')
st.caption('Can our planned staffing handle the next 14 operating days?')
as_of=st.session_state['as_of'];tol=st.session_state['tol']
raw=logic.outlook(as_of,tol)
if raw.empty: st.warning('No forecast days in this run.');st.stop()
history=data.daily()
# A run made after its operating day can use its observed closing backlog.
known=history.loc[history['date']<=as_of]
if known.empty: st.error('No backlog history is available by this forecast date.');st.stop()
carry=float(known.iloc[-1]['ending_backlog_wlu'])
plan=forward_plan(raw,carry)
plan['status']=plan['capacity_gap_hours'].map(lambda v:logic.classify_gap(v,tol))
n_short=int((plan['status']=='Shortage').sum())
cols=st.columns(4)
cols[0].metric('Shortage days',f'{n_short} / {len(plan)}')
cols[1].metric('New demand / day',f"{plan['incoming_wlu'].mean():,.0f} WLU")
cols[2].metric('Beginning backlog',f'{carry:,.0f} WLU')
cols[3].metric('Backlog after day 14',f"{plan.iloc[-1]['ending_backlog_wlu']:,.0f} WLU")
st.subheader('Required versus available labor')
fig=go.Figure()
fig.add_trace(go.Bar(x=plan['target_date'],y=plan['required_hours'],name='Hours required (including backlog)'))
fig.add_trace(go.Scatter(x=plan['target_date'],y=plan['expected_total_available_hours'],mode='lines+markers',name='Hours available'))
fig.update_layout(height=360,margin=dict(l=10,r=10,t=15,b=10),yaxis_title='Worker-hours',legend=dict(orientation='h',y=1.12))
st.plotly_chart(fig,use_container_width=True)
st.subheader('Daily plan')
show=plan[['target_date','incoming_wlu','beginning_backlog_wlu','required_hours','expected_total_available_hours','capacity_gap_hours','ending_backlog_wlu','status']].copy()
show.columns=['Date','New WLU','Carry-in WLU','Required hours','Available hours','Gap (hours)','Ending backlog WLU','Status']
st.dataframe(show,hide_index=True,use_container_width=True,column_config={'Date':st.column_config.DateColumn(format='MMM DD, YYYY')})
st.caption('Backlog is projected forward: next day’s beginning backlog equals the previous day’s projected ending backlog. '
           'This is a formula-based projection using saved historical forecasts, not a separately trained backlog model.')
st.info('Open **Staffing Decisions** to compare a change for a selected day. The effects shown there apply to that day; '
        'they do not automatically re-optimize the rest of the 14-day staffing schedule.')
