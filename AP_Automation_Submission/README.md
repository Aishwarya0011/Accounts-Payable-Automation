# Accounts Payable Automation System

## Project Overview

The Accounts Payable Automation System is designed to simplify invoice processing and management through OCR-based data extraction, invoice validation, purchase order matching, approval workflows, and payment tracking.

The application aims to reduce manual work, improve accuracy, and make invoice processing more efficient.

## Features

### 1. Invoice Capture
- Upload invoices in PDF and image formats.
- Support for multiple invoice uploads.

### 2. OCR and Data Extraction
- Extract text from uploaded invoices using OCR.
- Identify invoice numbers, dates, vendor details, and amounts.
- Extract relevant invoice information.

### 3. Invoice Validation
- Validate mandatory invoice fields.
- Identify duplicate invoices.
- Validate vendor and GST details.
- Check invoice amounts and totals.

### 4. Purchase Order Matching
- Two-way matching between purchase orders and invoices.
- Three-way matching between purchase orders, goods receipt notes, and invoices.
- Identify mismatches and discrepancies.

### 5. Approval Workflow
- Manage invoice approval statuses.
- Track approval progress.
- Support invoice review and approval.

### 6. Vendor Management
- Maintain vendor information.
- Manage vendor details and records.

### 7. Payment Tracking
- Track invoice payment statuses.
- Maintain payment-related information.

### 8. Dashboard and Reports
- View invoice summaries.
- Monitor pending approvals.
- Track invoice processing status.
- View relevant invoice information.

## Technologies Used

- Python
- Flask
- HTML
- CSS
- JavaScript
- SQLite
- Tesseract OCR

## Project Structure

```text
Accounts-Payable-Automation/
│
├── app.py
├── templates/
├── static/
├── uploads/
├── sample_invoices/
├── requirements.txt
├── database/
├── README.md
└── CHALLENGES_AND_LIMITATIONS.md
```

*The actual project structure may vary depending on the files present in the repository.*

## Installation and Setup

### Prerequisites

- Python 3.10 or later
- pip
- Tesseract OCR

### Step 1: Clone the Repository

```bash
git clone https://github.com/Aishwarya0011/Accounts-Payable-Automation.git
```

### Step 2: Navigate to the Project Directory

```bash
cd Accounts-Payable-Automation
```

### Step 3: Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows:**
```bash
venv\Scripts\activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000/
```

## Sample Data

The `sample_invoices` folder contains sample invoice files for testing invoice upload and processing functionality.

## Documentation

Refer to `CHALLENGES_AND_LIMITATIONS.md` for information about development challenges and current limitations.

## Future Enhancements

- Integration with ERP and accounting systems.
- Automated email notifications.
- Advanced OCR and AI-based extraction.
