# app/email/services/move/mark_deleted.py
def mark_deleted(imap, uid: str) -> bool:
    """
    Mark message as \Deleted using UID STORE.
    """
    try:
        typ, _ = imap.uid("STORE", uid, "+FLAGS.SILENT", r"(\Deleted)")
        return typ == "OK"
    except Exception:
        return False
