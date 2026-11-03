"""Predictive modeling: trained-model predictions, global importance and local model attribution."""
import joblib
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from pathlib import Path
from train_models import FEATURES,make_frame

ROOT=Path(__file__).resolve().parents[1]
st.title('Predictive Modeling')
st.caption('Two validated KPI models · historical synthetic warehouse data · scenario predictions, not causal effects')
@st.cache_resource
def load_models():
 return {k:joblib.load(ROOT/'models'/f'{k}.joblib') for k in FEATURES}
models=load_models();history=make_frame()
key=st.segmented_control('KPI',options=['workload','productivity'],format_func=lambda k:models[k]['label'],default='workload')
if key is None:st.stop()
bundle=models[key]; feats=bundle['features'];model=bundle['model'];m=bundle['metrics']
st.markdown('### What this KPI means')
if key=='workload':
 st.write('**New incoming workload (WLU)** measures daily pieces weighted by handling effort. It helps schedule labor to meet demand and avoid overtime or delayed shipments.')
else:
 st.write('**Worker productivity (WLU per worker-hour)** measures processing efficiency. It helps estimate capacity, cost per unit and operational throughput.')
st.caption('Algorithm: Random Forest regression captures nonlinear relationships and interactions without assuming linear effects. Last 20% of operating days held out chronologically; no random train/test shuffle. Lagged operational history uses only earlier operating days.')
c1,c2,c3=st.columns(3)
c1.metric('Holdout MAE',f"{m['mae']:,.2f}")
c2.metric('Holdout RMSE',f"{m['rmse']:,.2f}")
c3.metric('Naive previous-day MAE',f"{m['naive_mae']:,.2f}")
st.caption(f"Train through {m['train_end']} · test {m['test_start']} – {m['test_end']} ({m['test_rows']:,} days). A lower MAE is better. Models are trained using synthetic data; accuracy does not establish real-world validity.")
st.divider()
st.subheader('Explore a historical baseline and a new scenario')
pick=st.selectbox('Baseline operating date',options=list(range(len(history)-1,-1,-1)),format_func=lambda i:str(history.iloc[i]['date']))
base_row=history.iloc[pick][feats].astype(float)
base_df=pd.DataFrame([base_row],columns=feats)
base_pred=max(0,float(model.predict(base_df)[0]))
st.markdown('**Scenario predictor inputs**')
st.caption('Defaults are historical recorded/planned values on the selected date. These are exploratory feature changes, not promises about controllable warehouse interventions. Adjust values, then click Run scenario.')
name_map={'day_of_week_number':'Day of week (Mon=1)','month_number':'Month (1–12)','is_peak_season':'Peak season (0/1)','is_holiday':'Holiday (0/1)','workload_lag1':'Prior operating-day WLU','workload_lag7':'WLU 7 operating days earlier','workload_rolling7':'Average WLU over prior 7 operating days','beginning_backlog_wlu':'Backlog WLU at shift start','scheduled_worker_count':'Scheduled workers','scheduled_worker_hours':'Scheduled worker-hours','productivity_lag1':'Prior operating-day WLU/hour','productivity_lag7':'Productivity 7 operating days earlier','productivity_rolling7':'Average productivity over prior 7 operating days'}
with st.form(f'scenario_{key}'):
 cols=st.columns(3);entered={}
 for i,f in enumerate(feats):
  original=float(base_row[f]); integer=f in ('day_of_week_number','month_number','is_peak_season','is_holiday','scheduled_worker_count')
  if f in ('is_peak_season','is_holiday'):
   entered[f]=float(cols[i%3].selectbox(name_map.get(f,f),[0,1],index=int(original),key=f'{key}_{f}'))
  elif integer:
   bounds={'day_of_week_number':(1,7),'month_number':(1,12),'scheduled_worker_count':(0,250)}.get(f,(0,999999))
   entered[f]=float(cols[i%3].number_input(name_map.get(f,f),min_value=bounds[0],max_value=bounds[1],value=int(original),step=1,key=f'{key}_{f}'))
  else:
   entered[f]=float(cols[i%3].number_input(name_map.get(f,f),min_value=0.0,value=max(0.,original),step=1.0 if ('wlu' in f or 'hours' in f) else .05,format='%.2f',key=f'{key}_{f}'))
 submitted=st.form_submit_button('Run scenario',type='primary')
