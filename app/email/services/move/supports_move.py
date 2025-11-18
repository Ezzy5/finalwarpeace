# app/email/services/move/supports_move.py
def server_supports_move(imap) -> bool:
    """
    Check if the server advertises the MOVE capability (RFC 6851).
    """
    try:
        caps = imap.capabilities  # e.g. a set like {b'IMAP4REV1', b'MOVE', ...}
        return any(c.upper() == b"MOVE" for c in caps)
    except Exception:
        return False
