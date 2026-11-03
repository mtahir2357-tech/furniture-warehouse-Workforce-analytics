# Part 1 — Evaluation of Predictive Performance

**Project:** Furniture Warehouse Workforce Planning | **Source:** Original Week 7–8 generator ZIP and current GitHub saved Random Forest evaluation (reported separately) | **Data:** Synthetic, one warehouse, 2023–2025.

## Decision problem and KPI definitions

The warehouse manager must (1) anticipate incoming workload and peak demand before scheduling labor and (2) estimate processing capacity and potential backlog. **Daily incoming workload** is measured in weighted workload units (WLU). **Productivity** is the model's simulated processing *capacity rate* (WLU per worker-hour), not necessarily realized throughput divided by paid hours. **Ending backlog** is an accounting projection: `max(0, beginning backlog + new workload − processed workload)`; it is **not a separately trained predictive model**. Labor-hour requirements derive from predicted workload and productivity and should include carry-in backlog.

## a. Data division and decision timing

There are **939 daily operating records**. For the separately saved Random Forest regressions, the first 7 operating days establish lag features, leaving **932 model-ready days**: **596 train**, **149 validation**, **187 final test**. The last period is **May 28–December 31, 2025**. Time ordering (rather than random splitting) represents forecasting genuinely future warehouse days; candidate versions were selected on validation MAE before their reported final-test results.

The **original 14-day forecasting pipeline** is a *different* model. It issues rolling forecasts for 14 future operating days, using historical observations through the **prior operating day**, even though the forecast file's creation timestamp is **6:00 p.m. on the origin date**. The historical final-test-origin evaluation contains **173 distinct forecast origins** (May 28–December 2025; latest eligible origins stop early enough to have all 14 targets), or **2,422 horizon-specific forecasts**. These 2,422 rows overlap on target dates and should **not** be treated as 2,422 independent outcomes. This is a retrospective evaluation of the **existing, unmodified forecasting rule**, not a new model-selection experiment.

## b. Leakage check

- **Workload, original 14-day pipeline:** `step4_generate_forecasts_scenarios.py` uses `history = daily.iloc[:origin_idx]`. Thus workload lags, same-weekday history and estimated seasonality precede the forecast's date; no future actual workload enters its point-forecast calculation. Forecast creation time is 18:00 and the recorded cutoff is the prior operating date (conservative, if somewhat stale). The target's month, weekday and holiday are known in advance.
- **Conditional caveat:** `known_promotion_flag` is read from the *future target day's synthetic record*. The data generator creates promotions with a random flag; it does not prove that promotion dates were published by the forecast's issue time. Treat this feature as **valid only when there is a prepublished promotion calendar**. Planned future staffing hours are derived from pre-generated `fact_employee_day` schedules; these are also valid only if schedules were actually finalized and visible at issue time. When this cannot be demonstrated, rerun a **development-only sensitivity test** without the unverified feature or schedule assumption before further use.
- **Productivity, original planning estimate:** Uses the mean of the **28 preceding completed operating days**, not future realized productivity. No future actual productivity enters its computation. The forecast file also contains target-day actuals and error columns for *retrospective scoring only*; those must not be included in prediction inputs.
- **Random Forest KPI models:** Features use shifted workload/productivity lags and a shifted 7-day rolling average. Pre-shift opening backlog, worker count and planned hours are available only if the decision timestamp and schedule publication are enforced. Daily lag predictors support rolling **one-step-ahead** evaluation; the RF results **do not validate a fixed-origin 14-day forecast**.

## c. Metrics and relevance

**MAE** is the primary error metric: it measures average missed WLU or WLU/hour in terms the manager can interpret. **RMSE** highlights large misses that can cause labor shortages. **Bias (actual − predicted)** indicates systematic underprediction (positive values), important for peak-demand risk. **WAPE** summarizes absolute error relative to total volume. **Coverage** checks whether nominal **80% workload intervals** actually contain about 80% of actual outcomes; this is essential for risk-aware staffing. All metrics below are historical synthetic-data metrics, not industry-validated accuracy.

## d. Comparison with simple baselines

For the archived 14-day forecasts, each comparator uses only values through the **same previous-operating-day training cutoff as the original model**. The primary seasonal-naive baseline uses the last observed day with the *target weekday*; the secondary naive baseline carries forward the last observed cutoff-day value. **No model was tuned or selected using these final-test results.**

### Archived rolling forecasts (fully reproduced from original generator)

