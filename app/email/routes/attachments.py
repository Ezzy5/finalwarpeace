# app/email/routes/attachments.py
from __future__ import annotations

import io
import mimetypes
import email
from email.header import decode_header, make_header

from flask import abort, send_file, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_imap


def _decode(s: str | None) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s or ""


def _walk_parts_with_ids(msg: email.message.Message, prefix: str = ""):
    """Yield (part_id, part) pairs matching the scheme used when listing attachments."""
    if not msg.is_multipart():
        yield (prefix or "1", msg)
        return
    i = 1
    for part in msg.get_payload():
        part_id = f"{prefix}.{i}" if prefix else str(i)
        yield (part_id, part)
        if part.is_multipart():
            for sub_id, sub_part in _walk_parts_with_ids(part, part_id):
                yield (sub_id, sub_part)
        i += 1


def _guess_download_meta(filename: str | None, content_type: str | None) -> tuple[str, str]:
    """
    Ensure we have a usable (name, mimetype).
    If no filename extension, try to append one from mimetypes.
    """
    ct = (content_type or "application/octet-stream").split(";")[0].strip() or "application/octet-stream"
    name = (filename or "attachment").strip() or "attachment"

    # If name has no extension, try guessing from mimetype
    if "." not in name:
        ext = mimetypes.guess_extension(ct) or ""
        if ext and not name.lower().endswith(ext.lower()):
            name = name + ext

    # If mimetype unknown, try guessing from filename
    if ct == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(name)
        if guessed:
            ct = guessed

    return name, ct


def _q(mailbox: str) -> str:
    """Quote mailbox for IMAP commands if not already quoted."""
    if mailbox.startswith('"') and mailbox.endswith('"'):
        return mailbox
    # Escape any embedded quotes per RFC
    safe = mailbox.replace('"', r'\"')
    return f'"{safe}"'


def _select_mailbox(imap, mailbox: str, readonly: bool = True) -> bool:
    """
    Try selecting mailbox with quoting fallbacks:
      1) quoted
      2) unquoted (some servers accept bare INBOX)
    """
    typ, _ = imap.select(_q(mailbox), readonly=readonly)
    if typ == "OK":
        return True
    typ, _ = imap.select(mailbox, readonly=readonly)
    return typ == "OK"


def _fetch_rfc822(imap, folder: str, uid: str | int) -> bytes | None:
    """Fetch full RFC822 bytes for a message in folder by UID (with fallback to sequence number)."""
    if not _select_mailbox(imap, folder, readonly=True):
        return None

    # UID as str
    u = str(uid)

    # Prefer UID fetch
    typ, data = imap.uid("fetch", u, "(RFC822)")
    if typ == "OK" and data and isinstance(data[0], (tuple, list)):
        return data[0][1]

    # Some servers return list like [ (b'123 (RFC822 {n}', bytes), b')' ]
    if typ == "OK" and data and len(data) >= 2 and isinstance(data[0], (tuple, list)):
        try:
            return data[0][1]
        except Exception:
            pass

    # Fallback: some servers misbehave on UID; try sequence number fetch
    typ, data = imap.fetch(u, "(RFC822)")
    if typ == "OK" and data and isinstance(data[0], (tuple, list)):
        return data[0][1]

    return None


def _find_part_by_id(msg: email.message.Message, target_id: str) -> email.message.Message | None:
    for part_id, part in _walk_parts_with_ids(msg):
        if part_id == target_id:
            return part
    return None


def _get_account_or_404(acc_id: int) -> EmailConnection:
    conn = EmailConnection.query.filter_by(user_id=current_user.id, id=int(acc_id)).first()
    if not conn:
        abort(404, description="Account not found")
    return conn


# Route with filename in the URL (used by your template)
@bp.route("/mail/attachment/<path:folder>/<uid>/<part_id>/<path:filename>")
@login_required
def download_attachment(folder: str, uid: str, part_id: str, filename: str):
    """
    Download an attachment by part_id. 'filename' in the URL is cosmetic;
    we derive the actual name/extension from MIME when possible.
    Requires query parameter: ?acc=<id>
    """
    acc = request.args.get("acc", type=int)
    if not acc:
        abort(400, description="Missing acc")

    conn = _get_account_or_404(acc)
    cfg = build_runtime_cfg(conn)
    imap = open_imap(cfg)

    try:
        raw = _fetch_rfc822(imap, folder, uid)
        if not raw:
            abort(404, description="Message not found")

        msg = email.message_from_bytes(raw)
        part = _find_part_by_id(msg, part_id)
        if not part:
            abort(404, description="Attachment part not found")

        payload = part.get_payload(decode=True) or b""
        ctype = part.get_content_type() or "application/octet-stream"
        mime_name = _decode(part.get_filename()) if part.get_filename() else None
        download_name, mimetype = _guess_download_meta(mime_name or filename, ctype)

        bio = io.BytesIO(payload)
        return send_file(
            bio,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name,
            max_age=0,
            etag=False,
            conditional=False,
            last_modified=None,
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass


# Optional: also support without filename segment
@bp.route("/mail/attachment/<path:folder>/<uid>/<part_id>")
@login_required
def download_attachment_nofilename(folder: str, uid: str, part_id: str):
    acc = request.args.get("acc", type=int)
    if not acc:
        abort(400, description="Missing acc")

    conn = _get_account_or_404(acc)
    cfg = build_runtime_cfg(conn)
    imap = open_imap(cfg)

    try:
        raw = _fetch_rfc822(imap, folder, uid)
        if not raw:
            abort(404, description="Message not found")

        msg = email.message_from_bytes(raw)
        part = _find_part_by_id(msg, part_id)
        if not part:
            abort(404, description="Attachment part not found")

        payload = part.get_payload(decode=True) or b""
        ctype = part.get_content_type() or "application/octet-stream"
        mime_name = _decode(part.get_filename()) if part.get_filename() else None
        download_name, mimetype = _guess_download_meta(mime_name, ctype)

        bio = io.BytesIO(payload)
        return send_file(
            bio,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name,
            max_age=0,
            etag=False,
            conditional=False,
            last_modified=None,
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass
