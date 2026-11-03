import unittest
import pandas as pd
from src.planning import plan_day,forward_plan

class PlanningTests(unittest.TestCase):
 def test_carry_in_backlog(self):
  r=plan_day(400,100,2.0,225,0,1.0,20,100)
  self.assertAlmostEqual(r['ending_backlog_wlu'],50)
  self.assertAlmostEqual(r['required_hours'],250)
  self.assertAlmostEqual(r['capacity_gap_hours'],-25)
 def test_no_backlog_when_capacity_sufficient(self):
  r=plan_day(100,30,2,100,0,.75,20,100)
  self.assertEqual(r['ending_backlog_wlu'],0)
  self.assertEqual(r['processed_wlu'],130)
 def test_overtime_cost(self):
  r=plan_day(50,0,1,40,10,.5,20,100)
  self.assertAlmostEqual(r['labor_cost'],800)
 def test_negative_input_fails(self):
  with self.assertRaises(ValueError):plan_day(20,-1,1,40,0,1,20,100)
 def test_backlog_rolling(self):
  f=pd.DataFrame({'horizon_operating_days':[1,2], 'target_date':pd.to_datetime(['2025-01-02','2025-01-03']),
   'forecast_workload_units':[400,200], 'expected_productivity_wlu_per_hour':[2,2],
   'planned_regular_hours':[200,150], 'expected_available_regular_hours':[200,150],
   'avg_worker_hourly_rate':[20,20], 'projected_manager_labor_cost':[100,100]})
  p=forward_plan(f,100)
  self.assertAlmostEqual(p.iloc[0]['ending_backlog_wlu'],100)
  self.assertAlmostEqual(p.iloc[1]['beginning_backlog_wlu'],100)
  self.assertAlmostEqual(p.iloc[1]['ending_backlog_wlu'],0)
if __name__=='__main__': unittest.main()