| KPI | Horizon | Model MAE | Seasonal-naive MAE | Model RMSE | Model bias | MAE reduction vs seasonal naive |
|---|---|---:|---:|---:|---:|---:|
| Incoming workload (WLU) | 1 day | 64.61 | 92.78 | 84.66 | +3.08 | 30.4% |
| Incoming workload (WLU) | 14 days | 65.36 | 92.41 | 86.17 | +0.07 | 29.3% |
| Capacity-rate productivity (WLU/hour) | 1 day | 0.0764 | 0.0987 | 0.0966 | −0.0010 | 22.6% |
| Capacity-rate productivity (WLU/hour) | 14 days | 0.0740 | 0.1054 | 0.0918 | −0.0001 | 29.8% |

The original workload method is a **60% mean of the most recent 8 same-weekday observations + 40% mean of the most recent 28 operating days**, followed by estimated historical seasonal adjustments and assumed known holiday/promotion factors. Original productivity estimation is the **recent 28-day mean**, not Random Forest. These are meaningful improvements over a simple seasonal-naive historical benchmark **on the simulated data**, but do not prove external accuracy. A fixed forecast issued for 14 future operating days is a different operational task from tomorrow-only updating.

### Separate saved Random Forest one-step-ahead results (reported from GitHub evaluation, not independently retrained in this package)

| KPI | Selected RF final-test MAE | Previous-day baseline MAE | Reduction | Final-test RMSE |
|---|---:|---:|---:|---:|
| Workload (WLU) | 64.7122 | 106.1342 | 39.0% | 85.5691 |
| Productivity (WLU/hour) | 0.075314 | 0.110886 | 32.1% | 0.094655 |

The Random Forest baseline is a **previous-day** comparator, while the preceding rolling-forecast table uses **seasonal naive**; these are separate experiments and their reductions are **not directly comparable**. No trained Random Forest backlog predictor has been demonstrated. Backlog estimates inherit errors from workload, productivity, and actual worker availability, so do not report a backlog-model accuracy score without a dedicated historical end-to-end backtest.

## e. Error analysis and manager implications

| Workload-error segment | 1-day MAE | 14-day MAE | Implication |
|---|---:|---:|---|
| Peak season | 84.43 WLU (39 origins) | 74.93 WLU (52 origins) | Increased risk of labor shortfall during busy periods |
| Nonpeak | 58.84 WLU (134 origins) | 61.24 WLU (121 origins) | Generally lower error |
| Top 10% of *realized* demand (post-hoc only) | 140.24 WLU (18 origins) | 140.37 WLU (18 origins) | Extreme days were underforecast in this diagnostic group; actual high demand is not known in advance |

At a planning assumption of **1.65 WLU/hour**, a missed 140 WLU corresponds to approximately **85 additional worker-hours**; this is a sensitivity calculation, **not a measured shortage**, since actual available labor and backlog also matter. The model's apparent overall low bias conceals larger positive error during peak days.

The archived **80% prediction intervals are not calibrated across horizons**: on the evaluated origin cohort, observed coverage is **47.4% at horizon 1**, **87.3% at horizon 14**, and **70.0% across all horizons**. Original interval widths are rule-of-thumb values rather than empirically calibrated error quantiles. Do not use their nominal 80% probability as a trusted risk guarantee until calibration is performed on development data. The final period has already been viewed and **must not be reused for tuning**.

For productivity, the 1-day MAE is **0.0764 WLU/hour** and 14-day MAE **0.0740 WLU/hour**. Interpret these as errors in the synthetic *capacity-rate parameter*. They do not validate the impact of adding workers. In fact, all 939 daily records have **exactly 25 scheduled workers and 200 scheduled worker-hours**, so the synthetic data cannot identify productivity changes caused by staffing-level variation. Random Forest what-if effects involving staffing should be labeled statistical scenarios, **not causal effects**.

## Conclusion and explicit limitations

**Part 1 (a–e) is documented and calculated for the two predictive KPI quantities** (workload and productivity), with the derived-backlog distinction stated explicitly. The original forecasting function and its 28-day productivity assumption were independently reproduced for **all 12,166** archived rows: maximum disagreement after rounding **zero**. The forecast file can be restored exactly from the original Week 7–8 archive. Compared with an appropriately cutoff-aligned baseline, the archived workload forecasts have materially smaller errors on this synthetic history. Nonetheless, uncertainty intervals, future promotion/calendar availability, unchanging worker schedule, and real-world external calibration remain important limitations.

**Test-integrity rule:** The May–December 2025 historical final-test outcomes have already been inspected. Do not tune or choose a new candidate by looking at these errors and then claim this is an untouched final test. Any future model/interval improvements should be selected using earlier training and validation data only, and any genuinely independent final test must use new untouched future data or be clearly described as a fresh pre-registered evaluation.

**Source files:** Original `MRP_Weeks7_8_Submission (1).zip`, generator steps 1–5; current GitHub's `evaluate_week11.py`, `models/week11_evaluation.csv` (read-only review). Reproduction script and independent numerical outputs accompany this report.
