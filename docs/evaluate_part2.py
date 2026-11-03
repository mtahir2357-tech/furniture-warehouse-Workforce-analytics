"""Part 2: strictly pre-final-test, fixed-origin evaluation of candidate forecasting rules.
Uses original Weeks 7-8 dataset, does not modify it or use final holdout outcomes for selection.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import json
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'MRP_Weeks7_8_Submission'/'data'/'final'
D=pd.read_csv(SRC/'fact_daily_outcome.csv').merge(pd.read_csv(SRC/'dim_date.csv')[['date_key','date','day_of_week_number','month_number','is_holiday']],on='date_key',validate='one_to_one').sort_values('date').reset_index(drop=True)
F=pd.read_csv(SRC/'fact_workload_forecast.csv')
w=D.new_workload_units.to_numpy(float);prod=D.actual_productivity_wlu_per_hour.to_numpy(float);dow=D.day_of_week_number.to_numpy(int);months=D.month_number.to_numpy(int);holiday=D.is_holiday.to_numpy(int);promo=D.promotion_flag.to_numpy(int)
N=len(D); model_ready=N-7; train_end=7+int(model_ready*.64);test_start=7+int(model_ready*.8)
MAX_ORIGIN=N-15
assert train_end<test_start<=MAX_ORIGIN
# original is 8 weekday / 28 recent with seasonality and presumed known promotions
W_CAND={'Original: 8 weekday / 28 recent + promotion':(8,28,.60,True),
 'No future promotion input':(8,28,.60,False),
 'More weekday weight (80%)':(8,28,.80,True),
 '12-weekday history':(12,28,.60,True),
 '14-day recent mean':(8,14,.60,True)}
P_CAND={'Original: 28-day mean':('mean',28),
 '14-day mean':('mean',14),
 '56-day mean':('mean',56),
 '28-day median':('median',28),
 '14-day EWMA':('ewma',14)}

def estimate_p(i,candidate):
 typ,length=candidate;v=prod[max(0,i-length):i]
 if typ=='mean':return v.mean()
 if typ=='median':return np.median(v)
 if typ=='ewma':
  weights=(1-2/(length+1))**np.arange(len(v)-1,-1,-1)
  return np.average(v,weights=weights)

def forecast(i, j, cfg):
 wd_n,recent_n,weight,prom=cfg
 hist=w[:i];overall=hist.mean()
 wd=hist[dow[:i]==dow[j]][-wd_n:]
 f=weight*(wd.mean() if len(wd) else overall)+(1-weight)*hist[-recent_n:].mean()
 means=np.bincount(months[:i],weights=hist,minlength=13)/np.maximum(np.bincount(months[:i],minlength=13),1)
 tar_idx=(means[months[j]] if means[months[j]]>0 else overall)/overall
 org_idx=(means[months[i]] if means[months[i]]>0 else overall)/overall
 ratio=np.clip(tar_idx/org_idx,.70,1.35)
 f*=ratio**.70
 if holiday[j]:f*=.78
 if prom and promo[j]:f*=1.18
 return max(0.,float(f))

# Construct train-origin residuals for interval calibration, and development-validation forecasts.
records=[]
for i in range(56,min(MAX_ORIGIN,test_start-15)+1):
 phase='train' if i < train_end-14 else ('validation' if i>=train_end else 'purged')
 if phase=='purged':continue
 for h in range(1,15):
  j=i+h
  if j>=N:break
  row={'phase':phase,'origin_index':i,'origin_date':D.iloc[i].date,'target_date':D.iloc[j].date,'horizon':h,'actual_workload':w[j],'actual_productivity':prod[j], 'peak':int(months[j] in (11,12))}
  for nm,cfg in W_CAND.items():row['w|'+nm]=forecast(i,j,cfg)
  for nm,cfg in P_CAND.items():row['p|'+nm]=estimate_p(i,cfg)
  records.append(row)
T=pd.DataFrame(records)
# Check baseline against original archive (rounding tolerance); both use strictly pre-origin data.
file_idx={(int(r.forecast_date_key),int(r.horizon_operating_days)):r for r in F.itertuples()}
orig_w='w|Original: 8 weekday / 28 recent + promotion';orig_p='p|Original: 28-day mean'
comparisons=[]
for _,r in T.iterrows():
  fr=file_idx.get((int(D.iloc[int(r['origin_index'])].date_key),int(r['horizon'])))
  if fr is not None:comparisons.append((abs(float(r[orig_w])-fr.forecast_workload_units),abs(float(r[orig_p])-fr.expected_productivity_wlu_per_hour)))
assert comparisons and max(x[0] for x in comparisons)<.011 and max(x[1] for x in comparisons)<.00011

def scores(df,col,actual):
 err=df[actual].to_numpy()-df[col].to_numpy()
 return {'n':len(df),'MAE':float(np.mean(np.abs(err))),'RMSE':float(np.sqrt(np.mean(err*err))), 'bias':float(np.mean(err))}
rows=[]
val=T[T.phase=='validation'];train=T[T.phase=='train']
for k,cands,prefix,target in [('Workload',W_CAND,'w|','actual_workload'),('Productivity',P_CAND,'p|','actual_productivity')]:
 for name in cands:
  col=prefix+name
  for h,subset in [('All 1–14',val),('Day 1',val[val.horizon==1]),('Day 14',val[val.horizon==14])]:
   rows.append({'KPI':k,'Variant':name,'Horizon':h,**scores(subset,col,target)})
perf=pd.DataFrame(rows)
perf.to_csv(ROOT/'validation_candidate_comparison.csv',index=False)
selected={}
for key,prefix,cands in [('Workload','w|',W_CAND),('Productivity','p|',P_CAND)]:
 x=perf[(perf.KPI==key)&(perf.Horizon=='All 1–14')].sort_values('MAE')
 selected[key]=x.iloc[0].Variant
# Train-derived conformal-style marginal residual quantiles per horizon (overlapping origins; descriptive calibration).
# Candidate is chosen on validation point MAE; calibration uses train only and is checked on validation.
uncert=[]
for h in range(1,15):
 tr=train[train.horizon==h];va=val[val.horizon==h]
 old_col=orig_w;new_col='w|'+selected['Workload']
 # finite sample quantile of train absolute error for ~80% marginal coverage
 ab=np.sort(abs(tr.actual_workload.to_numpy()-tr[new_col].to_numpy()))
 rank=min(len(ab),int(np.ceil((len(ab)+1)*.8)))
 q=float(ab[rank-1])
 # old forecast uncertainty formula, with 1.28155 z; directly compare validation coverage
 old=va[old_col].to_numpy();actual=va.actual_workload.to_numpy()
 sd=np.maximum(1.,old*(.13+.012*(h-1)))
 lo=np.maximum(0.,old-1.2815515655*sd);hi=old+1.2815515655*sd
 new=va[new_col].to_numpy();clo=np.maximum(0,new-q);chi=new+q
 uncert.append({'horizon':h,'n_train':len(tr),'n_validation':len(va),'train_quantile_abs_error':q,
  'original_80pct_coverage_validation':float(np.mean((actual>=lo)&(actual<=hi))),
  'calibrated_80pct_coverage_validation':float(np.mean((actual>=clo)&(actual<=chi))),
  'original_avg_interval_width':float(np.mean(hi-lo)),
  'calibrated_avg_interval_width':float(np.mean(chi-clo))})
interval=pd.DataFrame(uncert);interval.to_csv(ROOT/'validation_interval_comparison.csv',index=False)
# Error segmentation selected vs original on validation, actual high volume post hoc diagnostic
segments=[]
q90=float(np.quantile(train[train.horizon==1].actual_workload,.9))
for key,prefix,target,old,new in [('Workload','w|','actual_workload',orig_w,'w|'+selected['Workload']),('Productivity','p|','actual_productivity',orig_p,'p|'+selected['Productivity'])]:
 for h in (1,14):
  sub=val[val.horizon==h]
  for name,z in [('Peak months Nov-Dec',sub[sub.peak==1]),('Other months',sub[sub.peak==0]),('High realized demand (post hoc)',sub[sub.actual_workload>=q90])]:
   for lbl,col in [('Original',old),('Revised selected',new)]:
    if len(z):segments.append({'KPI':key,'Horizon':h,'Segment':name,'Version':lbl,**scores(z,col,target)})
pd.DataFrame(segments).to_csv(ROOT/'validation_error_segments.csv',index=False)
meta={'train_origin_count':int(train.origin_index.nunique()),'validation_origin_count':int(val.origin_index.nunique()),'train_forecast_rows':len(train),'validation_forecast_rows':len(val),'train_origin_first':str(train.origin_date.min()),'train_origin_last':str(train.origin_date.max()),'validation_origin_first':str(val.origin_date.min()),'validation_origin_last':str(val.origin_date.max()),'final_test_start':str(D.iloc[test_start].date),'final_test_evaluated_in_part2':False,'selection_rule':'Minimum validation MAE over all 14 horizons per KPI; no test period used','selected':selected,'archive_forecast_reproduction_checked_records':len(comparisons),'archive_max_diff_workload':max(x[0] for x in comparisons),'archive_max_diff_productivity':max(x[1] for x in comparisons),'note':'Historical validation origins overlap in target date; coverage is descriptive and not independent. Future known promotion flags remain an unverified data-availability assumption.'}
(ROOT/'part2_protocol.json').write_text(json.dumps(meta,indent=2))
print(json.dumps(meta,indent=2))
print(perf[perf.Horizon=='All 1–14'].to_string(index=False))
print('Intervals overall unweighted',interval[['original_80pct_coverage_validation','calibrated_80pct_coverage_validation']].mean().to_dict())
