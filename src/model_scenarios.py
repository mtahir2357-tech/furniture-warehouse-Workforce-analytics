"""Pure, non-causal trained-model scenario logic and input constraints."""
from __future__ import annotations
import numpy as np
import pandas as pd


def model_predict(bundle: dict, inputs: pd.Series | dict) -> float:
    features = bundle['features']
    frame = pd.DataFrame([{f: float(inputs[f]) for f in features}], columns=features)
    return max(0.0, float(bundle['model'].predict(frame)[0]))


def scenario_inputs(kind: str, original: pd.Series, context_multiplier: float = 1.0,
                    worker_change: int = 0, hours_per_worker: float = 8.0) -> pd.Series:
    """Consistent contextual workload scenarios or jointly changing schedule count/hours.

    Historical lags change only in a *hypothetical prior-demand context*.
    Staffing model variations are statistical associations, not staffing treatment effects.
    """
    if not 0.75 <= context_multiplier <= 1.25:
        raise ValueError('Demand context must stay between 75% and 125%.')
    if abs(int(worker_change)) > 10:
        raise ValueError('Change cannot exceed ten workers.')
    if not 4 <= hours_per_worker <= 12:
        raise ValueError('Shift hours must be between four and twelve.')
    modified = original.copy().astype(float)
    if kind == 'workload':
        for field in ('workload_lag1', 'workload_lag7', 'workload_rolling7'):
            modified[field] *= context_multiplier
    elif kind == 'productivity':
        new_count = int(round(float(modified['scheduled_worker_count']))) + int(worker_change)
        if new_count < 0:
            raise ValueError('Scheduled worker count cannot be negative.')
        modified['scheduled_worker_count'] = new_count
        modified['scheduled_worker_hours'] = max(0.0, float(modified['scheduled_worker_hours']) + worker_change * hours_per_worker)
        if new_count == 0 and modified['scheduled_worker_hours'] > 0:
            raise ValueError('Cannot schedule hours with no workers.')
        if new_count > 0 and modified['scheduled_worker_hours'] > 12 * new_count:
            raise ValueError('Scheduled hours exceed twelve hours per worker.')
    else:
        raise ValueError('Unknown model kind')
    return modified


def validate_historical_ranges(data: pd.DataFrame, modified: pd.Series, kind: str):
    """Return warnings for values outside development training bounds; do not imply causal validity."""
    fields = (('workload_lag1','workload_lag7','workload_rolling7') if kind == 'workload'
              else ('scheduled_worker_count','scheduled_worker_hours'))
    warnings=[]
    for f in fields:
        low=float(data[f].quantile(.01));high=float(data[f].quantile(.99));value=float(modified[f])
        if not low <= value <= high:
            warnings.append(f'{f}={value:,.2f} is outside the training 1st–99th percentile ({low:,.2f}–{high:,.2f}).')
    return warnings


def sequential_local_contributions(bundle:dict, inputs: pd.Series | dict):
    """Signed, order-dependent individual contributions from a fixed training median."""
    fs=bundle['features'];ref={f:float(bundle['reference'][f]) for f in fs}
    start=model_predict(bundle,ref);previous=start;result=[]
    for f in fs:
        ref[f]=float(inputs[f]);next_=model_predict(bundle,ref)
        result.append({'Feature':f,'Contribution':next_-previous});previous=next_
    return start, pd.DataFrame(result)
