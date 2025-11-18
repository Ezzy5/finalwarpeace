from flask_login import login_required, current_user
from flask import jsonify, request, abort
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from app.models import User, Agreement
from app.extensions import db
from .. import bp
from .helpers import _check_csrf, _parse_yyyy_mm_dd, _today, FAR_FUTURE, _agreement_json

@bp.route("/api/agreements/<int:user_id>/create_indefinite", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_create_indef(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    _check_csrf()
    User.query.get_or_404(user_id)

    data = request.get_json(silent=True) or {}
    start_s = (data.get("start_date") or "").strip()
    try:
        start = _parse_yyyy_mm_dd(start_s) if start_s else _today()
    except Exception:
        return jsonify({"errors": {"start_date": "Invalid date (YYYY-MM-DD)."}}), 400

    a = Agreement(user_id=user_id, start_date=start, months=0, end_date=FAR_FUTURE, status="active")
    db.session.add(a)
    db.session.commit()
    return jsonify({"ok": True, "agreement": _agreement_json(a)})
