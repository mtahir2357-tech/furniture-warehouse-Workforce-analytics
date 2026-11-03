"""Read-only checks to run in the full existing GitHub checkout. No model tuning."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent

def run(root=ROOT):
    data=Path(root)/'data'; models=Path(root)/'models'
    daily=pd.read_csv(data/'fact_daily_outcome.csv')
    forecast=pd.read_csv(data/'fact_workload_forecast.csv')
    scenario=pd.read_csv(data/'fact_staffing_scenario.csv')
    date=pd.read_csv(data/'dim_date.csv')
    checks={
      'operating_days':len(daily),
      'forecast_rows':len(forecast),
      'forecast_origins':int(forecast.forecast_run_id.nunique()),
      'forecast_horizons':sorted(forecast.horizon_operating_days.unique().astype(int).tolist()),
      'scenario_rows':len(scenario),
      'unique_operating_dates':daily.date_key.is_unique,
      'unique_forecast_ids':forecast.forecast_id.is_unique,
      'scenario_join_missing':int((~scenario.forecast_id.isin(forecast.forecast_id)).sum()),
      'scenario_ids':sorted(scenario.scenario_id.unique().tolist()),
      'scheduled_worker_count_unique':sorted(daily.scheduled_worker_count.unique().astype(int).tolist()),
      'scheduled_worker_hours_unique':sorted(daily.scheduled_worker_hours.unique().astype(float).tolist()),
      'backlog_continuity_max_abs':float(np.abs(daily.beginning_backlog_wlu.iloc[1:].to_numpy()-daily.ending_backlog_wlu.iloc[:-1].to_numpy()).max()),
      'unavailable_real_user_test_evidence':True,
    }
    if len(forecast)>0:
        checks['horizon_completeness']=bool((forecast.groupby('forecast_run_id').horizon_operating_days.nunique()==14).all())
        checks['no_origin_in_forecast_targets']=bool((forecast.target_date_key>forecast.forecast_date_key).all())
        checks['forecast_actual_consistency_max_abs']=float(np.abs(forecast.actual_workload_units.to_numpy()-forecast.target_date_key.map(daily.set_index('date_key').new_workload_units).to_numpy()).max())
        # Compare previously saved archived forecasts with recorded actuals; no training / selection.
        a=forecast[forecast.horizon_operating_days==1]
        checks['archived_h1_MAE_all_history']=float(np.abs(a.actual_workload_units-a.forecast_workload_units).mean())
    f=models/'week11_evaluation.csv'
    if f.exists():
        e=pd.read_csv(f)
        checks['random_forest_evaluation_rows']=len(e)
        checks['rf_validation_selection_count']=int(e.Chosen_on_validation.sum())
    assert checks['unique_operating_dates'] and checks['unique_forecast_ids']
    assert checks['scenario_join_missing']==0
    assert checks['horizon_completeness'] and checks['no_origin_in_forecast_targets']
    assert checks['forecast_actual_consistency_max_abs']<.0001
    assert checks['backlog_continuity_max_abs']<.01
    return checks

if __name__=='__main__':print(json.dumps(run(),indent=2))
