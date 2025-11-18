from flask_login import login_required, current_user
from flask import jsonify, request, abort
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from app.models import Agreement
from app.extensions import db
from .. import bp
from .helpers import _check_csrf, _safe_int, _calc_end_months, _fmt

@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/extend", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_extend(user_id: int, agreement_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    _check_csrf()
    a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()

    data = request.get_json(silent=True) or {}
    add_months = _safe_int(data.get("months"), 0)
    if add_months <= 0:
        return jsonify({"errors": {"months": "Months must be positive."}}), 400

    a.end_date = _calc_end_months(a.end_date, add_months)
    a.months = (a.months or 0) + add_months
    a.status = "active"
    db.session.commit()

    return jsonify({"ok": True, "agreement": {
        "id": a.id, "start_date": _fmt(a.start_date),
        "months": a.months, "end_date": _fmt(a.end_date), "status": a.status
    }})
