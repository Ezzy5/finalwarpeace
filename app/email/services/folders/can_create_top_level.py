# app/email/services/folders/can_create_top_level.py
import time, random, string
from .quote import quote_folder

def _rand_suffix(n=6):
    import secrets
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

def can_create_top_level(imap) -> bool:
    """
    Probe if server lets us create at top-level (not under INBOX).
    Creates a short-lived test mailbox; deletes it if successful.
    """
    test_name = f"__probe_{int(time.time())}_{_rand_suffix()}"
    try:
        typ, _ = imap.create(quote_folder(test_name))
        if typ != "OK":
            return False
        # cleanup
        imap.delete(quote_folder(test_name))
        return True
    except Exception:
        # best effort cleanup
        try: imap.delete(quote_folder(test_name))
        except Exception: pass
        return False
