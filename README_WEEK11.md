# Week 11 — Local application update (review before any GitHub push)

This is a **tested overlay**, not a replacement for the complete GitHub repository. The repository's CSVs, models, and core modules must remain in place. **Nothing has been committed or pushed to GitHub.**

## What is included

- **Workforce Planning:** planned hours, new demand, and carry-forward backlog over 14 forecast operating days.
- **Staffing Decisions:** add/remove workers or add overtime and compare projected workload, capacity gap, ending backlog and labor cost.
- **Model Validation:** original saved two-model evaluation, separate Week 11 model comparison and segment errors (once evaluated), local/global explanations, and constrained KPI-model what-if inputs.
- `evaluate_week11.py`: compares original and revised Random Forest settings with chronological train/validation/test. **Selects on validation only**; writes comparisons and two selected-model files while preserving the original Week 10 binaries.
- `verify_week11.py`: validates original data/model integration on the real repository when executed there.
- `prepare_week11_report.py`: drafts an evaluation report using **actual generated model results** and leaves real-user-testing evidence blank.
- `tests/`: 11 tests including a synthetic miniature end-to-end model evaluation.
- `USABILITY_TEST_TEMPLATE.md`: a real outsider test still must be completed.

## Install into your local GitHub checkout

1. Download or clone your existing repository on your computer (it must already contain `data/` and `models/`).
2. Extract this ZIP, open Terminal inside the extracted `mrp_week11_patch` directory.
3. Run `python install_local.py /absolute/path/to/your/repository-folder`. The script verifies required existing files, backs up the Week 10 application/UI into `week10_snapshot/`, and copies the overlay to your **local** checkout. No GitHub action is performed.
4. From the repository folder run:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python verify_week11.py
python evaluate_week11.py
python prepare_week11_report.py
streamlit run app.py
```

5. Open all three pages. Confirm actual figures and historical reference dates, and compare two plausible scenarios. Review and approve the changes **before** updating GitHub.

If `python` points to an old interpreter, create a Python 3.11+ virtual environment first (see original README).

## Important: what has and has not been validated

- **Passed here:** all 11 Python tests on standalone formulas and a miniature synthetic test frame, plus Python syntax compilation.
- **Not independently run here:** actual GitHub CSV rows, the repository model binaries, or a live Streamlit UI (the container has no copy of the original CSV/model files and no Streamlit package).
- **No actual Week 11 model performance is claimed** until `evaluate_week11.py` is run inside your complete local repository. The model choice may be original if the attempted revision performs worse on validation.
- Your original 14-day forecast CSV and the two Random Forest regressions are **different pipelines**, and this release intentionally labels them separately rather than claiming that model scenario changes feed the precomputed forecast.
- **Backlog assumption:** unprocessed prior workload carries into the next operating day. Requires that the forecast was generated *after* the completed run-date shift. Validate decision timing before real-world application.
- Formula-based staffing estimates are not an optimized labor schedule and do not prove causal model effects.
- Synthetic data cannot demonstrate accuracy on real warehouse operations.

## Remaining submission requirements

- Run and check the real-data model comparison and segment errors.
- Complete a documented usability test with at least one real external participant and make an evidence-based improvement if needed.
- Write the concise evaluation report and film a seven-minute demonstration using actual results.
- Verify instructor/group access and preserve the Week 10 snapshot (preferably a GitHub tag/branch when you eventually approve an update).
