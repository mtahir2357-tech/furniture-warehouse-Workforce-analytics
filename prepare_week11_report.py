"""Generate a factual evaluation draft from real Week 11 evaluation artifacts.
External usability-test details must be completed manually using actual observations.
"""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent

def generate():
    evaluation=ROOT/'models'/'week11_evaluation.csv'
    segments=ROOT/'models'/'week11_segment_errors.csv'
    if not evaluation.exists() or not segments.exists():
        raise FileNotFoundError('Run python evaluate_week11.py with your complete repository first.')
    e=pd.read_csv(evaluation)
    s=pd.read_csv(segments)
    rows=[]
    for _,r in e.iterrows():
        rows.append(f"| {r['KPI']} | {r['Configuration']} | {'Yes' if r['Chosen_on_validation'] else 'No'} | "
                    f"{r['Development_validation_MAE']:.4f} | {r['Final_test_MAE']:.4f} | "
                    f"{r['Final_test_RMSE']:.4f} | {r['Naive_final_test_MAE']:.4f} |")
    segments=[]
    for k in e['KPI'].unique():
        selected=e[(e['KPI']==k)&(e['Chosen_on_validation']==True)].iloc[0]['Configuration']
        f=s[(s['KPI']==k)&(s['Configuration']==selected)&(s['N']>=5)]
        if len(f):
            worst=f.sort_values('MAE',ascending=False).iloc[0]
            segments.append(f"- **{k}:** highest observed segment MAE among groups with at least five test days was "
                           f"{worst['MAE']:.4f} in {worst['Group']}={worst['Segment']} (n={int(worst['N'])}). "
                           f"Compare sample size and mean target before interpreting this as systematic failure.")
    report=f'''# Week 11 Evaluation Report — draft generated from local execution

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
{chr(10).join(rows)}

**Improvement attempt:** Each KPI compares the original Random Forest (140 trees, minimum leaf 4) with a more-smoothed revision (240 trees, minimum leaf 8). The version selected using development validation is retained. Compare the observed MAE, not the mere fact that a revision was attempted.

## Conditions with higher prediction error

{chr(10).join(segments) if segments else 'No segment with at least five final-test cases was present.'}

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
'''
    dest=ROOT/'WEEK11_EVALUATION_REPORT_DRAFT.md'
    dest.write_text(report)
    print('Wrote',dest)

if __name__=='__main__':generate()
