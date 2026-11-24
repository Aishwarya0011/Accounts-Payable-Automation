"""generate_samples.py - makes the sample invoices in sample_invoices/ (run: python generate_samples.py)."""
import os
from datetime import date, timedelta

import pdfplumber
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_invoices")
BUYER = ("Demo Buyer Pvt Ltd", "29AABCD4321E1Z9")
V = {
    "sharma": ("Sharma Steel Traders", "12 Industrial Area, Bengaluru", "29AABCS1234F1Z5"),
    "apex": ("Apex Electronics Pvt Ltd", "45 Electronic City, Bengaluru", "29AAACA5678K1Z2"),
    "bharat": ("Bharat Fasteners", "7 MIDC Road, Pune", "27AAAFB9012M1Z8"),
    "quick": ("Quick Supplies", "3 Market Street, Bengaluru", "29AAAQQ1111Q1Z3"),
}


def money(x):
    return "{:,.2f}".format(x)


def make_invoice(filename, vendor, number, days_ago, po, items, tax_lines, total=None):
    """items = [(description, qty, rate)], tax_lines = [(label, amount)]"""
    name, addr, gstin = V[vendor]
    c = canvas.Canvas(os.path.join(OUT, filename), pagesize=A4)
    inv_date = (date.today() - timedelta(days=days_ago)).isoformat()
    y = 800
    c.setFont("Helvetica-Bold", 18); c.drawString(40, y, name); y -= 18
    c.setFont("Helvetica", 11); c.drawString(40, y, addr); y -= 16
    c.drawString(40, y, "GSTIN: " + gstin); y -= 30
    c.setFont("Helvetica-Bold", 14); c.drawString(40, y, "TAX INVOICE"); y -= 24
    c.setFont("Helvetica", 11)
    for line in ["Invoice No: " + number, "Invoice Date: " + inv_date, "PO Number: " + po,
                 "Bill To: " + BUYER[0], "Buyer GSTIN: " + BUYER[1]]:
        c.drawString(40, y, line); y -= 16
    y -= 14

    def header(y):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Sr"); c.drawString(70, y, "Description")
        c.drawRightString(360, y, "Qty"); c.drawRightString(440, y, "Rate"); c.drawRightString(540, y, "Amount")
        c.setFont("Helvetica", 11)
        return y - 18

    y = header(y)
    subtotal = 0
    for n, (desc, qty, rate) in enumerate(items, start=1):
        if y < 90:  # new page for long invoices
            c.showPage(); c.setFont("Helvetica", 11)
            y = 800; c.drawString(40, y, "Invoice %s - continued" % number); y -= 30
            y = header(y)
        amount = qty * rate
        subtotal += amount
        c.drawString(40, y, str(n)); c.drawString(70, y, desc)
        c.drawRightString(360, y, "%g" % qty); c.drawRightString(440, y, money(rate)); c.drawRightString(540, y, money(amount))
        y -= 22
    y -= 10
    tax = sum(a for _, a in tax_lines)
    rows = [("Sub Total:", subtotal)] + tax_lines + [("Grand Total:", total if total is not None else subtotal + tax)]
    for label, amt in rows:
        if y < 60:
            c.showPage(); c.setFont("Helvetica", 11); y = 800
        c.drawString(300, y, label); c.drawRightString(540, y, money(amt)); y -= 16
    c.save()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # 1. clean 2-way match, small amount -> Manager only
    make_invoice("01_clean_2way_sharma.pdf", "sharma", "INV-1001", 10, "PO-1001",
                 [("MS Angle 40x40", 60, 350.00), ("MS Flat Bar 25x5", 40, 180.00)],
                 [("CGST @ 9%", 2538.00), ("SGST @ 9%", 2538.00)])
    # 2. clean 3-way match -> Manager then Finance
    make_invoice("02_clean_3way_apex.pdf", "apex", "INV-2001", 35, "PO-1002",
                 [("Control Panel PLC", 4, 20000.00), ("Proximity Sensor", 20, 1500.00)],
                 [("CGST @ 9%", 9900.00), ("SGST @ 9%", 9900.00)])
    # 3. multi-page invoice, inter-state -> IGST
    items = [("Hex Bolt Grade A-%d" % n, 100, 10.00 + n) for n in range(1, 29)]
    make_invoice("03_multipage_bharat.pdf", "bharat", "BF-3001", 65, "PO-1003", items, [("IGST @ 18%", 12348.00)])
    # 4. duplicate of invoice 1
    make_invoice("04_duplicate_invoice.pdf", "sharma", "INV-1001", 10, "PO-1001",
                 [("MS Angle 40x40", 60, 350.00), ("MS Flat Bar 25x5", 40, 180.00)],
                 [("CGST @ 9%", 2538.00), ("SGST @ 9%", 2538.00)])
    # 5. wrong GST (IGST charged inside the same state, 10% rate)
    make_invoice("05_wrong_gst.pdf", "sharma", "INV-1005", 20, "PO-1005",
                 [("MS Round Bar 12mm", 100, 100.00)], [("IGST @ 10%", 1000.00)])
    # 6. 3-way mismatch: higher rate and more qty than received
    make_invoice("06_po_grn_mismatch.pdf", "apex", "INV-2002", 50, "PO-1004",
                 [("Industrial Relay", 50, 450.00)], [("CGST @ 9%", 2025.00), ("SGST @ 9%", 2025.00)])
    # 7. vendor not in master and PO does not exist
    make_invoice("07_unknown_vendor.pdf", "quick", "QS-77", 5, "PO-9999",
                 [("Packing Tape", 10, 50.00)], [("CGST @ 9%", 45.00), ("SGST @ 9%", 45.00)])
    # 8. scanned-style image (PNG) -> goes through Tesseract OCR
    make_invoice("_tmp_image.pdf", "sharma", "INV-1008", 100, "PO-1006",
                 [("MS Plate 10mm", 10, 2500.00)], [("CGST @ 9%", 2250.00), ("SGST @ 9%", 2250.00)])
    with pdfplumber.open(os.path.join(OUT, "_tmp_image.pdf")) as pdf:
        pdf.pages[0].to_image(resolution=200).original.save(os.path.join(OUT, "08_image_invoice.png"))
    os.remove(os.path.join(OUT, "_tmp_image.pdf"))
    print("Sample invoices created in", OUT)
