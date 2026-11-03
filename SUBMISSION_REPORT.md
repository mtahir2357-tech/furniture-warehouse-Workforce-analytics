# Predictive Workforce Planning — Validation and Revision Report

**Project:** Furniture Warehouse Workforce Analytics, Group 6  
**Data:** Single-warehouse synthetic operating history, 2023–2025.  
**Application baseline:** GitHub `main`, three-page Streamlit app, Week 10 snapshot retained in `week10_snapshot/`.  
**Revision status:** Local patch prepared; actual GitHub deployment and outside-user test are **not yet complete**.

## Decision objective and retained KPIs

The warehouse manager needs to (1) anticipate workload and backlog risk early enough to schedule capacity and (2) compare feasible labor adjustments against projected backlog and labor cost. Retained predictive KPIs: daily **incoming weighted workload (WLU)** and **productivity capacity-rate assumption (WLU/worker-hour)**. **Ending backlog WLU** is a *derived* output, not a third independently trained prediction model: `max(0, beginning backlog + incoming demand − processed capacity)`.

**Two distinct systems must not be conflated.** The original generator creates 14-day forecasts with a historical-rule demand model and smoothed productivity assumptions; the Week 10 GitHub repository also has Random Forest models for one-day-ahead workload and productivity. Their performance tables use different cohorts and different baseline rules.

## 1. Evaluate predictive performance (a–e)

**a. Data separation.** For the Random Forest KPI regressions, chronological operating-day model-ready history has 932 days: 596 training, 149 validation, 187 final test. Candidate RF settings were selected by validation MAE; the saved selected models were refitted on pretest history, then evaluated against May 28–December 31, 2025. Chronological splitting mirrors future prediction after earlier operations and prevents random mixing. The original rolling 14-day pipeline was assessed separately by forecast origin with its history cutoff before the target; development/validation fixed-origin experiments avoid forecasting across split boundaries. Overlapping 14-day target windows are not independent rows.

**b. Data leakage.** RF lag-1/lag-7 and shifted rolling-7 features use past completed days; calendar indicators are known. Opening backlog and planned hours are available only if the prediction is issued after the prior shift and after schedules are published. The original 14-day generator uses observed demand before each forecast origin, but takes `known_promotion_flag` from future synthetic target dates; future promotions and schedules are valid only when prepublished and available at issuance. No reliable timestamped schedule/promotion publication evidence exists. Actual target outcomes, forecast errors, high-demand outcomes, and derived actual capacity are scoring variables, not predictors. The original RF is one-day-ahead and must not be described as validated recursively for 14 days.

**c. Metrics.** MAE expresses typical misses directly in WLU or WLU/hour; RMSE penalizes extreme errors likely to produce staffing shortages; signed bias (actual minus prediction) identifies underforecasting; 80% interval coverage checks risk calibration. Relative improvement is against a stated baseline on the **same** cohort. Comparison of percent improvement from different periods/baselines is invalid.

**d. Random Forest test results — saved GitHub evaluation (`models/week11_evaluation.csv`):**

| KPI | Selected RF final-test MAE | Previous-operating-day naive MAE | Relative MAE reduction | RF RMSE |
|---|---:|---:|---:|---:|
| Workload WLU | 64.7122 | 106.1342 | 39.0% | 85.5691 |
| Productivity WLU/hour | 0.075314 | 0.110886 | 32.1% | 0.094655 |

This is the *saved* GitHub RF evaluation, not an independently retrained execution in this patch. Source report: `docs/PART1_PREDICTIVE_PERFORMANCE_REPORT.md`.

**d. Separate archived 14-day pipeline final-period retrospective:**

| KPI | Horizon | Historical-rule MAE | Seasonal-naive MAE | Relative MAE reduction |
|---|---|---:|---:|---:|
| Incoming workload WLU | Day 1 | 64.61 | 92.78 | 30.4% |
| Incoming workload WLU | Day 14 | 65.36 | 92.41 | 29.3% |
| Productivity WLU/hour | Day 1 | 0.0764 | 0.0987 | 22.6% |
| Productivity WLU/hour | Day 14 | 0.0740 | 0.1054 | 29.8% |

The synthetic forecasts outperform these baselines, but the result is **not** validation against live business data. The random-forest baseline is previous day while the 14-day baseline is seasonal naive, so their improvement percentages are not the same question.

