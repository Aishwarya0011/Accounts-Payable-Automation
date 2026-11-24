"""workflow.py - ties everything together: process an upload, run checks, create and handle approvals."""
import os
from datetime import datetime, timedelta

import db
import extractor
import validator

SLA_HOURS = float(os.environ.get("APPROVAL_SLA_HOURS", 48))  # approvals older than this get escalated


def due_time():
    return (datetime.now() + timedelta(hours=SLA_HOURS)).isoformat(sep=" ", timespec="seconds")


def process_invoice(path, filename, username):
    """Upload -> OCR/extract -> save -> validate/match -> approvals. Returns the new invoice id."""
    d = extractor.extract_invoice(path)
    inv_id = db.execute(
        "INSERT INTO invoices (filename, stored_path, pages, invoice_number, invoice_date, vendor_name, vendor_gstin,"
        " po_number, subtotal, cgst, sgst, igst, tax, total, status, ocr_confidence, raw_text, uploaded_by, uploaded_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (filename, path, d["pages"], d["invoice_number"], d["invoice_date"], d["vendor_name"], d["vendor_gstin"],
         d["po_number"], d["subtotal"], d["cgst"], d["sgst"], d["igst"], d["tax"], d["total"], "Uploaded",
         d["confidence"], d["raw_text"], username, db.now()))
    for it in d["items"]:
        db.execute("INSERT INTO invoice_items (invoice_id, description, qty, rate, amount) VALUES (?,?,?,?,?)",
                   (inv_id, it["description"], it["qty"], it["rate"], it["amount"]))
    db.log(username, "Uploaded", inv_id, "%s (%d page(s), extraction confidence %s%%)" % (filename, d["pages"], d["confidence"]))
    evaluate(inv_id, username)
    return inv_id


def evaluate(inv_id, username="system"):
    """Run validation + PO matching. Clean invoice -> approvals are created. Otherwise -> Exception."""
    db.execute("DELETE FROM approvals WHERE invoice_id=?", (inv_id,))
    inv = db.query("SELECT * FROM invoices WHERE id=?", (inv_id,), one=True)
    items = db.query("SELECT * FROM invoice_items WHERE invoice_id=?", (inv_id,))
    vendor = db.query("SELECT * FROM vendors WHERE gstin=?", (inv["vendor_gstin"],), one=True)

    errors = validator.validate(inv, items)
    match_type, match_errors = validator.match_po(inv, items)
    errors += match_errors

    status = "Exception" if errors else "Pending Approval"
    db.execute("UPDATE invoices SET status=?, match_type=?, errors=?, vendor_id=? WHERE id=?",
               (status, match_type, "\n".join(errors), vendor["id"] if vendor else None, inv_id))
    if errors:
        db.log(username, "Validation failed", inv_id, "%d issue(s)" % len(errors))
    else:
        db.log(username, "Validation passed", inv_id, "%s match OK" % match_type)
        build_approvals(inv_id, inv["total"])
    return status


def build_approvals(inv_id, total):
    """Look up the approval matrix for this amount. Level 1 starts now, later levels wait."""
    rules = db.query("SELECT * FROM approval_rules WHERE ? BETWEEN min_amount AND max_amount ORDER BY level", (total,))
    if not rules:
        rules = [{"role": "Manager", "level": 1}]  # safe default if no rule matches
    first_level = min(r["level"] for r in rules)
    for r in rules:
        pending = r["level"] == first_level
        db.execute("INSERT INTO approvals (invoice_id, level, role, status, due_at) VALUES (?,?,?,?,?)",
                   (inv_id, r["level"], r["role"], "Pending" if pending else "Waiting", due_time() if pending else None))
    db.log("system", "Approval requested", inv_id, "Roles: " + ", ".join(r["role"] for r in rules))


def act(approval_id, user, decision, comment):
    """Approve or reject one approval step. Returns (ok, message)."""
    ap = db.query("SELECT * FROM approvals WHERE id=?", (approval_id,), one=True)
    if not ap or ap["status"] != "Pending":
        return False, "This approval is no longer pending."
    # allowed if same role, or Admin acting on an escalated (overdue) approval
    if not (user["role"] == ap["role"] or (user["role"] == "Admin" and ap["escalated"])):
        return False, "Your role cannot act on this approval."
    if decision == "reject" and not comment.strip():
        return False, "Please add a comment when rejecting."

    status = "Approved" if decision == "approve" else "Rejected"
    db.execute("UPDATE approvals SET status=?, approver=?, comment=?, acted_at=? WHERE id=?",
               (status, user["username"], comment, db.now(), approval_id))
    inv_id = ap["invoice_id"]
    db.log(user["username"], "Approval " + status.lower(), inv_id, "%s step. %s" % (ap["role"], comment))

    if status == "Rejected":
        db.execute("UPDATE invoices SET status='Rejected' WHERE id=?", (inv_id,))
        db.execute("UPDATE approvals SET status='Cancelled' WHERE invoice_id=? AND status IN ('Pending','Waiting')", (inv_id,))
        return True, "Invoice rejected."

    # approved: if every approver of this level has approved, move to the next level (or finish)
    still_open = db.query("SELECT 1 FROM approvals WHERE invoice_id=? AND level=? AND status='Pending'",
                          (inv_id, ap["level"]), one=True)
    if still_open:
        return True, "Approved. Waiting for the other approver(s) at the same level."
    nxt = db.query("SELECT MIN(level) AS lvl FROM approvals WHERE invoice_id=? AND status='Waiting'", (inv_id,), one=True)
    if nxt["lvl"] is not None:
        db.execute("UPDATE approvals SET status='Pending', due_at=? WHERE invoice_id=? AND level=? AND status='Waiting'",
                   (due_time(), inv_id, nxt["lvl"]))
        return True, "Approved. Sent to the next approval level."
    db.execute("UPDATE invoices SET status='Approved', approved_at=? WHERE id=?", (db.now(), inv_id))
    db.log("system", "Invoice approved", inv_id, "All approval levels complete")
    return True, "Approved. The invoice is fully approved and ready for payment."


def run_reminders():
    """Reminder + escalation job. Run from the Admin 'Reminders' page (or a scheduler in real life)."""
    messages = []
    pending = db.query("SELECT a.*, i.invoice_number FROM approvals a JOIN invoices i ON i.id = a.invoice_id "
                       "WHERE a.status='Pending'")
    for a in pending:
        overdue = a["due_at"] and a["due_at"] <= db.now()
        if overdue and not a["escalated"]:
            db.execute("UPDATE approvals SET escalated=1 WHERE id=?", (a["id"],))
            text = "Invoice %s: %s approval is overdue, escalated to Admin" % (a["invoice_number"], a["role"])
            db.log("system", "Escalated", a["invoice_id"], text)
        else:
            text = "Reminder sent to %s for invoice %s" % (a["role"], a["invoice_number"])
            db.log("system", "Reminder", a["invoice_id"], text)
        print("[NOTIFY]", text)  # in real life this would be an email / SMS / push message
        messages.append(text)
    return messages
