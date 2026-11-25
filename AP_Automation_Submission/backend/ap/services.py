import re
from decimal import Decimal
from pathlib import Path
from django.conf import settings

def extract_text(file_path):
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception:
            pass
    try:
        import pytesseract
        from PIL import Image
        if suffix in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]:
            return pytesseract.image_to_string(Image.open(file_path))
        if suffix == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(pytesseract.image_to_string(page.to_image().original) for page in pdf.pages)
    except Exception:
        return ""
    return ""

def guess_fields(text):
    def find(pattern):
        m = re.search(pattern, text, re.I)
        return m.group(1).strip() if m else ""
    return {
        "invoice_number": find(r"(?:invoice\\s*(?:no|number|#)?)\\s*[:#-]?\\s*([A-Z0-9/-]+)"),
        "gstin": find(r"\\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\\b"),
        "total_amount": find(r"(?:grand\\s*total|total\\s*amount|total)\\s*[:₹ ]+([0-9,]+(?:\\.[0-9]{1,2})?)"),
    }

def validate_invoice(invoice):
    errors = []
    if not invoice.invoice_number: errors.append("Invoice number is required.")
    if not invoice.invoice_date: errors.append("Invoice date is required.")
    if not invoice.vendor_id: errors.append("Vendor must be selected.")
    if invoice.total_amount <= 0: errors.append("Total amount must be greater than zero.")
    if invoice.gstin and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", invoice.gstin):
        errors.append("GSTIN format is invalid.")
    duplicate = invoice.__class__.objects.exclude(pk=invoice.pk).filter(
        invoice_number=invoice.invoice_number, vendor=invoice.vendor
    ).exists() if invoice.invoice_number and invoice.vendor_id else False
    if duplicate: errors.append("Duplicate invoice number for this vendor.")
    if invoice.subtotal + invoice.tax_amount and abs(invoice.subtotal + invoice.tax_amount - invoice.total_amount) > Decimal("1.00"):
        errors.append("Subtotal plus tax does not match total amount.")
    return errors
