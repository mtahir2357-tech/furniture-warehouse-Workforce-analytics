"""Run python -m unittest discover -s tests -v in the full GitHub checkout."""
from pathlib import Path
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validate_submission import run

class SourceIntegrity(unittest.TestCase):
    def test_forecast_and_scenario_linkage(self):
        d=run(ROOT)
        self.assertEqual(d['operating_days'],939)
        self.assertEqual(d['forecast_rows'],12166)
        self.assertEqual(d['forecast_origins'],869)
        self.assertEqual(d['scenario_rows'],72996)
        self.assertEqual(d['forecast_horizons'],list(range(1,15)))
        self.assertEqual(d['scenario_join_missing'],0)
        self.assertTrue(d['horizon_completeness'])
    def test_operational_continuity(self):
        d=run(ROOT)
        self.assertLess(d['backlog_continuity_max_abs'],.01)
        self.assertLess(d['forecast_actual_consistency_max_abs'],.0001)
    def test_static_staffing_not_hidden(self):
        d=run(ROOT)
        self.assertEqual(d['scheduled_worker_count_unique'],[25])
        self.assertEqual(d['scheduled_worker_hours_unique'],[200.0])

if __name__=='__main__':unittest.main()
