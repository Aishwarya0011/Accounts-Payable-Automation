import csv, uuid
from datetime import date
from django.http import HttpResponse
from django.db.models import Sum, Count
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Vendor, PurchaseOrder, GoodsReceipt, Invoice, Approval, ApprovalRule, Payment, AuditEvent
from .serializers import *
from .services import extract_text, guess_fields, validate_invoice

def audit(action, obj, details=None):
    AuditEvent.objects.create(action=action, object_type=obj.__class__.__name__, object_id=obj.pk, details=details or {})

class VendorViewSet(viewsets.ModelViewSet):
    queryset=Vendor.objects.all().order_by("name"); serializer_class=VendorSerializer
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset=PurchaseOrder.objects.select_related("vendor").all(); serializer_class=PurchaseOrderSerializer
class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset=GoodsReceipt.objects.select_related("purchase_order").all(); serializer_class=GoodsReceiptSerializer
class InvoiceViewSet(viewsets.ModelViewSet):
    queryset=Invoice.objects.select_related("vendor","purchase_order").prefetch_related("lines").all().order_by("-uploaded_at")
    serializer_class=InvoiceSerializer

    def create(self, request, *args, **kwargs):
        f=request.FILES.get("file")
        if not f: return Response({"error":"Upload a file using field name 'file'."}, status=400)
        allowed=[".pdf",".png",".jpg",".jpeg",".tif",".tiff"]
        import os
        if os.path.splitext(f.name)[1].lower() not in allowed: return Response({"error":"Supported formats: PDF, PNG, JPG, TIFF."}, status=400)
        obj=Invoice.objects.create(source_file=f, status="NEEDS_REVIEW")
        text=extract_text(obj.source_file.path)
        obj.extracted_text=text
        fields=guess_fields(text)
        obj.invoice_number=fields["invoice_number"]
        obj.gstin=fields["gstin"]
        try:
            from decimal import Decimal
            obj.total_amount=Decimal(fields["total_amount"].replace(",","")) if fields["total_amount"] else 0
        except Exception: pass
        obj.save()
        audit("invoice_uploaded",obj,{"filename":f.name})
        return Response(InvoiceSerializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    def validate_invoice(self, request, pk=None):
        obj=self.get_object()
        obj.validation_errors=validate_invoice(obj)
        obj.status="VALIDATION_FAILED" if obj.validation_errors else "MATCHED"
        obj.save(); audit("invoice_validated",obj,{"errors":obj.validation_errors})
        return Response({"errors":obj.validation_errors,"status":obj.status})

    @action(detail=True, methods=["post"])
    def match(self, request, pk=None):
        obj=self.get_object()
        po=obj.purchase_order
        if not po:
            obj.match_result={"matched":False,"reason":"Select a purchase order first."}
        else:
            two=abs(po.total_amount-obj.total_amount) <= 1
            grn_id=request.data.get("grn_id")
            grn=GoodsReceipt.objects.filter(pk=grn_id,purchase_order=po).first() if grn_id else None
            three=bool(grn and abs(grn.received_amount-obj.total_amount)<=1)
            obj.match_result={"two_way_match":two,"three_way_match":three if grn else None,"grn_checked":bool(grn)}
        obj.save(); audit("invoice_matched",obj,obj.match_result)
        return Response(obj.match_result)

    @action(detail=True, methods=["post"])
    def submit_approval(self, request, pk=None):
        obj=self.get_object()
        rules=ApprovalRule.objects.filter(active=True).order_by("min_amount")
        rule=rules.filter(min_amount__lte=obj.total_amount).filter(max_amount__isnull=True).first() or rules.filter(min_amount__lte=obj.total_amount,max_amount__gte=obj.total_amount).first()
        role=rule.role if rule else "MANAGER"
        approval=Approval.objects.create(invoice=obj,role=role)
        obj.status="PENDING_APPROVAL"; obj.save(); audit("approval_requested",obj,{"role":role})
        return Response(ApprovalSerializer(approval).data,status=201)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        obj=self.get_object()
        approval=obj.approvals.filter(decision="PENDING").first()
        if not approval: return Response({"error":"No pending approval."},status=400)
        decision=request.data.get("decision")
        if decision not in ["APPROVED","REJECTED"]: return Response({"error":"decision must be APPROVED or REJECTED"},status=400)
        approval.decision=decision; approval.comments=request.data.get("comments",""); approval.approver=request.user if request.user.is_authenticated else None
        from django.utils import timezone
        approval.acted_at=timezone.now(); approval.save()
        obj.status=decision; obj.save(); audit("approval_decided",obj,{"decision":decision})
        return Response(ApprovalSerializer(approval).data)

    @action(detail=True, methods=["post"])
    def payment_request(self, request, pk=None):
        obj=self.get_object()
        if obj.status!="APPROVED": return Response({"error":"Only approved invoices can be sent for payment."},status=400)
        payment,created=Payment.objects.get_or_create(invoice=obj,defaults={"payment_reference":"PAY-"+uuid.uuid4().hex[:10].upper(),"amount":obj.total_amount})
        obj.status="PAYMENT_REQUESTED"; obj.save(); audit("payment_requested",obj,{"reference":payment.payment_reference})
        return Response(PaymentSerializer(payment).data,status=201 if created else 200)

class ApprovalRuleViewSet(viewsets.ModelViewSet):
    queryset=ApprovalRule.objects.all(); serializer_class=ApprovalRuleSerializer
class PaymentViewSet(viewsets.ModelViewSet):
    queryset=Payment.objects.select_related("invoice").all(); serializer_class=PaymentSerializer
    @action(detail=True,methods=["post"])
    def update_status(self,request,pk=None):
        obj=self.get_object(); new=request.data.get("status")
        if new not in ["REQUESTED","PROCESSING","PAID","FAILED"]: return Response({"error":"Invalid status."},status=400)
        obj.status=new
        if new=="PAID": obj.payment_date=date.today(); obj.invoice.status="PAID"; obj.invoice.save()
        obj.save(); audit("payment_status_updated",obj,{"status":new})
        return Response(PaymentSerializer(obj).data)

@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard(request):
    return Response({
        "invoice_count":Invoice.objects.count(),
        "pending_approvals":Approval.objects.filter(decision="PENDING").count(),
        "total_invoice_amount":Invoice.objects.aggregate(v=Sum("total_amount"))["v"] or 0,
        "paid_count":Payment.objects.filter(status="PAID").count(),
        "exception_count":Invoice.objects.filter(status="VALIDATION_FAILED").count(),
        "vendor_count":Vendor.objects.count(),
    })

@api_view(["GET"])
@permission_classes([AllowAny])
def report(request):
    kind=request.query_params.get("type","invoice_status")
    response=HttpResponse(content_type="text/csv")
    response["Content-Disposition"]=f'attachment; filename="{kind}_report.csv"'
    writer=csv.writer(response)
    if kind=="audit":
        writer.writerow(["Timestamp","Action","Object","Object ID","Details"])
        for x in AuditEvent.objects.order_by("-created_at"):
            writer.writerow([x.created_at,x.action,x.object_type,x.object_id,x.details])
    else:
        writer.writerow(["Invoice","Vendor","Date","Due date","Amount","Status"])
        for x in Invoice.objects.select_related("vendor").all():
            writer.writerow([x.invoice_number,x.vendor.name if x.vendor else "",x.invoice_date,x.due_date,x.total_amount,x.status])
    return response
