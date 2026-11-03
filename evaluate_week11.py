"""Week 11 chronological development/validation and once-only final test.

Run from repo root: python evaluate_week11.py
Keeps Week 10 models untouched. Writes Week 11 comparisons, segmented errors,
selected-model artifacts and data-availability notes into models/.
"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error
from train_models import make_frame, FEATURES, TARGETS

ROOT=Path(__file__).resolve().parent


def make_model(variant):
    args=dict(max_features=.85,random_state=42,n_jobs=-1)
    if variant=='original':return RandomForestRegressor(n_estimators=140,min_samples_leaf=4,**args)
    if variant=='revised':return RandomForestRegressor(n_estimators=240,min_samples_leaf=8,**args)
    raise ValueError(variant)


def metrics(y,p):
    y=np.asarray(y,dtype=float);p=np.asarray(p,dtype=float)
    return {'MAE':float(mean_absolute_error(y,p)),
            'RMSE':float(np.sqrt(mean_squared_error(y,p))),
            'Bias_actual_minus_pred':float(np.mean(y-p))}


def evaluate(frame=None, output_dir=None):
    d=make_frame().copy() if frame is None else frame.copy()
    d=d.sort_values('date').reset_index(drop=True)
    out=Path(output_dir) if output_dir is not None else ROOT/'models'
    out.mkdir(parents=True,exist_ok=True)
    n=len(d);train_end=int(n*.64);test_start=int(n*.8)
    if train_end<100 or test_start-train_end<30 or n-test_start<30:
        raise ValueError('Need at least 100 development days and 30 days each for validation/test.')
    if d['date'].duplicated().any():raise ValueError('Duplicate operating dates.')
    rows=[];seg=[];validation_models={};selected_names={}
    for key,features in FEATURES.items():
        X=d[features].astype(float);y=d[TARGETS[key]].astype(float)
        if X.isna().any().any() or y.isna().any():raise ValueError(f'Missing predictors for {key}')
        if np.isinf(X.to_numpy()).any():raise ValueError(f'Infinite predictors for {key}')
        val_scores={}
        # Only development data and the later validation slice select the configuration.
        for version in ('original','revised'):
            m=make_model(version)
            m.fit(X.iloc[:train_end],y.iloc[:train_end])
            pred=m.predict(X.iloc[train_end:test_start])
            val_scores[version]=metrics(y.iloc[train_end:test_start],pred)['MAE']
            validation_models[version]=m
        chosen=min(val_scores,key=val_scores.get)
        selected_names[key]=chosen
        validation_model=validation_models[chosen]
        perm=permutation_importance(validation_model,X.iloc[train_end:test_start],y.iloc[train_end:test_start],
                                    n_repeats=4,scoring='neg_mean_absolute_error',random_state=42,n_jobs=1)
        importance=dict(zip(features,[float(v) for v in perm.importances_mean]))
        reference={f:float(X.iloc[:test_start][f].median()) for f in features}
        # Refit using all pretest history, then evaluate the untouched final holdout.
        for version in ('original','revised'):
            m=make_model(version)
            m.fit(X.iloc[:test_start],y.iloc[:test_start])
            final_pred=m.predict(X.iloc[test_start:])
            result=metrics(y.iloc[test_start:],final_pred)
            naive_pred=d.iloc[test_start:][f'{key}_lag1'].to_numpy()
            naive=metrics(y.iloc[test_start:],naive_pred)
            rows.append({'KPI':key,'Configuration':version,'Chosen_on_validation':version==chosen,
                         'Development_validation_MAE':val_scores[version],
                         'Final_test_MAE':result['MAE'],'Final_test_RMSE':result['RMSE'],
                         'Final_test_bias':result['Bias_actual_minus_pred'],
                         'Naive_final_test_MAE':naive['MAE'],
                         'MAE_improvement_vs_naive_pct':100*(naive['MAE']-result['MAE'])/naive['MAE'] if naive['MAE'] else np.nan,
                         'Train_days':train_end,'Validation_days':test_start-train_end,'Test_days':n-test_start,
                         'Validation_end':str(d.iloc[test_start-1]['date']),
                         'Final_test_start':str(d.iloc[test_start]['date']),
                         'Final_test_end':str(d.iloc[-1]['date'])})
            test=d.iloc[test_start:].copy()
            test['abs_err']=np.abs(y.iloc[test_start:].to_numpy()-final_pred)
            test['bias']=y.iloc[test_start:].to_numpy()-final_pred
            for group,field in [('weekday','day_of_week_number'),('month','month_number'),('peak_season','is_peak_season')]:
                for value,g in test.groupby(field):
                    seg.append({'KPI':key,'Configuration':version,'Group':group,'Segment':str(value),
                                'N':len(g),'MAE':float(g['abs_err'].mean()),
                                'Bias':float(g['bias'].mean())})
            if version==chosen:
                bundle={'model':m,'features':features,'reference':reference,
                        'importance':importance,'key':key,'target':TARGETS[key],
                        'metrics':{'mae':result['MAE'],'rmse':result['RMSE'],
                                   'naive_mae':naive['MAE'],'test_rows':n-test_start},
                        'experiment':{'chosen_on_validation':chosen,
                                      'validation_MAE':val_scores,
                                      'importance_origin':'development validation only'}}
                joblib.dump(bundle,out/f'week11_selected_{key}.joblib',compress=3)
        print(f'{key}: validation selected {chosen}: {val_scores}')
    pd.DataFrame(rows).to_csv(out/'week11_evaluation.csv',index=False)
    pd.DataFrame(seg).to_csv(out/'week11_segment_errors.csv',index=False)
    notes={'source':'synthetic warehouse daily outcomes','date_sort':'chronological by operating day',
        'development_train_pct':64,'development_validation_pct':16,'final_test_pct':20,
        'selected_versions':selected_names,
        'feature_availability':{
            'workload':'Calendar and demand lag values must precede the prediction date.',
            'productivity':'Opening backlog and planned staff/hours must be known when decision is made; lagged realized productivity from only previous completed days.'},
        'limitations':['One-step-ahead historical holdout, not a validated 14-day recursive forecast.',
                       'Synthetic data not calibrated to actual operational data.',
                       'No causal effects are estimated by changing model predictors.',
                       'Final test results must not be used to select further configurations.']}
    (out/'week11_protocol.json').write_text(json.dumps(notes,indent=2))
    return pd.DataFrame(rows)

if __name__=='__main__':evaluate()
