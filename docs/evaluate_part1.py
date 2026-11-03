"""Read-only reproduction of archived forecasts against leakage-aligned baselines.
Requires the user-provided original Week 7/8 ZIP extracted next to this script.
Does not train, tune, or modify the final test.
"""
from pathlib import Path
import sys, json, hashlib
import pandas as pd
import numpy as np
root=Path(__file__).resolve().parent
src=root/'MRP_Weeks7_8_Submission'
folder=src/'data'/'final'
out=root/'results';out.mkdir(exist_ok=True)
code=src/'code';sys.path.insert(0,str(code))
from step4_generate_forecasts_scenarios import build_point_forecast
D=pd.read_csv(folder/'fact_daily_outcome.csv');C=pd.read_csv(folder/'dim_date.csv');F=pd.read_csv(folder/'fact_workload_forecast.csv')
D=D.merge(C[['date_key','date','day_of_week_number','month_number','is_holiday','is_peak_season']],on='date_key',validate='one_to_one').sort_values('date').reset_index(drop=True)
D['date']=pd.to_datetime(D.date);F=F.sort_values(['forecast_run_id','horizon_operating_days']).copy()
F['forecast_date']=pd.to_datetime(F.forecast_date_key.astype(str),format='%Y%m%d');F['target_date']=pd.to_datetime(F.target_date_key.astype(str),format='%Y%m%d')
idx={int(k):i for i,k in enumerate(D.date_key)};w=D.new_workload_units.to_numpy();p=D.actual_productivity_wlu_per_hour.to_numpy()
F['cutoff_idx']=F.training_cutoff_date_key.map(idx).astype(int);F['origin_idx']=F.forecast_date_key.map(idx).astype(int);F['target_idx']=F.target_date_key.map(idx).astype(int)
assert (F.cutoff_idx==F.origin_idx-1).all() and (F.target_idx>F.origin_idx).all()
# Reproduce archived generator point forecasts for all rows using historical training cutoffs.
cache={};points=[];prods=[]
for row in F.itertuples():
 i=int(row.origin_idx);target=D.iloc[int(row.target_idx)];
 if i not in cache:
  history=D.iloc[:i].copy();cache[i]=(history,float(history.actual_productivity_wlu_per_hour.tail(28).mean()))
 hist,ep=cache[i]
 target_row=pd.Series({'day_of_week_number':int(target.day_of_week_number),'month_number':int(target.month_number),'is_holiday':int(target.is_holiday),'promotion_flag':int(target.promotion_flag)})
 points.append(round(build_point_forecast(hist,target_row,D.iloc[i].date),2));prods.append(round(ep,4))
F['reproduced_point']=points;F['reproduced_productivity']=prods
F['point_match']=np.isclose(F.reproduced_point,F.forecast_workload_units,atol=.011)
F['prod_match']=np.isclose(F.reproduced_productivity,F.expected_productivity_wlu_per_hour,atol=.00011)
# True pre-origin baseline: cutoff is prior completed day; model itself deliberately excludes origin-day observed workload.
F['last_day_naive']=w[F.cutoff_idx.to_numpy()];F['productivity_last_day_naive']=p[F.cutoff_idx.to_numpy()]
weekdays=D.day_of_week_number.to_numpy();lookup={i:np.where(weekdays==i)[0] for i in set(weekdays)}
lastweekday=[];lastweekday_p=[]
for r in F.itertuples():
 day=int(weekdays[int(r.target_idx)]);older=lookup[day];j=older[np.searchsorted(older,int(r.cutoff_idx),side='right')-1];lastweekday.append(w[j]);lastweekday_p.append(p[j])
F['same_weekday_naive']=lastweekday;F['productivity_weekday_naive']=lastweekday_p
# Dates match the pre-existing, already-viewed historical test; never use to choose a new model.
model_ready=D.iloc[7:].reset_index(drop=True);test_start=model_ready.iloc[int(len(model_ready)*.8)].date
T=F[F.forecast_date>=test_start].copy()
T['peak_season']=T.target_idx.map(lambda i:int(D.iloc[int(i)].is_peak_season))
T['high_demand']=T.actual_workload_units>=D.new_workload_units.quantile(.9)
T['workload_err']=T.actual_workload_units-T.forecast_workload_units
T['productivity_actual']=p[T.target_idx.to_numpy()]
T['productivity_err']=T.productivity_actual-T.expected_productivity_wlu_per_hour
T['interval_covered']=(T.actual_workload_units>=T.lower_80_workload_units)&(T.actual_workload_units<=T.upper_80_workload_units)

