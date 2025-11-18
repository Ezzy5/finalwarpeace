from flask_login import login_required, current_user
from flask import jsonify, request, abort
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import User, Report
from app.permissions import require_permission, has_permission, USERS_REPORTS, USERS_CREATE_EDIT
from .. import bp
from .helpers import _parse_yyyy_mm_dd

@bp.route("/api/reports/<int:user_id>/set", methods=["POST"])
@login_required
@require_permission(USERS_REPORTS)
def api_reports_set(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    sanitary_last_s = data.get("sanitary_last", None)
    system_last_s   = data.get("system_last", None)

    errors, sanitary_last, system_last = {}, None, None
    if sanitary_last_s is not None and sanitary_last_s != "":
        try: sanitary_last = _parse_yyyy_mm_dd(sanitary_last_s.strip())
        except Exception: errors["sanitary_last"] = "Invalid date."
    if system_last_s is not None and system_last_s != "":
        try: system_last = _parse_yyyy_mm_dd(system_last_s.strip())
        except Exception: errors["system_last"] = "Invalid date."
    if errors: return jsonify({"errors": errors}), 400

    try:
        if not u.report:
            u.report = Report(user_id=u.id)
        if sanitary_last_s is not None:
            u.report.sanitary_last = sanitary_last
        if system_last_s is not None:
            u.report.system_last = system_last
        db.session.add(u.report)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "reports table missing; run migrations"}), 503

    return api_reports_get(user_id)  # reuse GET payload

# import placed at bottom to avoid circular
from .reports_get import api_reports_get
