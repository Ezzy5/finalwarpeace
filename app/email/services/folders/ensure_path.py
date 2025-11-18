# app/email/services/folders/ensure_path.py
from .get_namespace import get_namespace
from .get_delimiter import get_delimiter
from .split_any import split_any
from .folder_exists import folder_exists
from .create_single import create_single_folder

def _join(parts, delim): return delim.join(p for p in parts if p and str(p).strip())

def ensure_folder_path(imap, raw_path: str) -> dict:
    """
    Ensure a nested mailbox path exists. Accepts user path with '/' or '.'.
    Strategy:
      1) Detect delimiter (NAMESPACE -> LIST).
      2) Try to create at the exact path.
      3) If the FIRST SEGMENT fails to create and isn't INBOX, retry with INBOX/<delim>/<path>.
    Returns { ok, created:[...], delimiter, full_path, error? }.
    """
    if not raw_path or not raw_path.strip():
        return {"ok": False, "created": [], "delimiter": ".", "full_path": "", "error": "Empty folder name"}

    ns = get_namespace(imap)
    delim = (ns and ns.get("delim")) or get_delimiter(imap) or "."
    base_parts = split_any(raw_path)
    if not base_parts:
        return {"ok": False, "created": [], "delimiter": delim, "full_path": "", "error": "Invalid folder path"}

    # Helper: try creating the full path for given parts
    def _attempt(parts: list[str]):
        created = []
        built = []
        first_create_failed = False
        first_error = None

        for i, seg in enumerate(parts):
            built.append(seg)
            cur = _join(built, delim)

            # Never attempt to CREATE INBOX itself
            if seg.upper() == "INBOX":
                continue

            if folder_exists(imap, cur):
                continue

            ok, detail = create_single_folder(imap, cur)
            if not ok:
                if i == 0 and seg.upper() != "INBOX":
                    first_create_failed = True
                    first_error = detail or f'Failed to create "{cur}"'
                    break
                return {"ok": False, "created": created, "delimiter": delim, "full_path": _join(parts, delim),
                        "error": detail or f'Failed to create "{cur}"'}
            created.append(cur)

        return {"ok": True, "created": created, "delimiter": delim, "full_path": _join(parts, delim),
                "first_create_failed": first_create_failed, "first_error": first_error}

    # 1) Try exactly as requested
    res = _attempt(base_parts)
    if res.get("ok"):
        # Strip helper fields before returning
        res.pop("first_create_failed", None)
        res.pop("first_error", None)
        return res

    # 2) If first segment failed (top-level CREATE blocked), retry under INBOX
    if res.get("first_create_failed") and base_parts[0].upper() != "INBOX":
        inbox_parts = ["INBOX"] + base_parts
        res2 = _attempt(inbox_parts)
        res2.pop("first_create_failed", None)
        res2.pop("first_error", None)
        if res2.get("ok"):
            return res2
        # If retry also failed, return the more specific error
        return res2

    # Otherwise return the original error
    res.pop("first_create_failed", None)
    res.pop("first_error", None)
    return res
