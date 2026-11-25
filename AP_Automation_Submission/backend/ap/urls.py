from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import VendorViewSet, PurchaseOrderViewSet, GoodsReceiptViewSet, InvoiceViewSet, ApprovalRuleViewSet, PaymentViewSet, dashboard, report
router=DefaultRouter()
router.register("vendors",VendorViewSet)
router.register("purchase-orders",PurchaseOrderViewSet)
router.register("grns",GoodsReceiptViewSet)
router.register("invoices",InvoiceViewSet)
router.register("approval-rules",ApprovalRuleViewSet)
router.register("payments",PaymentViewSet)
urlpatterns=[path("",include(router.urls)),path("dashboard/",dashboard),path("reports/",report)]
