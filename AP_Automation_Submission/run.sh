#!/usr/bin/env bash
# macOS / Linux:  bash run.sh
python3 -m venv venv 2>/dev/null
source venv/bin/activate
pip install -r requirements.txt
echo
echo "Open http://127.0.0.1:5000 in your browser.  Press Ctrl+C here to stop."
python app.py
