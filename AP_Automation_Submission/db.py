"""db.py - SQLite helpers, table definitions and demo (seed) data.

We use plain SQL (sqlite3) on purpose: every query in the project is easy to read and explain.
"""
import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ap.db")


def now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us use row["column_name"]
    return conn


def query(sql, args=(), one=False):
    """Run a SELECT. Returns a list of rows, or a single row/None when one=True."""
    conn = get_db()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run INSERT / UPDATE / DELETE. Returns the id of the inserted row."""
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def log(user, action, invoice_id=None, detail=""):
    """Every important action is written to audit_logs (the 'audit tracking' requirement)."""
    execute("INSERT INTO audit_logs (ts, user, action, invoice_id, detail) VALUES (?,?,?,?,?)",
            (now(), user, action, invoice_id, detail))


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, role TEXT);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY, name TEXT, gstin TEXT UNIQUE, pan TEXT, email TEXT,
    bank_name TEXT, account_no TEXT, ifsc TEXT, status TEXT DEFAULT 'Pending');

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY, po_number TEXT UNIQUE, vendor_id INTEGER, match_type TEXT DEFAULT '2-way');
CREATE TABLE IF NOT EXISTS po_items (
    id INTEGER PRIMARY KEY, po_id INTEGER, description TEXT, qty REAL, rate REAL);

CREATE TABLE IF NOT EXISTS grns (
    id INTEGER PRIMARY KEY, grn_number TEXT UNIQUE, po_id INTEGER);
CREATE TABLE IF NOT EXISTS grn_items (
    id INTEGER PRIMARY KEY, grn_id INTEGER, description TEXT, qty REAL);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY, filename TEXT, stored_path TEXT, pages INTEGER,
    invoice_number TEXT, invoice_date TEXT, vendor_id INTEGER, vendor_name TEXT, vendor_gstin TEXT,
    po_number TEXT, subtotal REAL, cgst REAL, sgst REAL, igst REAL, tax REAL, total REAL,
    status TEXT, match_type TEXT, errors TEXT, ocr_confidence REAL, raw_text TEXT,
    uploaded_by TEXT, uploaded_at TEXT, approved_at TEXT);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY, invoice_id INTEGER, description TEXT, qty REAL, rate REAL, amount REAL);

CREATE TABLE IF NOT EXISTS approval_rules (
    id INTEGER PRIMARY KEY, min_amount REAL, max_amount REAL, role TEXT, level INTEGER);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY, invoice_id INTEGER, level INTEGER, role TEXT,
    status TEXT, approver TEXT, comment TEXT, due_at TEXT, acted_at TEXT, escalated INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY, invoice_id INTEGER, amount REAL, status TEXT,
    requested_at TEXT, paid_at TEXT, reference TEXT);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, invoice_id INTEGER, detail TEXT);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    empty = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    conn.close()
    if empty:
        seed()


def reset_db():
    """Delete the database file and rebuild it with fresh demo data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()


def seed():
    # --- users (one per role) ---
    for username, pwd, name, role in [
        ("clerk", "clerk123", "Asha (AP Clerk)", "Clerk"),
        ("manager", "manager123", "Ravi (Manager)", "Manager"),
        ("finance", "finance123", "Meera (Finance)", "Finance"),
        ("admin", "admin123", "Admin User", "Admin"),
    ]:
        execute("INSERT INTO users (username, password, name, role) VALUES (?,?,?,?)",
                (username, generate_password_hash(pwd), name, role))

    # --- vendor master (GSTINs are made-up but have the correct format) ---
    vendors = [
        ("Sharma Steel Traders", "29AABCS1234F1Z5", "AABCS1234F", "Active"),
        ("Apex Electronics Pvt Ltd", "29AAACA5678K1Z2", "AAACA5678K", "Active"),
        ("Bharat Fasteners", "27AAAFB9012M1Z8", "AAAFB9012M", "Active"),
        ("Nova Packaging", "29AAHCN3456P1Z4", "AAHCN3456P", "Pending"),  # waiting for onboarding approval
    ]
    vid = {}
    for i, (name, gstin, pan, status) in enumerate(vendors, start=1):
        vid[name] = execute(
            "INSERT INTO vendors (name, gstin, pan, email, bank_name, account_no, ifsc, status) VALUES (?,?,?,?,?,?,?,?)",
            (name, gstin, pan, name.split()[0].lower() + "@example.com", "State Bank of India",
             "3000000000%02d" % i, "SBIN0001234", status))

    # --- purchase orders and goods receipts ---
    def add_po(number, vendor, match_type, items):
        po_id = execute("INSERT INTO purchase_orders (po_number, vendor_id, match_type) VALUES (?,?,?)",
                        (number, vid[vendor], match_type))
        for desc, qty, rate in items:
            execute("INSERT INTO po_items (po_id, description, qty, rate) VALUES (?,?,?,?)", (po_id, desc, qty, rate))
        return po_id

    def add_grn(number, po_id, items):
        g = execute("INSERT INTO grns (grn_number, po_id) VALUES (?,?)", (number, po_id))
        for desc, qty in items:
            execute("INSERT INTO grn_items (grn_id, description, qty) VALUES (?,?,?)", (g, desc, qty))

    add_po("PO-1001", "Sharma Steel Traders", "2-way",
           [("MS Angle 40x40", 60, 350.00), ("MS Flat Bar 25x5", 40, 180.00)])

    po2 = add_po("PO-1002", "Apex Electronics Pvt Ltd", "3-way",
                 [("Control Panel PLC", 4, 20000.00), ("Proximity Sensor", 20, 1500.00)])
    add_grn("GRN-5001", po2, [("Control Panel PLC", 4), ("Proximity Sensor", 20)])

    add_po("PO-1003", "Bharat Fasteners", "2-way",
           [("Hex Bolt Grade A-%d" % n, 100, 10.00 + n) for n in range(1, 29)])  # 28 lines -> 2 page invoice

    po4 = add_po("PO-1004", "Apex Electronics Pvt Ltd", "3-way", [("Industrial Relay", 50, 400.00)])
    add_grn("GRN-5002", po4, [("Industrial Relay", 30)])  # only 30 received

    add_po("PO-1005", "Sharma Steel Traders", "2-way", [("MS Round Bar 12mm", 100, 100.00)])
    add_po("PO-1006", "Sharma Steel Traders", "2-way", [("MS Plate 10mm", 10, 2500.00)])

    # --- approval matrix: same level = parallel approval, next level starts after the level is complete ---
    for lo, hi, role, level in [
        (0, 50000, "Manager", 1),
        (50000.01, 200000, "Manager", 1), (50000.01, 200000, "Finance", 2),
        (200000.01, 1e12, "Manager", 1), (200000.01, 1e12, "Admin", 1), (200000.01, 1e12, "Finance", 2),
    ]:
        execute("INSERT INTO approval_rules (min_amount, max_amount, role, level) VALUES (?,?,?,?)",
                (lo, hi, role, level))
