# app/email/services/sync.py
"""
Mailbox sync engine.
IMAP supports IDLE for push; POP3 uses polling.
"""
import email
from datetime import datetime


def sync_imap(conn, folder="INBOX", limit=50):
    """
    Fetch latest messages from an IMAP connection.
    Returns list of dicts with basic metadata.
    """
    conn.select(folder)
    typ, data = conn.search(None, "ALL")
    ids = data[0].split()
    latest_ids = ids[-limit:]

    messages = []
    for msg_id in latest_ids:
        typ, msg_data = conn.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        messages.append({
            "id": msg_id.decode(),
            "subject": msg.get("Subject"),
            "from": msg.get("From"),
            "date": msg.get("Date"),
        })
    return messages


def sync_pop3(conn, limit=50):
    """
    Fetch latest messages from a POP3 connection.
    """
    num_messages = len(conn.list()[1])
    start = max(1, num_messages - limit + 1)
    messages = []

    for i in range(start, num_messages + 1):
        resp, lines, octets = conn.retr(i)
        raw = b"\n".join(lines)
        msg = email.message_from_bytes(raw)
        messages.append({
            "id": str(i),
            "subject": msg.get("Subject"),
            "from": msg.get("From"),
            "date": msg.get("Date"),
        })
    return messages
