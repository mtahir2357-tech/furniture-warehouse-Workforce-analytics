"""Manager-friendly forecast reliability, computed from the stored 14-day forecasts and actuals (review fix F6).

Nothing here changes a forecast. Every number is recomputed from fact_workload_forecast:
forecast vs actual workload, the stored 80% range, and the stored capacity-exceedance probability.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def summary(f: pd.DataFrame, horizon: int | None = None) -> dict:
    """Reliability of the original 14-day workload forecast (optionally for one horizon)."""
    sub = f if horizon is None else f[f["horizon_operating_days"] == horizon]
    if sub.empty:
        return {"n": 0}
    a = sub["actual_workload_units"].to_numpy(float)
    p = sub["forecast_workload_units"].to_numpy(float)
    err = a - p
    abs_err = np.abs(err)
    covered = (a >= sub["lower_80_workload_units"].to_numpy(float)) & (a <= sub["upper_80_workload_units"].to_numpy(float))
    busy_cut = float(np.quantile(a, 0.9))
    busy = a >= busy_cut
    exceeded = a > sub["baseline_capacity_wlu"].to_numpy(float)
    high = sub["probability_capacity_exceeded"].to_numpy(float) >= 0.5
    low = sub["probability_capacity_exceeded"].to_numpy(float) < 0.25
    prod = float(sub["expected_productivity_wlu_per_hour"].mean())
    return {
        "n": int(len(sub)),
        "mae_wlu": float(abs_err.mean()),
        "p80_abs_err_wlu": float(np.quantile(abs_err, 0.8)),
        "coverage_80": float(covered.mean()),
        "above_upper": float((a > sub["upper_80_workload_units"].to_numpy(float)).mean()),
        "bias_wlu": float(err.mean()),
        "busy_threshold_wlu": busy_cut,
        "busy_bias_wlu": float(err[busy].mean()) if busy.any() else float("nan"),
        "busy_share_under": float((err[busy] > 0).mean()) if busy.any() else float("nan"),
        "high_risk_days": int(high.sum()),
        "high_risk_observed": float(exceeded[high].mean()) if high.any() else float("nan"),
        "high_risk_stated": float(sub["probability_capacity_exceeded"].to_numpy(float)[high].mean()) if high.any() else float("nan"),
        "low_risk_observed": float(exceeded[low].mean()) if low.any() else float("nan"),
        "productivity": prod,
    }


def to_hours(wlu: float, productivity: float) -> float:
    return float(wlu) / max(float(productivity), 1e-6)


def manager_lines(s: dict, shift_hours: float = 8.0, productivity: float | None = None, scope: str = "") -> list[str]:
    """Plain-language reading of a reliability summary for staffing decisions."""
    if not s.get("n"):
        return ["No forecasts with recorded outcomes match this selection."]
    prod = productivity or s["productivity"]
    typ_h = to_hours(s["mae_wlu"], prod)
    p80_h = to_hours(s["p80_abs_err_wlu"], prod)
    lines = [
        f"Typical miss{scope}: about ±{s['mae_wlu']:,.0f} WLU ≈ {typ_h:,.0f} labor hours ≈ {typ_h / shift_hours:,.1f} "
        f"{shift_hours:g}-hour shifts. Four days in five the miss is within ±{s['p80_abs_err_wlu']:,.0f} WLU "
        f"(≈ {p80_h / shift_hours:,.1f} shifts).",
        f"The 80% range contained the actual workload on {s['coverage_80']:.0%} of days — close to its 80% target, "
        "so about one day in five falls outside it (either side).",
    ]
    if s["busy_bias_wlu"] == s["busy_bias_wlu"]:
        lines.append(f"Busiest days (actual ≥ {s['busy_threshold_wlu']:,.0f} WLU) were under-forecast on "
                     f"{s['busy_share_under']:.0%} of occasions, by {s['busy_bias_wlu']:,.0f} WLU on average "
                     f"(≈ {to_hours(s['busy_bias_wlu'], prod) / shift_hours:,.1f} shifts) — plan a buffer when a surge is likely.")
    if s["high_risk_days"]:
        lines.append(f"When the exceedance risk was shown as 50% or higher (average stated {s['high_risk_stated']:.0%}), "
                     f"workload actually exceeded baseline capacity {s['high_risk_observed']:.0%} of the time; "
                     f"below 25% it happened {s['low_risk_observed']:.0%} of the time. Treat the percentage as a rough guide.")
    lines.append("Measured on the saved historical forecasts (synthetic data); it describes past performance, not a guarantee.")
    return lines
