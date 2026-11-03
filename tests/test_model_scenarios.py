import unittest
import numpy as np
import pandas as pd
from src.model_scenarios import scenario_inputs,validate_historical_ranges,sequential_local_contributions,model_predict

class MockModel:
 def predict(self,x):
  return np.asarray(x['workload_lag1']*.2+x['workload_lag7']*.3+x['workload_rolling7']*.5)

class ScenarioTests(unittest.TestCase):
 def test_coherent_demand_lags(self):
  x=pd.Series({'workload_lag1':100,'workload_lag7':120,'workload_rolling7':110})
  y=scenario_inputs('workload',x,context_multiplier=1.1)
  self.assertAlmostEqual(y['workload_lag1'],110)
  self.assertAlmostEqual(y['workload_lag7'],132)
  self.assertAlmostEqual(y['workload_rolling7'],121)
 def test_staff_and_hours_move_together(self):
  x=pd.Series({'scheduled_worker_count':20,'scheduled_worker_hours':160})
  y=scenario_inputs('productivity',x,worker_change=2,hours_per_worker=8)
  self.assertEqual(y['scheduled_worker_count'],22)
  self.assertEqual(y['scheduled_worker_hours'],176)
 def test_unfeasible_staffing_rejected(self):
  x=pd.Series({'scheduled_worker_count':2,'scheduled_worker_hours':16})
  with self.assertRaises(ValueError):scenario_inputs('productivity',x,worker_change=-3)
 def test_local_steps_add_up(self):
  b={'features':['workload_lag1','workload_lag7','workload_rolling7'], 'reference':{'workload_lag1':80,'workload_lag7':90,'workload_rolling7':85},'model':MockModel()}
  q={'workload_lag1':100,'workload_lag7':120,'workload_rolling7':110}
  r,c=sequential_local_contributions(b,q)
  self.assertAlmostEqual(c['Contribution'].sum(),model_predict(b,q)-r)
 def test_quantile_warning(self):
  d=pd.DataFrame({'workload_lag1':range(100),'workload_lag7':range(100),'workload_rolling7':range(100)})
  w=validate_historical_ranges(d,pd.Series({'workload_lag1':500,'workload_lag7':50,'workload_rolling7':50}),'workload')
  self.assertEqual(len(w),1)
if __name__=='__main__':unittest.main()
