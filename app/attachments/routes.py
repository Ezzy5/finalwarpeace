import os
from flask import current_app, abort, send_from_directory
from flask_login import login_required
from . import bp
from ..models import Attachment

def _storage_dir():
    path = current_app.config.get("ATTACHMENTS_DIR")
    if not path:
        path = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(path, exist_ok=True)
    return path

def _can_access(att: Attachment) -> bool:
    # TODO tighten (director/owner/admin). For now allow logged-in users (already enforced by @login_required).
    return True

@bp.route("/<int:att_id>/inline")
@login_required
def inline(att_id: int):
    att = Attachment.query.get_or_404(att_id)
    if not _can_access(att):
        abort(403)
    return send_from_directory(
        _storage_dir(),
        att.stored_name or att.filename,
        mimetype=att.content_type or "application/octet-stream",
        as_attachment=False,
        download_name=att.filename or att.stored_name,
    )

@bp.route("/<int:att_id>/download")
@login_required
def download(att_id: int):
    att = Attachment.query.get_or_404(att_id)
    if not _can_access(att):
        abort(403)
    return send_from_directory(
        _storage_dir(),
        att.stored_name or att.filename,
        mimetype=att.content_type or "application/octet-stream",
        as_attachment=True,
        download_name=att.filename or att.stored_name,
    )
