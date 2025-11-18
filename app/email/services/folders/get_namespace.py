# app/email/services/folders/get_namespace.py
import re

def get_namespace(imap):
    """
    Try to get personal namespace (prefix, delimiter) via NAMESPACE (RFC 2342).
    Returns dict {"prefix": str, "delim": str} or None if unavailable.
    """
    try:
        typ, data = imap.namespace()
        if typ != "OK" or not data:
            return None
        # Example bytes: b'((("", ".")) NIL NIL)'
        s = data[0].decode(errors="replace")
        # Capture the first personal namespace tuple ("prefix","delim")
        m = re.search(r'\(\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)\)', s)
        if m:
            return {"prefix": m.group(1), "delim": m.group(2)}
    except Exception:
        pass
    return None
