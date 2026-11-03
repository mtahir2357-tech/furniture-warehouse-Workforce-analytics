# Furniture Fulfillment Workforce Planning Tool

Streamlit decision-support dashboard for furniture fulfillment workload forecasting, labor productivity modeling, and staffing scenarios. It reads the 12 synthetic CSV tables in `data/`.

## Run on a Mac

**Quick way.** Open Terminal, go to this folder, and run the launcher:

    cd ~/Downloads/Furniture_Workforce_Planning
    bash run_mac.sh

The first run creates a local Python environment and installs dependencies. Your browser then opens at http://localhost:8501.
Press Control + C in Terminal to stop.

**Manual way.**

    cd ~/Downloads/Furniture_Workforce_Planning
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    streamlit run app.py

If Terminal asks for an email address the first time, just press Return.

Next time: `cd` to the folder, `source .venv/bin/activate`, then `streamlit run app.py`.

Requires Python 3.11 or newer (`python3 --version`). Install from https://www.python.org/downloads/ if needed.

## Pages

| Section | Page | Decision supported |
| --- | --- | --- |
| Quick decision | Decision board (opens first) | Approve a recommended action per day in one click |
| Detailed analysis | 14-day overview | Which upcoming days need staffing review? |
| | Selected day detail | Why is this day short or over-staffed? |
| | Staffing scenarios | Which response balances capacity, risk, and cost? |
| | Decision & outcome | What was decided, and how did results compare? |
| Predictive Modeling | Model insights & scenarios | Forecast workload and productivity; inspect model explanations and compare what-if predictions |
| Performance | Forecast accuracy | MAE, RMSE, WAPE, bias, 80% coverage by horizon |
| | Operations history | Workload, labor, productivity, backlog, cost trends |

Use the sidebar to pick the **planning date** (snaps to the latest forecast run on or before it) and the
**balanced band** (default ±8 hours).

## Logic

- Required labor hours = forecast workload ÷ expected productivity
- Capacity gap = available labor hours − required labor hours (negative = shortage).
  The CSVs store `labor_gap_hours` with the opposite sign; the app converts it.
- Status: Shortage if gap < −band, Surplus if gap > +band, otherwise Balanced.
- Capacity-exceedance risk: Low < 25%, Moderate < 50%, High ≥ 50%.
- Backlog risk from projected utilization: Low < 90%, Moderate ≤ 105%, High > 105%.
- The custom scenario calculator reproduces `fact_staffing_scenario` exactly
  (availability ratio, 1.5× overtime, unchanged manager cost).

- Recommendation (Decision board): shortage → cheapest of +16 regular / +20 overtime hours that removes it;
  surplus → cut 16 regular hours unless that creates a shortage; otherwise keep the plan.

## Color code

| Status | Color | Icon | Meaning |
| --- | --- | --- | --- |
| Shortage | Coral red #D94F4F | ▼ | Available hours below need by more than the band |
| Balanced | Teal green #1F9D7A | ● | Within the balanced band |
| Surplus | Amber #D99A1E | ▲ | Available hours above need by more than the band |

Risk levels reuse the same scale: Low = teal, Moderate = amber, High = coral. Blue (#2F5BEA) marks
actions and selection. Every status also carries an icon and a label, so color is never the only signal.

These thresholds are MVP decision rules, not industry standards. Change them in `src/config.py`.

## Files

    app.py                 entry point, sidebar, navigation
    src/config.py          thresholds, palette switch, scenario labels
    src/data.py            cached CSV loaders
    src/logic.py           decision logic and scenario calculator
    src/ui.py              styling and reusable components
    views/                 one file per page
    data/                  the 12 CSV tables; decision_log.csv is created on first save

## Customizing

- Colors live at the top of `src/ui.py` (`STATUS` for shortage/balanced/surplus, plus the frame colors)
  and in `.streamlit/config.toml` (theme and dark sidebar).
- Saved decisions: `data/decision_log.csv` (also downloadable from the Decision page).

The data is synthetic and not calibrated to a real warehouse. The tool supports, and does not
replace, the manager's staffing decision.

## Predictive modeling

Open **Predictive Modeling → Model insights & scenarios** in the left navigation. Two trained KPI regressions, model explainability, what-if and scenario summaries are included. See `MODEL_DOCUMENTATION.md` for definitions, performance, methodology and limitations. To retrain: `python train_models.py`.

## Repository notes

This is a demonstration built on **synthetic data**, not operational records from a real facility. The model files are saved for convenience. Avoid committing local credentials, private warehouse data, or generated decision logs. Model evaluations and limits are documented in `MODEL_DOCUMENTATION.md`.
