from flask_login import login_required, current_user
from flask import jsonify, request, abort
from sqlalchemy.exc import OperationalError
from app.models import User, Uniform
from app.permissions import require_permission, has_permission, USERS_UNIFORMS, USERS_CREATE_EDIT
from app.extensions import db
from .. import bp
from .helpers import _parse_yyyy_mm_dd, _calc_end_months, _safe_int, _fmt, _today

@bp.route("/api/uniforms/<int:user_id>/create", methods=["POST"])
@login_required
@require_permission(USERS_UNIFORMS)
def api_uniforms_create(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    assigned_s = (data.get("assigned_date") or "").strip()
    renew_m = _safe_int(data.get("renew_every_months"), 0)

    errors = {}
    if not kind: errors["kind"] = "Required."
    try: assigned = _parse_yyyy_mm_dd(assigned_s)
    except Exception:
        errors["assigned_date"] = "Invalid date."
        assigned = None
    if renew_m <= 0: errors["renew_every_months"] = "Must be positive."
    if errors: return jsonify({"errors": errors}), 400

    next_due = _calc_end_months(assigned, renew_m)

    try:
        un = Uniform(user_id=user_id, kind=kind, assigned_date=assigned,
                     renew_every_months=renew_m, next_due_date=next_due)
        db.session.add(un)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "uniforms table missing; run migrations"}), 503

    return jsonify({"ok": True, "item": {
        "id": un.id, "kind": un.kind,
        "assigned_date": _fmt(un.assigned_date),
        "renew_every_months": un.renew_every_months,
        "next_due_date": _fmt(un.next_due_date),
    }})
