from flask_login import login_required, current_user
from flask import jsonify, abort, current_app
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import RewardPenalty
from app.permissions import require_permission, has_permission, USERS_REWARDS, USERS_PENALTY, USERS_CREATE_EDIT
from .. import bp

@bp.route("/api/rewards/<int:user_id>/<int:rp_id>/delete", methods=["POST"])
@login_required
@require_permission(USERS_REWARDS)
def api_rewards_delete(user_id: int, rp_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    try:
        rp = RewardPenalty.query.filter_by(id=rp_id, user_id=user_id).first_or_404()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "reward_penalties table missing; run migrations"}), 503

    t = (getattr(rp, "type", "") or "reward").lower()
    if t == "penalty":
        if not has_permission(current_user, USERS_PENALTY):
            abort(403)
    else:
        if not has_permission(current_user, USERS_REWARDS):
            abort(403)

    try:
        db.session.delete(rp)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        current_app.logger.exception("Failed to delete reward/penalty id=%s", rp_id)
        return jsonify({"errors": {"_": f"Failed to delete: {type(ex).__name__}"}}), 400

    return jsonify({"ok": True})
