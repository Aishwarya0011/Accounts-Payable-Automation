# Challenges and Limitations

## Challenges Faced

### 1. OCR Data Extraction
Extracting accurate information from invoices with different layouts, fonts, and formats was challenging.

**Solution:** Implemented OCR-based text extraction to identify important invoice details such as invoice numbers, dates, vendor information, and amounts.

### 2. Data Validation
Handling missing fields, incorrect values, duplicate invoices, and inconsistent vendor information required multiple validation checks.

**Solution:** Implemented validation logic for mandatory fields, duplicate invoice numbers, GST details, vendor information, and invoice totals.

### 3. Invoice Matching
Comparing invoice details with purchase orders and goods receipt notes was challenging because the information could differ.

**Solution:** Implemented two-way and three-way matching logic to identify mismatches and discrepancies.

### 4. Approval Workflow
Managing invoice approvals and tracking different approval statuses required proper workflow handling.

**Solution:** Implemented an approval mechanism to manage invoice status and approval progress.

### 5. Database Management
Maintaining relationships between invoices, vendors, purchase orders, payments, and approval records required proper database organisation.

**Solution:** Structured the database to store and manage related information.

## Limitations

- OCR accuracy depends on invoice image quality, formatting, and text clarity.
- Scanned invoice processing requires Tesseract OCR installation.
- Email ingestion requires valid IMAP credentials and server configuration.
- Live banking integration is not available.
- ERP and external accounting system integration is not implemented.
- Automated reminders and escalation require additional scheduling and notification configuration.
- The complete end-to-end test suite has not been executed.
- The current implementation uses Flask, server-rendered templates, and SQLite instead of ReactJS, Django, and PostgreSQL.
