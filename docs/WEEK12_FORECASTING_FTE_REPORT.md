# Week 12 — Forecasting Model Comparison and FTE Workforce Planning

**Furniture Warehouse Workforce Analytics** · single synthetic warehouse, 939 operating days (Jan 2 2023 – Dec 31 2025).
All numbers below are generated from `models/forecast_comparison/` by `python evaluate_forecasting.py`; none were typed by hand.

## 1. What was compared

| KPI | Target column | Unit |
|---|---|---|
| Daily Workload | `new_workload_units` | WLU |
| Labor Productivity | `actual_productivity_wlu_per_hour` | WLU per worker-hour (`effective_capacity_wlu = worker_total_hours × productivity`) |

Four methods, for both KPIs and both horizons (next operating day; next 14 operating days):

1. **Weekday Average** — expanding mean of the target's weekday, using days up to the forecast origin only.
2. **Random Forest** — the existing Week 10/11 one-step feature set (reproduced exactly) plus an origin-anchored direct feature set; configuration chosen on validation.
3. **XGBoost** — origin-anchored direct features; six regularised configurations tuned on validation only.
4. **Prophet** — weekly + yearly seasonality + the published holiday calendar; **refitted at every forecast origin** on history up to that origin; three configurations tuned on validation.

## 2. Evaluation design (leakage controls)

* **Forecast-origin rule:** a forecast issued at the end of operating day *t* uses outcomes from days ≤ *t* only. Target-day calendar (weekday, month, peak-season flag, published holidays) is treated as known. Promotions (no timestamped calendar), staffing outcomes, productivity and backlog after the origin are never inputs.
* **14-day forecasts are direct, not recursive:** one model pooled over horizons 1–14 with the horizon as a feature; every history feature is anchored at the origin. The existing one-step features (`lag1`, beginning backlog) are only used at horizon 1, where they are genuinely known; using them at longer horizons raises an error.
* **Chronological split (identical dates to Week 11):** development ≤ 2024-12-04; validation 2024-12-05 – 2025-05-27; final period 2025-05-28 – 2025-12-31. No random shuffling.
* **Tuning:** each configuration is trained on targets observed by the development cut-off and scored on validation origins only. The lowest-validation-MAE configuration is refitted on development + validation targets and scored **once** on the final period.
* **Identical evaluation dates:** next-day = every origin whose next operating day is in the period; 14-day = origins whose complete 14-day window is inside the period (all 14 horizons pooled). The code asserts that all four methods are scored on the same origin/target pairs.
* **Final period status:** these dates were already viewed in Week 11, so final-period results are labelled **retrospective**, not an untouched test.
* **Metrics:** MAE, RMSE, WAPE = Σ|e| / Σ|actual|, bias = mean(actual − forecast) (positive = under-forecast), MAE improvement vs the weekday-average baseline, peak-day MAE (actual workload ≥ 90th percentile of the development period, 418.6 WLU — a post-hoc diagnostic), and a **Diebold–Mariano test** of equal absolute error versus the baseline (Newey–West variance with lag 13 for overlapping 14-day windows).

**Reproduction check:** inside the new framework the existing Week 11 Random Forest models give final-period MAE **64.712 WLU** and **0.07531 WLU/hour** (revised) and 65.339 / 0.07593 (original) — identical to `models/week11_evaluation.csv`.

## 3. Four-model comparison tables

Bold model = lowest MAE in that table.

**Daily Workload (WLU) · Next operating day · Validation (selection)** — 149 forecast dates, 149 forecasts, targets 2024-12-05 to 2025-05-27

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Weekday Average | expanding_same_weekday | 62.68 | 79.26 | 20.09 | +3.14 | Reference | — | 144.82 | 2 |
| Random Forest | enhanced_revised | 64.30 | 79.80 | 20.61 | +1.27 | -2.59 | 0.239 | 144.16 | 3 |
| XGBoost | d2_lr03_l10 | 64.52 | 80.73 | 20.68 | +3.04 | -2.93 | 0.334 | 145.07 | 4 |
| **Prophet** | additive_cps005 | 62.19 | 79.47 | 19.93 | +4.67 | +0.78 | 0.745 | 138.76 | 1 |

