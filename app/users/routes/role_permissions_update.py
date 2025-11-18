# app/users/routes/role_permissions_update.py
from flask import jsonify, request
from flask_login import login_required

from .. import bp
from ...extensions import db
from ...models import Role, Permission
from app.permissions import PERMISSION_CATALOG


@bp.post("/api/roles/<int:role_id>/permissions")
@login_required
def api_role_permissions_update(role_id: int):
    role = Role.query.get_or_404(role_id)
    data = request.get_json(silent=True) or {}
    desired = set(data.get("codes") or [])

    # Restrict to known codes (safety)
    allowed = set(PERMISSION_CATALOG.keys())
    desired &= allowed

    # Model A: Many-to-many sync
    perms = Permission.query.filter(Permission.code.in_(desired)).all()
    role.permissions = perms

    db.session.commit()
    return jsonify({"ok": True, "assigned_codes": sorted(desired)})
