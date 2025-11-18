# app/users/routes/permissions_catalog.py
from flask import jsonify
from flask_login import login_required

from .. import bp
from app.permissions import PERMISSION_CATALOG


@bp.get("/api/permissions")
@login_required
def api_permissions_catalog():
    # Flat list for UI
    items = [{"code": c, "name": n} for c, n in PERMISSION_CATALOG.items()]
    items.sort(key=lambda x: x["name"].lower())
    return jsonify({"items": items})