**Daily Workload (WLU) · Next operating day · Final period (retrospective)** — 187 forecast dates, 187 forecasts, targets 2025-05-28 to 2025-12-31

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Weekday Average | expanding_same_weekday | 64.44 | 85.95 | 20.35 | +6.78 | Reference | — | 153.80 | 2 |
| Random Forest | enhanced_revised | 64.82 | 85.75 | 20.47 | +2.62 | -0.59 | 0.729 | 149.98 | 3 |
| XGBoost | d2_lr03_l10 | 65.57 | 86.43 | 20.71 | +4.61 | -1.75 | 0.485 | 150.19 | 4 |
| **Prophet** | additive_cps005 | 64.33 | 85.61 | 20.32 | +0.41 | +0.17 | 0.945 | 138.93 | 1 |

**Daily Workload (WLU) · Next 14 operating days · Validation (selection)** — 136 forecast dates, 1904 forecasts, targets 2024-12-05 to 2025-05-27

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Weekday Average | expanding_same_weekday | 60.87 | 76.79 | 19.54 | +2.67 | Reference | — | 141.52 | 2 |
| Random Forest | enhanced_leaf16 | 63.30 | 79.80 | 20.32 | +4.55 | -3.99 | 0.013 | 141.85 | 4 |
| XGBoost | d2_lr03_l10 | 62.53 | 78.56 | 20.07 | +5.67 | -2.74 | 0.045 | 141.68 | 3 |
| **Prophet** | additive_cps005 | 60.59 | 77.12 | 19.45 | +6.59 | +0.46 | 0.771 | 138.83 | 1 |

**Daily Workload (WLU) · Next 14 operating days · Final period (retrospective)** — 174 forecast dates, 2436 forecasts, targets 2025-05-28 to 2025-12-31

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Weekday Average | expanding_same_weekday | 65.27 | 87.05 | 20.51 | +8.58 | Reference | — | 154.75 | 3 |
| **Random Forest** | enhanced_leaf16 | 64.93 | 86.09 | 20.40 | +6.53 | +0.52 | 0.626 | 143.81 | 1 |
| XGBoost | d2_lr03_l10 | 65.73 | 86.42 | 20.65 | +6.03 | -0.70 | 0.600 | 145.80 | 4 |
| Prophet | additive_cps005 | 65.13 | 86.27 | 20.47 | +1.64 | +0.22 | 0.901 | 139.32 | 2 |

**Labor Productivity (WLU/hour) · Next operating day · Validation (selection)** — 149 forecast dates, 149 forecasts, targets 2024-12-05 to 2025-05-27

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Weekday Average | expanding_same_weekday | 0.0712 | 0.0927 | 4.32 | +0.0048 | Reference | — | 0.0725 | 2 |
| **Random Forest** | enhanced_leaf16 | 0.0712 | 0.0930 | 4.32 | +0.0056 | +0.02 | 0.987 | 0.0698 | 1 |
| XGBoost | d2_lr03_l10 | 0.0713 | 0.0933 | 4.33 | +0.0097 | -0.15 | 0.952 | 0.0711 | 3 |
| Prophet | additive_cps005 | 0.0731 | 0.0947 | 4.44 | +0.0002 | -2.74 | 0.147 | 0.0691 | 4 |

**Labor Productivity (WLU/hour) · Next operating day · Final period (retrospective)** — 187 forecast dates, 187 forecasts, targets 2025-05-28 to 2025-12-31

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Weekday Average** | expanding_same_weekday | 0.0740 | 0.0940 | 4.49 | +0.0064 | Reference | — | 0.0712 | 1 |
| Random Forest | enhanced_leaf16 | 0.0746 | 0.0943 | 4.53 | +0.0086 | -0.78 | 0.612 | 0.0707 | 2 |
| XGBoost | d2_lr03_l10 | 0.0757 | 0.0951 | 4.59 | +0.0090 | -2.21 | 0.402 | 0.0709 | 3 |
| Prophet | additive_cps005 | 0.0778 | 0.0973 | 4.72 | -0.0009 | -5.02 | 0.018 | 0.0756 | 4 |

