"""Decision log stored as a CSV next to the data."""
from datetime import datetime

import pandas as pd

from src.config import DECISION_LOG

COLUMNS = [
    "saved_at", "forecast_run", "target_date", "scenario", "final_action",
    "planned_regular_hours", "planned_overtime_hours", "expected_available_hours",
    "projected_capacity_gap", "projected_labor_cost", "notes",
]


def load() -> pd.DataFrame:
    if DECISION_LOG.exists():
        return pd.read_csv(DECISION_LOG)
    return pd.DataFrame(columns=COLUMNS)


def save(rows: list[dict]):
    if not rows:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    df = pd.DataFrame([{**{c: "" for c in COLUMNS}, "saved_at": stamp, **r} for r in rows])[COLUMNS]
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DECISION_LOG, mode="a", header=not DECISION_LOG.exists(), index=False)


def latest_for_run(run: pd.Timestamp) -> pd.DataFrame:
    """Most recent decision per target date for one forecast run."""
    log = load()
    if log.empty:
        return log
    log = log[log["forecast_run"] == run.strftime("%Y-%m-%d")]
    return log.drop_duplicates("target_date", keep="last").set_index("target_date")
