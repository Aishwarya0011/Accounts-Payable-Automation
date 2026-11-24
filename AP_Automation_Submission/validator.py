"""validator.py - the Invoice Validation Engine and the PO Matching module."""
import re

from db import query

GSTIN_RE = re.compile(r"^(0[1-9]|[12][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
GST_SLABS = [0, 5, 12, 18, 28]   # allowed GST rates in %
BUYER_STATE_CODE = "29"          # our (buyer) company is in Karnataka -> same state = CGST+SGST, else IGST
TOLERANCE = 1.0                  # rupees of rounding difference we accept
PRICE_TOLERANCE = 0.02           # invoice rate may be up to 2% above the PO rate


def valid_gstin(gstin):
    return bool(GSTIN_RE.match(gstin or ""))


def validate(inv, items):
    """Returns a list of error messages. Empty list = invoice is clean."""
    errors = []

    # 1. mandatory fields
    for field, label in [("invoice_number", "Invoice number"), ("invoice_date", "Invoice date"),
                         ("vendor_name", "Vendor name"), ("vendor_gstin", "Vendor GSTIN"),
                         ("po_number", "PO number"), ("total", "Total amount")]:
        if not inv[field]:
            errors.append("Mandatory field missing: " + label)
    if not items:
        errors.append("No line items found")

    # 2. duplicate invoice (same vendor GSTIN + same invoice number already exists)
    if inv["invoice_number"] and inv["vendor_gstin"]:
        dup = query("SELECT id FROM invoices WHERE invoice_number=? AND vendor_gstin=? AND id<>?",
                    (inv["invoice_number"], inv["vendor_gstin"], inv["id"]), one=True)
        if dup:
            errors.append("Duplicate invoice: %s from this vendor already exists (invoice #%d)"
                          % (inv["invoice_number"], dup["id"]))

    # 3. vendor master
    if inv["vendor_gstin"]:
        vendor = query("SELECT * FROM vendors WHERE gstin=?", (inv["vendor_gstin"],), one=True)
        if not vendor:
            errors.append("Vendor not found in vendor master (GSTIN %s)" % inv["vendor_gstin"])
        elif vendor["status"] != "Active":
            errors.append("Vendor is not approved yet (status: %s)" % vendor["status"])

    # 4. GST / tax
    if inv["vendor_gstin"] and not valid_gstin(inv["vendor_gstin"]):
        errors.append("Vendor GSTIN format is invalid: " + inv["vendor_gstin"])
    elif inv["vendor_gstin"]:
        same_state = inv["vendor_gstin"][:2] == BUYER_STATE_CODE
        if same_state and inv["igst"] > 0:
            errors.append("Same-state supply must have CGST + SGST, but IGST was charged")
        if not same_state and (inv["cgst"] > 0 or inv["sgst"] > 0):
            errors.append("Inter-state supply must have IGST, but CGST/SGST was charged")
    if inv["subtotal"] > 0:
        rate = inv["tax"] / inv["subtotal"] * 100
        if min(abs(rate - s) for s in GST_SLABS) > 0.3:
            errors.append("GST rate %.1f%% is not a valid slab (0/5/12/18/28)" % rate)
    if abs(inv["cgst"] - inv["sgst"]) > TOLERANCE:
        errors.append("CGST and SGST amounts should be equal")

    # 5. amounts
    line_sum = sum(i["amount"] for i in items)
    if items and abs(line_sum - inv["subtotal"]) > TOLERANCE:
        errors.append("Line items add up to %.2f but subtotal is %.2f" % (line_sum, inv["subtotal"]))
    if abs(inv["subtotal"] + inv["tax"] - inv["total"]) > TOLERANCE:
        errors.append("Subtotal + tax = %.2f but total is %.2f" % (inv["subtotal"] + inv["tax"], inv["total"]))
    for i in items:
        if abs(i["qty"] * i["rate"] - i["amount"]) > TOLERANCE:
            errors.append("Line '%s': qty x rate is not equal to amount" % i["description"])
    return errors


def norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def match_po(inv, items):
    """2-way match: invoice vs PO.  3-way match: invoice vs PO vs GRN (goods received).
    Which one is used is decided by the match_type stored on the PO.
    Returns (match_type, list_of_errors)."""
    if not inv["po_number"]:
        return "-", []  # already reported by the mandatory-field check
    po = query("SELECT * FROM purchase_orders WHERE po_number=?", (inv["po_number"],), one=True)
    if not po:
        return "-", ["PO %s not found" % inv["po_number"]]

    errors = []
    vendor = query("SELECT * FROM vendors WHERE gstin=?", (inv["vendor_gstin"],), one=True)
    if vendor and vendor["id"] != po["vendor_id"]:
        errors.append("PO %s belongs to a different vendor" % po["po_number"])

    po_items = {norm(r["description"]): r for r in query("SELECT * FROM po_items WHERE po_id=?", (po["id"],))}
    received = {}
    if po["match_type"] == "3-way":
        rows = query("SELECT gi.description AS d, SUM(gi.qty) AS q FROM grn_items gi "
                     "JOIN grns g ON g.id = gi.grn_id WHERE g.po_id=? GROUP BY gi.description", (po["id"],))
        received = {norm(r["d"]): r["q"] for r in rows}
        if not received:
            errors.append("3-way match needs a GRN but none exists for " + po["po_number"])

    for it in items:
        p = po_items.get(norm(it["description"]))
        if not p:
            errors.append("PO match: item '%s' is not on %s" % (it["description"], po["po_number"]))
            continue
        if it["qty"] > p["qty"]:
            errors.append("PO match: '%s' invoiced qty %g is more than PO qty %g" % (it["description"], it["qty"], p["qty"]))
        if it["rate"] > p["rate"] * (1 + PRICE_TOLERANCE):
            errors.append("PO match: '%s' rate %.2f is higher than PO rate %.2f" % (it["description"], it["rate"], p["rate"]))
        if po["match_type"] == "3-way" and received:
            got = received.get(norm(it["description"]), 0)
            if it["qty"] > got:
                errors.append("GRN match: '%s' invoiced qty %g but only %g received" % (it["description"], it["qty"], got))
    return po["match_type"], errors
