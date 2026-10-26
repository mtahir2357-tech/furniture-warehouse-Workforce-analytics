# Predictive Modeling — Technical Documentation

**Decision-maker:** Manager, single furniture fulfillment warehouse. All operational records are **synthetic**, so these are prototype findings, not validated commercial performance.

## Two selected KPIs

1. **Daily incoming workload (WLU).** `new_workload_units`, the amount of new inbound fulfillment work weighted for piece-handling complexity. A forward-looking workload estimate can inform staffing/capacity decisions, fulfillment reliability and overtime cost planning.
2. **Worker productivity (WLU/worker-hour).** `actual_productivity_wlu_per_hour`, historical units of handling effort completed per worker labor hour. Forecasting productivity supports staffing-hour estimates, resource usage and labor-cost control.

## Predictor specifications

- **Workload:** operating-day weekday, month, peak season flag, holiday flag; new workload 1 and 7 prior operating days ago, and mean workload across prior seven operating days. Calendar and historical demand encode weekly patterns, seasonality, and recent demand momentum.
- **Productivity:** weekday, month, peak season; starting backlog, scheduled worker count, scheduled worker hours, productivity one and seven operating days ago, and mean productivity across seven previous operating days. Workforce plans, opening backlog, seasonal patterns and recent actual production are relevant predictive signals. Beginning backlog and staffing plans must be known **before** the shift when applying forecasts; otherwise these are retrospective scenarios only.

All moving aggregates shift before rolling; *no same-day target measurements* enter features. All features used in models are explicitly shown in `train_models.py`.

## Algorithm, validation and model assessment

Both use scikit-learn **RandomForestRegressor**, 140 trees, 4 minimum observations per leaf. This reasonably captures nonlinear effects with limited tuning and provides flexible nonlinear baseline prediction. Rows are strictly sorted by operating date, first 80% for training, last 20% held out. No random split and no training on the holdout.

| KPI | Holdout MAE | Holdout RMSE | Previous-day naive MAE | Train/test operating days |
|---|---:|---:|---:|---:|
| Workload WLU | 65.3214 | 86.1887 | 106.1342 | 745 / 187 |
| Productivity WLU/hour | 0.07593 | 0.09546 | 0.11089 | 745 / 187 |

Training end: 2025-05-27; testing period: 2025-05-28 to 2025-12-31. The previous-day benchmark is computed on the same holdout days. The training script writes model artifacts and evaluation JSON reproducibly. A single chronological holdout is only an initial validation; production use would require walk-forward revalidation and real data.

## Application integration

- Existing original dashboard sections are retained.
- New **Predictive Modeling → Model insights & scenarios** page is `views/predictive_modeling.py`.
- Per KPI: definitions, historical prediction baseline, interactive model-feature scenario inputs, updated KPI forecast, change, generated manager summary.
- **Overall importance:** held-out permutation importance (increase in MAE) with a global bar chart.
- **Individual contributions:** exact additive, **order-dependent sequential reference substitutions**, beginning at training feature medians. This is an accepted non-SHAP model-based attribution method. Values show model changes in KPI units, but *depend on feature ordering*, and are **not** causal effects or independent marginal effects. Distinct from global importance.
- Models saved in `models/*.joblib`; `train_models.py` regenerates them.

## Important limitations

1. All data is synthetic and not independently calibrated against warehouse history.
2. These what-if inputs simulate changed **model predictors**, and may create combinations not seen during training; they do not ensure feasibility, change real demand, or establish causation.
3. Some inputs (prior observed demand/productivity) are contextual assumptions and not operational controls. Staffing plan values can be varied in the productivity model but are still observational associations.
4. Scenarios cannot be considered guaranteed labor-cost savings or operational outcomes. Existing staffing scenario planning remains a separate formula-based layer.
5. The productivity model assumes starting backlog and published staffing schedule are available when making a pre-shift prediction. For a multi-day forecast, these should be forecast/proposed in advance rather than read from future actuals.
6. High predictor collinearity can distort permutation and sequential attribution; model predictions can be inaccurate on unusual dates or out-of-distribution values.

## Feature and implementation reference

| Capability | Location |
|---|---|
| KPI definition and manager relevance | This report; Predictive Modeling page |
| Predictor identification and rationale | This report; `train_models.py` |
| Build and save trained predictive models | `train_models.py`; `models/` |
| Algorithm rationale | This report; Predictive Modeling page |
| Global predictor importance and local contributions | Predictive Modeling page, two separate charts |
| Contribution direction, magnitude, practical meaning, noncausal interpretation | Predictive Modeling page and local contribution text |
| What-if inputs and baseline/updated comparison | Predictive Modeling page |
| Automatic summary for each scenario | Predictive Modeling page |

## Run

On macOS, extract the ZIP, open Terminal in the folder and run `bash run_mac.sh`. Alternatively create a venv, run `pip install -r requirements.txt` and `streamlit run app.py`. To retrain, run `python train_models.py`.