**Labor Productivity (WLU/hour) · Next 14 operating days · Validation (selection)** — 136 forecast dates, 1904 forecasts, targets 2024-12-05 to 2025-05-27

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Weekday Average** | expanding_same_weekday | 0.0716 | 0.0934 | 4.35 | +0.0040 | Reference | — | 0.0730 | 1 |
| Random Forest | enhanced_leaf16 | 0.0763 | 0.0986 | 4.64 | +0.0145 | -6.52 | 0.004 | 0.0725 | 4 |
| XGBoost | d3_lr05_mae | 0.0733 | 0.0952 | 4.46 | +0.0086 | -2.38 | 0.089 | 0.0692 | 2 |
| Prophet | multiplicative_cps005 | 0.0749 | 0.0957 | 4.55 | -0.0004 | -4.51 | 0.012 | 0.0725 | 3 |

**Labor Productivity (WLU/hour) · Next 14 operating days · Final period (retrospective)** — 174 forecast dates, 2436 forecasts, targets 2025-05-28 to 2025-12-31

| Model | Config | MAE | RMSE | WAPE (%) | Bias | Improvement vs Baseline (%) | DM p-value | Peak-day MAE | Rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Weekday Average** | expanding_same_weekday | 0.0736 | 0.0930 | 4.46 | +0.0076 | Reference | — | 0.0730 | 1 |
| Random Forest | enhanced_leaf16 | 0.0764 | 0.0961 | 4.63 | +0.0093 | -3.87 | 0.080 | 0.0772 | 3 |
| XGBoost | d3_lr05_mae | 0.0749 | 0.0941 | 4.54 | +0.0086 | -1.81 | 0.159 | 0.0784 | 2 |
| Prophet | multiplicative_cps005 | 0.0772 | 0.0958 | 4.68 | +0.0018 | -4.86 | 0.004 | 0.0773 | 4 |

## 4. Selected forecasting technique per KPI

Selection rule: lowest **validation** MAE; RMSE, WAPE, bias and peak-day error are supporting evidence.

| KPI · horizon | Selected (validation MAE) | vs baseline (validation) | DM p-value | Final-period rank | Lowest final-period MAE |
|---|---|---:|---:|---:|---|
| Workload · next day | Prophet (62.19 WLU) | +0.78% | 0.745 | 1 of 4 | Prophet |
| Workload · 14 days | Prophet (60.59 WLU) | +0.46% | 0.771 | 2 of 4 | Random Forest |
| Productivity · next day | Random Forest (0.07115 WLU/h) | +0.02% | 0.987 | 2 of 4 | Weekday Average |
| Productivity · 14 days | Weekday Average (0.07163 WLU/h) | reference | — | 1 of 4 | Weekday Average |

**Interpretation.** Prophet is the strongest validated workload method at both horizons, mainly through lower error on peak-demand days (e.g. 138.8 vs 141.5 WLU at 14 days on validation) and lower final-period bias. However, **no trained model is statistically better than the simple weekday-average baseline for either KPI or horizon** (all p > 0.7), and the gaps between methods are about 1% of MAE or less. Some candidates are significantly *worse* than the baseline: Random Forest (p = 0.013) and XGBoost (p = 0.045) for 14-day workload on validation, and Prophet for productivity in the final period. The weekday-average baseline is therefore a credible, transparent fallback, and the original Random Forest models' Week 11 improvement over a *previous-day* naive baseline does not carry over against a weekday baseline (final-period MAE 64.71 vs 64.44 WLU).

For staffing, the 14-day selections are used: **Prophet for workload and Weekday Average for productivity**.

## 5. FTE implementation

Configurable in `src/config.py` and on the Workforce planning (FTE) page:

| Assumption | Default | Source |
|---|---|---|
| Standard shift | 8 h | requested standard |
| Full-time week | 40 h | requested standard; `dim_employee.regular_weekly_hours` |
| Worker roster (maximum scheduled per day) | 30 | `dim_employee` (6 regular + 24 temporary workers) |
| Weekly hour cap | 50 h | `dim_employee.weekly_hour_cap` |
| Max overtime per worker-day | 2 h | (50 − 40) h/week over 5 shifts |
| Minimum scheduled workers | 20 | planning-policy **assumption**, not source data |

Formulas (`src/fte.py`):

* Required Daily FTE = Required Labor Hours / 8; Available Daily FTE = Available Labor Hours / 8; FTE Gap = Required − Available (positive = shortage); Weekly FTE = Weekly Labor Hours / 40.
* Daily FTE is labelled **8-hour worker-shift equivalents**, not contractual headcount. Decimal values are kept for comparison; only "additional whole worker-shift equivalents" is rounded up.
* Available hours = planned regular hours × expected availability (**applied once**) + planned overtime. **Manager hours are never added to productive capacity**; only manager cost enters labor cost. Overtime is paid at 1.5× and is not reduced again by availability.
* Specified example, verified in `tests/test_fte.py`: 215.8 required h and 194 available h → 26.98 required FTE, 24.25 available FTE, 2.73 FTE shortfall, **3** additional whole shifts.

