# app/email/services/folders/specials.py
from __future__ import annotations
from typing import Dict, Optional, Tuple, List
import re

# ---------- low-level LIST helpers ----------

def _ensure_text(b) -> str:
    return b.decode(errors="ignore") if isinstance(b, (bytes, bytearray)) else str(b)

def _detect_delimiter(data: List[bytes]) -> str:
    for row in data:
        txt = _ensure_text(row)
        m = re.search(r'\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]+)"\s+', txt)
        if m:
            return m.group("delim") or "/"
    return "/"

def _extract_name_from_list_line(line: str) -> Optional[str]:
    qs = re.findall(r'"([^"]+)"', line)
    if qs:
        return qs[-1]
    parts = line.strip().split()
    return parts[-1] if parts else None

def _imap_list_all(imap) -> Tuple[str, List[str]]:
    attempts = [
        lambda: imap.list(),
        lambda: imap.list(pattern="*"),
        lambda: imap.list("", "*"),
    ]
    for call in attempts:
        try:
            typ, data = call()
            if typ == "OK" and data:
                delim = _detect_delimiter(data)
                lines = [_ensure_text(x) for x in data if x]
                return delim or "/", lines
        except Exception:
            pass
    return "/", []

def _index_mailboxes(imap) -> Tuple[str, List[str]]:
    delim, lines = _imap_list_all(imap)
    names: List[str] = []
    for ln in lines:
        nm = _extract_name_from_list_line(ln)
        if nm:
            names.append(nm)
    return delim or "/", names

# ---------- public: choose one canonical folder per special ----------

def resolve_specials(imap, provider_hint: str = "") -> Dict[str, str]:
    """
    Choose a single canonical mailbox for each special.
    We prefer provider-native names first (e.g. [Gmail]/Sent Mail), then common aliases,
    then INBOX.<alias>, finally plain fallbacks.
    """
    _delim, names = _index_mailboxes(imap)
    NU = {n.upper(): n for n in names}

    PREFER = {
        "inbox":  ["INBOX", "Inbox"],
        "sent":   ["[Gmail]/Sent Mail", "[Google Mail]/Sent Mail", "Sent Mail", "Sent Items", "Sent", "INBOX.Sent"],
        "drafts": ["[Gmail]/Drafts", "[Google Mail]/Drafts", "Drafts", "INBOX.Drafts"],
        "spam":   ["[Gmail]/Spam", "[Google Mail]/Spam", "Spam", "Junk", "INBOX.Spam", "INBOX.Junk"],
        "trash":  ["[Gmail]/Trash", "[Google Mail]/Trash", "Trash", "Bin", "Deleted Items", "INBOX.Trash"],
        "archive":["[Gmail]/All Mail", "[Google Mail]/All Mail", "All Mail", "Archive", "INBOX.Archive"],
    }

    out: Dict[str, str] = {}
    for key, prefs in PREFER.items():
        chosen = None
        for cand in prefs:
            if cand.upper() in NU:
                chosen = NU[cand.upper()]
                break
        if not chosen:
            chosen = prefs[-1]  # fallback string (even if not present on server)
        out[key] = chosen
    return out

def resolve_label_to_real(label: str, specials: Dict[str, str]) -> Optional[str]:
    """
    Map a friendly label ('Inbox','Sent','Drafts','Spam','Trash','Archive','All Mail')
    to the real server mailbox path as chosen by resolve_specials().
    """
    key = (label or "").strip().lower()
    aliases = {
        "inbox": "inbox",
        "sent": "sent",
        "sent mail": "sent",
        "sent items": "sent",
        "drafts": "drafts",
        "draft": "drafts",
        "spam": "spam",
        "junk": "spam",
        "trash": "trash",
        "bin": "trash",
        "deleted items": "trash",
        "archive": "archive",
        "all mail": "archive",  # we treat All Mail as Archive in the UI
    }
    mapped = aliases.get(key, key)
    return specials.get(mapped)

def resolve_real_to_label(full: str, specials: Dict[str, str]) -> str:
    """
    Best-effort inverse mapping: given a real server path, return a friendly label.
    """
    if not full:
        return ""
    f = full.lower()
    for lbl_key, real in specials.items():
        if real and real.lower() == f:
            return {
                "inbox": "Inbox",
                "sent": "Sent",
                "drafts": "Drafts",
                "spam": "Spam",
                "trash": "Trash",
                "archive": "Archive",
            }.get(lbl_key, full)
    return full

# ---------- public: normalize tree (dedupe + friendly labels) ----------

def normalize_top_level_labels(tree: List[dict], specials: Dict[str,str], delim: str) -> List[dict]:
    """
    Keep exactly one node per special at top-level with a friendly label.
    Hide ANY alias/duplicate for a special (including Inbox vs INBOX) anywhere in the tree.
    """
    chosen = {
        "Inbox":   specials.get("inbox"),
        "Sent":    specials.get("sent"),
        "Drafts":  specials.get("drafts"),
        "Spam":    specials.get("spam"),
        "Trash":   specials.get("trash"),
        "Archive": specials.get("archive"),
    }

    ALIASES = {
        "Inbox":   {"INBOX", "Inbox"},
        "Sent":    {"Sent", "Sent Mail", "Sent Items", "INBOX.Sent", "[Gmail]/Sent Mail", "[Google Mail]/Sent Mail"},
        "Drafts":  {"Drafts", "INBOX.Drafts", "[Gmail]/Drafts", "[Google Mail]/Drafts"},
        "Spam":    {"Spam", "Junk", "INBOX.Spam", "INBOX.Junk", "[Gmail]/Spam", "[Google Mail]/Spam"},
        "Trash":   {"Trash", "Bin", "Deleted Items", "INBOX.Trash", "[Gmail]/Trash", "[Google Mail]/Trash"},
        "Archive": {"Archive", "All Mail", "INBOX.Archive", "[Gmail]/All Mail", "[Google Mail]/All Mail"},
    }

    def is_alias_of(full: str, key: str) -> bool:
        fu = (full or "").upper()
        for a in ALIASES.get(key, set()):
            if fu == a.upper():
                return True
        return False

    def cleanse(nodes: List[dict]) -> List[dict]:
        out = []
        for n in nodes:
            full = n.get("full") or ""
            drop = False
            for key, chosen_full in chosen.items():
                if chosen_full and is_alias_of(full, key) and full.upper() != chosen_full.upper():
                    drop = True
                    break
            if drop:
                continue
            n["children"] = cleanse(n.get("children") or [])
            out.append(n)
        return out

    cleaned = cleanse(tree)

    # dedupe top-level by 'full' (case-insensitive)
    seen = set()
    top: List[dict] = []
    for n in cleaned:
        fu = (n.get("full") or "").upper()
        if fu in seen:
            continue
        seen.add(fu)
        top.append(n)

    # ensure chosen specials exist exactly once at top with friendly labels
    for key in ["Inbox","Sent","Drafts","Spam","Trash","Archive"]:
        full = chosen.get(key)
        if not full:
            continue
        full_u = full.upper()
        present = False
        for n in top:
            if (n.get("full") or "").upper() == full_u:
                n["label"] = key
                present = True
                break
        if not present:
            top.append({"full": full, "label": key, "children": []})

    # order system folders first
    order = {"inbox":0,"sent":1,"drafts":2,"spam":3,"trash":4,"archive":5}
    top.sort(key=lambda n: (order.get((n.get("label") or "").lower(), 99), (n.get("label") or "").lower()))
    return top
