# app/email/services/mail_ops.py
from __future__ import annotations
from typing import Optional, Tuple
import imaplib
from email.message import EmailMessage
import email.utils
import re

# ----------------- low-level helpers -----------------

def _quote_mailbox(name: str) -> str:
    if name is None:
        return '""'
    s = str(name).replace("\\", "\\\\").replace('"', r'\"')
    return f'"{s}"'

def _has_capability(imap, cap: str) -> bool:
    want = cap.upper()
    try:
        caps = getattr(imap, "capabilities", None)
        if not caps:
            try:
                imap._simple_command("CAPABILITY")
                imap._untagged_response(imap._get_line())
            except Exception:
                return False
            caps = getattr(imap, "capabilities", None) or ()
        norm = set((c.decode() if isinstance(c, (bytes, bytearray)) else str(c)).upper() for c in caps)
        return want in norm
    except Exception:
        return False

def _select_ok(imap, mailbox: str, readonly: bool = False) -> bool:
    try:
        typ, _ = imap.select(mailbox, readonly=readonly)
        if (typ or "").upper() == "OK":
            return True
    except Exception:
        pass
    try:
        typ, _ = imap.select(_quote_mailbox(mailbox), readonly=readonly)
        return (typ or "").upper() == "OK"
    except Exception:
        return False

def _uid_exists_in_mailbox(imap, mailbox: str, uid: str | int) -> bool:
    """Check if a UID still exists in a mailbox (selects it read-only)."""
    uid_s = str(uid)
    if not _select_ok(imap, mailbox, readonly=True):
        return False
    try:
        typ, data = imap.uid("search", None, "UID", uid_s)
        return (typ or "").upper() == "OK" and data and data[0] and uid_s.encode() in data[0].split()
    except Exception:
        return False