**e. Prediction errors.** Archived one-day workload peak-season MAE is 84.43 WLU versus 58.84 outside peak season; realized top-decile high-demand dates have ~140.24 WLU error. These post-hoc outcome groups are diagnostic only, not known before scheduling. An underforecast of 140 WLU at the assumed 1.65 WLU/hour translates to about 85 required worker-hours; actual shortage depends on available capacity. Archived one-day nominal 80% coverage was only ~47.4%; risk bands should not be read as true probabilities. Productivity errors represent a synthetic processing-capacity parameter, not a measured causal staff-count response.

**Test integrity:** The May–December 2025 outcomes were already inspected in previous work. Do not select further candidates with these data and label it an untouched final test. New model configurations require earlier development/validation or genuinely new holdout observations.

## 2. Improve models and document (a–d)

For the GitHub **Random Forest KPI regressions**, the existing `evaluate_week11.py` tested original Random Forest (140 trees / min leaf 4) against revised (240 trees / min leaf 8), using the same chronological training and validation cohorts. Selected by validation MAE: revised workload 64.3594 versus original 64.9169; revised productivity 0.0731719 versus original 0.0734161. After selection, saved refit final test MAE: revised workload 64.7122 versus original 65.3393; revised productivity 0.0753143 versus original 0.0759325. The gains are **small**, not strong evidence of production improvement. The supplied Week 11 selected bundles remain the selected candidate without further tuning.

A **separate 14-day forecasting experiment** used training/validation data only: replacing a 28-day recent-demand component with 14 days reduced pooled validation workload MAE from 61.0218 to 60.8503 (0.28%); a 56-day rather than 28-day productivity average reduced MAE from 0.072033 to 0.071254 (1.08%). They were provisionally selected **only for the experimental archive**. Neither experiment replaces the deployed original 14-day forecasts in this patch. Calibrated empirical 80% interval coverage improved from 70.3% to 80.4% on validation, but widths increased substantially (day 1: 104.1 → 205.2 WLU). Calibrated intervals and exceedance probabilities are **not** shipped into this dashboard because calibration and downstream probability integration were not verified end-to-end.

**Remaining limitations:** synthetic data calibration; all 939 days use exactly 25 scheduled workers and 200 scheduled hours; future schedule/promotion provenance; high-demand miss risk; interval miscalibration; no external backtest of staffing actions; overlapping forecast windows; mismatch between RF prediction and historical-rule pipeline. The minor difference in `fact_employee_day.csv` relative to the earlier generator archive is floating-point precision in certain rows. Original file is preserved.

## 3. Explanations and what-if changes (a–f)

The revised Streamlit application has three decision-focused sections: **Workforce Planning**, **Staffing Decisions**, and **Model Validation**. The model-validation section displays performance, bounds and limitations; global permutation importance is separate from ordered median-reference, **individual** contributions (not SHAP and not causal). Inputs identify controllable staffing/hour choices vs externally determined demand history. Checks enforce nonnegative counts, overtime up to 80 hours, nonnegative regular hours, capacity-rate >0 and bounded availability; RF what-if flags 1st–99th-percentile extrapolation and disallows impossible worker/hours combinations. Current-versus-proposed staffing comparison shows inputs, available/required hours, capacity gap, backlog, labor cost, and an automatic non-causal summary. The manager-facing staffing page uses deterministic capacity accounting rather than claiming the trained RF model predicts effects of adding workers. A changed day does not automatically replan all 14 days.

## 4. External user testing — **not yet completed**

A genuine outside-group participant is required. `USABILITY_PROTOCOL.md` gives five tasks, a response form, error/misinterpretation log, and an improvement record. No participant, observations, or application changes *based on testing* are claimed in advance. Once the test happens, record the participant's broad role (no confidential details), results, a genuine revision if needed, and retest. Do not fabricate an interview or use group members as the outside tester.

## 5. Deliverables status

| Deliverable | Status |
|---|---|
| Revised app source, verified forecast data, validation reports, integrity tests | Prepared in patch |
| Setup instructions/dependencies | Prepared |
| Week 10 copy and change trace | Existing `week10_snapshot/` plus installer backups |
| Group contributions summary | Prepared from Week 10 submission; verify/update actual roles |
| Structured outside-user test | Protocol ready; **human test outstanding** |
| Seven-minute demonstration video | Script ready; **recording outstanding** |
| GitHub update | **Not pushed**; read-only connector, local installation required |
| Instructor and member access | **Needs human confirmation** |

**Release gate:** Run `python validate_submission.py` and `python -m unittest discover -s tests -v`, open all three tabs locally, complete outside-user test, document resulting changes, record video, then push files to a review branch or `main` following your team's access process.
