from flask_login import login_required
from flask import jsonify, request
from app.extensions import db
from app.models import User
from app.permissions import require_permission, USERS_CREATE_EDIT
from .. import bp

@bp.post("/api/suspend/<int:user_id>")
@login_required
@require_permission(USERS_CREATE_EDIT)
def api_suspend(user_id: int):
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    suspended = bool(data.get("suspended"))
    u.is_suspended = suspended
    db.session.commit()
    return jsonify({"ok": True, "item": {"id": u.id, "is_suspended": bool(u.is_suspended)}})