Where FTE appears: **14-day overview** (required / available FTE, FTE gap, extra shifts per day), **Staffing scenarios** (FTE columns for every predefined scenario, the custom scenario and the selected option), and the newly registered **Workforce planning (FTE)** page.

### Integrated chain (Workforce planning page)

Forecast workload → forecast productivity → required labor hours (incl. carried-in backlog) → required FTE → available FTE → FTE gap → lowest-cost feasible response. The forecast source can be switched between the **original 14-day pipeline** and the **validated model selection**. The model source is offered only for forecast runs from 2024-12-04 to 2025-12-15, where every forecast is out-of-sample (validation origins from development-trained models; final-period origins from models refitted on development + validation). Targets, units and horizons match the original run. The validated models use outcomes through the planning date, while the original pipeline uses outcomes through the day before; this difference is stated on the page.

The response adds whole regular shifts first, covers a small remainder with overtime when that is cheaper, never exceeds the roster or the overtime cap, never reduces below the minimum staffing level, and flags any day it cannot cover (the unmet work is carried forward as backlog). Weekly shift and overtime caps are also checked. Workload uncertainty: an optional higher-workload view adds the 80th-percentile under-forecast measured on **validation** forecasts of the selected workload model (for the original pipeline, its upper 80% bound, which is noted as uncalibrated).

## 6. Tests

`python -m unittest discover -s tests -v` → **44 tests, all passing** (14 existing + 30 new):

* `tests/test_forecasting.py`: split dates equal Week 11; perturbing every outcome after an origin leaves all features of earlier origins unchanged (leakage test); weekday average equals an independent computation; existing one-step features are horizon-1 only; training rows never pass the cut-off; Prophet is refitted on history ending at each origin; MAE/RMSE/WAPE/bias hand-calculated; Diebold–Mariano behaviour; all four methods produce finite forecasts for both KPIs and both horizons; every saved metric recomputed from the saved forecasts; identical evaluation dates across methods; selection equals the lowest validation MAE; existing Random Forest reproduction matches Week 11.
* `tests/test_fte.py`: the specified example; surplus, exact multiples and round-up; weekly FTE; availability applied once; manager hours excluded; overtime pay; shortage covered by shifts; small remainder by overtime; roster and overtime limits making a day infeasible (with the resulting backlog); minimum staffing; backlog carry-over; policy validation; consistency with the pipeline's saved hours.
* `tests/test_app_pages.py`: every navigation page renders headlessly; all original pages remain registered; the comparison section works for all 8 KPI × horizon × period combinations; the Workforce planning page works with the model source and the higher-workload view.

The app tests also pass in a clean environment built only from `requirements.txt` (Streamlit 1.56.0, no XGBoost/Prophet), confirming that the deployed app needs no new dependencies. A local `streamlit run app.py` returned HTTP 200 on the health check and pages.

## 7. Limitations

1. Fully synthetic data; results describe internal simulated performance only.
2. The final period was viewed in Week 11; final-period numbers are retrospective, not an untouched test.
3. Validation MAE of tuned methods is slightly optimistic because their configurations were chosen on the same window; the untuned baseline has no such advantage.
4. Overlapping 14-day windows reuse target days; the Diebold–Mariano test uses a Newey–West correction, but forecasts are not independent.
5. Scheduled staffing is constant (25 workers / 200 h), so no model learns staffing effects on productivity.
6. Random Forest and XGBoost are trained once per period, while Prophet is refitted at every origin; all respect the origin rule, but refresh frequency differs.
7. The minimum staffing level (20) is an assumption; the staffing response is a transparent rule, not an optimiser.
8. Saved Week 10 `.joblib` files were pickled with scikit-learn 1.8.0 and load under 1.9.1 with a version warning (pre-existing; unchanged).

## 8. How to reproduce

```bash
pip install -r requirements-forecasting.txt
python evaluate_forecasting.py           # ~1 minute on 8 cores; writes models/forecast_comparison/
python -m unittest discover -s tests -v
streamlit run app.py
```
