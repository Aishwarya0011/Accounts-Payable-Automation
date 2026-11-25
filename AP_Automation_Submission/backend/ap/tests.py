from django.test import TestCase
from .models import Vendor, Invoice
from .services import validate_invoice
from decimal import Decimal
class InvoiceValidationTests(TestCase):
    def test_missing_required_fields_reported(self):
        invoice=Invoice(invoice_number="",total_amount=Decimal("0"))
        errors=validate_invoice(invoice)
        self.assertIn("Invoice number is required.",errors)
        self.assertIn("Vendor must be selected.",errors)
        self.assertIn("Total amount must be greater than zero.",errors)
    def test_valid_gstin_pattern_not_flagged(self):
        vendor=Vendor.objects.create(name="Test Vendor",vendor_code="V001",gstin="29ABCDE1234F1Z5")
        invoice=Invoice(vendor=vendor,invoice_number="INV-1",total_amount=Decimal("100"))
        errors=validate_invoice(invoice)
        self.assertFalse(any("GSTIN format" in e for e in errors))
