# app/users/routes/whoami.py
from flask import jsonify
from flask_login import login_required, current_user

from .. import bp
from app.permissions import is_admin_like


@bp.get("/api/_whoami")
@login_required
def api_whoami():
    role = getattr(current_user, "role", None)
    return jsonify({
        "id": getattr(current_user, "id", None),
        "email": getattr(current_user, "email", None),
        "role_name": getattr(role, "name", None),
        "admin_like": bool(is_admin_like(current_user)),
        "codes": _iter_codes_from(role),
    })
