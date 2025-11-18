# app/tickets/routes/files.py
from flask import request, send_file, abort, send_from_directory
from flask_login import login_required

from .. import bp
from .helpers import safe_attachment_abs_path, ticket_upload_root

@bp.route("/preview")
@login_required
def preview():
    rel_path = request.args.get("path", "")
    abs_path = safe_attachment_abs_path(rel_path)
    # Guess mime type (like before)
    import mimetypes
    mime, _ = mimetypes.guess_type(str(abs_path))
    return send_file(str(abs_path), mimetype=mime or "application/octet-stream", as_attachment=False)

@bp.route("/download")
@login_required
def download():
    rel_path = request.args.get("path", "")
    abs_path = safe_attachment_abs_path(rel_path)
    return send_file(str(abs_path), as_attachment=True)

@bp.route("/attachment/<path:path>")
@login_required
def attachment(path: str):
    """
    This endpoint serves files inside TICKETS_UPLOADS_DIR (older flow).
    Comment attachments saved by this file use ATTACHMENTS_DIR + preview/download.
    """
    root = ticket_upload_root().resolve()
    file_path = (root / path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        abort(400, description="Invalid path")
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    return send_from_directory(root, str(file_path.relative_to(root)))
