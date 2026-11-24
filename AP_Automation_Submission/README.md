# Accounts Payable Automation (Existing Project)

## Important technology-stack note
This supplied project currently uses **Flask + server-rendered Jinja templates + SQLite**.
It does **not** use the recruiter's mandatory stack of **ReactJS + Django + PostgreSQL**.
Do not describe this archive as compliant with the mandatory stack. It needs a React frontend,
Django backend, and PostgreSQL integration before it can meet that requirement.

## Included functionality in the supplied code
- Invoice upload (PDF/JPG/JPEG/PNG/TIF/TIFF) and bulk upload
- Text extraction from PDFs and OCR for image/scanned invoices (requires local Tesseract for OCR)
- Invoice field and line-item extraction
- Invoice validation and duplicate checks
- Purchase-order matching and goods-received-note matching
- Role-based, multi-level approvals with reminders/escalation logic
- Vendor onboarding and master data
- Payment request/status tracking and payment advice/export
- Dashboard and reports/audit log pages
- Sample invoices and an end-to-end test script

Feature availability depends on local dependencies and configuration. Email ingestion requires
IMAP credentials. Banking-system integration is represented by local payment/export workflow,
not a live bank connection.

## Requirements
- Python 3.10 or newer recommended
- Install Python dependencies from `requirements.txt`
- Tesseract OCR installed separately and available on PATH for image/scanned-document OCR

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

## Run on macOS/Linux
1. Open a terminal in this folder.
2. Create and activate a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Start the application:
   - `python app.py`
5. Open `http://127.0.0.1:5000` in your browser.

## Demo accounts
- AP Clerk: `clerk` / `clerk123`
- Manager: `manager` / `manager123`
- Finance: `finance` / `finance123`
- Admin: `admin` / `admin123`

Change the development secret key and demo passwords before any real deployment.
The app initializes its SQLite database and demo records on startup.

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