def compute(g,col,target):
 y=g[target].to_numpy();pred=g[col].to_numpy();e=y-pred
 return {'n':len(g),'mae':round(float(np.mean(np.abs(e))),4),'rmse':round(float(np.sqrt(np.mean(e**2))),4),'bias_actual_minus_pred':round(float(np.mean(e)),4),'wape_pct':round(float(100*np.sum(np.abs(e))/np.sum(y)),2)}
rows=[]
for h,hlabel in [(1,'1-day'),(14,'14-day'),(None,'all 1–14')]:
 g=T if h is None else T[T.horizon_operating_days==h]
 for k,target,methods in [('workload','actual_workload_units',[('archived_forecast','forecast_workload_units'),('last-observed cutoff baseline','last_day_naive'),('same-weekday cutoff baseline','same_weekday_naive')]),('productivity','productivity_actual',[('archived 28-day mean','expected_productivity_wlu_per_hour'),('last-observed cutoff baseline','productivity_last_day_naive'),('same-weekday cutoff baseline','productivity_weekday_naive')])]:
  for m,c in methods:rows.append({'kpi':k,'horizon':hlabel,'method':m,**compute(g,c,target)})
metrics=pd.DataFrame(rows);metrics.to_csv(out/'evaluation_comparisons.csv',index=False)
segments=[]
for h in [1,14]:
 g=T[T.horizon_operating_days==h]
 for name,z in [('peak',g[g.peak_season==1]),('nonpeak',g[g.peak_season==0]),('top-decile actual demand (post hoc)',g[g.high_demand]),('remaining demand',g[~g.high_demand])]:
  if len(z):segments.append({'horizon':h,'segment':name,**compute(z,'forecast_workload_units','actual_workload_units')})
seg=pd.DataFrame(segments);seg.to_csv(out/'workload_error_segments.csv',index=False)
horiz=[]
for h,g in T.groupby('horizon_operating_days'):
 horiz.append({'horizon':int(h),'n':len(g),'mae_wlu':compute(g,'forecast_workload_units','actual_workload_units')['mae'],'coverage_80pct':round(float(g.interval_covered.mean()),4),'mae_productivity':compute(g,'expected_productivity_wlu_per_hour','productivity_actual')['mae']})
pd.DataFrame(horiz).to_csv(out/'all_horizon_diagnostics.csv',index=False)
summary={'data_days':len(D),'forecast_rows':len(F),'forecast_runs':int(F.forecast_run_id.nunique()),'matching_reproduced_point_rows':int(F.point_match.sum()),'matching_reproduced_productivity_rows':int(F.prod_match.sum()),'max_point_difference':float((F.forecast_workload_units-F.reproduced_point).abs().max()),'max_productivity_difference':float((F.expected_productivity_wlu_per_hour-F.reproduced_productivity).abs().max()),'test_start':str(test_start.date()),'test_origin_count':int(T.forecast_run_id.nunique()),'test_forecast_rows':len(T),'test_overall_interval_coverage_pct':round(100*T.interval_covered.mean(),2),'test_day1_interval_coverage_pct':round(100*T.loc[T.horizon_operating_days==1,'interval_covered'].mean(),2),'test_day14_interval_coverage_pct':round(100*T.loc[T.horizon_operating_days==14,'interval_covered'].mean(),2),'scheduled_worker_counts':D.scheduled_worker_count.unique().tolist(),'scheduled_worker_hour_counts':D.scheduled_worker_hours.unique().tolist(),'source_6pm_forecast':'uses cutoff previous operating day, not origin-day actual','special_notes':'Historical final test already inspected; evaluation is reporting only and cannot guide further tuning.'}
(out/'verification_summary.json').write_text(json.dumps(summary,indent=2))
print('SUMMARY',json.dumps(summary,indent=2));print('METRICS\n',metrics.to_string(index=False));print('SEGMENTS\n',seg.to_string(index=False));print('HORIZON\n',pd.DataFrame(horiz).to_string(index=False))
