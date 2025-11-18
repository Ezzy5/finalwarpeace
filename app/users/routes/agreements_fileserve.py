# app/users/routes/agreements_fileserve.py
from __future__ import annotations
import os, mimetypes

from flask import current_app, send_from_directory, abort, Response
from flask_login import login_required

from .. import bp
from app.permissions import require_permission, USERS_AGREEMENT

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Ensure Windows/Python mimetype table knows .docx
mimetypes.add_type(DOCX_MIME, ".docx", strict=False)

def _agreements_dir() -> str:
    base = current_app.config.get("AGREEMENTS_UPLOAD_DIR")
    if not base:
        base = os.path.join(current_app.instance_path, "agreements")
    os.makedirs(base, exist_ok=True)
    return base

@bp.get("/agreements/file/<path:stored_name>", endpoint="agreements_file")
@login_required
@require_permission(USERS_AGREEMENT)
def agreements_file(stored_name: str):
    """
    Serve agreement attachments by stored_name (uuid_basename.ext).
    If the file is a DOCX but the name lacks '.docx', force a correct
    download filename and MIME so browsers save as .docx.
    """
    base = _agreements_dir()
    safe_name = os.path.basename(stored_name)
    full = os.path.join(base, safe_name)

    if not os.path.isfile(full):
        current_app.logger.warning("Agreement file NOT FOUND: %s", full)
        abort(404)

    # Try to detect type by extension and by file signature (PK.. = zip/docx)
    guessed = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    is_docx = safe_name.lower().endswith(".docx")
    if not is_docx:
        try:
            with open(full, "rb") as fh:
                magic = fh.read(4)
            if magic[:2] == b"PK":  # DOCX is a zip container -> treat as DOCX when no ext
                is_docx = True
        except Exception:
            pass

    # Decide headers
    if is_docx:
        # Always serve as download with a .docx filename
        download_name = safe_name if safe_name.lower().endswith(".docx") else f"{safe_name}.docx"
        resp: Response = send_from_directory(
            base,
            safe_name,
            as_attachment=True,
            mimetype=DOCX_MIME,
            download_name=download_name,
        )
        # Some servers/browsers prefer explicit Content-Type
        resp.headers["Content-Type"] = DOCX_MIME
        return resp

    # Non-DOCX: let browser preview (HTML/TXT/PDF), fall back to download if unknown
    as_attach = guessed == "application/octet-stream"
    return send_from_directory(
        base,
        safe_name,
        as_attachment=as_attach,
        mimetype=guessed,
        download_name=safe_name,
    )
