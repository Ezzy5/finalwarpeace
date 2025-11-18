# app/email/routes/folder_delete.py
from __future__ import annotations
from flask import request, jsonify, abort
from flask_login import login_required, current_user
import imaplib

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_imap
from app.email.services.mailbox import list_folders_tree

SPECIAL_LAST_SEG = {
    "INBOX", "SENT", "SENT ITEMS", "SENT MAIL", "DRAFTS",
    "SPAM", "JUNK", "TRASH", "BIN", "DELETED ITEMS",
    "ARCHIVE", "ALL MAIL"
}

def _is_gmail_root(path: str) -> bool:
    return path.startswith("[Gmail]") or path.startswith("[Google Mail]")

def _is_subfolder(path: str, delim: str) -> bool:
    return (delim in path) and (not _is_gmail_root(path))

def _is_protected(path: str, delim: str) -> bool:
    """Only allow deleting subfolders (never top-level specials or Gmail roots)."""
    if not path:
        return True
    if _is_gmail_root(path):
        return True
    # not a subfolder? (no delimiter) -> protected
    if delim not in path:
        return True
    # block deleting specials by last segment
    last = path.split(delim)[-1].strip().upper()
    if last in SPECIAL_LAST_SEG:
        return True
    # block exact INBOX.<special> roots (e.g., INBOX.Sent)
    parent = path.rsplit(delim, 1)[0]
    if parent.upper() == "INBOX" and last in SPECIAL_LAST_SEG:
        return True
    return False

def _q(mailbox: str) -> str:
    """Quote mailbox for IMAP SELECT."""
    return '"' + (mailbox or "").replace('"', r'\"') + '"'

def _select_mailbox(imap, mailbox: str, readonly: bool=True) -> bool:
    try:
        typ, _ = imap.select(_q(mailbox), readonly=readonly)
        if typ == "OK":
            return True
    except Exception:
        pass
    try:
        typ, _ = imap.select(mailbox, readonly=readonly)
        return typ == "OK"
    except Exception:
        return False

def _has_child_mailboxes(imap, path: str) -> bool:
    # Check for any direct/recursive children
    try:
        typ, data = imap.list(_q(path), "%")
        if typ == "OK" and data:
            # If LIST with "%" shows something other than self, we have children
            for ln in data:
                if not ln:
                    continue
                try:
                    txt = ln.decode(errors="ignore")
                except Exception:
                    txt = str(ln)
                # if a listed name begins with path + delimiter, it's a child
                # quick heuristic: if the quoted "path" appears and line isn't exactly the mailbox itself
                if path not in txt.strip('"'):
                    return True

        # try "*" as a fallback, more expensive / recursive
        typ2, data2 = imap.list(_q(path), "*")
        if typ2 == "OK" and data2:
            for ln in data2:
                if not ln:
                    continue
                try:
                    txt = ln.decode(errors="ignore")
                except Exception:
                    txt = str(ln)
                # child if it starts with path + delim (server-dependent parsing)
                if f'"{path}' in txt or f"{path}{'/'}" in txt or f"{path}{'.'}" in txt:
                    if path not in txt.strip('"'):
                        return True
    except Exception:
        # Be safe: if unsure, assume it has children -> block deletion
        return True
    return False

def _move_all_messages_to_parent(imap, path: str, parent: str) -> tuple[bool, str|None]:
    """Copy all mails from path -> parent, then delete originals in path."""
    if not _select_mailbox(imap, path, readonly=False):
        return False, "Cannot select folder for cleanup"
    typ, data = imap.uid("search", None, "ALL")
    if typ != "OK":
        return False, "Search failed"

    uids = (data and data[0].split()) if data and data[0] else []
    if not uids:
        return True, None

    # copy in batches
    for uid in uids:
        try:
            typ, _ = imap.uid("copy", uid, parent)
            if typ != "OK":
                return False, f"Copy failed for UID {uid.decode(errors='ignore')}"
        except imaplib.IMAP4.error as e:
            return False, f"Copy error: {e}"

    # mark deleted and expunge from source
    try:
        imap.uid("store", b",".join(uids), "+FLAGS.SILENT", r"(\Deleted)")
        imap.expunge()
    except imaplib.IMAP4.error as e:
        return False, f"Expunge failed: {e}"

    return True, None

@bp.post("/mail/folder/delete")
@login_required
def mail_folder_delete():
    data = request.get_json(silent=True) or {}
    acc_id = data.get("acc")
    path = (data.get("path") or "").strip()

    if not acc_id or not path:
        abort(400, description="Missing acc or path")

    # account ownership
    account = EmailConnection.query.filter_by(user_id=current_user.id, id=int(acc_id)).first()
    if not account:
        abort(404, description="Account not found")

    cfg = build_runtime_cfg(account)
    imap = open_imap(cfg)
    try:
        info = list_folders_tree(imap)
        delim = info.get("delim", "/")

        # enforce policy: only subfolders deletable
        if _is_protected(path, delim):
            return jsonify(ok=False, error='Only subfolders can be deleted (not system folders).'), 400

        # block if any sub-mailboxes exist
        if _has_child_mailboxes(imap, path):
            return jsonify(ok=False, error='Folder has subfolders. Delete subfolders first.'), 400

        # compute parent path
        parent = path.rsplit(delim, 1)[0] if delim in path else "INBOX"
        if parent.strip() == "":
            parent = "INBOX"

        # move messages to parent (their "original place")
        ok, err = _move_all_messages_to_parent(imap, path, parent)
        if not ok:
            return jsonify(ok=False, error=err or "Failed to move messages to parent"), 400

        # unsubscribe (best-effort)
        try:
            imap.unsubscribe(path)
        except Exception:
            pass

        # delete the now-empty mailbox
        typ, _ = imap.delete(path)
        if typ != "OK":
            return jsonify(ok=False, error=f'IMAP DELETE failed for "{path}"'), 400

        return jsonify(ok=True, deleted=path, moved_to=parent)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
