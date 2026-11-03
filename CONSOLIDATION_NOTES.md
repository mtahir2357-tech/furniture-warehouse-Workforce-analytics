# Consolidation record — November 3, 2026

## Sources

1. `furniture-warehouse-Workforce-analytics.zip` — full working repository. Authoritative source for **all 12 data CSVs** and saved model files.
2. `MRP_Validation_Submission_Update(1).zip` — revised three-section `app.py`, validation scripts, reports, usability protocol and demonstration outline.

## Merge choices

- Preserved **all 12 original CSVs** from the uploaded full GitHub package, and **all** trained model artifacts, reports, original modules and tests.
- Integrated revised `app.py`, `validate_submission.py`, all available patch `docs/`, `SUBMISSION_REPORT.md`, `USABILITY_PROTOCOL.md`, `DEMO_SCRIPT.md`, `CONTRIBUTIONS.md`, and `tests/test_submission.py`.
- Saved pre-merge `app.py` and `requirements.txt` in `week10_snapshot/before_validation_patch/`, retaining the entire existing Week 10 snapshot.
- Updated main README and dependencies for the consolidated full project. Pinned scikit-learn 1.9.1 to match the saved models.
- Did **not** include the patch installer: this ZIP is already merged and standalone. No repository upload or push was performed.

## Important conflicting data file

Both packages contain `data/fact_workload_forecast.csv` with **12,166 rows and identical forecast IDs, workload point forecasts and expected productivity values**. However, their **80% lower and upper bounds, forecast standard deviations and probability-of-capacity-exceedance columns differ on more than 11,000 rows**, with 1,536 interval-coverage flags changed. Because the revised interval figures have not been independently verified end-to-end with staffing risk logic, the full GitHub original table is retained. Neither version's interval probabilities should be presented as calibrated.

## Automated checks run on the complete merged project

- 939 unique operating days; 12,166 forecast rows across 869 runs and 14 operating-day horizons; 72,996 staffing scenario records.
- Forecast IDs unique, all scenario forecast IDs link, forecast actuals match daily outcomes and backlog carries day-to-day with 0 difference.
- All **14/14** unit and integration checks passed (models/scenarios/planning/source integrity).
- Loaded selected workload/productivity model bundles and generated numeric predictions. The local Python environment had scikit-learn 1.8.0 and showed a model-version warning; the project's requirements now pin 1.9.1. This check is **not** a clean proof of version-matched inference.
- Python code was parsed/compiled; a live Streamlit browser exercise was **not** completed in this environment.

## Open requirements

- Conduct real external usability test and document actual feedback and resulting change.
- Inspect the running application on the target computer, with the pinned dependencies, and verify two staffing scenarios plus the model-explanation view.
- Review the difference between two forecasting systems; do not mix RF test performance with archived 14-day forecast performance.
- Note that development and final test outcomes have already been inspected in prior iterations; do not perform further tuning on the inspected test window and label it untouched.
- Prepare and record final 7-minute video, verify group contributions, push approved project and confirm instructor/group access.

**Submission readiness: consolidated and automatically checked, but not yet ready to represent as externally user-tested or fully live-validated.**
