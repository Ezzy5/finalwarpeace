# app/email/services/folders/get_delimiter.py
def get_delimiter(imap) -> str:
    """
    Robustly detect hierarchy delimiter.
    Priority:
      1) If LIST shows an 'INBOX<delim>Something' line, use that quoted delim.
      2) Else use the first LIST "" "" delim.
      3) Else fallback "." (common) then "/".
    """
    # Try to find a line with INBOX children; this is the most reliable in practice.
    try:
        typ, data = imap.list("", "*")
        if typ == "OK" and data:
            for raw in data:
                if not raw:
                    continue
                line = raw.decode(errors="replace")
                # Typical line: (\HasNoChildren) "." "INBOX.Sent"
                if '"INBOX' in line or ' "INBOX' in line:
                    parts = line.split('"')
                    # expected pattern: (...flags...) "DELIM" "NAME"
                    if len(parts) >= 3 and parts[1]:
                        return parts[1]
    except Exception:
        pass

    # Fallback to LIST "" ""
    try:
        typ, data = imap.list("", "")
        if typ == "OK" and data and data[0]:
            line = data[0].decode(errors="replace")
            parts = line.split('"')
            if len(parts) >= 3 and parts[1]:
                return parts[1]
    except Exception:
        pass

    # Last resort: commonly "." on cPanel/Dovecot, "/" elsewhere
    return "."
