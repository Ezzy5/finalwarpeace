from flask_login import login_required, current_user
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.models import User, RewardPenalty
from app.permissions import USERS_REWARDS, USERS_PENALTY, has_permission
from .. import bp

def _serialize_row(rp, _rows_cache=None):
    from datetime import date
    d = getattr(rp, "date", None)
    date_iso = d.isoformat() if d and hasattr(d, "isoformat") else None
    return {
        "id": getattr(rp, "id", None),
        "user_id": getattr(rp, "user_id", None),
        "type": (getattr(rp, "type", None) or "reward"),
        "date": date_iso,
        "note": getattr(rp, "note", None),
    }

def require_any_permission(*perms):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*a, **k):
            if any(has_permission(current_user, p) for p in perms):
                return fn(*a, **k)
            return jsonify({"error": "Forbidden"}), 403
        return wrapper
    return deco

@bp.route("/api/rewards/<int:user_id>", methods=["GET"])
@login_required
@require_any_permission(USERS_REWARDS, USERS_PENALTY)
def api_rewards_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        q = RewardPenalty.query.filter_by(user_id=u.id).order_by(
            RewardPenalty.date.desc(), RewardPenalty.id.desc()
        )
        rows = q.all()
    except Exception:
        rows = (RewardPenalty.query.filter_by(user_id=u.id)
                .order_by(RewardPenalty.id.desc()).all())

    can_view_rewards = has_permission(current_user, USERS_REWARDS)
    can_view_penalty = has_permission(current_user, USERS_PENALTY)

    rewards, penalties = [], []
    for rp in rows:
        item = _serialize_row(rp, _rows_cache=rows)
        rp_type = (item.get("type") or "reward").lower()
        if rp_type == "penalty":
            if can_view_penalty:
                penalties.append(item)
        else:
            if can_view_rewards:
                rewards.append(item)
    return jsonify({"rewards": rewards, "penalties": penalties}), 200
