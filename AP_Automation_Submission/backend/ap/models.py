from django.db import models
from django.contrib.auth.models import User

class Vendor(models.Model):
    name = models.CharField(max_length=180)
    vendor_code = models.CharField(max_length=50, unique=True)
    gstin = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    bank_account_name = models.CharField(max_length=180, blank=True)
    bank_account_number = models.CharField(max_length=80, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    onboarding_status = models.CharField(max_length=20, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.vendor_code} - {self.name}"

class PurchaseOrder(models.Model):
    po_number = models.CharField(max_length=60, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, default="OPEN")

class GoodsReceipt(models.Model):
    grn_number = models.CharField(max_length=60, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="grns")
    received_amount = models.DecimalField(max_digits=14, decimal_places=2)

class Invoice(models.Model):
    STATUS = [(x,x.replace("_"," ").title()) for x in ["UPLOADED","NEEDS_REVIEW","VALIDATION_FAILED","MATCHED","PENDING_APPROVAL","APPROVED","REJECTED","PAYMENT_REQUESTED","PAID"]]
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL)
    invoice_number = models.CharField(max_length=100, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="INR")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gstin = models.CharField(max_length=15, blank=True)
    source_file = models.FileField(upload_to="invoices/", null=True, blank=True)
    extracted_text = models.TextField(blank=True)
    validation_errors = models.JSONField(default=list, blank=True)
    match_result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, choices=STATUS, default="UPLOADED")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

class Approval(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=40)
    decision = models.CharField(max_length=20, default="PENDING")
    comments = models.TextField(blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)

class ApprovalRule(models.Model):
    role = models.CharField(max_length=40)
    min_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)

class Payment(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name="payment")
    payment_reference = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, default="REQUESTED")
    payment_date = models.DateField(null=True, blank=True)
    advice_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=60)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
