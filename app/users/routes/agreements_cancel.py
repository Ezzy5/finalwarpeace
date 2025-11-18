from flask_login import login_required, current_user
from flask import jsonify, abort
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from app.models import Agreement
from app.extensions import db
from .. import bp
from .helpers import _check_csrf, _agreement_json

@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/cancel", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_cancel(user_id: int, agreement_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    _check_csrf()
    a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()
    a.status = "cancelled"
    db.session.commit()
    return jsonify({"ok": True, "agreement": _agreement_json(a)})
