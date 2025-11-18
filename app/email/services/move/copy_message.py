# app/email/services/move/copy_message.py
from .quote import quote_folder

def copy_message(imap, uid: str, dest_folder: str) -> bool:
    """
    UID COPY to destination folder.
    """
    try:
        typ, _ = imap.uid("COPY", uid, quote_folder(dest_folder))
        return typ == "OK"
    except Exception:
        return False