scenario_df=pd.DataFrame([entered],columns=feats)
new_pred=max(0,float(model.predict(scenario_df)[0]))
delta=new_pred-base_pred
x,y,z=st.columns(3)
x.metric('Baseline model prediction',f'{base_pred:,.2f}')
y.metric('Scenario model prediction',f'{new_pred:,.2f}')
z.metric('Change from baseline',f'{delta:+,.2f}',delta=f'{delta/base_pred:+.1%}' if base_pred else 'N/A')
changed=[(name_map.get(f,f),float(base_row[f]),entered[f]) for f in feats if not np.isclose(float(base_row[f]),entered[f])]
if submitted:
 text_inputs='; '.join(f'{n}: {a:,.2f} → {b:,.2f}' for n,a,b in changed) if changed else 'No inputs changed.'
 direction='higher' if delta>0.005 else 'lower' if delta<-.005 else 'unchanged'
 st.info(f'**Scenario summary:** {text_inputs}  **Result:** predicted {bundle["label"].lower()} is {new_pred:,.2f}, {direction} than baseline {base_pred:,.2f} (change {delta:+,.2f}; {delta/base_pred:+.1%} if baseline is nonzero). **Implication:** '+('Higher workload may require more planned capacity; lower workload may leave spare capacity.' if key=='workload' else 'Productivity differences can change estimated labor-hours needed for a fixed workload.')+' **Limitations:** These are model-based associations on synthetic data, not guaranteed changes caused by the chosen inputs. Other operations, constraints and uncertainty are not represented.')
st.divider()
st.subheader('Why the model makes predictions')
imp=pd.Series(bundle['importance']).sort_values(ascending=True)
fig=px.bar(x=imp.values,y=[name_map.get(s,s) for s in imp.index],orientation='h',labels={'x':'Increase in holdout MAE after feature shuffled','y':''},title='Overall predictor importance · permutation on holdout data')
st.plotly_chart(fig,use_container_width=True)
st.caption('Global importance measures how much model accuracy worsens when a predictor is shuffled on held-out days. It does not show direction or causality. Values may be unstable when features correlate.')
# Exact additive sequential reference walk: order-dependent attribution; separate from permutation importance.
ref=pd.DataFrame([bundle['reference']],columns=feats);prev=float(model.predict(ref)[0]);steps=[]
for f in feats:
 ref.loc[0,f]=scenario_df.loc[0,f]
 next_=float(model.predict(ref)[0]);steps.append((f,next_-prev));prev=next_
contrib=pd.Series(dict(steps)).sort_values()
fig2=px.bar(x=contrib.values,y=[name_map.get(s,s) for s in contrib.index],orientation='h',labels={'x':'Prediction difference (KPI units)','y':''},title='Individual scenario prediction · sequential reference contributions')
st.plotly_chart(fig2,use_container_width=True)
reference_prediction=float(model.predict(pd.DataFrame([bundle['reference']],columns=feats))[0])
st.caption(f'Local explanation: starting from the training-median reference prediction ({reference_prediction:,.2f}), each predictor is replaced in the displayed feature order with its scenario value. The signed steps sum to the un-clipped model prediction difference; positive values raise the predicted KPI, negative values lower it. Contributions depend on feature order and are not causal, especially for correlated predictors.')
for f,v in sorted(steps,key=lambda q:abs(q[1]),reverse=True)[:3]:
 st.write(f"• **{name_map.get(f,f)}**: {v:+,.2f} prediction units relative to the preceding reference step; scenario input {entered[f]:,.2f}.")
