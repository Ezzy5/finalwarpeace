# app/email/services/move/try_uid_move.py
from .quote import quote_folder

def try_uid_move(imap, uid: str, dest_folder: str) -> bool:
    """
    Attempt native UID MOVE. Returns True if OK, False if not supported or fails.
    """
    try:
        tag = imap._new_tag()
        imap.send(f"{tag} UID MOVE {uid} {quote_folder(dest_folder)}\r\n".encode("utf-8"))
        typ, data = imap._command_complete("UID", tag)
        return typ == "OK"
    except Exception:
        return False
