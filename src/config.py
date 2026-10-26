"""Central settings for the dashboard. Change values here, not in the pages."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DECISION_LOG = DATA_DIR / "decision_log.csv"

APP_TITLE = "Furniture Fulfillment Workforce Planning Tool"
APP_SHORT = "Workforce Planning"

# A day is "Balanced" when |capacity gap| <= this many hours (one 8-hour shift).
# Adjustable from the sidebar; this is a proposed MVP rule, not an industry threshold.
DEFAULT_BALANCED_TOLERANCE_HRS = 8.0

OVERTIME_MULTIPLIER = 1.5

# Probability that forecast workload exceeds baseline capacity: <low = Low, <high = Moderate, else High
EXCEEDANCE_RISK_BANDS = (0.25, 0.50)

# Projected capacity utilization: <low = Low backlog risk, <=high = Moderate, >high = High
UTILIZATION_RISK_BANDS = (0.90, 1.05)

# Scenario display names and their role in the decision (Week 6 decision logic).
SCENARIO_LABELS = {
    "S01": "Current plan",
    "S02": "Increase regular hours",
    "S03": "Add overtime",
    "S04": "High demand (stress test)",
    "S05": "Low productivity (stress test)",
    "S06": "Reduce regular hours",
}
ACTION_SCENARIOS = ["S01", "S02", "S03", "S06"]
STRESS_SCENARIOS = ["S04", "S05"]
