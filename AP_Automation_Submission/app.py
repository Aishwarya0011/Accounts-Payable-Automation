"""app.py - the Flask web application (all pages / routes)."""
import csv
import io
import os
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

import db
import validator
import workflow

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
ALLOWED = {"pdf", "jpg", "jpeg", "png", "tif", "tiff"}
os.makedirs(UPLOAD_DIR, exist_ok=True)
db.init_db()


# ---------------- login / permissions ----------------
@app.before_request
def load_user():
    g.user = None
    if session.get("uid"):
        g.user = db.query("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
    if g.user is None and request.endpoint not in ("login", "static"):
        return redirect(url_for("login"))


@app.context_processor
def inject_user():
    return {"user": g.user}


@app.template_filter("inr")
def inr(value):
    return "{:,.2f}".format(value or 0)


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if g.user["role"] not in roles:
                flash("Your role (%s) cannot do that." % g.user["role"], "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db.query("SELECT * FROM users WHERE username=?", (request.form["username"].strip(),), one=True)
        if u and check_password_hash(u["password"], request.form["password"]):
            session["uid"] = u["id"]
            db.log(u["username"], "Logged in")
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("dashboard"))


# ---------------- dashboard ----------------
@app.route("/dashboard")
def dashboard():
    by_status = db.query("SELECT status, COUNT(*) AS n, SUM(total) AS amount FROM invoices GROUP BY status")
    stats = db.query("SELECT AVG(ocr_confidence) AS ocr, "
                     "AVG((julianday(approved_at) - julianday(uploaded_at)) * 24) AS tat FROM invoices", one=True)
    # invoice aging: unpaid invoices grouped by how old the invoice date is
    buckets = {"0-30 days": [0, 0.0], "31-60 days": [0, 0.0], "61-90 days": [0, 0.0], "90+ days": [0, 0.0]}
    unpaid = db.query("SELECT invoice_date, total FROM invoices WHERE status NOT IN ('Paid','Rejected','Exception')")
    for r in unpaid:
        try:
            age = (datetime.now() - datetime.strptime(r["invoice_date"], "%Y-%m-%d")).days
        except (TypeError, ValueError):
            continue
        key = "0-30 days" if age <= 30 else "31-60 days" if age <= 60 else "61-90 days" if age <= 90 else "90+ days"
        buckets[key][0] += 1
        buckets[key][1] += r["total"]
    pending = db.query("SELECT a.*, i.invoice_number, i.vendor_name, i.total FROM approvals a "
                       "JOIN invoices i ON i.id = a.invoice_id WHERE a.status='Pending' AND "
                       "(a.role=? OR (? = 'Admin' AND a.escalated=1))", (g.user["role"], g.user["role"]))
    vendors = db.query("SELECT vendor_name, COUNT(*) AS n, SUM(total) AS amount FROM invoices "
                       "GROUP BY vendor_name ORDER BY amount DESC")
    pay = db.query("SELECT status, COUNT(*) AS n, SUM(amount) AS amount FROM payments GROUP BY status")
    max_amount = max([b[1] for b in buckets.values()] + [1])
    return render_template("dashboard.html", by_status=by_status, stats=stats, buckets=buckets,
                           max_amount=max_amount, pending=pending, vendors=vendors, pay=pay)


# ---------------- invoice capture ----------------
@app.route("/upload", methods=["GET", "POST"])
@roles_required("Clerk", "Admin")
def upload():
    if request.method == "POST":
        done = 0
        for f in request.files.getlist("files"):  # bulk upload: many files in one go
            name = secure_filename(f.filename or "")
            if not name:
                continue
            if name.rsplit(".", 1)[-1].lower() not in ALLOWED:
                flash("%s: file type not supported (use PDF, JPG, PNG or TIFF)." % name, "error")
                continue
            path = os.path.join(UPLOAD_DIR, datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + name)
            f.save(path)
            workflow.process_invoice(path, name, g.user["username"])
            done += 1
        if done:
            flash("%d invoice(s) uploaded and processed." % done, "ok")
        return redirect(url_for("invoices"))
    return render_template("upload.html")


@app.route("/invoices")
def invoices():
    status = request.args.get("status", "")
    if status:
        rows = db.query("SELECT * FROM invoices WHERE status=? ORDER BY id DESC", (status,))
    else:
        rows = db.query("SELECT * FROM invoices ORDER BY id DESC")
    return render_template("invoices.html", rows=rows, status=status)


def num(text):
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return 0.0


@app.route("/invoice/<int:inv_id>")
def invoice_detail(inv_id):
    inv = db.query("SELECT * FROM invoices WHERE id=?", (inv_id,), one=True)
    if not inv:
        abort(404)
    return render_template(
        "invoice_detail.html", inv=inv,
        items=db.query("SELECT * FROM invoice_items WHERE invoice_id=?", (inv_id,)),
        approvals=db.query("SELECT * FROM approvals WHERE invoice_id=? ORDER BY level, id", (inv_id,)),
        payment=db.query("SELECT * FROM payments WHERE invoice_id=?", (inv_id,), one=True),
        logs=db.query("SELECT * FROM audit_logs WHERE invoice_id=? ORDER BY id", (inv_id,)))


@app.route("/invoice/<int:inv_id>/file")
def invoice_file(inv_id):
    inv = db.query("SELECT * FROM invoices WHERE id=?", (inv_id,), one=True)
    if not inv or not os.path.exists(inv["stored_path"]):
        abort(404)
    return send_file(inv["stored_path"])


@app.route("/invoice/<int:inv_id>/edit", methods=["POST"])
@roles_required("Clerk", "Admin")
def invoice_edit(inv_id):
    """Human review step: fix what the OCR got wrong, then validate again."""
    inv = db.query("SELECT * FROM invoices WHERE id=?", (inv_id,), one=True)
    if not inv or inv["status"] != "Exception":
        flash("Only invoices with exceptions can be edited.", "error")
        return redirect(url_for("invoice_detail", inv_id=inv_id))
    f = request.form
    cgst, sgst, igst = num(f["cgst"]), num(f["sgst"]), num(f["igst"])
    db.execute("UPDATE invoices SET invoice_number=?, invoice_date=?, vendor_name=?, vendor_gstin=?, po_number=?,"
               " subtotal=?, cgst=?, sgst=?, igst=?, tax=?, total=? WHERE id=?",
               (f["invoice_number"].strip(), f["invoice_date"].strip(), f["vendor_name"].strip(),
                f["vendor_gstin"].strip().upper(), f["po_number"].strip().upper(), num(f["subtotal"]),
                cgst, sgst, igst, round(cgst + sgst + igst, 2), num(f["total"]), inv_id))
    db.execute("DELETE FROM invoice_items WHERE invoice_id=?", (inv_id,))
    for desc, qty, rate, amount in zip(f.getlist("desc"), f.getlist("qty"), f.getlist("rate"), f.getlist("amount")):
        if desc.strip():
            db.execute("INSERT INTO invoice_items (invoice_id, description, qty, rate, amount) VALUES (?,?,?,?,?)",
                       (inv_id, desc.strip(), num(qty), num(rate), num(amount)))
    db.log(g.user["username"], "Invoice corrected", inv_id, "Fields edited by user")
    status = workflow.evaluate(inv_id, g.user["username"])
    flash("Saved. New status: " + status, "ok" if status == "Pending Approval" else "error")
    return redirect(url_for("invoice_detail", inv_id=inv_id))


# ---------------- approvals ----------------
@app.route("/approvals")
def approvals():
    rows = db.query("SELECT a.*, i.invoice_number, i.vendor_name, i.total FROM approvals a "
                    "JOIN invoices i ON i.id = a.invoice_id WHERE a.status='Pending' AND "
                    "(a.role=? OR (? = 'Admin' AND a.escalated=1)) ORDER BY a.due_at", (g.user["role"], g.user["role"]))
    return render_template("approvals.html", rows=rows)


@app.route("/approval/<int:ap_id>", methods=["POST"])
def approval_action(ap_id):
    ok, msg = workflow.act(ap_id, g.user, request.form["decision"], request.form.get("comment", ""))
    flash(msg, "ok" if ok else "error")
    return redirect(request.referrer or url_for("approvals"))


@app.route("/rules", methods=["GET", "POST"])
@roles_required("Admin")
def rules():
    """Configurable approval matrix."""
    if request.method == "POST":
        if request.form.get("delete"):
            db.execute("DELETE FROM approval_rules WHERE id=?", (request.form["delete"],))
        else:
            db.execute("INSERT INTO approval_rules (min_amount, max_amount, role, level) VALUES (?,?,?,?)",
                       (num(request.form["min_amount"]), num(request.form["max_amount"]),
                        request.form["role"], int(request.form["level"])))
        db.log(g.user["username"], "Approval matrix changed")
        return redirect(url_for("rules"))
    return render_template("rules.html", rows=db.query("SELECT * FROM approval_rules ORDER BY min_amount, level"))


@app.route("/reminders", methods=["POST"])
@roles_required("Admin")
def reminders():
    msgs = workflow.run_reminders()
    flash("Reminder job finished: %d notification(s). %s" % (len(msgs), " | ".join(msgs)), "ok")
    return redirect(url_for("approvals"))


# ---------------- payments ----------------
@app.route("/invoice/<int:inv_id>/request-payment", methods=["POST"])
@roles_required("Finance", "Admin")
def request_payment(inv_id):
    inv = db.query("SELECT * FROM invoices WHERE id=?", (inv_id,), one=True)
    if not inv or inv["status"] != "Approved":
        flash("Only approved invoices can be sent for payment.", "error")
    else:
        db.execute("INSERT INTO payments (invoice_id, amount, status, requested_at) VALUES (?,?,?,?)",
                   (inv_id, inv["total"], "Requested", db.now()))
        db.execute("UPDATE invoices SET status='Payment Requested' WHERE id=?", (inv_id,))
        db.log(g.user["username"], "Payment requested", inv_id, "Amount %s" % inv["total"])
        flash("Payment request created.", "ok")
    return redirect(url_for("invoice_detail", inv_id=inv_id))


@app.route("/payments")
def payments():
    rows = db.query("SELECT p.*, i.invoice_number, i.vendor_name FROM payments p "
                    "JOIN invoices i ON i.id = p.invoice_id ORDER BY p.id DESC")
    return render_template("payments.html", rows=rows)


@app.route("/payments/<int:pay_id>/pay", methods=["POST"])
@roles_required("Finance", "Admin")
def mark_paid(pay_id):
    p = db.query("SELECT * FROM payments WHERE id=?", (pay_id,), one=True)
    if p and p["status"] == "Requested":
        ref = request.form.get("reference", "").strip() or "UTR" + datetime.now().strftime("%y%m%d%H%M%S")
        db.execute("UPDATE payments SET status='Paid', paid_at=?, reference=? WHERE id=?", (db.now(), ref, pay_id))
        db.execute("UPDATE invoices SET status='Paid' WHERE id=?", (p["invoice_id"],))
        db.log(g.user["username"], "Payment marked paid", p["invoice_id"], "Reference " + ref)
        flash("Payment marked as paid.", "ok")
    return redirect(url_for("payments"))


@app.route("/payments/<int:pay_id>/advice")
def payment_advice(pay_id):
    """Payment advice: a print-friendly page (use the browser's Print -> Save as PDF)."""
    p = db.query("SELECT * FROM payments WHERE id=?", (pay_id,), one=True) or abort(404)
    inv = db.query("SELECT * FROM invoices WHERE id=?", (p["invoice_id"],), one=True)
    vendor = db.query("SELECT * FROM vendors WHERE id=?", (inv["vendor_id"],), one=True)
    return render_template("advice.html", p=p, inv=inv, vendor=vendor)


@app.route("/payments/export")
@roles_required("Finance", "Admin")
def payments_export():
    """Bank upload file (CSV). This stands in for the real banking-system integration."""
    rows = db.query("SELECT p.id AS payment_id, p.amount, i.invoice_number, v.name AS beneficiary, v.account_no, v.ifsc FROM payments p "
                    "JOIN invoices i ON i.id = p.invoice_id JOIN vendors v ON v.id = i.vendor_id "
                    "WHERE p.status='Requested'")
    return csv_response("bank_payment_file.csv", ["payment_id", "amount", "invoice_number", "beneficiary", "account_no", "ifsc"], rows)


# ---------------- vendors ----------------
@app.route("/vendors")
def vendors():
    return render_template("vendors.html", rows=db.query("SELECT * FROM vendors ORDER BY id"))


@app.route("/vendors/new", methods=["GET", "POST"])
@app.route("/vendors/<int:vid>/edit", methods=["GET", "POST"])
@roles_required("Clerk", "Admin")
def vendor_form(vid=None):
    vendor = db.query("SELECT * FROM vendors WHERE id=?", (vid,), one=True) if vid else None
    if request.method == "POST":
        f = request.form
        gstin = f["gstin"].strip().upper()
        if not validator.valid_gstin(gstin):
            flash("GSTIN format is not valid (example: 29AABCS1234F1Z5).", "error")
            return render_template("vendor_form.html", vendor=f)
        values = (f["name"].strip(), gstin, f["pan"].strip().upper(), f["email"].strip(),
                  f["bank_name"].strip(), f["account_no"].strip(), f["ifsc"].strip().upper())
        try:
            if vendor:
                db.execute("UPDATE vendors SET name=?, gstin=?, pan=?, email=?, bank_name=?, account_no=?, ifsc=? WHERE id=?",
                           values + (vid,))
                db.log(g.user["username"], "Vendor updated", None, "%s (bank details may have changed)" % values[0])
            else:  # a new vendor starts as Pending -> an Admin must approve (onboarding workflow)
                db.execute("INSERT INTO vendors (name, gstin, pan, email, bank_name, account_no, ifsc, status)"
                           " VALUES (?,?,?,?,?,?,?, 'Pending')", values)
                db.log(g.user["username"], "Vendor created", None, values[0] + " (pending approval)")
        except Exception:
            flash("A vendor with this GSTIN already exists.", "error")
            return render_template("vendor_form.html", vendor=f)
        flash("Vendor saved.", "ok")
        return redirect(url_for("vendors"))
    return render_template("vendor_form.html", vendor=vendor)


@app.route("/vendors/<int:vid>/status", methods=["POST"])
@roles_required("Admin")
def vendor_status(vid):
    status = request.form["status"]
    db.execute("UPDATE vendors SET status=? WHERE id=?", (status, vid))
    db.log(g.user["username"], "Vendor " + status.lower(), None, "Vendor id %d" % vid)
    return redirect(url_for("vendors"))


# ---------------- reports ----------------
REPORTS = {
    "ap-aging": ("AP aging report",
                 "SELECT invoice_number, vendor_name, invoice_date, total, status, "
                 "CAST(julianday('now') - julianday(invoice_date) AS INTEGER) AS age_days, "
                 "CASE WHEN julianday('now') - julianday(invoice_date) <= 30 THEN '0-30' "
                 "WHEN julianday('now') - julianday(invoice_date) <= 60 THEN '31-60' "
                 "WHEN julianday('now') - julianday(invoice_date) <= 90 THEN '61-90' ELSE '90+' END AS bucket "
                 "FROM invoices WHERE status NOT IN ('Paid','Rejected','Exception') ORDER BY age_days DESC"),
    "invoice-status": ("Invoice status report",
                       "SELECT id, invoice_number, vendor_name, invoice_date, total, status, match_type, uploaded_at "
                       "FROM invoices ORDER BY id"),
    "exceptions": ("Exception report",
                   "SELECT id, invoice_number, vendor_name, total, errors FROM invoices WHERE status='Exception' ORDER BY id"),
    "gst": ("GST / tax report",
            "SELECT invoice_number, vendor_name, vendor_gstin, subtotal, cgst, sgst, igst, tax, total, status "
            "FROM invoices WHERE status IN ('Pending Approval','Approved','Payment Requested','Paid') ORDER BY invoice_date"),
    "audit": ("Audit log",
              "SELECT ts, user, action, invoice_id, detail FROM audit_logs ORDER BY id DESC"),
}


def csv_response(filename, columns, rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([r[c] for c in columns])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=" + filename})


@app.route("/reports")
def reports_index():
    return render_template("reports.html", reports=REPORTS, name=None, rows=[], columns=[], title="")


@app.route("/reports/<name>")
def report(name):
    if name not in REPORTS:
        abort(404)
    title, sql = REPORTS[name]
    rows = db.query(sql)
    columns = rows[0].keys() if rows else []
    return render_template("reports.html", reports=REPORTS, name=name, rows=rows, columns=columns, title=title)


@app.route("/reports/<name>.csv")
def report_csv(name):
    if name not in REPORTS:
        abort(404)
    rows = db.query(REPORTS[name][1])
    columns = list(rows[0].keys()) if rows else []
    return csv_response(name + ".csv", columns, rows)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
