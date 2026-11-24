@echo off
REM Windows: double-click this file (or run it in Command Prompt) from inside the project folder.
if not exist venv ( python -m venv venv )
call venv\Scripts\activate
pip install -r requirements.txt
echo.
echo Open http://127.0.0.1:5000 in your browser.  Press Ctrl+C here to stop.
python app.py
