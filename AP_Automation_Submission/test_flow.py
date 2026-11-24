"""test_flow.py - runs the whole project end to end without a browser.
Run:  python test_flow.py      (it resets the demo database first)
"""
import glob
import os

os.environ["APPROVAL_SLA_HOURS"] = "0"  # so the reminder/escalation job treats approvals as overdue

import db
db.reset_db()
import app as appmod

client = appmod.app.test_client()
passed = 0


def check(label, condition):
    global passed
    print(("PASS  " if condition else "FAIL  ") + label)
    assert condition, label
    passed += 1


def login(username, password):
    client.get("/logout")
    r = client.post("/login", data={"username": username, "password": password})
    assert r.status_code == 302


def status_of(inv_id):
    return db.query("SELECT status FROM invoices WHERE id=?", (inv_id,), one=True)["status"]


def pending_approval_id(inv_id, role):
    row = db.query("SELECT id FROM approvals WHERE invoice_id=? AND role=? AND status='Pending'", (inv_id, role), one=True)
    return row["id"] if row else None


# 1. upload all sample invoices in one bulk upload
login("clerk", "clerk123")
files = sorted(glob.glob("sample_invoices/*"))
data = {"files": [(open(f, "rb"), os.path.basename(f)) for f in files]}
client.post("/upload", data=data, content_type="multipart/form-data")
expected = {1: "Pending Approval", 2: "Pending Approval", 3: "Pending Approval", 4: "Exception",
            5: "Exception", 6: "Exception", 7: "Exception", 8: "Pending Approval"}
for inv_id, want in expected.items():
    check("invoice %d (%s) -> %s" % (inv_id, os.path.basename(files[inv_id - 1]), want), status_of(inv_id) == want)
check("multi-page invoice has 2 pages and 28 lines",
      db.query("SELECT pages FROM invoices WHERE id=3", one=True)["pages"] == 2 and
      db.query("SELECT COUNT(*) AS n FROM invoice_items WHERE invoice_id=3", one=True)["n"] == 28)
check("duplicate detected", "Duplicate" in db.query("SELECT errors FROM invoices WHERE id=4", one=True)["errors"])
check("GST error detected", "IGST" in db.query("SELECT errors FROM invoices WHERE id=5", one=True)["errors"])
check("3-way mismatch detected", "GRN match" in db.query("SELECT errors FROM invoices WHERE id=6", one=True)["errors"])
check("unknown vendor detected", "vendor master" in db.query("SELECT errors FROM invoices WHERE id=7", one=True)["errors"])
check("image invoice read with OCR", db.query("SELECT total FROM invoices WHERE id=8", one=True)["total"] == 29500.0)

# 2. the clerk corrects invoice 5 (human review) and it passes
client.post("/invoice/5/edit", data={
    "invoice_number": "INV-1005", "invoice_date": "2026-11-01", "vendor_name": "Sharma Steel Traders",
    "vendor_gstin": "29AABCS1234F1Z5", "po_number": "PO-1005", "subtotal": "10000", "cgst": "900", "sgst": "900",
    "igst": "0", "total": "11800", "desc": ["MS Round Bar 12mm"], "qty": ["100"], "rate": ["100"], "amount": ["10000"]})
check("corrected invoice 5 passes validation", status_of(5) == "Pending Approval")

# 3. approvals: a clerk cannot approve; manager approves small invoice
ap = pending_approval_id(1, "Manager")
client.post("/approval/%d" % ap, data={"decision": "approve"})
check("clerk cannot approve", status_of(1) == "Pending Approval")
login("manager", "manager123")
client.post("/approval/%d" % ap, data={"decision": "approve", "comment": "ok"})
check("manager approves invoice 1 (single level)", status_of(1) == "Approved")

# 4. two-level approval for invoice 2 (Manager -> Finance)
client.post("/approval/%d" % pending_approval_id(2, "Manager"), data={"decision": "approve"})
check("invoice 2 still pending after manager (needs Finance)", status_of(2) == "Pending Approval")
login("finance", "finance123")
client.post("/approval/%d" % pending_approval_id(2, "Finance"), data={"decision": "approve"})
check("invoice 2 approved after finance", status_of(2) == "Approved")

# 5. rejection needs a comment
login("manager", "manager123")
ap3 = pending_approval_id(3, "Manager")
client.post("/approval/%d" % ap3, data={"decision": "reject", "comment": ""})
check("reject without comment is blocked", status_of(3) == "Pending Approval")
client.post("/approval/%d" % ap3, data={"decision": "reject", "comment": "Price too high"})
check("invoice 3 rejected with comment", status_of(3) == "Rejected")

# 6. escalation: admin runs the reminder job and approves an overdue step
login("admin", "admin123")
client.post("/reminders")
check("overdue approval escalated", db.query("SELECT COUNT(*) AS n FROM approvals WHERE escalated=1", one=True)["n"] >= 1)
client.post("/approval/%d" % pending_approval_id(8, "Manager"), data={"decision": "approve", "comment": "escalation"})
check("admin approved escalated invoice 8", status_of(8) == "Approved")

# 7. payments
login("finance", "finance123")
client.post("/invoice/1/request-payment")
check("payment requested", status_of(1) == "Payment Requested")
check("bank file export works", b"payment_id" in client.get("/payments/export").data)
pay = db.query("SELECT id FROM payments WHERE invoice_id=1", one=True)["id"]
client.post("/payments/%d/pay" % pay, data={"reference": "UTR123"})
check("payment marked paid", status_of(1) == "Paid")
check("payment advice page opens", client.get("/payments/%d/advice" % pay).status_code == 200)

# 8. vendor onboarding
login("clerk", "clerk123")
client.post("/vendors/new", data={"name": "Test Vendor", "gstin": "29AAAAA1111A1Z5", "pan": "AAAAA1111A",
                                  "email": "t@example.com", "bank_name": "HDFC", "account_no": "123", "ifsc": "HDFC0000001"})
check("new vendor starts Pending", db.query("SELECT status FROM vendors WHERE name='Test Vendor'", one=True)["status"] == "Pending")
login("admin", "admin123")
vid = db.query("SELECT id FROM vendors WHERE name='Test Vendor'", one=True)["id"]
client.post("/vendors/%d/status" % vid, data={"status": "Active"})
check("admin approves vendor", db.query("SELECT status FROM vendors WHERE id=?", (vid,), one=True)["status"] == "Active")

# 9. every page and report opens
for url in ["/dashboard", "/invoices", "/invoice/1", "/invoice/4", "/approvals", "/vendors", "/payments", "/rules", "/reports",
            "/reports/ap-aging", "/reports/invoice-status", "/reports/exceptions", "/reports/gst", "/reports/audit",
            "/reports/gst.csv", "/reports/audit.csv", "/upload", "/invoice/1/file"]:
    check("GET %s -> 200" % url, client.get(url).status_code == 200)

print("\nAll %d checks passed." % passed)
