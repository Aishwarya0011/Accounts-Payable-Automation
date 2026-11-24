"""email_ingest.py - pulls invoice attachments from an email inbox (IMAP) into the system.

Set these environment variables, then run:  python email_ingest.py
    IMAP_HOST (default imap.gmail.com), IMAP_USER, IMAP_PASSWORD (for Gmail use an App Password)
Every unread email's PDF/JPG/PNG/TIFF attachment is saved and processed like a normal upload.
"""
import email
import imaplib
import os
from datetime import datetime

import workflow
from app import ALLOWED, UPLOAD_DIR


def fetch_invoices(host, user, password):
    mail = imaplib.IMAP4_SSL(host)
    mail.login(user, password)
    mail.select("INBOX")
    _, ids = mail.search(None, "UNSEEN")  # unread emails only (fetching marks them as read)
    count = 0
    for num in ids[0].split():
        _, data = mail.fetch(num, "(RFC822)")
        message = email.message_from_bytes(data[0][1])
        for part in message.walk():
            name = part.get_filename()
            if name and name.rsplit(".", 1)[-1].lower() in ALLOWED:
                path = os.path.join(UPLOAD_DIR, datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + os.path.basename(name))
                with open(path, "wb") as f:
                    f.write(part.get_payload(decode=True))
                workflow.process_invoice(path, os.path.basename(name), "email-ingest")
                count += 1
    mail.logout()
    return count


if __name__ == "__main__":
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    user, password = os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASSWORD")
    if not (user and password):
        print("Set IMAP_USER and IMAP_PASSWORD first (see the top of this file).")
    else:
        print("%d invoice(s) imported from email." % fetch_invoices(host, user, password))
