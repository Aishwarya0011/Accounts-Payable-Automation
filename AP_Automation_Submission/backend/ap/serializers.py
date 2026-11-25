from rest_framework import serializers
from .models import Vendor, PurchaseOrder, GoodsReceipt, Invoice, InvoiceLine, Approval, ApprovalRule, Payment, AuditEvent

class VendorSerializer(serializers.ModelSerializer):
    class Meta: model = Vendor; fields = "__all__"
class PurchaseOrderSerializer(serializers.ModelSerializer):
    class Meta: model = PurchaseOrder; fields = "__all__"
class GoodsReceiptSerializer(serializers.ModelSerializer):
    class Meta: model = GoodsReceipt; fields = "__all__"
class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta: model = InvoiceLine; fields = "__all__"
class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    class Meta: model = Invoice; fields = "__all__"
class ApprovalSerializer(serializers.ModelSerializer):
    class Meta: model = Approval; fields = "__all__"
class ApprovalRuleSerializer(serializers.ModelSerializer):
    class Meta: model = ApprovalRule; fields = "__all__"
class PaymentSerializer(serializers.ModelSerializer):
    class Meta: model = Payment; fields = "__all__"
class AuditEventSerializer(serializers.ModelSerializer):
    class Meta: model = AuditEvent; fields = "__all__"
