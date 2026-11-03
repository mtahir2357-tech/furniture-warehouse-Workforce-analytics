"""Feasible, single-day scenario changes with carry-in backlog and comparisons."""
import pandas as pd
import streamlit as st
from src import data,logic
from src.planning import plan_day,forward_plan

st.title('Staffing Decisions')
st.caption('Compare today’s plan with a feasible staffing change. All results are simulated.')
as_of=st.session_state['as_of'];tol=st.session_state['tol']
raw=logic.outlook(as_of,tol)
if raw.empty:st.warning('No forecast run.');st.stop()
hist=data.daily();known=hist.loc[hist['date']<=as_of]
if known.empty:st.error('Missing starting backlog.');st.stop()
forward=forward_plan(raw,float(known.iloc[-1]['ending_backlog_wlu']))
options=list(range(len(raw)))
i=st.selectbox('Operating day to review',options,format_func=lambda j:raw.iloc[j]['target_date'].strftime('%a, %b %d, %Y'))
r=raw.iloc[i];b=forward.iloc[i]
regular=float(r['planned_regular_hours']);overtime=0.0
rate=float(r['avg_worker_hourly_rate']);manager_cost=float(r['projected_manager_labor_cost'])
availability=float(r['expected_available_regular_hours'])/regular if regular>0 else 0.0
base_prod=float(r['expected_productivity_wlu_per_hour']);base_wlu=float(r['forecast_workload_units'])
start_backlog=float(b['beginning_backlog_wlu'])
base=plan_day(base_wlu,start_backlog,base_prod,regular,overtime,availability,rate,manager_cost)
with st.form('staffing'):
    st.markdown('### Adjust the staffing plan')
    c1,c2=st.columns(2)
    with c1:
        worker_delta=st.number_input('Workers to add / remove',min_value=-int(regular//8),max_value=30,value=0,step=1,
                         help='One scheduled 8-hour shift per worker; changes apply to this day only.')
        overtime_delta=st.number_input('Overtime hours to add',min_value=0.0,max_value=80.0,value=0.0,step=2.0)
    with c2:
        st.metric('Original regular labor',f'{regular:,.0f} hours')
        st.metric('Original expected availability',f'{availability:.0%}')
    submit=st.form_submit_button('Compare with current plan',type='primary')
new_regular=regular+worker_delta*8
if new_regular<0:
    st.error('Staffing reduction exceeds available hours.');st.stop()
changed=plan_day(base_wlu,start_backlog,base_prod,new_regular,overtime_delta,availability,rate,manager_cost)
fields=[('Expected available hours','expected_total_available_hours','h'),
        ('Capacity gap','capacity_gap_hours','h'),('Projected ending backlog','ending_backlog_wlu',' WLU'),
        ('Estimated labor cost','labor_cost','$')]
st.subheader('Current plan vs. proposed change')
for title,key,unit in fields:
    a=float(base[key]);v=float(changed[key]);delta=v-a
    left,right=st.columns(2)
    with left: st.metric(f'{title} · current',f'${a:,.0f}' if unit=='$' else f'{a:,.1f}{unit}')
    with right: st.metric(f'{title} · proposed',f'${v:,.0f}' if unit=='$' else f'{v:,.1f}{unit}',delta=f'{delta:+,.1f}{unit}' if unit!='$' else f'${delta:+,.0f}',delta_color='off')
status=logic.classify_gap(changed['capacity_gap_hours'],tol)
st.success(f'Scenario result: {status.lower()} under a ±{tol:,.0f}-hour planning margin.') if status=='Balanced' else st.info(f'Scenario result: {status.lower()} under a ±{tol:,.0f}-hour planning margin.')
st.caption('Total work includes forecast new workload **plus** carry-in backlog. Cost assumes a 1.5× overtime multiplier and unchanged manager cost. '
           'The worker-count adjustment assumes eight regular hours per additional worker, not an independently validated scheduling optimization.')
