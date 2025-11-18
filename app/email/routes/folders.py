# app/email/routes/folders.py
from __future__ import annotations

from flask import request, jsonify
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_imap
from app.email.services.folders.ensure_path import ensure_folder_path
from app.email.services.folders.get_delimiter import get_delimiter
from app.email.services.folders.split_any import split_any

# If you have join_path util with a different signature, we won't rely on it to avoid mismatch.
# from app.email.services.folders.join_path import join_path

SPECIAL_LAST_SEG = {
    "INBOX", "SENT", "SENT ITEMS", "SENT MAIL", "DRAFTS",
    "SPAM", "JUNK", "TRASH", "BIN", "DELETED ITEMS",
    "ARCHIVE", "ALL MAIL"
}

def _normalize_path(raw: str, delim: str) -> str:
    """Normalize any incoming raw path (may contain '.' or '/' etc.) into server delimiter."""
    parts = [p for p in split_any(raw) if p]  # split_any handles '.', '/', '\' etc.
    return delim.join(parts) if parts else ""

@bp.route("/mail/folder/create", methods=["POST"])
@login_required
def create_folder():
    """
    JSON body (new client preferred):
      { acc: <id>, name: "<new-or-nested>", parent?: "<existing parent path>" }

    Also accepted for backward-compat:
      { acc: <id>, path: "<full path to create>" }

    Returns JSON:
      { ok: bool, created: [<created mailbox names>], full_path: str, delimiter: str, expand: str, error?: str }
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid or missing JSON body"}), 400

    acc_id = data.get("acc")
    name = (data.get("name") or "").strip()
    parent = (data.get("parent") or "").strip()
    raw_path = (data.get("path") or "").strip()

    if not acc_id:
        return jsonify({"ok": False, "error": "Missing acc"}), 400

    # Resolve account
    conn = EmailConnection.query.filter_by(user_id=current_user.id, id=int(acc_id)).first()
    if not conn:
        return jsonify({"ok": False, "error": "Account not found"}), 404

    cfg = build_runtime_cfg(conn)
    imap = open_imap(cfg)

    try:
        delim = get_delimiter(imap) or "/"

        # If client sent path, normalize it; otherwise build from parent + name.
        if raw_path:
            full_path = _normalize_path(raw_path, delim)
        else:
            if not name:
                return jsonify({"ok": False, "error": "Missing name"}), 400
            # sanitize just in case
            name = name.replace('"', '').replace("\r", "").replace("\n", "").strip()
            if not name:
                return jsonify({"ok": False, "error": "Missing name"}), 400

            if parent:
                parent_norm = _normalize_path(parent, delim)
                name_norm = _normalize_path(name, delim)
                full_path = delim.join([p for p in [parent_norm, name_norm] if p])
            else:
                full_path = _normalize_path(name, delim)

        if not full_path:
            return jsonify({"ok": False, "error": "Invalid or empty path"}), 400

        # Do not allow creating a folder whose LAST segment is a reserved special name
        last_seg = full_path.split(delim)[-1].strip().upper()
        if last_seg in SPECIAL_LAST_SEG:
            return jsonify({"ok": False, "error": "Folder name is reserved"}), 400

        # Create (and subscribe) the path; ensure_folder_path is expected to be idempotent
        # and return a dict like: { ok, created: [...], full_path, delimiter, error? }
        res = ensure_folder_path(imap, full_path)

        # Normalize response shape and status code
        ok = bool(res.get("ok"))
        created = res.get("created") or []
        # ensure fields we promise
        out = {
            "ok": ok,
            "created": created,
            "full_path": res.get("full_path") or full_path,
            "delimiter": res.get("delimiter") or delim,
            # hint which branch to expand on the client (show the new folder, or its parent)
            "expand": parent or res.get("full_path") or full_path,
        }
        if not ok:
            out["error"] = res.get("error") or "Failed to create folder"
            return jsonify(out), 400

        return jsonify(out), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        try:
            imap.logout()
        except Exception:
            pass
