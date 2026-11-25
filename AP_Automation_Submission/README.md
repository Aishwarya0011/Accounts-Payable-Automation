# Accounts Payable Automation

A fresh full-stack implementation using **React**, **Django REST Framework**, and **PostgreSQL**.
Python is the language used by Django; JavaScript is used by React. No Flask or SQLite is used.

## Included modules
- Invoice upload (PDF, PNG, JPG, JPEG, TIFF) with multi-file selection
- OCR extraction using Tesseract when installed; PDF text extraction fallback
- Editable extracted invoice fields and line-item storage
- Mandatory field, duplicate invoice, GST-format, amount and vendor validation
- PO vs invoice (2-way) and PO vs GRN vs invoice (3-way) matching
- Vendor master and bank-detail fields
- Role-based approval actions and configurable approval thresholds
- Payment request creation and payment status tracking (simulation only)
- Dashboard summaries and CSV reports/audit events

## Important scope boundaries
This is a runnable project foundation, not a production ERP/AP platform.
- Email ingestion is not connected to a real mailbox.
- Real bank transfer/banking API integration is not included; payment status is simulated.
- Approval reminders, automatic escalation, parallel approvals and mobile push approvals are not implemented.
- OCR accuracy is not guaranteed; users should review and correct extracted fields.
- GST validation checks format/basic consistency only; it does not query GSTN.
- The dashboard shows operational counts from the local database; OCR accuracy and processing turnaround are not independently benchmarked.
- TIFF support depends on Pillow/Tesseract support in the host environment.
- The automated test suite is included but must be run in the target environment before claiming verified results.

## Requirements
- Docker Desktop (recommended), or PostgreSQL 15+
- Node.js 20+
- Python 3.11+
- Tesseract OCR installed and available on PATH (optional but recommended)

## Run with Docker (PostgreSQL + Django API)
From this folder:
```bash
docker compose up --build
```
API: http://localhost:8000/api/
Django admin: http://localhost:8000/admin/

Create an admin user in another terminal:
```bash
docker compose exec backend python manage.py createsuperuser
```

## Run React frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

The frontend calls the Django API at http://localhost:8000/api/.

## Local backend without Docker
Create a PostgreSQL database and set:
```text
DATABASE_URL=postgres://ap_user:ap_password@localhost:5432/ap_automation
DJANGO_SECRET_KEY=change-this-for-local-use
```
Then:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Demo data
Create a superuser, log into `/admin/`, and add vendors, purchase orders and GRNs.
A default demo account is deliberately not hard-coded. Create users and assign groups/roles in Django admin.

## Tests
```bash
cd backend
python manage.py test
```
Run tests before submission and record the actual output in your demo/report.

## Security notes
Set a strong secret key, configure allowed hosts/CORS, use HTTPS, secure uploaded files,
and review authorization before production deployment. Do not use sample credentials in production.
