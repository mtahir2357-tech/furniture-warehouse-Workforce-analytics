# Week 11 Evaluation Report — draft generated from local execution

**Data source:** Synthetic single-warehouse operating history, 2023–2025. Results below are read from `models/week11_evaluation.csv`, not assumed results.

## Evaluation design

- Chronological train (64%), validation (16%), and final test (20%) by operating day. No random shuffle.
- Candidate configurations were selected using only development validation MAE. Final test was evaluated afterward and should not be reused for further tuning.
- Workload predictors: calendar information and previous actual operating-day demand lags/rolling average.
- Productivity predictors: calendar, starting backlog, planned staffing count/hours, and prior-day productivity history.
- Prediction time assumptions: staff schedules and starting backlog are known before shift. Lagged observations must be from completed days; this does **not** establish valid fourteen-day recursive KPI model forecasts.

## Original versus revised models

| KPI | Configuration | Selected on validation | Validation MAE | Final test MAE | Final test RMSE | Naive final test MAE |
|---|---|---|---:|---:|---:|---:|
| workload | original | No | 64.9169 | 65.3393 | 86.2004 | 106.1342 |
| workload | revised | Yes | 64.3594 | 64.7122 | 85.5691 | 106.1342 |
| productivity | original | No | 0.0734 | 0.0759 | 0.0955 | 0.1109 |
| productivity | revised | Yes | 0.0732 | 0.0753 | 0.0947 | 0.1109 |

**Improvement attempt:** Each KPI compares the original Random Forest (140 trees, minimum leaf 4) with a more-smoothed revision (240 trees, minimum leaf 8). The version selected using development validation is retained. Compare the observed MAE, not the mere fact that a revision was attempted.

## Conditions with higher prediction error

- **workload:** highest observed segment MAE among groups with at least five test days was 86.7704 in month=11 (n=25). Compare sample size and mean target before interpreting this as systematic failure.
- **productivity:** highest observed segment MAE among groups with at least five test days was 0.0892 in weekday=5 (n=31). Compare sample size and mean target before interpreting this as systematic failure.

These are descriptive errors on synthetic data, not established industry effects. Additional calibration and walk-forward checks would be needed for operational use.

## Explanations and what-if

- Show overall permutation feature importance and order-dependent individual reference-substitution contributions separately.
- What-if settings constrain workload history changes and couple planned staffing count with scheduled hours.
- Baseline and revised predictions, input changes and differences appear side by side.
- These are non-causal statistical scenario comparisons. Staffing-day capacity, backlog and cost use separate deterministic planning formulas.

## External user test

**PARTICIPANT / CONTEXT: [Complete after actual test]**

**Tasks:** baseline interpretation; predictor explanations; two feasible what-if comparisons; management decision; missing information.

**Observed feedback and problems: [Not yet supplied]**

**Application change made because of test: [Not yet supplied]**

## Limitations and future work

- The dataset is fully synthetic; neither model has established real-warehouse accuracy.
- Week 11 KPI model holdout is a one-step-ahead retrospective evaluation. The saved fourteen-day historical forecast is separate.
- Productivity prediction needs pre-shift backlog and planned staffing inputs.
- Forecast-interval coverage, real shift feasibility, and scenario assumptions require additional calibration.
- Backlog is a carried-forward accounting projection, not a separately trained predictive KPI.

## Group member contributions

**Muhammad Tahir:** [Confirm tasks actually completed]

**Bishal Prajapati:** [Confirm tasks actually completed]
