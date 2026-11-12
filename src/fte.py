"""Full-time-equivalent (FTE) workforce calculations and feasible staffing responses.

Definitions (configurable in src/config.py)
-------------------------------------------
* Daily FTE = 8-hour worker-shift equivalents, NOT contractual full-time headcount.
    Required Daily FTE  = Required Labor Hours  / shift hours (8)
    Available Daily FTE = Available Labor Hours / shift hours (8)
    FTE Gap             = Required Daily FTE - Available Daily FTE   (positive = shortage)
* Weekly FTE = Weekly Labor Hours / standard full-time week (40).
* Decimal FTE values are kept for comparisons; only "additional whole worker-shift
  equivalents" is rounded up.
* Available labor hours are WORKER hours only: planned regular hours x expected availability
  (applied once) + planned overtime. Manager hours are never added to productive capacity;
  manager cost is carried separately in the labor cost.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from src.config import (
    FULL_TIME_WEEK_HOURS,
    MAX_DAILY_OVERTIME_PER_WORKER,
    MIN_SCHEDULED_WORKERS,
    OVERTIME_MULTIPLIER,
    SHIFT_HOURS,
    WEEKLY_HOUR_CAP,
    WORKER_ROSTER,
)
from src.planning import plan_day


@dataclass(frozen=True)
class StaffingPolicy:
    shift_hours: float = SHIFT_HOURS
    week_hours: float = FULL_TIME_WEEK_HOURS
    roster_workers: int = WORKER_ROSTER
    min_workers: int = MIN_SCHEDULED_WORKERS
    max_ot_per_worker_day: float = MAX_DAILY_OVERTIME_PER_WORKER
    overtime_multiplier: float = OVERTIME_MULTIPLIER
    weekly_hour_cap: float = WEEKLY_HOUR_CAP
    operating_days_per_week: int = 6

    def __post_init__(self):
        if self.shift_hours <= 0 or self.week_hours <= 0:
            raise ValueError("Shift and week hours must be positive.")
        if self.weekly_hour_cap < self.week_hours:
            raise ValueError("Weekly hour cap cannot be below the full-time week.")
        if self.min_workers < 0 or self.roster_workers < self.min_workers:
            raise ValueError("Roster must be at least the minimum staffing level.")
        if self.max_ot_per_worker_day < 0:
            raise ValueError("Overtime cap cannot be negative.")

    @property
    def weekly_shift_cap(self) -> float:
        """Regular shifts the roster can work in one week (each worker = week_hours / shift_hours shifts)."""
        return self.roster_workers * self.week_hours / self.shift_hours


def check_feasibility(regular_hours: float, overtime_hours: float, policy: StaffingPolicy = StaffingPolicy()) -> dict:
    """Validate one day's staffing plan against operational constraints.

    Infeasible (hard limits): negative hours; more scheduled workers than the roster; fewer than
    the minimum staffing level (project assumption); overtime above the per-worker daily cap, or
    overtime with nobody scheduled. Warnings (allowed, but flagged): partial shifts and a daily
    headcount above what the roster can sustain over a full operating week.
    """
    issues, warnings = [], []
    reg, ot = float(regular_hours), float(overtime_hours)
    if not (math.isfinite(reg) and math.isfinite(ot)):
        return {"feasible": False, "issues": ["Hours must be finite numbers."], "warnings": [],
                "scheduled_workers": float("nan"), "overtime_cap": 0.0}
    if reg < 0 or ot < 0:
        issues.append("Hours cannot be negative.")
    workers = max(reg, 0.0) / policy.shift_hours
    ot_cap = workers * policy.max_ot_per_worker_day
    if workers > policy.roster_workers + 1e-9:
        issues.append(f"{workers:.1f} scheduled workers exceed the roster of {policy.roster_workers} "
                      f"({policy.roster_workers * policy.shift_hours:g} regular hours maximum).")
    if workers < policy.min_workers - 1e-9:
        issues.append(f"{workers:.1f} scheduled workers is below the {policy.min_workers}-worker minimum "
                      "(project assumption).")
    if ot > ot_cap + 1e-9:
        issues.append(f"{ot:g} overtime hours exceed the cap of {ot_cap:g} h "
                      f"({policy.max_ot_per_worker_day:g} h × {workers:.1f} scheduled workers).")
    if abs(workers - round(workers)) > 1e-9:
        warnings.append(f"{reg:g} regular hours is not a whole number of {policy.shift_hours:g}-hour shifts.")
    sustainable = policy.weekly_shift_cap / policy.operating_days_per_week
    if not issues and workers > sustainable + 1e-9:
        warnings.append(f"{workers:.0f} workers is above the {sustainable:g} per day the roster can sustain over a "
                        f"{policy.operating_days_per_week}-day week; feasible for this day only if other days use fewer.")
    return {"feasible": not issues, "issues": issues, "warnings": warnings,
            "scheduled_workers": workers, "overtime_cap": ot_cap}


def budget_check(cost: float, budget: float | None) -> dict | None:
    """Compare a daily labor cost with an optional budget. None when no budget is set."""
    if budget is None:
        return None
    over = float(cost) - float(budget)
    return {"within": over <= 1e-9, "over_by": max(0.0, over), "headroom": max(0.0, -over),
            "label": "Within budget" if over <= 1e-9 else f"Over budget by ${over:,.0f}"}


def round_half_up(x: float, digits: int = 2) -> float:
    """Conventional rounding for display (2.725 -> 2.73), avoiding binary floating-point artefacts."""
    return float(Decimal(repr(round(float(x), 10))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def to_fte(hours: float, shift_hours: float = SHIFT_HOURS) -> float:
    if shift_hours <= 0:
        raise ValueError("Shift hours must be positive.")
    return float(hours) / shift_hours


def whole_shifts(fte_shortage: float) -> int:
    """Whole worker-shift equivalents needed to cover a decimal FTE shortage (round up only here)."""
    return int(math.ceil(round(max(0.0, float(fte_shortage)), 9)))


def fte_summary(required_hours: float, available_hours: float, shift_hours: float = SHIFT_HOURS) -> dict:
    req = to_fte(required_hours, shift_hours)
    avail = to_fte(available_hours, shift_hours)
    gap = req - avail
    return {
        "required_fte": req,
        "available_fte": avail,
        "fte_gap": gap,
        "fte_shortage": max(0.0, gap),
        "fte_surplus": max(0.0, -gap),
        "additional_shifts": whole_shifts(gap),
        "fte_status": "Shortage" if gap > 1e-9 else ("Surplus" if gap < -1e-9 else "Balanced"),
    }


def weekly_fte(hours: float, week_hours: float = FULL_TIME_WEEK_HOURS) -> float:
    if week_hours <= 0:
        raise ValueError("Week hours must be positive.")
    return float(hours) / week_hours


def staffing_response(workload: float, productivity: float, beginning_backlog: float,
                      planned_regular_hours: float, availability_ratio: float,
                      hourly_rate: float, manager_cost: float,
                      policy: StaffingPolicy = StaffingPolicy()) -> dict:
    """Current plan vs. the lowest-cost feasible response for one day.

    Response order: add whole regular shifts (up to the roster), then overtime (up to the
    per-worker daily cap). For a surplus, remove whole shifts only while the day stays
    covered and the minimum staffing policy is respected. Infeasible shortages are reported,
    never hidden; their unmet work is carried as backlog.
    """
    sh = policy.shift_hours
    planned_workers = planned_regular_hours / sh
    cur = plan_day(workload, beginning_backlog, productivity, planned_regular_hours, 0.0,
                   availability_ratio, hourly_rate, manager_cost)
    cur_fte = fte_summary(cur["required_hours"], cur["expected_total_available_hours"], sh)
    gap_hours = cur["required_hours"] - cur["expected_total_available_hours"]
    productive_per_shift = sh * availability_ratio
    notes = []
    add_shifts, ot = 0, 0.0
    if gap_hours > 1e-9:
        # Regular hours cost 1x per productive hour and overtime 1.5x, so whole extra shifts come first;
        # the final partial shift is covered with overtime when that is cheaper and within the cap.
        spare = max(0, int(math.floor(policy.roster_workers - planned_workers + 1e-9)))
        def ot_cap(k):
            return (planned_workers + k) * policy.max_ot_per_worker_day
        full = int(math.floor(round(gap_hours / productive_per_shift, 9))) if productive_per_shift > 0 else 0
        add_shifts = min(full, spare)
        remaining = gap_hours - add_shifts * productive_per_shift
        if remaining > 1e-9:
            ot_cheaper = remaining * policy.overtime_multiplier < productive_per_shift
            if add_shifts < spare and (not ot_cheaper or remaining > ot_cap(add_shifts) + 1e-9):
                add_shifts += 1
            else:
                ot = min(remaining, ot_cap(add_shifts))
        if add_shifts >= spare and gap_hours - add_shifts * productive_per_shift - ot > 1e-6:
            notes.append(f"Roster limit: only {spare} additional workers are available (roster {policy.roster_workers}); "
                         f"overtime is capped at {policy.max_ot_per_worker_day:g} h per scheduled worker.")
    elif gap_hours < -1e-9:
        removable = int(math.floor(round(-gap_hours / productive_per_shift, 9))) if productive_per_shift > 0 else 0
        floor_room = max(0, int(math.floor(planned_workers - policy.min_workers + 1e-9)))
        add_shifts = -min(removable, floor_room)
        if removable > floor_room:
            notes.append(f"Minimum staffing policy keeps at least {policy.min_workers} scheduled workers.")
    new_regular = planned_regular_hours + add_shifts * sh
    rec = plan_day(workload, beginning_backlog, productivity, new_regular, ot,
                   availability_ratio, hourly_rate, manager_cost)
    rec_fte = fte_summary(rec["required_hours"], rec["expected_total_available_hours"], sh)
    feasible = rec["required_hours"] - rec["expected_total_available_hours"] <= 1e-6
    if not feasible:
        notes.append(f"Infeasible within policy: {rec['required_hours'] - rec['expected_total_available_hours']:,.1f} "
                     f"labor hours remain uncovered and {rec['ending_backlog_wlu']:,.0f} WLU carry over as backlog.")
    if planned_workers < policy.min_workers:
        notes.append(f"Current plan schedules {planned_workers:.0f} workers, below the {policy.min_workers}-worker minimum.")
    return {
        "planned_workers": planned_workers,
        "current": {**cur, **cur_fte},
        "recommended": {**rec, **rec_fte, "scheduled_workers": planned_workers + add_shifts,
                        "regular_hours": new_regular, "overtime_hours": ot},
        "shift_change": add_shifts,
        "overtime_hours": ot,
        "feasible": feasible,
        "notes": notes,
    }


def horizon_plan(days: pd.DataFrame, initial_backlog: float, policy: StaffingPolicy = StaffingPolicy(),
                 workload_col: str = "workload", productivity_col: str = "productivity") -> pd.DataFrame:
    """Forward 14-day FTE plan.

    ``days`` needs columns: target_date, workload, productivity, planned_regular_hours,
    availability_ratio, hourly_rate, manager_cost. The current plan and the recommended
    response each carry their own projected backlog forward.
    """
    out = []
    carry_cur = carry_rec = float(initial_backlog)
    for _, r in days.iterrows():
        args = (float(r["planned_regular_hours"]), float(r["availability_ratio"]),
                float(r["hourly_rate"]), float(r["manager_cost"]))
        cur = plan_day(float(r[workload_col]), carry_cur, float(r[productivity_col]), args[0], 0.0, args[1], args[2], args[3])
        resp = staffing_response(float(r[workload_col]), float(r[productivity_col]), carry_rec, *args, policy=policy)
        f = fte_summary(cur["required_hours"], cur["expected_total_available_hours"], policy.shift_hours)
        rec = resp["recommended"]
        out.append({
            "target_date": r["target_date"],
            "workload_wlu": float(r[workload_col]),
            "productivity": float(r[productivity_col]),
            "beginning_backlog_wlu": carry_cur,
            "required_hours": cur["required_hours"],
            "available_hours": cur["expected_total_available_hours"],
            **f,
            "capacity_wlu": cur["capacity_wlu"],
            "ending_backlog_wlu": cur["ending_backlog_wlu"],
            "labor_cost": cur["labor_cost"],
            "rec_beginning_backlog_wlu": carry_rec,
            "rec_required_fte": rec["required_fte"],
            "rec_shift_change": resp["shift_change"],
            "rec_overtime_hours": resp["overtime_hours"],
            "rec_scheduled_workers": rec["scheduled_workers"],
            "rec_available_hours": rec["expected_total_available_hours"],
            "rec_available_fte": rec["available_fte"],
            "rec_required_hours": rec["required_hours"],
            "rec_fte_gap": rec["fte_gap"],
            "rec_ending_backlog_wlu": rec["ending_backlog_wlu"],
            "rec_labor_cost": rec["labor_cost"],
            "rec_feasible": resp["feasible"],
            "rec_notes": " ".join(resp["notes"]),
        })
        carry_cur = cur["ending_backlog_wlu"]
        carry_rec = rec["ending_backlog_wlu"]
    plan = pd.DataFrame(out)
    if plan.empty:
        return plan
    week = pd.to_datetime(plan["target_date"]).dt.to_period("W-SUN").astype(str)
    plan["week"] = week
    wk = plan.groupby("week").agg(week_required_hours=("required_hours", "sum"),
                                  week_rec_shifts=("rec_scheduled_workers", "sum"),
                                  week_rec_overtime=("rec_overtime_hours", "sum"))
    plan = plan.join(wk, on="week")
    plan["weekly_required_fte"] = plan["week_required_hours"] / policy.week_hours
    plan["week_shift_cap_exceeded"] = plan["week_rec_shifts"] > policy.weekly_shift_cap + 1e-9
    ot_week_cap = policy.roster_workers * max(0.0, policy.weekly_hour_cap - policy.week_hours)
    plan["week_overtime_cap_exceeded"] = plan["week_rec_overtime"] > ot_week_cap + 1e-9
    return plan
