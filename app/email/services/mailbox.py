# app/email/services/mailbox.py
from __future__ import annotations

import re
import imaplib
import email
from email.message import Message
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from typing import Optional

# --------------------
# Small helpers
# --------------------

def _decode(s: Optional[str]) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s

def _quote_mailbox(name: str) -> str:
    safe = (name or "").replace("\\", "\\\\").replace('"', r'\"')
    return f'"{safe}"'

def _select_ok(imap, mailbox: str, readonly: bool = True) -> bool:
    # Try raw select first
    try:
        typ, _ = imap.select(mailbox, readonly=readonly)
        if typ == "OK":
            return True
    except Exception:
        pass
    # Then quoted (handles spaces, brackets, slashes, etc.)
    try:
        typ, _ = imap.select(_quote_mailbox(mailbox), readonly=readonly)
        return typ == "OK"
    except Exception:
        return False

def _imap_since_date(days: int) -> str:
    # IMAP date format: DD-Mon-YYYY
    t = datetime.utcnow() - timedelta(days=max(0, days))
    return t.strftime("%d-%b-%Y")

# --------------------
# LIST parsing / tree
# --------------------

# Typical line:  (\HasNoChildren) "/" "INBOX/Sent"
_LIST_RE = re.compile(r'^\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]+)"\s+(?P<name>.+)$')

def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    return name

def _pretty_from_flags_and_name(flags: set[str], delim: str, name: str) -> str:
    """Human label hint (final placement handled later)."""
    upper = name.upper()
    # Gmail namespace
    if name.startswith("[Gmail]/") or name.startswith("[Google Mail]/"):
        tail = name.split("/", 1)[1]
        mapping = {
            "Sent Mail": "Sent",
            "Spam": "Spam",
            "Trash": "Trash",
            "Drafts": "Drafts",
            "All Mail": "All Mail",
            "Starred": "Starred",
            "Important": "Important",
        }
        return mapping.get(tail, tail)

    # Flags-based
    f = {x.capitalize() for x in flags}
    if "Sent" in f: return "Sent"
    if "Trash" in f: return "Trash"
    if "Junk" in f or "Spam" in f: return "Spam"
    if "Drafts" in f: return "Drafts"
    if "Archive" in f: return "Archive"

    # INBOX and children
    if upper == "INBOX":
        return "Inbox"
    prefix = f"INBOX{delim}"
    if name.startswith(prefix):
        rest = name[len(prefix):]
        return "Inbox › " + " › ".join(rest.split(delim))

    # Generic
    parts = name.split(delim)
    return " › ".join(parts) if len(parts) > 1 else name

