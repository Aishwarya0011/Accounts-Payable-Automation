# Implementation Notes and Current Limitations

This document records observations from inspecting the supplied project. It does not claim
that these were personally encountered or resolved during development.

## Existing implementation
The project contains a Flask application with Jinja templates, SQLite persistence, invoice
extraction/validation, PO/GRN matching, approval workflow, vendor management, payment tracking,
dashboard/report pages, sample invoices, and a test-flow script.

## Key compatibility gap
The recruitment email mandates ReactJS, Django, and PostgreSQL. The supplied source uses Flask,
server-rendered templates, and SQLite. This is a fundamental stack mismatch, not a configuration
change. A compliant implementation requires a React client, Django application/API, PostgreSQL
models/migrations, and integration testing across those components.

## Integration limitations visible in the source
- OCR for image/scanned files depends on Tesseract being installed on the host machine.
- Email ingestion depends on IMAP server credentials supplied through environment variables.
- Payment tracking/export is implemented locally; a live banking-system connection is not present.
- The reminder/escalation logic is invoked by an application action; a production scheduler and
  real notification delivery would need to be configured.
- The supplied end-to-end test script is included but was not executed in this packaging step.

## Before submission
1. Rebuild or migrate the application to ReactJS + Django + PostgreSQL.
2. Run the full test flow in a configured environment and retain actual results.
3. Verify OCR using both text PDFs and scanned/image invoices.
4. Configure and test any external email, notification, ERP, or banking integrations that are claimed.
5. Record a demo of the actual running application and explain only features that are implemented.
