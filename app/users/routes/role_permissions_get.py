# app/users/routes/role_permissions_get.py
from flask import jsonify
from flask_login import login_required

from .. import bp
from ...models import Role, Permission
from app.permissions import PERMISSION_CATALOG


@bp.get("/api/roles/<int:role_id>/permissions")
@login_required
def api_role_permissions(role_id: int):
    role = Role.query.get_or_404(role_id)

    # Catalog
    catalog = [{"code": c, "name": n} for c, n in PERMISSION_CATALOG.items()]
    catalog.sort(key=lambda x: x["name"].lower())

    # Assigned (Model A)
    assigned = set()
    if hasattr(role, "permissions") and role.permissions is not None:
        assigned = {p.code for p in role.permissions}

    return jsonify({
        "role": {"id": role.id, "name": role.name},
        "permissions": catalog,
        "assigned_codes": sorted(assigned),
    })
