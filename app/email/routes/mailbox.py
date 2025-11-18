# app/email/routes/mailbox.py
from __future__ import annotations

import email
from email.message import Message
from typing import Optional, Tuple

from flask import request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_imap
from app.email.services.mailbox import list_folders_tree, list_messages, get_message
from app.email.routes._helpers import _is_spa_request
from app.email.services.folders.specials import resolve_specials


# -----------------------
# Small local utilities
# -----------------------

def _first_account() -> Optional[EmailConnection]:
    return EmailConnection.query.filter_by(user_id=current_user.id).first()

def _accounts_for_user():
    return EmailConnection.query.filter_by(user_id=current_user.id).all()

def _quote_mailbox(name: str) -> str:
    # Escape backslashes and double-quotes, then wrap in quotes.
    safe = (name or "").replace("\\", "\\\\").replace('"', r'\"')
    return f'"{safe}"'

def _select_ok(imap, mailbox: str, readonly: bool = True) -> bool:
    # Try raw first, then quoted
    try:
        typ, _ = imap.select(mailbox, readonly=readonly)
        if typ == "OK":
            return True
    except Exception:
        pass
    try:
        typ, _ = imap.select(_quote_mailbox(mailbox), readonly=readonly)
        return typ == "OK"
    except Exception:
        return False

def _walk_parts_with_ids(msg: Message, prefix: str = ""):
    if not msg.is_multipart():
        yield (prefix or "1", msg)
        return
    for i, part in enumerate(msg.get_payload(), start=1):
        part_id = f"{prefix}.{i}" if prefix else str(i)
        yield (part_id, part)
        if part.is_multipart():
            for sub_id, sub_part in _walk_parts_with_ids(part, part_id):
                yield (sub_id, sub_part)

def _parse_message_to_dict(em: Message) -> dict:
    # Build same shape used by templates
    def _decode_header(val: Optional[str]) -> str:
        if not val:
            return ""
        from email.header import decode_header, make_header
        try:
            return str(make_header(decode_header(val)))
        except Exception:
            return val

    plain, html = None, None
    attachments = []
    for part_id, part in _walk_parts_with_ids(em):
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        if filename:
            filename = _decode_header(filename)

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
        "subject": _decode_header(em.get("Subject")),
        "from": _decode_header(em.get("From")),
        "to": _decode_header(em.get("To")),
        "cc": _decode_header(em.get("Cc")),
        "date": em.get("Date"),
        "message_id": em.get("Message-ID"),
    }
    return {"headers": hdr, "plain": plain, "html": html, "attachments": attachments}

def _fetch_rfc822_by_uid(imap, folder: str, uid: str) -> Optional[bytes]:
    if not _select_ok(imap, folder, readonly=True):
        return None
    # Try UID fetch
    try:
        typ, data = imap.uid("fetch", uid, "(RFC822)")
        if typ == "OK" and data and isinstance(data[0], tuple) and data[0][1]:
            return data[0][1]
    except Exception:
        pass
    # Fallback: treat uid as sequence number
    try:
        typ, data = imap.fetch(uid, "(RFC822)")
        if typ == "OK" and data and isinstance(data[0], tuple) and data[0][1]:
            return data[0][1]
    except Exception:
        pass
    return None

def _search_uid_by_message_id(imap, folder: str, message_id: str) -> Optional[str]:
    if not message_id:
        return None
    if not _select_ok(imap, folder, readonly=True):
        return None
    # Try CHARSET UTF-8 then fallback
    for args in (("CHARSET", "UTF-8", "HEADER", "MESSAGE-ID", message_id),
                 (None, "HEADER", "MESSAGE-ID", message_id)):
        try:
            if args[0] is None:
                typ, data = imap.uid("search", None, *args[1:])
            else:
                typ, data = imap.uid("search", *args)
            if typ == "OK" and data and data[0]:
                uids = data[0].split()
                if uids:
                    return uids[-1].decode("utf-8", "ignore")
        except Exception:
            continue
    return None

def _label_for(folder_full: str, tree: list[dict], delim: str) -> str:
    if not folder_full:
        return "INBOX"
    stack = list(tree)
    while stack:
        n = stack.pop()
        if n.get("full") == folder_full:
            return n.get("label") or folder_full.split(delim)[-1]
        stack.extend(n.get("children") or [])
    return folder_full.split(delim)[-1] if delim in folder_full else folder_full


# -----------------------
# Routes
# -----------------------

@bp.get("/mail")
@login_required
def mailbox_home():
    acc_id = request.args.get("acc", type=int)
    account = (
        EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()
        if acc_id else _first_account()
    )
    if not account:
        panel_html = render_template(
            "email/mailbox.html",
            account=None,
            accounts=_accounts_for_user(),
            folders_tree=[],
            folder_delim="/",
            selected_folder="INBOX",
            selected_label="Inbox",
            messages=[],
            expand_path="",
        )
        return panel_html if _is_spa_request() else render_template("dashboard.html", initial_panel=panel_html)

    # Resolve real Inbox path and redirect to it (prevents None folder)
    cfg = build_runtime_cfg(account)
    imap = open_imap(cfg)
    try:
        specials = resolve_specials(imap, account.provider or "")
        inbox_real = specials.get("inbox") or "INBOX"
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return redirect(url_for("email.mailbox_folder", folder=inbox_real, acc=account.id))


