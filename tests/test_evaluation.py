"""Run a small end-to-end training experiment without changing repository models."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

class ModelEvaluationTests(unittest.TestCase):
 def test_training_pipeline_and_artifacts(self):
  rng=np.random.default_rng(3)
  n=210
  d=pd.DataFrame({'date':pd.date_range('2024-01-01',periods=n,freq='B'),
      'day_of_week_number':np.tile(np.arange(1,6),42),'month_number':np.repeat([1,2,3,4,5,6,7],30),
      'is_peak_season':np.zeros(n),'is_holiday':np.zeros(n),'beginning_backlog_wlu':rng.uniform(0,100,n),
      'scheduled_worker_count':rng.integers(22,32,n),'scheduled_worker_hours':rng.uniform(180,240,n),
      'workload_lag1':rng.uniform(200,550,n),'workload_lag7':rng.uniform(200,550,n),
      'workload_rolling7':rng.uniform(250,500,n),'productivity_lag1':rng.uniform(1.3,2.2,n),
      'productivity_lag7':rng.uniform(1.3,2.2,n),'productivity_rolling7':rng.uniform(1.3,2.2,n)})
  d['new_workload_units']=.6*d['workload_lag1']+.4*d['workload_lag7']+rng.normal(0,15,n)
  d['actual_productivity_wlu_per_hour']=.5*d['productivity_lag1']+.5*d['productivity_rolling7']+rng.normal(0,.08,n)
  features={'workload':['day_of_week_number','month_number','is_peak_season','is_holiday','workload_lag1','workload_lag7','workload_rolling7'],
            'productivity':['day_of_week_number','month_number','is_peak_season','beginning_backlog_wlu','scheduled_worker_count','scheduled_worker_hours','productivity_lag1','productivity_lag7','productivity_rolling7']}
  fake=types.ModuleType('train_models');fake.make_frame=lambda:d;fake.FEATURES=features
  fake.TARGETS={'workload':'new_workload_units','productivity':'actual_productivity_wlu_per_hour'}
  previous=sys.modules.get('train_models')
  sys.modules['train_models']=fake
  try:
   spec=importlib.util.spec_from_file_location('_evaluate_patch',ROOT/'evaluate_week11.py')
   mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
   with tempfile.TemporaryDirectory() as tmp:
    result=mod.evaluate(output_dir=tmp)
    self.assertEqual(len(result),4)
    self.assertEqual(result.groupby('KPI')['Chosen_on_validation'].sum().to_dict(),{'productivity':1,'workload':1})
    for name in ['week11_evaluation.csv','week11_segment_errors.csv','week11_protocol.json',
                 'week11_selected_workload.joblib','week11_selected_productivity.joblib']:
     self.assertTrue((Path(tmp)/name).exists(),name)
  finally:
   if previous is None:sys.modules.pop('train_models',None)
   else:sys.modules['train_models']=previous

if __name__=='__main__':unittest.main()
