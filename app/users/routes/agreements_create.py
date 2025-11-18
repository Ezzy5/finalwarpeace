from flask_login import login_required, current_user
from flask import jsonify, request, abort
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from app.models import User, Agreement
from app.extensions import db
from .. import bp
from .helpers import _check_csrf, _parse_yyyy_mm_dd, _calc_end_months, _safe_int, _fmt

@bp.route("/api/agreements/<int:user_id>/create", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_create(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    _check_csrf()
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    start_s = (data.get("start_date") or "").strip()
    months = _safe_int(data.get("months"), 0)
    errors = {}
    try:
        start = _parse_yyyy_mm_dd(start_s)
    except Exception:
        start = None
        errors["start_date"] = "Invalid date (YYYY-MM-DD)."
    if months <= 0:
        errors["months"] = "Months must be positive."
    if errors:
        return jsonify({"errors": errors}), 400

    end = _calc_end_months(start, months)
    a = Agreement(user_id=user_id, start_date=start, months=months, end_date=end, status="active")
    db.session.add(a)
    db.session.commit()
    return jsonify({"ok": True, "agreement": {
        "id": a.id, "user_id": a.user_id,
        "start_date": _fmt(a.start_date), "months": a.months,
        "end_date": _fmt(a.end_date), "status": a.status,
        "kind": "finite"
    }})
