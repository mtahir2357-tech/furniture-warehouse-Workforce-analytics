# Part 2 — Improve the Models and Document the Results

**Furniture Warehouse Workforce Planning Tool**  
**Scope:** Original Week 7–8 fixed-origin 14-operating-day workload and productivity forecasting pipeline. The GitHub Random Forest one-step-ahead models are a **separate pipeline**, and are not claimed as part of these retraining experiments.  
**Dataset:** Single synthetic warehouse, 939 operating days (2023–2025). No real-world performance is established.

## Evaluation design: protecting the final test

- We reproduced the archived original forecast formula and the 28-day productivity estimate using historical values strictly before the forecast origin. Source: `MRP_Weeks7_8_Submission (1).zip` and `step4_generate_forecasts_scenarios.py`.
- We kept the previously established chronological 64% / 16% / 20% operating-day separation. For this **14-day fixed-origin** experiment, the last admissible development and validation forecast origin is **14 operating days before the next partition**. That ensures none of the outcomes used for training/calibration or validation falls in a later partition.
- Calibration/development: **533 origins, 7,462 horizon-specific forecasts**, March 8, 2023–November 18, 2024. Validation: **135 origins, 1,890 horizon-specific forecasts**, December 5, 2024–May 10, 2025. Fourteen future operating-day outcomes for each validation origin end no later than May 27, 2025.
- **Protected final test begins May 28, 2025. No outcomes in this period were used in this Part 2 experiment.** Earlier Part 1 inspection of final-test performance means that period cannot be called genuinely untouched in a future development cycle.
- The **single predefined selection rule** was minimum *validation MAE pooled over 14 horizons* for each KPI. Validation results are diagnostic, not a new final test. Overlapping forecast origins reuse actual target dates and should not be treated as independent observations.

## a. Improvement opportunities and changes implemented

**Workload — incoming weighted workload units (WLU).** The original rule weighs the previous 8 same-weekday readings (60%) and the previous 28 operating-day mean (40%), then applies a historical seasonality ratio and assumed known event multipliers. We evaluated four variations: removing the unverified future-promotion signal, 80% same-weekday weight, 12 same-weekday observations, and replacing the 28-day recent mean with a **14-day recent mean**. Rationale: respond more quickly to recent demand without changing the overall interpretable method. All historical inputs end *before* the forecast origin.

**Productivity — expected synthetic processing-capacity rate (WLU/hour), not observed completed WLU divided by paid hours.** The original rule is the preceding **28-operating-day mean**. We evaluated the 14-day mean, 56-day mean, 28-day median and a 14-day exponentially weighted mean. Rationale: reduce random fluctuations in the synthetic capacity rate; a longer smoothing window may offer more stable estimates.

**Workload uncertainty improvement.** Original symmetric intervals were constructed from a rule-of-thumb forecast percentage with an increasing width by horizon. We estimated the **80th percentile of absolute historical forecast errors for each horizon using development/calibration origins only**, then calculated `max(0, forecast − q_h)` and `forecast + q_h`. The horizon-specific error widths and their validation coverage are reported separately. This is a descriptive empirical residual calibration, *not* a distribution-free guarantee because forecast-origin errors overlap and demand can shift.

## b–c. Consistent original versus revised comparison (validation only)

| KPI | Version | All horizons MAE | All horizons RMSE | Day-1 MAE | Day-14 MAE |
|---|---|---:|---:|---:|---:|
| Incoming workload (WLU) | Original: 8 same-weekday + 28-day recent mean | 61.0218 | 77.0304 | **63.2325** | **62.7717** |
| Incoming workload (WLU) | Revised: 8 same-weekday + **14-day** recent mean | **60.8503** | **76.7807** | 63.2372 | 62.9168 |
| Productivity capacity rate (WLU/hour) | Original: 28-day mean | 0.072033 | 0.093930 | 0.071036 | 0.073996 |
| Productivity capacity rate (WLU/hour) | Revised: **56-day** mean | **0.071254** | **0.093109** | **0.070464** | **0.073246** |

**Selection and interpretation:** Under the predetermined *pooled* validation MAE criterion, the revised workload and productivity versions are provisionally retained for the prototype. The workload MAE reduction is only **0.28%**, and the productivity reduction only **1.08%**. The revised workload version is **slightly worse at day 1 and day 14**, despite its small pooled advantage. Thus, these are **not demonstrated material point-forecast improvements**. Do not claim statistically significant gains or operational savings. The original simpler versions remain defensible alternatives if day-1/day-14 performance, robustness or simplicity takes priority.

