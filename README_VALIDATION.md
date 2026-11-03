# Validation and submission instructions

The two uploaded packages have already been merged. **Do not run the old overlay `install_patch.py`.** This is a complete standalone project, not an overlay.

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python validate_submission.py
python -m unittest discover -s tests -v
streamlit run app.py
```

See `README.md` for the detailed procedure and `CONSOLIDATION_NOTES.md` for precise source-file decisions. A terminal and live UI smoke test are still required in the target environment.