@bp.get("/mail/folder/<path:folder>")
@login_required
def mailbox_folder(folder):
    acc_id  = request.args.get("acc", type=int)
    q       = request.args.get("q") or None
    sort    = request.args.get("sort", "date_desc")
    unread  = bool(request.args.get("unread"))
    has_att = bool(request.args.get("has_attach"))
    last7   = bool(request.args.get("last7"))
    expand  = request.args.get("expand") or ""

    account = (
        EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()
        if acc_id else _first_account()
    )
    if not account:
        flash("No connected email account.", "warning")
        return redirect(url_for("email.status"))

    # Ensure a concrete folder
    if not folder:
        cfg = build_runtime_cfg(account)
        imap = open_imap(cfg)
        try:
            specials = resolve_specials(imap, account.provider or "")
            folder = specials.get("inbox") or "INBOX"
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    cfg = build_runtime_cfg(account)
    imap = open_imap(cfg)
    try:
        tree_info = list_folders_tree(imap)
        folders_tree = tree_info["tree"]
        folder_delim = tree_info["delim"]

        messages = list_messages(
            imap,
            folder=folder,
            q=q,
            sort=sort,
            unread=unread,
            has_attach=has_att,
            last7=last7,
            limit=100,
            offset=0,
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    selected_label = _label_for(folder, folders_tree, folder_delim)

    panel_html = render_template(
        "email/mailbox.html",
        account=account,
        accounts=_accounts_for_user(),
        folders_tree=folders_tree,
        folder_delim=folder_delim,
        selected_folder=folder,
        selected_label=selected_label,
        messages=messages,
        expand_path=expand,
    )
    return panel_html if _is_spa_request() else render_template("dashboard.html", initial_panel=panel_html)


@bp.route("/mail/message/<path:folder>/<uid>", methods=["GET"])
@login_required
def mailbox_message(folder, uid):
    acc_id = request.args.get("acc", type=int)
    expand = request.args.get("expand", "")
    mid = request.args.get("mid")  # optional Message-ID fallback

    # 1) Resolve account strictly from ?acc= (do not silently switch accounts)
    account = None
    if acc_id:
        account = EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()
    if not account:
        # Show the panel, but with a clear None message state
        panel_html = render_template(
            "email/message.html",
            account=None,
            accounts=EmailConnection.query.filter_by(user_id=current_user.id).all(),
            folders_tree=[],
            folder_delim="/",
            selected_folder=folder or "INBOX",
            message=None,
            message_uid=str(uid),
            expand_path=expand,
        )
        return panel_html if _is_spa_request() else render_template("dashboard.html", initial_panel=panel_html)

    # 2) Load folders + resolve real folder path (so 'Sent' / 'Spam' labels work)
    folders_tree, folder_delim, msg, selected_folder = [], "/", None, folder
    cfg = build_runtime_cfg(account)
    imap = open_imap(cfg)
    try:
        tree_info = list_folders_tree(imap)
        folders_tree = tree_info.get("tree", [])
        folder_delim = tree_info.get("delim", "/")

        # Map common labels to provider’s real folders
        specials = resolve_specials(imap, account.provider or "")
        label_key = (folder or "").strip().lower()
        mapped_real = {
            "inbox":   specials.get("inbox")   or "INBOX",
            "sent":    specials.get("sent"),
            "drafts":  specials.get("drafts"),
            "spam":    specials.get("spam")    or specials.get("junk"),
            "trash":   specials.get("trash"),
            "archive": specials.get("archive"),
            "all mail": specials.get("all_mail") or specials.get("all") or specials.get("allmail"),
        }.get(label_key)

        real_folder = mapped_real or folder
        selected_folder = real_folder

        # 3) Fetch smart: UID → sequence → Message-ID search (if provided)
        msg = get_message(imap, real_folder, str(uid), message_id=mid)

        # Final courtesy fallback: if you clicked a label like 'Sent' but the server’s
        # path is different and mapping didn’t match for some reason, try the original.
        if msg is None and mapped_real and mapped_real != folder:
            msg = get_message(imap, folder, str(uid), message_id=mid)
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    panel_html = render_template(
        "email/message.html",
        account=account,
        accounts=EmailConnection.query.filter_by(user_id=current_user.id).all(),
        folders_tree=folders_tree,
        folder_delim=folder_delim,
        selected_folder=selected_folder or "INBOX",
        message=msg,
        message_uid=str(uid),
        expand_path=expand,
    )
    return panel_html if _is_spa_request() else render_template("dashboard.html", initial_panel=panel_html)
