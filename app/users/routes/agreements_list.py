from flask_login import login_required
from flask import jsonify
from app.models import Agreement, User
from app.permissions import require_permission, has_permission, USERS_AGREEMENT
from .. import bp
from .helpers import _today, _agreement_json, _is_indef

@bp.route("/api/agreements/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_list(user_id: int):
    User.query.get_or_404(user_id)
    ags = (Agreement.query.filter_by(user_id=user_id)
           .order_by(Agreement.start_date.desc()).all())

    active, history = [], []
    today = _today()
    changed = False
    for a in ags:
        if a.status == "active" and (a.months or 0) > 0 and a.end_date and a.end_date < today:
            a.status = "expired"
            changed = True
        (active if a.status == "active" else history).append(_agreement_json(a))
    if changed:
        from app.extensions import db
        db.session.commit()
    return jsonify({"active": active, "history": history})
