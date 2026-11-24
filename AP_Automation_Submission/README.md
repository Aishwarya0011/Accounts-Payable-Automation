# Accounts Payable Automation


## Run on Windows
1. Open a terminal in this folder.
2. Create and activate a virtual environment:
   - `py -m venv .venv`
   - `.venv\\Scripts\\activate`
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Start the application:
   - `py app.py`
5. Open `http://127.0.0.1:5000` in your browser.


## Demo accounts
- AP Clerk: `clerk` / `clerk123`
- Manager: `manager` / `manager123`
- Finance: `finance` / `finance123`
- Admin: `admin` / `admin123`



## Testing
The repository includes `test_flow.py`, an end-to-end Flask test-client script. Run it with:
`python test_flow.py`

The test script resets the local demo database before running. It is included but has not
been executed in this packaging step. Python syntax compilation was checked during packaging;
that check does not prove runtime functionality.

## Project structure
- `app.py` — Flask routes and web application
- `db.py` — SQLite schema, queries, and demo seed data
- `extractor.py` — PDF/image text extraction and OCR
- `validator.py` — invoice validation and PO/GRN matching
- `workflow.py` — approval and invoice-processing workflow
- `email_ingest.py` — optional IMAP attachment ingestion
- `templates/` — server-rendered HTML templates
- `static/` — CSS and JavaScript
- `sample_invoices/` — sample PDF/image invoices
- `test_flow.py` — end-to-end test script