def _get_message_id_by_uid(imap, mailbox: str, uid: str | int) -> Optional[str]:
    """Fetch Message-ID header of a specific UID."""
    uid_s = str(uid)
    if not _select_ok(imap, mailbox, readonly=True):
        return None
    try:
        typ, data = imap.uid("fetch", uid_s, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if (typ or "").upper() != "OK" or not data:
            return None
        raw = b""
        for part in data:
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
                raw += part[1]
        text = raw.decode(errors="ignore")
        m = re.search(r"^Message-ID:\s*(.+)\r?$", text, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            return None
        return m.group(1).strip()
    except Exception:
        return None

def _message_id_exists_in_mailbox(imap, mailbox: str, message_id: str) -> bool:
    """Best-effort: search by header Message-ID in destination."""
    if not message_id:
        return False
    if not _select_ok(imap, mailbox, readonly=True):
        return False
    try:
        # Some servers support HEADER search; others don't. Try and ignore errors.
        typ, data = imap.uid("search", None, "HEADER", "MESSAGE-ID", message_id)
        return (typ or "").upper() == "OK" and data and data[0]
    except Exception:
        return False

def _ensure_mailbox_exists(imap, src_mailbox: str, dest_mailbox: str) -> bool:
    """Create destination if needed; reselect source R/W for further ops."""
    if _select_ok(imap, dest_mailbox, readonly=True):
        _select_ok(imap, src_mailbox, readonly=False)
        return True
    try:
        imap.create(_quote_mailbox(dest_mailbox))
    except Exception:
        pass
    ok = _select_ok(imap, dest_mailbox, readonly=True)
    _select_ok(imap, src_mailbox, readonly=False)
    return ok

# ----------------- public helpers used elsewhere -----------------

def append_draft(imap, drafts_mailbox: str, msg: EmailMessage, draft_uid: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    if not _select_ok(imap, drafts_mailbox, readonly=False):
        try:
            imap.create(_quote_mailbox(drafts_mailbox))
        except Exception:
            pass
        if not _select_ok(imap, drafts_mailbox, readonly=False):
            return False, None, f"Cannot select Drafts: {drafts_mailbox}"

    try:
        typ, _ = imap.append(_quote_mailbox(drafts_mailbox), r"(\Draft)", None, msg.as_bytes())
        if (typ or "").upper() != "OK":
            return False, None, "IMAP APPEND to Drafts failed"
    except imaplib.IMAP4.error as e:
        return False, None, f"APPEND error: {e}"

    try:
        _select_ok(imap, drafts_mailbox, readonly=False)
        typ, data = imap.uid("search", None, "ALL")
        if (typ or "").upper() == "OK" and data and data[0]:
            last_uid = data[0].split()[-1].decode("utf-8", errors="ignore")
            if draft_uid:
                try:
                    imap.uid("store", draft_uid, "+FLAGS.SILENT", r"(\Deleted)")
                    imap.expunge()
                except Exception:
                    pass
            return True, last_uid, None
    except Exception:
        pass
    return True, None, None

def append_sent_copy(imap, sent_mailbox: str, msg: EmailMessage) -> Tuple[bool, Optional[str]]:
    if not _select_ok(imap, sent_mailbox, readonly=False):
        try:
            imap.create(_quote_mailbox(sent_mailbox))
        except Exception:
            pass
        if not _select_ok(imap, sent_mailbox, readonly=False):
            return False, f"Cannot select Sent: {sent_mailbox}"

    try:
        typ, _ = imap.append(_quote_mailbox(sent_mailbox), None, None, msg.as_bytes())
        if (typ or "").upper() != "OK":
            return False, "IMAP APPEND to Sent failed"
    except imaplib.IMAP4.error as e:
        return False, f"APPEND error: {e}"
    return True, None

# ----------------- the important one: MOVE without duplicates -----------------

def move_to_mailbox(imap, from_mailbox: str, uid: str | int, to_mailbox: str) -> Tuple[bool, Optional[str]]:
    """
    Move a message safely, avoiding duplicates even if the request triggers twice.

    Strategy:
      1) Ensure source selected R/W and destination exists (create if needed).
      2) Try UID MOVE (quoted). If success -> done.
      3) If not OK, check if source UID still exists; if it's already gone -> done.
      4) Try UID MOVE (raw dest). Same post-check.
      5) If still present, get Message-ID; if identical Message-ID already in dest -> just delete source.
      6) Else COPY to dest, then delete from source and EXPUNGE.
    """
    uid_s = str(uid)

    # Source must be R/W for MOVE or STORE/EXPUNGE
    if not _select_ok(imap, from_mailbox, readonly=False):
        return False, f"Cannot select source: {from_mailbox}"

    # Ensure destination exists
    if not _ensure_mailbox_exists(imap, from_mailbox, to_mailbox):
        return False, f"Cannot create/select dest: {to_mailbox}"

    dest_q = _quote_mailbox(to_mailbox)

    # 1) Try UID MOVE if supported
    if _has_capability(imap, "MOVE"):
        try:
            typ, _ = imap.uid("MOVE", uid_s, dest_q)
            if (typ or "").upper() == "OK":
                return True, None
            # Post-check: if the UID disappeared from source, it's a success
            if not _uid_exists_in_mailbox(imap, from_mailbox, uid_s):
                return True, None
            # Retry without quotes once
            typ, _ = imap.uid("MOVE", uid_s, to_mailbox)
            if (typ or "").upper() == "OK":
                return True, None
            if not _uid_exists_in_mailbox(imap, from_mailbox, uid_s):
                return True, None
        except imaplib.IMAP4.error:
            # If the first MOVE partially worked, the UID may already be gone:
            if not _uid_exists_in_mailbox(imap, from_mailbox, uid_s):
                return True, None
            # else fall through to COPY
            pass

    # 2) Fallback: COPY + delete, but avoid duplicate COPY
    #    Check by Message-ID if one is already in dest
    msg_id = _get_message_id_by_uid(imap, from_mailbox, uid_s)
    if msg_id and _message_id_exists_in_mailbox(imap, to_mailbox, msg_id):
        # It's already there; just delete from source
        try:
            typ, _ = imap.uid("STORE", uid_s, "+FLAGS.SILENT", r"(\Deleted)")
            if (typ or "").upper() != "OK":
                return False, "STORE \\Deleted failed"
            imap.expunge()
            return True, None
        except imaplib.IMAP4.error as e:
            return False, str(e)

    # Not in dest yet → do COPY + delete
    try:
        typ, _ = imap.uid("COPY", uid_s, dest_q)
        if (typ or "").upper() != "OK":
            # Retry raw dest once
            typ, _ = imap.uid("COPY", uid_s, to_mailbox)
            if (typ or "").upper() != "OK":
                return False, f"COPY {uid_s} -> {to_mailbox} failed"

        typ, _ = imap.uid("STORE", uid_s, "+FLAGS.SILENT", r"(\Deleted)")
        if (typ or "").upper() != "OK":
            return False, "STORE \\Deleted failed"

        imap.expunge()
        return True, None
    except imaplib.IMAP4.error as e:
        return False, str(e)
