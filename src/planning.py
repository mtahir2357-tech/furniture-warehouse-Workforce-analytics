"""Forward inventory-of-work accounting for daily staffing plans.

All figures WLU, worker-hours, and dollars; formula outputs are deterministic,
NOT trained backlog model forecasts. The data pipeline's older scenario records
are preserved separately, rather than silently relabeled.
"""
from __future__ import annotations
import math
import pandas as pd


def plan_day(incoming_wlu:float,beginning_backlog_wlu:float,productivity_wlu_per_hour:float,
             regular_hours:float,overtime_hours:float,availability_ratio:float,
             hourly_rate:float,manager_cost:float)->dict:
    vals=[incoming_wlu,beginning_backlog_wlu,productivity_wlu_per_hour,regular_hours,
          overtime_hours,availability_ratio,hourly_rate,manager_cost]
    if any(not math.isfinite(float(v)) for v in vals):
        raise ValueError('Inputs must be finite numbers.')
    if any(float(v)<0 for v in vals):
        raise ValueError('Workload, labor hours, costs, and backlog cannot be negative.')
    if productivity_wlu_per_hour<=0: raise ValueError('Productivity must be greater than zero.')
    if not 0<=availability_ratio<=1: raise ValueError('Availability must be between 0 and 1.')
    available_regular=regular_hours*availability_ratio
    total_hours=available_regular+overtime_hours
    required_wlu=beginning_backlog_wlu+incoming_wlu
    capacity=total_hours*productivity_wlu_per_hour
    processed=min(required_wlu,capacity)
    end_backlog=max(0.0,required_wlu-processed)
    labor_cost=available_regular*hourly_rate+overtime_hours*hourly_rate*1.5+manager_cost
    required_hours=required_wlu/productivity_wlu_per_hour
    return dict(incoming_wlu=incoming_wlu,beginning_backlog_wlu=beginning_backlog_wlu,
      total_workload_wlu=required_wlu,capacity_wlu=capacity,processed_wlu=processed,
      ending_backlog_wlu=end_backlog,expected_regular_hours=available_regular,
      expected_total_available_hours=total_hours,required_hours=required_hours,
      capacity_gap_hours=total_hours-required_hours,utilization=required_hours/total_hours if total_hours>0 else float('inf'),
      labor_cost= labor_cost)


def forward_plan(forecast_rows:pd.DataFrame,initial_backlog_wlu:float)->pd.DataFrame:
    """Each forecast day carries its predicted unprocessed work into next day.
    Expects forecast_rows in horizon order and baseline scenario columns joined.
    """
    out=[];carry=float(initial_backlog_wlu)
    for _,r in forecast_rows.sort_values('horizon_operating_days').iterrows():
        h=plan_day(float(r['forecast_workload_units']),carry,
          float(r['expected_productivity_wlu_per_hour']),float(r['planned_regular_hours']),0.0,
          float(r['expected_available_regular_hours'])/float(r['planned_regular_hours']) if float(r['planned_regular_hours'])>0 else 0.0,
          float(r['avg_worker_hourly_rate']),float(r['projected_manager_labor_cost']))
        h.update(target_date=r['target_date'],horizon_operating_days=int(r['horizon_operating_days']),
                 source_forecast_wlu=float(r['forecast_workload_units']))
        out.append(h);carry=h['ending_backlog_wlu']
    return pd.DataFrame(out)
