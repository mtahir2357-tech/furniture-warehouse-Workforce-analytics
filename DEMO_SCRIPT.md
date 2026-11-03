# Seven-minute demonstration — recording script (not yet recorded)

**0:00–0:45 — Problem and decision-maker.** Single furniture warehouse manager plans labor across 14 operating days; two high-value questions: where might workload exceed staffing, and which feasible staffing change manages backlog/cost trade-offs?

**0:45–1:45 — Workload forecasting.** Show synthetic history and selected forecast origin. Explain WLU, productivity WLU/hour, carry-in and ending backlog. Explain that 14-day forecast values come from the original historical-rule generator, not RF.

**1:45–2:45 — KPI evaluation.** In Model Validation show 64/16/20 chronological split, test MAE/RMSE and naive baseline for the *separate one-day RF* workload and productivity models; saved test reductions approximately 39.0% and 32.1%. Note that these are synthetic data results and the test has already been inspected.

**2:45–3:30 — Improvement and uncertainty.** Original versus revised RF validation; describe minor gains. Explain separate 14-day validation improvement, plus empirical interval calibration and why intervals are not yet deployed as trusted probabilities.

**3:30–5:30 — Complete what-if.** In Staffing Decisions choose one example date; show baseline. Compare adding 2 workers, then switch to adding 12 overtime hours. Read hours available, gap, projected ending backlog, labor cost, and automatically generated summary. Explicitly state that capacity is calculated deterministically at unchanged productivity; results are not causal evidence.

**5:30–6:15 — Explanations and inputs.** Choose a historical reference date under Model Validation. Show global permutation importance vs order-dependent individual prediction explanation. Show manager-proposed staffing variables vs external workload history, and an out-of-range warning.

**6:15–7:00 — Usefulness, real test and limitations.** Show actual completed outside-user-test feedback and real resulting UI change *after performing the test*; state data and schedule provenance limits, high-demand error risk, and uncalibrated archived intervals. Finish with how the tool informs decisions without replacing human judgment.

**Recording checklist:** App running, screen and audio captured, true participant feedback included, no confidential data, duration about 7 minutes, video uploaded to accessible location and link placed in GitHub README/submission.