def list_folders_tree(imap_conn):
    """
    Returns: {"tree": [nodes], "delim": "<delimiter>"}
    node = { "full": "<server path>", "label": "Human Label", "children": [...] }

    Rules:
      - Robust LIST (tries several patterns)
      - Promote special folders (Inbox, Sent, Drafts, Spam, Trash, Archive, All Mail) to TOP LEVEL
      - Subfolders of a special go under that special
      - Other INBOX.* (non-special) go under Inbox
      - **Never** show any special or its subtree under Inbox (no duplicates)
    """
    # 1) Collect raw LIST lines from multiple patterns
    combos = [
        ("", "*"), ("", "%"),
        ("INBOX", "*"), ("INBOX", "%"),
        (None, None),  # bare LIST
    ]
    lines = []
    for ref, pat in combos:
        try:
            if ref is None and pat is None:
                typ, d = imap_conn.list()
            else:
                typ, d = imap_conn.list(ref or "", pat or "*")
            if typ == "OK" and d:
                lines.extend([x for x in d if x])
        except Exception:
            continue

    if not lines:
        return {"tree": [{"full": "INBOX", "label": "Inbox", "children": []}], "delim": "/"}

    # 2) Parse lines -> flat with discovered delimiter
    flat = []
    delim = "/"
    for raw in lines:
        try:
            line = raw.decode(errors="replace")
        except Exception:
            continue

        m = _LIST_RE.match(line)
        if m:
            flags_str = (m.group("flags") or "").strip()
            delim = _clean_name(m.group("delim")) or delim
            name = _clean_name(m.group("name"))
            flags = set(t.lstrip("\\") for t in flags_str.split() if t)
        else:
            parts = line.split('"')
            if len(parts) >= 3:
                if parts[1]:
                    delim = parts[1]
                name = parts[-2]
                flags = set()
            else:
                continue

        if not name:
            continue

        label = _pretty_from_flags_and_name(flags, delim, name)
        flat.append({"full": name, "label": label, "flags": {x.upper() for x in flags}})

    # 3) Detect special-use folders and map to canonical labels
    specials = ["Inbox", "Sent", "Drafts", "Spam", "Trash", "Archive", "All Mail"]
    special_full = {k: None for k in specials}

    def up(s): return (s or "").upper()
    def is_under(prefix_full: str, name_full: str) -> bool:
        return bool(prefix_full) and name_full.startswith(prefix_full + delim)
    def last_seg(full: str) -> str:
        parts = [p for p in full.split(delim) if p]
        return parts[-1].upper() if parts else ""

    # Explicit Inbox
    for it in flat:
        if up(it["full"]) == "INBOX":
            special_full["Inbox"] = it["full"]

    # Gmail namespace
    for it in flat:
        f = it["full"]
        if f.startswith("[Gmail]/") or f.startswith("[Google Mail]/"):
            tail_u = up(f.split("/", 1)[1])
            if tail_u == "SENT MAIL": special_full["Sent"] = f
            elif tail_u == "DRAFTS": special_full["Drafts"] = f
            elif tail_u == "SPAM": special_full["Spam"] = f
            elif tail_u == "TRASH": special_full["Trash"] = f
            elif tail_u == "ALL MAIL": special_full["All Mail"] = f

    # Common last-segment names (top-level or INBOX.<x>)
    name_map = {
        "Sent":     {"SENT", "SENT ITEMS", "SENT MAIL"},
        "Drafts":   {"DRAFTS", "DRAFT"},
        "Spam":     {"SPAM", "JUNK"},
        "Trash":    {"TRASH", "BIN", "DELETED ITEMS"},
        "Archive":  {"ARCHIVE", "ARCHIVED"},
        "All Mail": {"ALL MAIL", "ALLMAIL"},
    }
    for it in flat:
        seg = last_seg(it["full"])
        for lbl, variants in name_map.items():
            if special_full[lbl] is None and seg in variants:
                special_full[lbl] = it["full"]

    # Flags fallback
    for it in flat:
        f = it["flags"]
        if special_full["Sent"]    is None and ("SENT"    in f): special_full["Sent"]    = it["full"]
        if special_full["Drafts"]  is None and ("DRAFTS"  in f): special_full["Drafts"]  = it["full"]
        if special_full["Trash"]   is None and ("TRASH"   in f): special_full["Trash"]   = it["full"]
        if special_full["Spam"]    is None and ("SPAM" in f or "JUNK" in f): special_full["Spam"] = it["full"]
        if special_full["Archive"] is None and ("Archive".upper() in f or "ARCHIVE" in f): special_full["Archive"] = it["full"]

    if special_full["Inbox"] is None:
        special_full["Inbox"] = "INBOX"

    # 4) Build hierarchy with top-level specials and NO duplicates under Inbox
    root: dict[str, dict] = {}

    def ensure_node(container: dict, full: str, label: str):
        if full not in container:
            container[full] = {"full": full, "label": label, "children": {}}
        return container[full]

    # Promote specials to top level
    for label in specials:
        full = special_full.get(label)
        if full:
            ensure_node(root, full, label)

    def insert_under(parent_node, parent_full, child_full):
        """Create nested nodes under parent based on path difference."""
        if not is_under(parent_full, child_full):
            return
        rel = child_full[len(parent_full) + len(delim):]
        parts = [p for p in rel.split(delim) if p]
        cursor = parent_node["children"]
        path_accum = [parent_full]
        for seg in parts:
            path_accum.append(seg)
            fp = delim.join(path_accum)
            node = ensure_node(cursor, fp, seg)
            cursor = node["children"]

    inbox_full = special_full["Inbox"]
    special_paths = {lbl: sp for lbl, sp in special_full.items() if sp}

    for it in flat:
        full = it["full"]

        # Skip exact specials (already top level)
        if any(full == sp for sp in special_paths.values()):
            continue

        # If it's under a special (e.g., INBOX.Sent.Foo) -> nest under that special
        placed = False
        for lbl, sp in special_paths.items():
            if lbl == "Inbox":
                continue  # handle Inbox branch separately
            if is_under(sp, full):
                parent = root.get(sp) or ensure_node(root, sp, lbl)
                insert_under(parent, sp, full)
                placed = True
                break
        if placed:
            continue

        # If it's under INBOX AND NOT the special or its subtree -> put under Inbox
        if inbox_full and is_under(inbox_full, full):
            # Do not place any special or its subtree under Inbox
            if any(full == sp or is_under(sp, full) for lbl, sp in special_paths.items() if lbl != "Inbox"):
                continue
            parent = root.get(inbox_full) or ensure_node(root, inbox_full, "Inbox")
            insert_under(parent, inbox_full, full)
            continue

        # Outside INBOX and not under any special -> top level by last segment
        ensure_node(root, full, full.split(delim)[-1])

    # dict -> sorted list
    def dict_to_list(d: dict) -> list[dict]:
        items = []
        order = {"Inbox": 0, "Sent": 1, "Drafts": 2, "Spam": 3, "Trash": 4, "Archive": 5, "All Mail": 6}
        for _, v in d.items():
            children = dict_to_list(v["children"])
            items.append({"full": v["full"], "label": v["label"], "children": children})
        items.sort(key=lambda n: (order.get(n["label"], 100), n["label"].lower()))
        return items

    tree = dict_to_list(root)
    return {"tree": tree, "delim": delim}

