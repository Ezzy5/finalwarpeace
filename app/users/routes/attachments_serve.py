from flask_login import login_required
from app.permissions import require_permission, USERS_VIEW
from .. import bp
from .helpers import _ensure_upload_dir, serve_file_from

@bp.route("/attachments/<path:stored_name>", methods=["GET"])
@login_required
@require_permission(USERS_VIEW)
def serve_attachment(stored_name: str):
    upload_dir = _ensure_upload_dir()
    return serve_file_from(upload_dir, stored_name, require_exists=True)
