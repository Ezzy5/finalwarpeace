# app/email/services/folders/folder_exists.py
from .quote import quote_folder

def folder_exists(imap, full_name: str) -> bool:
    """
    Return True if folder exists on server.
    INBOX is special and should be treated as existing.
    """
    if not full_name:
        return False
    if full_name.upper() == "INBOX":
        return True  # never try to create INBOX

    try:
        typ, data = imap.list("", quote_folder(full_name))
        if typ != "OK":
            return False
        if not data:
            return False

        # Some servers return case-variant names; be lenient.
        target = full_name.upper()
        for raw in data:
            if not raw:
                continue
            s = raw.decode(errors="replace")
            # The name is usually the last "quoted" token
            if '"' in s:
                name = s.rsplit('"', 2)[-2]  # between last two quotes
                if name.upper() == target:
                    return True
        # If we got any line at all for this pattern, assume exists
        return any(d for d in data)
    except Exception:
        return False
