# app/email/services/move/expunge.py
def expunge_mailbox(imap) -> bool:
    """
    EXPUNGE current mailbox (remove messages flagged \Deleted).
    """
    try:
        typ, _ = imap.expunge()
        return typ == "OK"
    except Exception:
        return False
