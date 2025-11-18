import os
from uuid import uuid4
from flask_login import login_required, current_user
from flask import jsonify, request, current_app
from werkzeug.utils import secure_filename
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from app.models import User, Agreement, Attachment
from app.extensions import db
from .. import bp
from .helpers import _check_csrf, _agreements_dir

@bp.route("/api/agreements/<int:user_id>/attach", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_attach(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        from flask import abort
        abort(403)

    _check_csrf()
    user = User.query.get_or_404(user_id)
    agreement_id = request.form.get("agreement_id", type=int)
    if not agreement_id:
        return jsonify({"error": "agreement_id is required"}), 400

    a = Agreement.query.filter_by(id=agreement_id, user_id=user.id).first_or_404()
    f = request.files.get("file")
    if not f or f.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    dest = _agreements_dir()
    orig = secure_filename(f.filename)
    stored = f"{uuid4().hex}_{orig}"
    save_path = os.path.join(dest, stored)
    current_app.logger.info("Saving agreement attachment to %s", save_path)
    f.save(save_path)

    att = Attachment(
        user_id=user.id, agreement_id=a.id,
        filename=orig, stored_name=stored, content_type=f.mimetype or None,
    )
    db.session.add(att)
    db.session.commit()
    return jsonify({"ok": True, "attachment": {"id": att.id, "filename": att.filename, "stored_name": att.stored_name}})
