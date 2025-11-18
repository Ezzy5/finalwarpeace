from flask_login import login_required, current_user
from flask import jsonify, request, current_app
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import User, RewardPenalty
from app.permissions import require_permission, has_permission, USERS_CREATE_EDIT, USERS_REWARDS, USERS_PENALTY
from .. import bp
from .helpers import _parse_iso_date

@bp.route("/api/rewards/<int:user_id>/create", methods=["POST"])
@login_required
@require_permission(USERS_CREATE_EDIT)
def api_rewards_create(user_id: int):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    rtype = (data.get("type") or "").strip().lower()
    rdate = _parse_iso_date(data.get("date"))
    note = (data.get("note") or "").strip()

    if rtype == "reward":
        if not has_permission(current_user, USERS_REWARDS):
            return jsonify({"error": "Forbidden"}), 403
    elif rtype == "penalty":
        if not has_permission(current_user, USERS_PENALTY):
            return jsonify({"error": "Forbidden"}), 403
    else:
        return jsonify({"errors": {"type": "Must be 'reward' or 'penalty'."}}), 400

    errors = {}
    if not rdate:
        errors["date"] = "Invalid or missing date (YYYY-MM-DD)."
    if errors:
        return jsonify({"errors": errors}), 400

    if not hasattr(RewardPenalty, "type"):
        current_app.logger.exception("RewardPenalty.type column missing. Run migrations.")
        return jsonify({"errors": {
            "_": "Server not migrated. Please run DB migrations (missing column 'type' on reward_penalties)."
        }}), 400

    try:
        rp = RewardPenalty(user_id=user.id, type=rtype, date=rdate, note=note or None)
        db.session.add(rp)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        current_app.logger.exception("Failed to create reward/penalty for user_id=%s", user.id)
        return jsonify({"errors": {"_": f"Failed to create: {type(ex).__name__}"}}), 400

    def _serialize_row(rp, _rows_cache=None):
        return {
            "id": getattr(rp, "id", None),
            "user_id": getattr(rp, "user_id", None),
            "type": (getattr(rp, "type", None) or "reward"),
            "date": (getattr(rp, "date").isoformat() if getattr(rp, "date", None) else None),
            "note": getattr(rp, "note", None),
        }

    return jsonify({"ok": True, "item": _serialize_row(rp, _rows_cache=[rp])}), 200
