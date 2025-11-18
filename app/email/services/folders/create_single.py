# app/email/services/folders/create_single.py
from .quote import quote_folder

def create_single_folder(imap, full_name: str) -> tuple[bool, str]:
    """
    Create a single-level mailbox (no recursion).
    Returns (ok, detail). Treats "already exists" as ok=True.
    """
    try:
        typ, data = imap.create(quote_folder(full_name))
        if typ == "OK":
            return True, "OK"

        detail = _detail_text(data)
        if _is_already_exists(detail) or folder_exists_safe(imap, full_name):
            return True, "EXISTS"

        return False, detail or "CREATE failed"
    except Exception as e:
        return False, f"EXC: {e}"

def folder_exists_safe(imap, full_name: str) -> bool:
    try:
        typ, data = imap.list("", quote_folder(full_name))
        return typ == "OK" and bool(data and any(d for d in data))
    except Exception:
        return False

def _detail_text(data) -> str:
    if not data:
        return ""
    try:
        if isinstance(data[0], (bytes, bytearray)):
            return data[0].decode(errors="replace")
        return str(data)
    except Exception:
        return str(data)

def _is_already_exists(detail: str) -> bool:
    if not detail:
        return False
    up = detail.upper()
    # Common server phrasings
    return ("ALREADY" in up and "EXIST" in up) or ("MAILBOX EXISTS" in up) or ("ALREADYEXISTS" in up)
