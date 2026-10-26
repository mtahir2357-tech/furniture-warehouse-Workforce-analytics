#!/bin/bash
# One-command launcher for macOS. Usage:  bash run_mac.sh
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install Python 3.11+ from https://www.python.org/downloads/ and run this again."
  exit 1
fi
if [ ! -d ".venv" ]; then
  echo "First run: creating environment and installing packages (about a minute)..."
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install --upgrade pip -q
  pip install -r requirements.txt -q
else
  source .venv/bin/activate
fi
# Skip Streamlit's one-time email prompt so the app starts straight away.
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
  mkdir -p "$HOME/.streamlit"
  printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi
echo "Starting dashboard at http://localhost:8501  (press Control+C to stop)"
streamlit run app.py
