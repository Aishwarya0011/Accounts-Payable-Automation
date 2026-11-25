from django.contrib import admin
from .models import Vendor, PurchaseOrder, GoodsReceipt, Invoice, InvoiceLine, Approval, ApprovalRule, Payment, AuditEvent
admin.site.register([Vendor, PurchaseOrder, GoodsReceipt, Invoice, InvoiceLine, Approval, ApprovalRule, Payment, AuditEvent])
