"""extractor.py - read an invoice file (PDF / image) and pull out the fields.

Step 1: get text.  PDFs with real text -> pdfplumber.  Scanned pages and images -> Tesseract OCR.
Step 2: find the fields in that text with simple regular expressions (rule-based field identification).
Step 3 (optional): if GEMINI_API_KEY is set and fields are missing, ask Gemini to fill the gaps.
"""
import json
import os
import re

import pdfplumber
from PIL import Image, ImageSequence


# ---------- Step 1: file -> text ----------
def ocr_image(img):
    import pytesseract
    if os.environ.get("TESSERACT_CMD"):  # Windows: path to tesseract.exe if it is not on PATH
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    return pytesseract.image_to_string(img, config="--psm 6")  # psm 6 = read as lines of text (keeps table rows together)


def text_from_pdf(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text.strip()) < 20:  # no real text on the page -> it is a scan, so use OCR
                text = ocr_image(page.to_image(resolution=200).original)
            pages.append(text)
    return "\n".join(pages), len(pages)


def text_from_image(path):
    img = Image.open(path)
    pages = [ocr_image(frame.convert("RGB")) for frame in ImageSequence.Iterator(img)]  # TIFF can have many pages
    return "\n".join(pages), len(pages)


# ---------- Step 2: text -> fields ----------
def money(s):
    return float(s.replace(",", ""))


def to_iso(date_text):
    """Turn 2026-11-10 or 10/11/2026 into 2026-11-10."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", date_text)
    if m:
        return date_text
    m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", date_text)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return date_text


def first(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def parse_invoice(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    data = {
        "vendor_name": lines[0] if lines else "",  # vendor name is the first line of the invoice
        "invoice_number": first(r"Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-/]*)", text, re.I),
        "invoice_date": "",
        "vendor_gstin": first(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b", text),  # first GSTIN = vendor's
        "po_number": first(r"\b(PO-\d{3,})\b", text),
        "subtotal": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "tax": 0.0, "total": 0.0,
        "items": [],
    }
    raw_date = first(r"Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})", text, re.I)
    data["invoice_date"] = to_iso(raw_date) if raw_date else ""

    amount = r"[^\d\n]*([\d,]+\.\d{2})"
    v = first(r"Sub\s*Total" + amount, text, re.I)
    data["subtotal"] = money(v) if v else 0.0
    v = first(r"Grand\s*Total" + amount, text, re.I)
    data["total"] = money(v) if v else 0.0
    for tax_name in ("cgst", "sgst", "igst"):
        v = first(tax_name.upper() + r"[^\n]*?([\d,]+\.\d{2})\s*$", text, re.I | re.M)
        data[tax_name] = money(v) if v else 0.0
    data["tax"] = round(data["cgst"] + data["sgst"] + data["igst"], 2)

    # line items: "1  MS Angle 40x40   60   350.00   21,000.00"  ->  sr, description, qty, rate, amount
    row = re.compile(r"^\s*\d+\s+(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")
    for line in lines:
        m = row.match(line)
        if m:
            data["items"].append({"description": m.group(1).strip(), "qty": float(m.group(2)),
                                  "rate": money(m.group(3)), "amount": money(m.group(4))})
    return data


def confidence(data):
    """Share of the key fields we managed to find (shown on the dashboard as OCR accuracy)."""
    checks = [data["invoice_number"], data["invoice_date"], data["vendor_name"], data["vendor_gstin"],
              data["po_number"], data["subtotal"], data["tax"], data["total"], data["items"]]
    return round(100.0 * sum(1 for c in checks if c) / len(checks), 1)


# ---------- Step 3 (optional): Gemini fills gaps ----------
def ai_extract(text):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {}
    import requests
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
    prompt = ("Extract these fields from the invoice text and reply with JSON only: invoice_number, invoice_date "
              "(YYYY-MM-DD), vendor_name, vendor_gstin, po_number, subtotal, cgst, sgst, igst, total, and items "
              "(list of {description, qty, rate, amount}).\n\n" + text[:8000])
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        r = requests.post(url, json=body, timeout=30)
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:  # never let the AI step break the upload
        print("Gemini step skipped:", e)
        return {}


# ---------- main entry ----------
def extract_invoice(path):
    ext = path.rsplit(".", 1)[-1].lower()
    text, pages = text_from_pdf(path) if ext == "pdf" else text_from_image(path)
    data = parse_invoice(text)
    if confidence(data) < 100:  # something is missing -> let AI try (only if a key is configured)
        ai = ai_extract(text)
        for k, v in ai.items():
            if k in data and not data[k] and v:
                data[k] = v
        data["tax"] = round(data["cgst"] + data["sgst"] + data["igst"], 2)
    data["raw_text"] = text
    data["pages"] = pages
    data["confidence"] = confidence(data)
    return data
