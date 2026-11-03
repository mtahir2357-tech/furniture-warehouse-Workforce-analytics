"""Week 11 model assessment and constrained individual model what-if analysis."""
import json
from pathlib import Path
import joblib
import pandas as pd
import streamlit as st
import plotly.express as px
from train_models import make_frame
from src.model_scenarios import (model_predict, scenario_inputs,
    validate_historical_ranges, sequential_local_contributions)

ROOT=Path(__file__).resolve().parents[1]
LABELS={'workload':'Incoming workload (WLU)','productivity':'Worker productivity (WLU/hour)'}
st.title('Model Validation')
st.caption('Historical synthetic data · evidence for model reliability, not production guarantees')

source=ROOT/'models'/'evaluation.json'
if not source.exists():
    st.error('Missing models/evaluation.json. Copy your original models folder here.')
    st.stop()
evaluations=json.loads(source.read_text())
rows=[]
for key,m in evaluations.items():
    base=m.get('naive_mae',0)
    rows.append({'KPI':LABELS.get(key,key),'Original MAE':m.get('mae'),
        'Original RMSE':m.get('rmse'),'Previous-day baseline MAE':base,
        'Improvement vs baseline':(base-m['mae'])/base if base else None,
        'Test days':m.get('test_rows')})
st.subheader('Original trained models')
st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True,
    column_config={'Improvement vs baseline':st.column_config.NumberColumn(format='%.1%')})
st.caption('Reported original Week 10 holdout results; the saved 14-day planning forecasts are a separate historical forecasting system.')

eval_path=ROOT/'models'/'week11_evaluation.csv'
seg_path=ROOT/'models'/'week11_segment_errors.csv'
if eval_path.exists():
    df=pd.read_csv(eval_path)
    st.subheader('Original versus revised: protected final test')
    st.dataframe(df,hide_index=True,use_container_width=True)
    st.caption('Configuration selection uses only chronological development validation. Final-test comparisons are reported after selection, not used for tuning.')
else:
    st.warning('Week 11 experiments have not been executed on the real repository dataset. Run `python evaluate_week11.py` before submitting.')
if seg_path.exists():
    with st.expander('Errors by weekday and season'):
        st.dataframe(pd.read_csv(seg_path),hide_index=True,use_container_width=True)

st.divider()
st.subheader('Individual prediction and what-if comparison')
st.caption('These what-if examples change predictors in the trained KPI models. The staffing page separately calculates capacity and cost using engineering formulas.')
kind=st.selectbox('Model',list(LABELS),format_func=lambda k:LABELS[k])
model_path=ROOT/'models'/f'week11_selected_{kind}.joblib'
if not model_path.exists():model_path=ROOT/'models'/f'{kind}.joblib'
if not model_path.exists():
    st.warning('Trained model file unavailable; use existing `models/` artifacts.')
    st.stop()
bundle=joblib.load(model_path)
if model_path.name.startswith('week11_selected_'):
    st.caption('Using the configuration selected on Week 11 development validation, then refitted before final testing.')
else:
    st.caption('Using the original saved Week 10 model.')
frame=make_frame()
# Keep the demonstration retrospective, explicitly avoiding future-available-feature claims.
select=st.selectbox('Historical reference day',range(len(frame)-1,-1,-1),format_func=lambda i:str(frame.iloc[i]['date']))
base=frame.iloc[select][bundle['features']].astype(float)
with st.form(f'what_if_{kind}'):
    if kind=='workload':
        st.markdown('**Hypothetical recent-demand context (external, not manager-controlled)**')
        factor=st.slider('Prior demand versus the recorded history',75,125,100,5,format='%d%%')/100
        st.caption('Scales the previous-day, previous-week, and seven-day-average demand predictors together. Calendar inputs remain unchanged.')
        revised=scenario_inputs(kind,base,context_multiplier=factor)
    else:
        st.markdown('**Staffing-plan scenario inputs (manager-proposed, subject to scheduling constraints)**')
        change=st.slider('Change in scheduled workers',-10,10,0)
        shift=st.slider('Scheduled hours per added or removed worker',4,12,8)
        revised_error=None
        try:revised=scenario_inputs(kind,base,worker_change=change,hours_per_worker=shift)
        except ValueError as exc:
            revised_error=str(exc);revised=base.copy()
        st.caption('Worker count and scheduled hours are adjusted together. A trained association is not a causal estimate of changing staff.')
    run=st.form_submit_button('Compare predictions',type='primary')
if kind=='productivity' and revised_error:
    st.error(revised_error)
    st.stop()
train_cut=int(len(frame)*.8)
train_data=frame.iloc[:train_cut]
warnings=validate_historical_ranges(train_data,revised,kind)
if warnings:
    st.warning('Plausibility warning: '+' '.join(warnings)+' Interpret this scenario cautiously.')
original_pred=model_predict(bundle,base)
revised_pred=model_predict(bundle,revised)
cs=st.columns(3)
cs[0].metric('Reference prediction',f'{original_pred:,.3f}')
cs[1].metric('What-if prediction',f'{revised_pred:,.3f}')
cs[2].metric('Model-estimated difference',f'{revised_pred-original_pred:+,.3f}')
changes=[{'Predictor':f,'Recorded context':float(base[f]),'Scenario context':float(revised[f]),'Difference':float(revised[f]-base[f])}
         for f in bundle['features'] if abs(float(revised[f]-base[f]))>1e-8]
if changes:
    st.dataframe(pd.DataFrame(changes),hide_index=True,use_container_width=True)
else:
    st.info('No predictor values changed. Choose a different scenario to compare.')
if run:
    st.info(f'Model-based comparison: {LABELS[kind].lower()} changes by {revised_pred-original_pred:+,.3f} relative to the historical reference. '
            +'This is an exploratory statistical difference, not evidence that the scenario will cause the change. '
            +'Operational constraints, rare events, and prediction errors remain important.')
with st.expander('Global importance and explanation of this individual prediction'):
    importance=pd.Series(bundle.get('importance',{}),dtype=float).sort_values()
    if not importance.empty:
        st.plotly_chart(px.bar(x=importance.values,y=importance.index,orientation='h',
            labels={'x':'Permutation increase in MAE','y':''},title='Overall feature importance'),use_container_width=True)
    refpred, steps=sequential_local_contributions(bundle,revised)
    st.plotly_chart(px.bar(steps.sort_values('Contribution'),x='Contribution',y='Feature',orientation='h',
        title='Individual prediction: ordered median-reference substitutions'),use_container_width=True)
    st.caption(f'Reference prediction {refpred:,.3f}. Contributions are order-dependent, can be unreliable with correlated features, and do not establish causality.')

with st.expander('Leakage, reliability and decision-time limitations',expanded=True):
    st.markdown('''
- **Development vs test:** Original model used an 80% chronological training / 20% test split. Week 11 evaluation adds a development validation window. Do not tune using the last test window.
- **Forecast time:** Prior observed demand and productivity lags are available for one-step-ahead prediction. Multi-day predictions cannot use actual future observations as inputs.
- **Schedule:** Planned worker count/hours and beginning backlog must be known when a prediction is issued. Scenarios involving unknown future values are hypothetical.
- **Different forecasts:** The saved 14-day planning forecasts are not generated by these Random Forest models; do not compare their error values as if they were the same experiment.
- **Data:** Entirely synthetic, not independently calibrated to a real warehouse. Backlog projection is deterministic, not a third machine-learning model.
- **Causal interpretation:** Changing a predictor in a fitted model does not prove a real operational intervention will create that change.
''')
