"""Run after overlay installation to check actual CSV, forecast, and model wiring."""
from pathlib import Path
import json
import joblib
import numpy as np
from src import data,logic
from src.planning import forward_plan
from train_models import make_frame

ROOT=Path(__file__).resolve().parent

def main():
    expected=['dim_date','dim_employee','dim_product','dim_scenario','dim_workflow_activity',
      'fact_daily_outcome','fact_employee_day','fact_order','fact_order_line',
      'fact_staffing_scenario','fact_workflow_event','fact_workload_forecast']
    missing=[n for n in expected if not (ROOT/'data'/f'{n}.csv').exists()]
    if missing:raise AssertionError('Missing CSVs: '+', '.join(missing))
    runs=data.forecast_runs()
    assert len(runs)>0,'No forecast run dates'
    all_daily=data.daily()
    assert all_daily['date'].is_unique,'Duplicate daily dates'
    as_of=runs[-1]
    full=logic.outlook(as_of,8.0)
    assert len(full)>0,'No target rows in latest run'
    assert full['target_date'].is_unique,'Duplicate forecast targets'
    history=all_daily[all_daily['date']<=as_of]
    assert not history.empty,'No known starting backlog'
    first_backlog=float(history.iloc[-1]['ending_backlog_wlu'])
    plan=forward_plan(full,first_backlog)
    assert len(plan)==len(full),'Day count changed'
    assert np.isclose(plan.iloc[0]['beginning_backlog_wlu'],first_backlog)
    assert np.allclose(plan['total_workload_wlu'],plan['incoming_wlu']+plan['beginning_backlog_wlu'])
    assert (plan['ending_backlog_wlu']>=0).all(),'Negative backlog'
    assert (plan['expected_total_available_hours']>=0).all(),'Negative hours'
    assert np.allclose(plan['beginning_backlog_wlu'].iloc[1:],plan['ending_backlog_wlu'].iloc[:-1])
    f=make_frame()
    assert len(f)>100,'Model training history too short'
    assert f['date'].is_monotonic_increasing
    report=json.loads((ROOT/'models'/'evaluation.json').read_text())
    for key in ('workload','productivity'):
        assert key in report,'Missing original KPI'
        p=ROOT/'models'/f'{key}.joblib'
        bundle=joblib.load(p)
        inputs=f.iloc[[-1]][bundle['features']].astype(float)
        prediction=float(bundle['model'].predict(inputs)[0])
        assert np.isfinite(prediction),'Invalid model prediction'
        print(f'{key}: trained model loads; latest retrospective prediction={prediction:.3f}')
    print(f'PASS: 12 source tables, {len(all_daily)} daily rows, {len(runs)} forecast runs, {len(plan)} planning days, 2 saved models.')
    print(f'Carry-in WLU={first_backlog:.2f}; projected final WLU={plan.iloc[-1]["ending_backlog_wlu"]:.2f}')
    print('CAVEAT: This checks schema/wiring and arithmetic, not live Streamlit visuals or real-warehouse validity.')

if __name__=='__main__':main()
