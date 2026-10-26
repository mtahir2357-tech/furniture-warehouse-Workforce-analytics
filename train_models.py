"""Reproducible, time-ordered predictive models. Run: python train_models.py"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT=Path(__file__).resolve().parent
MODEL_DIR=ROOT/'models'; MODEL_DIR.mkdir(exist_ok=True)
DATA=ROOT/'data'
FEATURES={
 'workload':['day_of_week_number','month_number','is_peak_season','is_holiday','workload_lag1','workload_lag7','workload_rolling7'],
 'productivity':['day_of_week_number','month_number','is_peak_season','beginning_backlog_wlu','scheduled_worker_count','scheduled_worker_hours','productivity_lag1','productivity_lag7','productivity_rolling7'],
}
TARGETS={'workload':'new_workload_units','productivity':'actual_productivity_wlu_per_hour'}
LABELS={'workload':'Daily incoming workload (WLU)','productivity':'Worker productivity (WLU/hour)'}

def make_frame():
 d=pd.read_csv(DATA/'fact_daily_outcome.csv')
 cal=pd.read_csv(DATA/'dim_date.csv')[['date_key','date','day_of_week_number','month_number','is_peak_season','is_holiday']]
 d=d.merge(cal,on='date_key',validate='one_to_one').sort_values('date').reset_index(drop=True)
 for source,prefix in [('new_workload_units','workload'),('actual_productivity_wlu_per_hour','productivity')]:
  d[f'{prefix}_lag1']=d[source].shift(1)
  d[f'{prefix}_lag7']=d[source].shift(7)
  d[f'{prefix}_rolling7']=d[source].shift(1).rolling(7).mean()
 return d.dropna(subset=[*FEATURES['workload'],*FEATURES['productivity']]).reset_index(drop=True)

def train():
 d=make_frame(); split=int(len(d)*.8)
 if split<100: raise ValueError('Insufficient training history')
 manifest={}
 for key,features in FEATURES.items():
  x=d[features].astype(float);y=d[TARGETS[key]].astype(float)
  model=RandomForestRegressor(n_estimators=140,min_samples_leaf=4,max_features=0.85,random_state=42,n_jobs=-1)
  model.fit(x.iloc[:split],y.iloc[:split])
  actual=y.iloc[split:];pred=model.predict(x.iloc[split:])
  perm=permutation_importance(model,x.iloc[split:],actual,n_repeats=5,random_state=42,scoring='neg_mean_absolute_error',n_jobs=1)
  metrics={'mae':float(mean_absolute_error(actual,pred)),'rmse':float(np.sqrt(mean_squared_error(actual,pred))), 'naive_mae':float(mean_absolute_error(actual,d.iloc[split:][f'{key}_lag1'])), 'train_rows':split,'test_rows':len(d)-split,'train_end':str(d.iloc[split-1]['date']),'test_start':str(d.iloc[split]['date']),'test_end':str(d.iloc[-1]['date'])}
  baseline={f:float(x.iloc[:split][f].median()) for f in features}
  bundle={'model':model,'features':features,'reference':baseline,'metrics':metrics,'importance':dict(zip(features,map(float,perm.importances_mean))), 'target':TARGETS[key],'label':LABELS[key],'key':key}
  joblib.dump(bundle,MODEL_DIR/f'{key}.joblib',compress=3)
  manifest[key]=metrics
  print(key,metrics)
 (MODEL_DIR/'evaluation.json').write_text(json.dumps(manifest,indent=2))
 return manifest
if __name__=='__main__':train()