Other candidate outcomes and segment-level results are available in `validation_candidate_comparison.csv` and `validation_error_segments.csv`. The no-promotion version had an overall validation workload MAE of **62.27 WLU**; this is useful as a leakage-safe fallback when there is no documented promotion calendar, but it sacrifices point accuracy on this simulated validation period.

### Forecast uncertainty: more useful improvement

| Measure, validation period | Original nominal 80% intervals | Revised train-error-calibrated intervals |
|---|---:|---:|
| Coverage over all horizons | **70.3%** | **80.4%** |
| Day-1 coverage | **46.7%** | **78.5%** |
| Day-14 coverage | **85.2%** | **80.0%** |
| Average day-1 interval width | **104.1 WLU** | **205.2 WLU** |

The calibrated intervals better match the intended *marginal* 80% validation coverage, but the improved coverage at day 1 comes with **roughly double the interval width**. They should be presented as more conservative planning ranges—not more accurate point estimates or guaranteed risk probabilities. Do not copy them into the active dashboard without verifying that downstream capacity-exceedance calculations use an appropriate distribution or empirical tail method rather than treating these intervals as normal-theory standard deviations.

### Error cases

- At the one-day horizon, realized high-demand dates (top decile threshold based on the development period; classification is **post hoc**) still have workload MAE roughly **136.81 WLU** under the revised model, versus **63.24 WLU** overall. High-demand underprediction remains an important staffing risk. The post-hoc group is a diagnostic category, **not** a feature available before the shift.
- Both original and revised workload models have comparatively low average bias on validation; small global bias can conceal large positive errors on individual busy days.
- Productivity 14-day peak-month error was **0.09561 WLU/hour** in the revised version, but only **9 relevant validation-origin observations** contributed, so this should not be generalized.

## d. Remaining limitations and uncertainty

1. **Fully synthetic data:** The generators explicitly impose workload seasonality, workforce mix, disruption rates, productivity and scheduling assumptions. Evaluation establishes only internal simulated performance; validation on real warehouse data is still needed.
2. **No staffing variation:** `scheduled_worker_count` is **25 on all 939 days**, and `scheduled_worker_hours` is **200 throughout**. These experiments do not establish productivity changes from hiring or removing workers. The app's staffing scenarios must remain formula-based demonstrations, not causal predictions.
3. **Promotion/schedule availability:** The original forecasting code reads target-day promotion flags from the synthetic outcome table and assumes they are known by forecast time. Neither a timestamped published promotion calendar nor a schedule publication history has been verified. **If unverified, do not use the promotion input operationally.** The chosen workload revision retains it and is only conditionally deployment-eligible.
4. **Uncertainty:** Calibration was estimated on overlapping historical origins, and the distribution may change. The revised empirical intervals have not been independently tested on future, unseen real data. The final-test period has already been viewed in the Part 1 analysis, so future evaluation must distinguish retrospective reporting from untouched prospective testing.
5. **Decision-level validation:** Smaller KPI MAE does not automatically demonstrate lower labor cost, less overtime or backlog. Backlog and staffing outcomes remain deterministic simulations downstream of workload/productivity, and a complete chronological end-to-end staffing-decision backtest is still needed.
6. **Scope:** These results describe only the original 14-day forecasting pipeline, **not** the separately saved GitHub Random Forest models. No GitHub deployment, CSV replacement, or model binary overwrite has occurred.

## Conclusion and retention decision

**Provisionally retain** the 14-day recent workload mean and 56-day productivity mean within a *development-only experimental implementation*, based on the declared pooled validation MAE criterion. **Retain the original production/source pipeline unchanged until review.** The stronger documented improvement is train-residual calibration of workload prediction intervals (70.3% → 80.4% validation coverage), but intervals become wider and must not be represented as certainty. Improvements remain small and constrained by synthetic-data and decision-time availability assumptions.

**Reproducibility:** Run `python evaluate_part2.py` in a directory containing the provided original Week 7–8 archive extracted into `MRP_Weeks7_8_Submission/`. The script creates candidate tables, calibration comparisons, validation segments and a protected-test protocol manifest. It neither trains with nor evaluates May 28–December 31, 2025 outcomes.