# --------------------
# Message listing
# --------------------

def list_messages(
    imap_conn,
    folder: str = "INBOX",
    q: str | None = None,
    sort: str = "date_desc",   # or "date_asc"
    unread: bool = False,
    has_attach: bool = False,  # best-effort via BODYSTRUCTURE heuristic
    last7: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    """
    Return a lightweight list of messages for a folder (backward compatible signature).
    Filters/sort are optional; you can still call list_messages(imap, folder, limit=50).
    """
    # 1) SELECT safely (handles names with spaces/brackets)
    if not _select_ok(imap_conn, folder, readonly=True):
        return []

    # 2) Build SEARCH criteria
    base_terms = ["ALL"]
    if unread:
        base_terms.append("UNSEEN")
    if last7:
        base_terms.extend(["SINCE", _imap_since_date(7)])

    def _uid_search_terms(terms: list[str]) -> set[bytes]:
        # Try UTF-8 charset first
        try:
            typ, data = imap_conn.uid("search", "CHARSET", "UTF-8", *terms)
            if typ == "OK" and data and data[0]:
                return set(data[0].split())
        except imaplib.IMAP4.error:
            pass
        typ, data = imap_conn.uid("search", None, *terms)
        if typ == "OK" and data and data[0]:
            return set(data[0].split())
        return set()

    # Query: SUBJECT or FROM union
    if q:
        uid_set = list(_uid_search_terms(base_terms + ["SUBJECT", q]).union(
                       _uid_search_terms(base_terms + ["FROM", q])))
    else:
        typ, data = imap_conn.uid("search", None, *base_terms)
        if typ != "OK" or not data or not data[0]:
            return []
        uid_set = list(data[0].split())

    if not uid_set:
        return []

    # Convert bytes->str
    uids = [u.decode(errors="ignore") if isinstance(u, (bytes, bytearray)) else str(u) for u in uid_set]

    # 3) Fetch INTERNALDATE for sorting (chunked)
    date_map: dict[str, Optional[datetime]] = {}

    def _fetch_internaldate_chunk(uid_list: list[str]):
        if not uid_list:
            return
        uid_batch = ",".join(uid_list)
        typ, resp = imap_conn.uid("fetch", uid_batch, "(INTERNALDATE)")
        if typ != "OK" or not resp:
            return
        for part in resp:
            if not isinstance(part, tuple) or not part[0]:
                continue
            header = part[0].decode(errors="ignore") if isinstance(part[0], (bytes, bytearray)) else str(part[0])
            m_uid = re.search(r'UID\s+(\d+)', header)
            m_date = re.search(r'INTERNALDATE\s+"([^"]+)"', header)
            if m_uid and m_date:
                uid = m_uid.group(1)
                try:
                    dt = parsedate_to_datetime(m_date.group(1))
                except Exception:
                    dt = None
                date_map[uid] = dt

    CHUNK = 500
    for i in range(0, len(uids), CHUNK):
        _fetch_internaldate_chunk(uids[i:i+CHUNK])

    def _uid_int(u: str) -> int:
        try:
            return int(u)
        except Exception:
            return 0

    if sort in ("date_desc", "date_asc"):
        reverse = (sort == "date_desc")
        uids.sort(key=lambda u: ((date_map.get(u) is None), date_map.get(u) or datetime.min, _uid_int(u)), reverse=reverse)
    else:
        # Fallback: UID numeric desc
        uids.sort(key=_uid_int, reverse=True)

    # Paging
    start = max(0, int(offset))
    end = max(start, start + int(limit))
    uids_page = uids[start:end]

    # 4) Build FETCH items (headers + optional BODYSTRUCTURE for attach heuristic)
    want_bs = bool(has_attach)
    fetch_items = "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)]"
    if want_bs:
        fetch_items += " BODYSTRUCTURE"
    fetch_items += ")"

    msgs = []
    for uid in uids_page:
        try:
            typ, msg_data = imap_conn.uid("fetch", uid, fetch_items)
            if typ != "OK" or not msg_data:
                continue

            raw_header = None
            bodystructure_text = ""
            for part in msg_data:
                if isinstance(part, tuple):
                    head = part[0]
                    body = part[1]
                    if isinstance(head, (bytes, bytearray)) and b"BODY[HEADER.FIELDS" in head:
                        raw_header = body
                    else:
                        if isinstance(body, (bytes, bytearray)):
                            bodystructure_text += body.decode(errors="ignore")
                elif isinstance(part, (bytes, bytearray)):
                    bodystructure_text += part.decode(errors="ignore")

            # Fallback: some servers return the header as the only tuple
            if not raw_header:
                tup = next((p for p in msg_data if isinstance(p, tuple)), None)
                if tup and isinstance(tup[1], (bytes, bytearray)):
                    raw_header = tup[1]
            if not raw_header:
                continue

            hdr = email.message_from_bytes(raw_header)
            subj = _decode(hdr.get("Subject"))
            from_ = _decode(hdr.get("From"))
            date_hdr = hdr.get("Date")
            mid = hdr.get("Message-ID")

            if has_attach:
                bs = bodystructure_text.lower()
                if ("\"attachment\"" not in bs) and ("filename" not in bs):
                    continue

            msgs.append({
                "uid": uid,
                "subject": subj or "(no subject)",
                "from": from_ or "",
                "date": date_hdr or "",
                "message_id": mid or "",
                "preview": None,
            })
        except Exception:
            continue

    return msgs

# --------------------
# Read one message
# --------------------

def _walk_parts_with_ids_msg(msg: Message, prefix: str = ""):
    if not msg.is_multipart():
        yield (prefix or "1", msg)
        return
    for i, part in enumerate(msg.get_payload(), start=1):
        part_id = f"{prefix}.{i}" if prefix else str(i)
        yield (part_id, part)
        if part.is_multipart():
            for sub_id, sub_part in _walk_parts_with_ids_msg(part, part_id):
                yield (sub_id, sub_part)

def _build_message_dict(em: Message) -> dict:
    plain, html = None, None
    attachments = []
    for part_id, part in _walk_parts_with_ids_msg(em):
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        if filename:
            filename = _decode(filename)

        if filename or ("attachment" in disp):
            payload = part.get_payload(decode=True) or b""
            attachments.append({
                "part_id": part_id,
                "filename": filename or "attachment",
                "content_type": ctype or "application/octet-stream",
                "size": len(payload),
            })
        else:
            if ctype == "text/plain" and plain is None:
                try:
                    plain = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
                except Exception:
                    plain = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
            elif ctype == "text/html" and html is None:
                try:
                    html = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
                except Exception:
                    html = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")

    hdr = {
        "subject": _decode(em.get("Subject")),
        "from": _decode(em.get("From")),
        "to": _decode(em.get("To")),
        "cc": _decode(em.get("Cc")),
        "date": em.get("Date"),
        "message_id": em.get("Message-ID"),
    }
    return {"headers": hdr, "plain": plain, "html": html, "attachments": attachments}

def _uid_fetch_rfc822(imap, uid_str: str) -> Optional[bytes]:
    """Fetch RFC822 by UID, handling various server response shapes."""
    try:
        typ, data = imap.uid("fetch", uid_str, "(RFC822)")
        if typ != "OK" or not data:
            return None
        for part in data:
            if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
                return part[1]
        return None
    except Exception:
        return None

def _seq_fetch_rfc822(imap, seq_str: str) -> Optional[bytes]:
    """Fallback: fetch by sequence number."""
    try:
        typ, data = imap.fetch(seq_str, "(RFC822)")
        if typ != "OK" or not data:
            return None
        for part in data:
            if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
                return part[1]
        return None
    except Exception:
        return None

def _uid_search_by_mid(imap, mid: str) -> list[str]:
    """Search UID(s) by Message-ID."""
    if not mid:
        return []
    try:
        typ, data = imap.uid("search", "CHARSET", "UTF-8", "HEADER", "MESSAGE-ID", mid)
        if typ == "OK" and data and data[0]:
            return [u.decode(errors="ignore") for u in data[0].split()]
    except imaplib.IMAP4.error:
        pass
    typ, data = imap.uid("search", None, "HEADER", "MESSAGE-ID", mid)
    if typ == "OK" and data and data[0]:
        return [u.decode(errors="ignore") for u in data[0].split()]
    return []

def get_message(imap_conn, folder: str, uid: str, message_id: str | None = None):
    """
    Smart fetch:
      1) SELECT folder (quoted if needed)
      2) UID FETCH RFC822
      3) Fallback: FETCH by sequence number
      4) Fallback: UID SEARCH by Message-ID (if provided), then UID FETCH
    """
    if not _select_ok(imap_conn, folder, readonly=True):
        return None

    uid_str = uid if isinstance(uid, str) else str(uid)

    # 1) Try UID fetch
    raw = _uid_fetch_rfc822(imap_conn, uid_str)
    if raw:
        return _build_message_dict(email.message_from_bytes(raw))

    # 2) Fallback: treat given uid as sequence-number
    raw = _seq_fetch_rfc822(imap_conn, uid_str)
    if raw:
        return _build_message_dict(email.message_from_bytes(raw))

    # 3) Fallback: search by Message-ID (if available)
    if message_id:
        for cand in _uid_search_by_mid(imap_conn, message_id):
            raw = _uid_fetch_rfc822(imap_conn, cand)
            if raw:
                return _build_message_dict(email.message_from_bytes(raw))

    return None
