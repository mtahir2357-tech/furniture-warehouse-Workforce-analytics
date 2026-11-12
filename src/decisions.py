"""Decision log stored as a CSV next to the data."""
from datetime import datetime

import pandas as pd

from src.config import DECISION_LOG

COLUMNS = [
    "saved_at", "forecast_run", "target_date", "scenario", "final_action",
    "planned_regular_hours", "planned_overtime_hours", "expected_available_hours",
    "projected_capacity_gap", "projected_labor_cost", "notes",
    # The alternative that was considered but NOT implemented (Keep current plan / Monitor), kept apart from
    # the plan that was actually recorded above so the history is never misleading.
    "proposed_not_implemented", "proposed_labor_cost",
]
ACTIONS = ("Implement selected scenario", "Keep current plan", "Monitor and revisit tomorrow")


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
    if DECISION_LOG.exists():
        old = pd.read_csv(DECISION_LOG)
        if list(old.columns) != COLUMNS:  # older log without the new columns: rewrite it once with the full header
            pd.concat([old.reindex(columns=COLUMNS), df], ignore_index=True).to_csv(DECISION_LOG, index=False)
            return
    df.to_csv(DECISION_LOG, mode="a", header=not DECISION_LOG.exists(), index=False)


def decision_record(action: str, selected: dict, baseline: dict, forecast_run: str, target_date: str,
                    notes: str = "") -> dict:
    """The row saved for a manager decision. Hours, overtime, gap and cost always describe the plan that is
    actually implemented:

    * Implement selected scenario -> the selected scenario (must be feasible under the staffing policy);
    * Keep current plan           -> the baseline (current) plan;
    * Monitor and revisit tomorrow -> the baseline plan stays in place; the selected scenario is recorded only
      as 'proposed, not implemented'.
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")
    implement = action == ACTIONS[0]
    if implement and not selected.get("feasible", True):
        raise ValueError("An infeasible scenario cannot be recorded as implemented.")
    plan = selected if implement else baseline
    differs = selected.get("scenario_id") != baseline.get("scenario_id") or selected.get("label") != baseline.get("label")
    proposed = (not implement) and differs
    tags = []
    if plan.get("over_budget"):
        tags.append("[recorded plan over daily labor budget]")
    if proposed:
        tags.append(f"[{selected['label']} proposed, not implemented]")
    return {
        "forecast_run": forecast_run, "target_date": target_date,
        "scenario": plan["label"], "final_action": action,
        "planned_regular_hours": round(float(plan["planned_regular_hours"]), 1),
        "planned_overtime_hours": round(float(plan["planned_overtime_hours"]), 1),
        "expected_available_hours": round(float(plan["expected_total_available_hours"]), 1),
        "projected_capacity_gap": round(float(plan["capacity_gap_hours"]), 1),
        "projected_labor_cost": round(float(plan["projected_total_labor_cost"]), 2),
        "notes": " ".join([notes.strip(), *tags]).strip(),
        "proposed_not_implemented": selected["label"] if proposed else "",
        "proposed_labor_cost": round(float(selected["projected_total_labor_cost"]), 2) if proposed else "",
    }


def latest_for_run(run: pd.Timestamp) -> pd.DataFrame:
    """Most recent decision per target date for one forecast run."""
    log = load()
    if log.empty:
        return log
    log = log[log["forecast_run"] == run.strftime("%Y-%m-%d")]
    return log.drop_duplicates("target_date", keep="last").set_index("target_date")
